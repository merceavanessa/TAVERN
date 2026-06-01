import os
import pandas as pd
import plotly.io as pio

import plotly.graph_objects as go
from plotly.subplots import make_subplots
import plotly.colors as pc
import numpy as np

from tavern.config import config
from tavern.data_utils import set_activity_level
from tavern.orbit_tracks_utils import plot_orbit_tracks

pio.templates.default = "plotly_dark" if config.theme == 'dark' else "plotly_white"
pio.renderers.default = "browser"

def get_available_plots():
    """
    Get available plot types and satellites from the plots directory.
    
    Returns:
        tuple: (satellites, plot_types) - Lists of available satellites and plot types
    """
    satellites = set()
    plot_types = set()

    for filename in os.listdir(config.plots_path):
        if filename.endswith('.html'):
            parts = filename.split('_')
            if len(parts) >= 3:  # Ensure valid filename structure
                plot_type = parts[1]  # e.g., 'barplot' or 'boxplot'
                satellite = parts[2]+'_'+parts[3]  # e.g., 'S3A'
                satellites.add(satellite)
                plot_types.add(plot_type)

    return sorted(list(satellites)), sorted(list(plot_types))

def get_available_response_time_plots():
    """
    Get available response time plots, satellites, and filtering options.
    
    Returns:
        tuple: (satellites, plot_types, bzthr_options, corthr_options, extra24htime) - 
               Lists of available options
    """
    satellites = set()
    plot_types = set()
    bzthr_options = ['0', '9999']
    corthr_options = ['0.7', '0.8', '0.9']
    extra24htime = ['included', 'not-included', 'before and after']

    for filename in os.listdir(config.alignments_path):
        if filename.endswith('.html'):
            parts = filename.split('_')
            if len(parts) >= 3:
                plot_type = 'atmospheric response times'
                if 'RD' in filename: # is satellite
                    satellite = parts[3]+'_'+parts[4]
                else:
                    satellite = 'all_satellites'

                satellite = satellite.removesuffix('.html')

                satellites.add(satellite)
                plot_types.add(plot_type)

    return sorted(list(satellites)), sorted(list(plot_types)), bzthr_options, corthr_options, extra24htime

def get_available_orbit_tracks():
    """
    Get available orbit decay track plots, dates, and altitude ranges.
    
    Returns:
        tuple: (dates, altitude_options, default_date, default_altitude) -
               Lists of available dates and altitude options, plus defaults
    """
    import re
    
    dates = set()
    altitude_options = set()
    
    try:
        for filename in os.listdir(config.orbit_plots_path):
            if filename.endswith('.html'):
                # Extract date from filename: aDot_m_s_tracks_sc_{above|below}_600_km_{date}.html
                match = re.search(r'(below|above)_600_km_(.+?)\.html$', filename)
                if match:
                    altitude = match.group(1)
                    date = match.group(2)
                    dates.add(date)
                    altitude_options.add(altitude)
    except (FileNotFoundError, AttributeError):
        pass
    
    dates = sorted(list(dates))
    altitude_options = sorted(list(altitude_options))
    
    # Default to first date and 'below'
    default_date = dates[0] if dates else None
    default_altitude = 'below' if 'below' in altitude_options else (altitude_options[0] if altitude_options else None)
    
    return dates, altitude_options, default_date, default_altitude

def get_plot_html(filename, plot_dir=None):
    """
    Get the HTML content of a plot file.
    
    Args:
        filename (str): Name of the plot file
        plot_dir (str, optional): Directory containing the plot. Defaults to config.plots_path.
        
    Returns:
        str: HTML content of the plot
    """
    if plot_dir is None:
        plot_dir = config.plots_path
        
    file_path = os.path.join(plot_dir, filename)
    print(file_path)
    try:
        with open(file_path, 'r') as f:
            return f.read()
    except FileNotFoundError:
        return "<p>Plot not found.</p>"

