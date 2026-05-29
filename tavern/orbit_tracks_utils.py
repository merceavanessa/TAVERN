import plotly.graph_objects as go
import pandas as pd
import numpy as np
from datetime import datetime
from skyfield.api import load, wgs84, utc

default_markers = ['circle', 'square', 'diamond', 'x', 'triangle-up', 'triangle-down', 'pentagon', 'hexagon', 'hexagon2', 'circle', 'square', 'diamond', 'x', 'triangle-up']

def compute_subsolar_point_distance(df_sat):
    df_sat = df_sat.copy()
    lat1 = np.deg2rad(df_sat['lat_ell [deg]'])
    lon1 = np.deg2rad(df_sat['lon_ell [deg]'])
    lat2 = np.deg2rad(df_sat['subsolar_lat'])
    lon2 = np.deg2rad(df_sat['subsolar_lon'])

    dlon = np.arctan2(np.sin(lon1 - lon2), np.cos(lon1 - lon2))
    # using the Haversine formula
    a = np.sin((lat1-lat2)/2)**2 + np.cos(lat1)*np.cos(lat2)*np.sin(dlon/2)**2
    df_sat['distance_to_subsolar_point'] = np.rad2deg(2*np.arcsin(np.sqrt(a)))

    return df_sat[['distance_to_subsolar_point']]

def compute_subsolar_point(df_sat):
    df_sat = df_sat.copy()
    planets = load('de421.bsp')
    earth, sun = planets['earth'], planets['sun']
    ts = load.timescale()

    df_res = df_sat.resample('5min').mean()

    idx = df_res.index
    if idx.tz is None:
        idx = idx.tz_localize(utc)
    else:
        idx = idx.tz_convert(utc)

    times = ts.from_datetimes(idx.to_pydatetime())

    geocentric_sun = earth.at(times).observe(sun)
    subpoints = wgs84.subpoint(geocentric_sun)

    df_res['subsolar_lon'] = (subpoints.longitude.degrees + 360) % 360
    df_res['subsolar_lat'] = subpoints.latitude.degrees
    df_sat['subsolar_lon'] = df_res['subsolar_lon'].reindex(df_sat.index, method='nearest')
    df_sat['subsolar_lat'] = df_res['subsolar_lat'].reindex(df_sat.index, method='nearest')
    # df_sat['distance_to_subsolar_point'] = np.sqrt((df_sat['lon_ell [deg]'] - df_sat['subsolar_lon'])**2 + (df_sat['lat_ell [deg]'] - df_sat['subsolar_lat'])**2)

    return df_sat[['subsolar_lon', 'subsolar_lat']]

def get_tracks_for_time(dfs, target_time, duration, resolution, satellite_dict, columns):
    all_tracks = {'low-altitude': {}, 'high-altitude': {}}

    start = pd.to_datetime(target_time)
    end = pd.to_datetime(target_time) + duration

    for sat, dataframe in dfs.items():
        df = dataframe.copy()
        df = df[(df.index >= start) & (df.index <= end)]
        df = df.resample(resolution).mean()

        lons =  df['lon_ell [deg]'].values
        lats =  df['lat_ell [deg]'].values
        decay_vals = df['orbital_decay_rate'].values
        decay_time = df.index

        additional_data = df[columns]

        if satellite_dict[sat]['altitude'] < 600:
            all_tracks['low-altitude'][satellite_dict[sat]['name']] = (lons, lats, decay_vals, decay_time, additional_data)
        else:
            all_tracks['high-altitude'][satellite_dict[sat]['name']] = (lons, lats, decay_vals, decay_time, additional_data)

        print(f"Processed satellite: {satellite_dict[sat]['name']} with altitude {satellite_dict[sat]['altitude']} km")

    all_vals_low = np.concatenate([t[2] for t in list(all_tracks['low-altitude'].values())])
    all_vals_high = np.concatenate([t[2] for t in list(all_tracks['high-altitude'].values())])
    to_plot = {
            's/c below 600 km' : (all_tracks['low-altitude'], all_vals_low.min(), all_vals_low.max()),
            's/c above 600 km': (all_tracks['high-altitude'], all_vals_high.min(), all_vals_high.max())}

    return to_plot

