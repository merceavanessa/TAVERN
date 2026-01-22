import os
from tavern.config import config
import numpy as np
import pandas as pd
import plotly.colors as pc
import plotly.graph_objects as go
from plotly.subplots import make_subplots

import plotly.io as pio

pio.templates.default = "plotly_dark"
pio.renderers.default = "browser"

def plot_daily_boxplot(df_all_stats, satellite, year, month):
    print (df_all_stats.index.Day)
    df_all_stats_days = df_all_stats[(df_all_stats.index.Month == month) & (df_all_stats.index.Year == year)]
    df_all_stats_days = df_all_stats_days.pivot(index='Day', columns='Function', values='orbital_decay')
    df_all_stats_days = df_all_stats_days.reset_index()
    df_all_stats_days = df_all_stats_days.sort_values(by='Day')
    df_all_stats_days = df_all_stats_days.set_index('Day')

    fig = go.Figure()
    for i, day in enumerate(df_all_stats_days.index):
        df_day = df_all_stats_days[df_all_stats_days.index == day]
        fig.add_trace(go.Box(y=df_day['orbital_decay'], name=day))

    fig.update_layout(title=f"Orbital Decay Boxplot for {satellite} in {year}-{month}", height=900, width=1200)
    fig.write_html(f"../../../TAVERN/data/stats_boxplot_{satellite}_{year}-{month}.html")