def create_time_series_visualization(satellite, date_start, date_end, selected_feature):
    """
    Create a time series visualization comparing a selected feature with the orbital decay rate.
    
    Args:
        satellite (str): Satellite identifier
        date_start (str): Start date for the visualization
        date_end (str): End date for the visualization
        selected_feature (str): Feature to visualize alongside orbital decay
        
    Returns:
        str: HTML content of the plot
    """
    c = [config.get_active_decay_feature(), 'Kp', selected_feature] if selected_feature != 'Kp' else [config.get_active_decay_feature(), 'Kp']
    if selected_feature == 'activity_level':
        c.remove(selected_feature)
        
    df = pd.read_parquet(f'{config.data_path}/{satellite}.parquet', columns=c)
    df = df.loc[date_start:date_end]
    
    df.interpolate(inplace=True)
    df = set_activity_level(df, config.geomagnetic_storm_levels)
    
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    
    tc1 = '#E8825A'
    tc2 = '#17a2b8'

    fig.add_trace(go.Scatter(
        x=df.index, y=df[selected_feature], mode='lines',
        name=f'{config.feature_names[selected_feature]}', line=dict(color=tc1), opacity=0.7
    ), secondary_y=False)

    fig.add_trace(go.Scatter(
        x=df.index, y=-df[config.get_active_decay_feature()], mode='lines',
        name=config.feature_names[config.get_active_decay_feature()], line=dict(color=tc2), opacity=0.7
    ), secondary_y=True)

    fig.update_layout(
        title=f'{config.feature_names[selected_feature]} and Orbital Decay Rate',
        xaxis_title='Time',
        yaxis_title=config.feature_names[selected_feature],
        yaxis2_title=config.feature_names[config.get_active_decay_feature()],
        yaxis=dict(title_font_color=tc1, tickfont=dict(color=tc1)),
        yaxis2=dict(overlaying='y', side='right', title_font_color=tc2, tickfont=dict(color=tc2)),
        font=dict(size=12),
        showlegend=True,
        height=450
    )
    
    return fig.to_html(full_html=False)

def get_available_spatial_decay_plots():
    """
    Get available spatial decay plots and satellites.
    Returns:
        tuple: (satellites, exclude_options, default_satellite, default_exclude)
    """
    import re
    satellites = set()
    try:
        for filename in os.listdir(config.spatial_decay_plots_path):
            if filename.startswith('decay_spatial_latlondist_') and filename.endswith('.pdf'):
                match = re.search(r'decay_spatial_latlondist_\d+_(.+?)\.pdf$', filename)
                if match:
                    satellites.add(match.group(1))
    except (FileNotFoundError, AttributeError, TypeError):
        pass
    satellites = sorted(list(satellites))
    exclude_options = ['No', 'Yes']
    default_satellite = satellites[0] if satellites else None
    return satellites, exclude_options, default_satellite, 'No'

def get_spatial_decay_pdf_path(satellite, exclude_may_oct):
    """
    Get the full PDF file path for a spatial decay plot.
    Args:
        satellite (str): Satellite code (e.g., 'S3A', 'SWMA')
        exclude_may_oct (str): 'Yes' or 'No' to exclude May-October 2024
    Returns:
        str: Full file path to the PDF, or None if not found
    """
    prefix = 'without-may-october-2024_' if exclude_may_oct == 'Yes' else ''
    try:
        for filename in os.listdir(config.spatial_decay_plots_path):
            if (prefix in filename) and satellite in filename and filename.endswith('.pdf'):
                return os.path.join(config.spatial_decay_plots_path, filename)
    except (FileNotFoundError, AttributeError, TypeError):
        pass
    return None