def plot_orbit_tracks(dfs, target_time, duration=None, resolution='1min', satellite_dict = {}, columns = ['F10.7', 'Hp30', 'SymH']):
    to_plot = get_tracks_for_time(dfs, target_time, duration, resolution, satellite_dict, columns)
    if not duration:
        duration = pd.to_timedelta(48, unit='h')

    planets = load('de421.bsp')
    earth, sun = planets['earth'], planets['sun']
    ts = load.timescale()

    for altitude_range, (sat_tracks, vmin, vmax) in to_plot.items():

        fig = go.Figure()
        sat_list = list(sat_tracks.keys())

        fig.add_trace(
            go.Scattergeo(
                lon=[0],
                lat=[0],
                mode="markers",
                name="Subsolar point",
               marker=dict(
                    size=18,
                    color="yellow",
                    line=dict(color="orange", width=2),
                    opacity=0.9
                ),
                showlegend=True,
            )
        )

        for m, sat in enumerate(sat_list):
            lons, lats, decay, decay_time, additional_data = sat_tracks[sat]

            fig.add_trace(
                go.Scattergeo(
                    lon=[lons[0]],
                    lat=[lats[0]],
                    mode="markers",
                    name=sat,
                    legendgroup=sat,
                    showlegend=True,
                    marker=dict(
                        size=15,
                        color=[decay[0]],
                        colorscale="agsunset",
                        cmin=vmin,
                        cmax=vmax,
                        symbol=default_markers[m % len(default_markers)],
                        colorbar=dict(
                            title=dict(
                                text="Orbital decay rate (m d⁻¹)",
                                side="right",
                            ),
                            len=0.6,
                            y=0.5,
                            yanchor="middle",
                        ) if m == 0 else None,
                    ),
                )
            )

        ref_sat = sat_list[0]
        ref_time = sat_tracks[ref_sat][3]
        max_len = len(ref_time)

        frames = []

        for idx in range(max_len):
            real_time = ref_time[idx].strftime("%Y-%m-%d %H:%M:%S")

            frame_data = []

            dt = datetime.fromisoformat(real_time).replace(tzinfo=utc)
            t = ts.from_datetime(dt)

            geocentric_sun = earth.at(t).observe(sun)
            subpoint = wgs84.subpoint(geocentric_sun)

            frame_data.append(
                go.Scattergeo(
                    lon=[subpoint.longitude.degrees],
                    lat=[subpoint.latitude.degrees],
                    mode="markers",
                    marker=dict(
                        size=18,
                        color="yellow",
                        line=dict(color="orange", width=2),
                        opacity=0.9
                    ),
                    name="Subsolar point",
                    hovertext=f"Subsolar point<br>"
                              f"Longitude: {subpoint.longitude.degrees:.2f}<br>"
                              f"Latitude: {subpoint.latitude.degrees:.2f}",
                )
            )

            for m, sat in enumerate(sat_list):
                lons, lats, decay, decay_time, additional_data = sat_tracks[sat]

                j = min(idx, len(lons) - 1)

                frame_data.append(
                    go.Scattergeo(
                        lon=[lons[j]],
                        lat=[lats[j]],
                        mode="markers",
                        marker=dict(
                            size=15,
                            color=[decay[j]],
                            colorscale="agsunset",
                            cmin=vmin,
                            cmax=vmax,
                            symbol=default_markers[m % len(default_markers)],
                        ),
                        hovertemplate=
                            f"Satellite: {sat}<br>"
                            f"Longitude: {lons[j]:.2f}<br>"
                            f"Latitude: {lats[j]:.2f}<br>"
                            f"Altitude: {altitudes[sat]}<br>"
                            f"Orbital decay rate: {decay[j]:.2f} (m d⁻¹)<br>"
                            f"{'<br>'.join([f'{col}: {additional_data[col].iloc[j]:.2f}' for col in columns])}"
                    )
                )

            frames.append(
                go.Frame(
                    data=frame_data,
                    name=str(idx),
                    layout=go.Layout(
                        annotations=[dict(
                                text=f"{altitude_range}<br>Time: {real_time}",
                                x=0.5,
                                y=0.1,
                                xref="paper",
                                yref="paper",
                                showarrow=False,
                                font=dict(size=14),
                        )]
                    )
                )
            )

        fig.frames = frames

        steps = [
            dict(
                method="animate",
                args=[
                    [str(k)],
                    {
                        "mode": "immediate",
                        "frame": {"duration": 41, "redraw": True},
                        "transition": {"duration": 0},
                    },
                ],
                label=str(k),
            )
            for k in range(max_len)
        ]

        sliders = [
            dict(
                y=0.05,
                active=0,
                currentvalue={"prefix": "Frame: "},
                pad={"t": 20},
                steps=steps,
            )
        ]

        updatemenus = [
            dict(
                type="buttons",
                x=0.05,
                y=1.05,
                showactive=False,
                buttons=[
                    dict(
                        label="Play",
                        method="animate",
                        args=[
                            None,
                            {
                                "frame": {"duration": 41, "redraw": True},
                                "transition": {"duration": 0},
                                "fromcurrent": True,
                            },
                        ],
                    ),
                    dict(
                        label="Pause",
                        method="animate",
                        args=[
                            [None],
                            {
                                "mode": "immediate",
                                "frame": {"duration": 0},
                                "transition": {"duration": 0},
                            },
                        ],
                    ),
                ],
            ),
            dict(
                type="dropdown",
                x=0.0,
                y=1.05,
                buttons=[
                    dict(
                        label="Natural Earth",
                        method="relayout",
                        args=[{"geo.projection.type": "natural earth"}],
                    ),
                    dict(
                        label="Orthographic",
                        method="relayout",
                        args=[{"geo.projection.type": "orthographic"}],
                    ),
                ],
            ),
        ]

        fig.update_layout(
            annotations=[
                dict(
                    text=f"{altitude_range}<br>Time: {real_time}",
                    x=0.5,
                    y=0.1,
                    xref="paper",
                    yref="paper",
                    showarrow=False,
                    font=dict(size=14),
                ),
                dict(
                    text=f"Data source: Bernese reduced-dynamic POD latitude/longitude coordinates (WGS84 ellipsoid) with {resolution} sampling.<br>Hover on the satellite markers for additional data.",
                    x=0.5,
                    y=0.05,
                    xref="paper",
                    yref="paper",
                    showarrow=False,
                    font=dict(size=10, color="gray"),
                )
            ],
            geo=dict(
                projection_type="natural earth",
                showland=True,
                landcolor="#eaeaea",
                showocean=True,
                oceancolor="white",
                showcoastlines=True,
                coastlinecolor="gray",
                coastlinewidth=0.7,
                showframe=True,
                lataxis=dict(showgrid=True, dtick=30),
                lonaxis=dict(showgrid=True, dtick=60),
            ),
            sliders=sliders,
            updatemenus=updatemenus,
            margin=dict(l=0, r=60, t=60, b=40),
        )

        filename = f"./data/orbital_decay_tracks_{altitude_range.replace(' ', '_').replace('/', '')}_{target_time.replace(':', '-')}.html"
        fig.write_html(filename, config={"responsive": True}, auto_play=False)