def plot_time_series_with_storms(df, satellite, cols_to_plot, overlay='Geomagnetic Storms', rs='3H'):
    fig = make_subplots(
        rows=len(cols_to_plot) + 1, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.02,
        subplot_titles=(config.feature_names.get('orbital_decay', 'Orbital Decay'),) + tuple(
            config.feature_names.get(col, col) for col in cols_to_plot),
    )

    if overlay == 'Geomagnetic Storms':
        unique_event_ids = df['unique_event_id'].dropna().unique()
        storm_strengths = {}
        for storm_id in unique_event_ids:
            storm_strength = df[df['unique_event_id'] == storm_id]['activity_level'].iloc[0]
            storm_strengths[storm_id] = storm_strength

    df = df.resample(rs).mean(numeric_only=True)

    fig.update_layout(
        title=f"Orbital decay against {overlay} for {config.satellite_info[satellite]['name']}." if overlay != 'None' else f"Orbital decay and additional features for {config.satellite_info[satellite]['name']}." if len(cols_to_plot) > 0 else f"Orbital decay for {config.satellite_info[satellite]['name']}.",
        title_x=0.5,
        font=dict(size=20),
        height=600 * (len(cols_to_plot) + 1)
    )

    for annotation in fig.layout.annotations:
        annotation.font = dict(size=20)

    geomagnetic_storm_levels = config.geomagnetic_storm_levels
    if overlay == 'Geomagnetic Storms':
        for storm_id in unique_event_ids:
            storm_strength = storm_strengths[storm_id]
            storm_times = df[df['unique_event_id'] == storm_id].index
            if len(storm_times) == 0:
                continue
            storm_start = storm_times[0]
            n_levels = len(geomagnetic_storm_levels)
            indices = np.linspace(0, len(pc.sequential.Plasma ) - 1, n_levels).astype(int)
            storm_colors = {}
            for key, idx in zip(geomagnetic_storm_levels.keys(), indices):
                storm_colors[key] = pc.sequential.Plasma [idx]

            fig.add_trace(
                go.Scatter(
                    x=[storm_start, storm_start],
                    y=[df['orbital_decay'].min(), df['orbital_decay'].max()],
                    mode='lines',
                    line=dict(color=storm_colors.get(storm_strength, 'gray'), width=10),#, dash='dash'),
                    opacity=0.25,
                    name=storm_strength,
                    legendgroup=storm_strength,
                    showlegend=False
                ),
                row=1, col=1
            )

        for i, (level, (low, high)) in enumerate(geomagnetic_storm_levels.items()):
            if level == 'G0 (Quiet to Unsettled)':
                continue
            fig.add_trace(
                go.Scatter(
                    x=[None],
                    y=[None],
                    mode='lines',
                    line=dict(color=storm_colors.get(level, 'gray'), width=10),
                    opacity=0.45,
                    name=level,
                    legendgroup=level,
                    showlegend=True,
                )
            )

            fig.update_layout(legend_title_text='Geomagnetic Storm Levels')

    elif 'ICME' in overlay:
        c=0
        colors = pc.sequential.Reds[::int(len(pc.sequential.Reds)/3)]
        colors += pc.sequential.Blues[::int(len(pc.sequential.Blues)/3)]

        for flag, filename in config.flag_files.items():
            cme_df = pd.read_csv(os.path.join(config.flags_path, config.general_settings.flag_files[flag]))
            start_time_name = 'Disturbance_time' if 'Disturbance_time' in cme_df.columns else 'icme_start_time'
            cme_start_name = 'ICME_Start' if 'ICME_Start' in  cme_df.columns else 'mo_start_time'
            cme_end_name = 'ICME_End' if 'ICME_End' in  cme_df.columns else 'mo_end_time'

            cme_df[start_time_name] = pd.to_datetime(cme_df[start_time_name])
            cme_df[cme_start_name] = pd.to_datetime(cme_df[cme_start_name])
            cme_df[cme_end_name] = pd.to_datetime(cme_df[cme_end_name])

            for col in [cme_start_name]:
                for i, row in cme_df.iterrows():
                    fig.add_trace(
                        go.Scatter(
                            x=[row[col], row[col]],
                            y=[df['orbital_decay'].min(), df['orbital_decay'].max()],
                            mode='lines',
                            line=dict(color=colors[c], width=3, dash='dash'),
                            opacity=0.35,
                            name= f"{config.event_catalog_feature_names[col]} ({flag})",
                            legendgroup=flag,
                            showlegend=False,
                        ),
                        row=1, col=1
                    )


                fig.add_trace(
                    go.Scatter(
                        x=[None],
                        y=[None],
                        mode='lines',
                        line=dict(color=colors[c], width=3, dash='dash'),
                        opacity=0.35,
                        name=f"{config.event_catalog_feature_names[col]} ({flag})",
                        legendgroup=flag,
                        showlegend=True,
                    )
                )

                fig.update_layout(legend_title_text='ICME Catalog Events')

                c+=1

    fig.add_trace(
        go.Scatter(
            x=df.index,
            y=df['orbital_decay'],
            mode='markers+lines',
            marker=dict(
                color=df['decay_level'],
                colorscale='plasma',
                size=6,
                showscale=True,
                colorbar=dict(title="Decay<br>strength", thickness=10),
            ),
            line=dict(color='gray', width=1),
            name=config.feature_names.get('orbital_decay', 'Orbital Decay'),
            showlegend=False
        ),
        row=1, col=1
    )

    for col in cols_to_plot:
        if col == 'Kp (LASP)':
            fig.add_trace(
                go.Scatter(
                    x=df.index,
                    y=df[col],
                    mode='markers',
                    marker=dict(
                        color=df[col],
                        # colorscale='Viridis',
                        size=6,
                        showscale=True,
                        colorbar=dict(title="Kp<br>value", x=1.15, thickness=10),
                    ),
                    line=dict(color='gray', width=1),
                    name=config.feature_names.get(col, col),
                    showlegend=False
                ),
                row=cols_to_plot.index(col) + 2, col=1
            )
        else:
            fig.add_trace(
                go.Scatter(
                    x=df.index,
                    y=df[col],
                    mode='lines',
                    showlegend=False
                ),
                row=cols_to_plot.index(col) + 2, col=1
            )

    fig.update_layout(
        legend=dict(
            orientation="h",  # horizontal legend
            yanchor="top",  # anchor point on the legend box
            y=-0.075,  # position below the plot (negative y moves it below)
            xanchor="center",  # center horizontally
            x=0.5
        )    )

    html = fig.to_html()

    note = f"Storm times are extended by 24H for visibility. In case of continuous storms, the strongest storm level is selected for plotting throughout the entire period. Resampled to {rs} cadence for faster plotting."
    html += f"<p style='font-size:14px;color:gray;text-align:center;'>{note}</p>"
    return html