def plot_time_series_with_storms(df, satellite, cols_to_plot, overlay='Geomagnetic Storms', rs='3H'):
    """
    Plot different time series with storms.
    Args:
        df (pd.DataFrame): Dataframe containing time series
        satellite (str): Satellite code (e.g., 'S3A', 'SWMA')
        cols_to_plot (list): List of columns to plot alongside decay and storms
        overlay (str): Type of overlay to include ('Geomagnetic Storms', 'ICME', 'IP Shocks', or 'None')
        rs (str): Resampling frequency (e.g., '3H' for 3-hourly mean)
     Returns:
        str: HTML content of the plot
    """
    fig = make_subplots(
        rows=len(cols_to_plot) + 1, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.02,
    )

    if overlay == 'Geomagnetic Storms':
        unique_event_ids = df['unique_event_id'].dropna().unique()
        storm_strengths = {}
        for storm_id in unique_event_ids:
            storm_strength = df[df['unique_event_id'] == storm_id]['activity_level'].iloc[0]
            storm_strengths[storm_id] = storm_strength

    df = df.resample(rs).mean(numeric_only=True)

    fig.update_layout(
        title=f"Orbital decay rate against {overlay} for {config.satellite_info[satellite]['name']}." if overlay != 'None' else f"Orbital decay rate and additional features for {config.satellite_info[satellite]['name']}." if len(cols_to_plot) > 0 else f"Orbital decay for {config.satellite_info[satellite]['name']}.",
        title_x=0.5,
        font=dict(size=12),
        height=400 * (len(cols_to_plot) + 1)
    )

    for annotation in fig.layout.annotations:
        annotation.font = dict(size=12)

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
            # for key, idx in zip(geomagnetic_storm_levels.keys(), indices):
            #     storm_colors[key] = pc.sequential.Plasma [idx]
            greens = pc.sequential.Greens[3:]
            indices = np.linspace(0, len(greens) - 1, n_levels).astype(int)
            for key, idx in zip(geomagnetic_storm_levels.keys(), indices):
                storm_colors[key] = greens[idx]

            fig.add_trace(
                go.Scatter(
                    x=[storm_start, storm_start],
                    y=[(-df[config.get_active_decay_feature()]).min(), (-df[config.get_active_decay_feature()]).max()],
                    mode='lines',
                    line=dict(color=storm_colors.get(storm_strength, 'gray'), width=10),#, dash='dash'),
                    opacity=0.35,
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

            fig.update_layout(legend_title_text='Geomagnetic Storm Levels (Onset Time)')

    elif 'ICME' in overlay:
        c=0
        colors = ['#c7372f', '#1a5f9e', '#2ca02c', '#ff7f0e']

        for flag, filename in config.flag_files['ICME'].items():
            cme_df = pd.read_csv(os.path.join(config.flags_path, config.flag_files['ICME'][flag]))
            start_time_name = 'Disturbance_time' if 'Disturbance_time' in cme_df.columns else 'icme_start_time'
            cme_start_name = 'ICME_Start' if 'ICME_Start' in  cme_df.columns else 'mo_start_time'
            cme_end_name = 'ICME_End' if 'ICME_End' in  cme_df.columns else 'mo_end_time'

            cme_df[start_time_name] = pd.to_datetime(cme_df[start_time_name])
            cme_df[cme_start_name] = pd.to_datetime(cme_df[cme_start_name])
            cme_df[cme_end_name] = pd.to_datetime(cme_df[cme_end_name])

            for col in [cme_start_name, cme_end_name]:
                for i, row in cme_df.iterrows():
                    fig.add_trace(
                        go.Scatter(
                            x=[row[col], row[col]],
                            y=[(-df[config.get_active_decay_feature()]).min(),
                               (-df[config.get_active_decay_feature()]).max()],
                            mode='lines',
                            line=dict(color=colors[c], width=3, dash='dash'),
                            opacity=0.35,
                            name= f"{config.event_catalog_feature_names[col]} ({flag})",
                            legendgroup=flag,
                            showlegend=True if i == 0 else False,
                        ),
                        row=1, col=1
                    )

                fig.update_layout(legend_title_text='ICME Catalog Events')

                c+=1

    elif 'IP Shocks' in overlay:
        for flag, filename in config.flag_files[overlay].items():
            IPShocks_df = pd.read_csv(os.path.join(config.flags_path, filename))
            print("------------------------------------")
            print(len(IPShocks_df))
            IPShocks_df.index = pd.to_datetime(IPShocks_df['Time'])
            for k, time in enumerate(IPShocks_df.index):
                fig.add_trace(
                    go.Scatter(
                        x=[time, time],
                        y=[(-df[config.get_active_decay_feature()]).min(), (-df[config.get_active_decay_feature()]).max()],
                        mode='lines',
                        line=dict(color='darkblue', width=3, dash='dash'),
                        opacity=0.35,
                        name=f"{config.event_catalog_feature_names['Shock_Arrival_Time']} ({flag})",
                        legendgroup=flag,
                        showlegend=True if k == 0 else False,
                    ),
                    row=1, col=1
                )

    fig.add_trace(
        go.Scatter(
            x=df.index,
            y=-df[config.get_active_decay_feature()],
            mode='markers+lines',
            marker=dict(
                color=df['decay_level'],
                colorscale='plasma',
                size=6,
                showscale=True,
                colorbar=dict(title="Decay<br>strength", thickness=10),
            ),
            line=dict(color='gray', width=1),
            name=config.feature_names.get(config.get_active_decay_feature(), 'Orbital Decay Rate'),
            showlegend=False
        ),
        row=1, col=1
    )

    for col in cols_to_plot:
        if col == 'Kp':
            fig.add_trace(
                go.Scatter(
                    x=df.index,
                    y=df[col],
                    mode='markers+lines',
                    marker=dict(
                        color=df[col],
                        size=6,
                        showscale=True,
                        colorbar=dict(title="Kp", x=1.15, thickness=10),
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
                    mode='markers+lines',
                    showlegend=False
                ),
                row=cols_to_plot.index(col) + 2, col=1
            )

    fig.update_yaxes(title_text=config.feature_names.get(config.get_active_decay_feature(), 'Orbital Decay'), row=1, col=1)
    for i, col in enumerate(cols_to_plot):
        fig.update_yaxes(title_text=config.feature_names.get(col, col), row=i + 2, col=1)

    fig.update_layout(
        legend=dict(
            orientation="h",  # horizontal legend
            yanchor="top",  # anchor point on the legend box
            y=-0.075,  # position below the plot (negative y moves it below)
            xanchor="center",  # center horizontally
            x=0.5,
        )    )

    for i in range(1, len(cols_to_plot) + 2):
        fig.update_xaxes(autorange=True, row=i, col=1)
        fig.update_yaxes(autorange=True, row=i, col=1)
    fig.update_layout(uirevision="keep")

    html = fig.to_html()

    note = f"Storm times are extended by 24H for visibility. In case of continuous storms, the strongest storm level is selected for plotting throughout the entire period. Resampled to {rs} resolution (3h-mean) for faster plotting."
    html += f"<p style='font-size:14px;color:gray;text-align:center;'>{note}</p>"
    return html


def get_data_plot_html(selected_additional_features, selected_overlay, selected_satellite):
    af = selected_additional_features.copy()
    if 'Kp' not in af:
        af += ['Kp']

    print(f"Loading data for satellite {selected_satellite} with additional features {af} and decay feature {config.get_active_decay_feature()}")

    df = pd.read_parquet(f'{config.data_path}/{selected_satellite}.parquet', columns= af + [config.get_active_decay_feature()])
    df = set_activity_level(df, config.geomagnetic_storm_levels)
    plot_html = plot_time_series_with_storms(df, satellite=selected_satellite,
                                             cols_to_plot=selected_additional_features, overlay=selected_overlay)
    del df
    return plot_html