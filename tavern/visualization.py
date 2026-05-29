"""
Visualization module for the TAVERN application.
Handles creating and retrieving visualizations.
"""
import os
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import plotly.express as px

from tavern.config import config
from tavern.data_utils import set_activity_level

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
    Create a time series visualization comparing a selected feature with orbital decay.
    
    Args:
        satellite (str): Satellite identifier
        date_start (str): Start date for the visualization
        date_end (str): End date for the visualization
        selected_feature (str): Feature to visualize alongside orbital decay
        
    Returns:
        str: HTML representation of the plot
    """
    c = ['aDot_m_s', 'Kp', selected_feature] if selected_feature != 'Kp' else ['aDot_m_s', 'Kp']
    if selected_feature == 'activity_level':
        c.remove(selected_feature)
        
    df = pd.read_parquet(f'{config.data_path}/{satellite}.parquet', columns=c)
    df = df.loc[date_start:date_end]
    
    df.interpolate(inplace=True)
    df = set_activity_level(df, config.geomagnetic_storm_levels)
    
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    
    default_colors = px.colors.qualitative.Plotly
    tc1 = default_colors[3 % len(default_colors)]
    tc2 = default_colors[2 % len(default_colors)]

    fig.add_trace(go.Scatter(
        x=df.index, y=df[selected_feature], mode='lines',
        name=f'{config.feature_names[selected_feature]}', line=dict(color=tc1)
    ), secondary_y=False)

    fig.add_trace(go.Scatter(
        x=df.index, y=-df['aDot_m_s'], mode='lines',
        name=config.feature_names['aDot_m_s'], line=dict(color=tc2)
    ), secondary_y=True)

    fig.update_layout(
        title=f'{config.feature_names[selected_feature]} and Orbital Decay Rate',
        xaxis_title='Time',
        yaxis_title=config.feature_names[selected_feature],
        yaxis2_title=config.feature_names['aDot_m_s'],
        yaxis=dict(title_font_color=tc1, tickfont=dict(color=tc1)),
        yaxis2=dict(overlaying='y', side='right', title_font_color=tc2, tickfont=dict(color=tc2)),
        font=dict(size=18),
        showlegend=True
    )
    
    return fig.to_html(full_html=False)