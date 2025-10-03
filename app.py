from dotenv import set_key
from flask import Flask, render_template, request
from flask_caching import Cache
import os
import json
import pandas as pd
import plotly.io as pio
import plotly.graph_objects as go

from plotly.subplots import make_subplots
from flask_debugtoolbar import DebugToolbarExtension
import gc
import plotly.colors as pc
import plotly.express as px
import re
import numpy as np
from scipy.stats import t

# SETTINGS
pio.templates.default = "plotly_dark"
pio.renderers.default = "browser"

PLOTS_DIR = './data'
CONFIG_PATH = '/Users/vanessa/PhD/Dev/SELAnalysis/SpaceWeatherImpact/data/2023-01-01_2024-12-31/configs/POD/config.json'
additional_features = ['SymH (Omni)', 'AsyD (Omni)',
                       'F10.7 (LASP)', 'F30 (LASP)', 'Kp (LASP)', 'ap (LASP)',
                       '|avg B|', 'Bz GSE', 'Flow Speed (km/s',
                       'Proton density (n/cc)', 'Temperature (K)', 'Alpha/Proton Ratio',
                       'Flow pressure (nPa)', 'Electric Field (Mv/m)', 'Plasma beta',
                       'Alfven mach number', 'Magnetosonic mach number', 'Vz Velocity (km/s)',
                       'Approximate Distance to SEL (Re)',
                       ]

BASE_PATH = '/Users/vanessa/PhD/Dev/SELAnalysis/SpaceWeatherImpact/data/2023-01-01_2024-12-31/processed/'
file_label = '2023-01-01_2024-12-31'

# APP START
app = Flask(__name__)

app.debug = True
app.config['SECRET_KEY'] = 'super-secret'
toolbar = DebugToolbarExtension(app)

# # Configure caching (file-based)
# cache = Cache(app, config={
#     'CACHE_TYPE': 'filesystem',
#     'CACHE_DIR': 'cache-directory',
#     'CACHE_DEFAULT_TIMEOUT': 3600
# })


def load_config():
    with open(CONFIG_PATH) as f:
        return json.load(f)

def get_available_plots():
    satellites = set()
    plot_types = set()

    for filename in os.listdir(PLOTS_DIR):
        if filename.endswith('.html'):
            parts = filename.split('_')
            if len(parts) >= 3:  # Ensure valid filename structure
                plot_type = parts[1]  # e.g., 'barplot' or 'boxplot'
                satellite = parts[2]+'_'+parts[3]  # e.g., 'S3A'
                satellites.add(satellite)
                plot_types.add(plot_type)

    plot_types.add('boxplot-day')  # Add boxplot as a default plot type

    return sorted(list(satellites)), sorted(list(plot_types))


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

# ROUTES

@app.route('/')
def index():
    return render_template('index.html')


@app.route('/data/statistics', methods=['GET', 'POST'])
def statistics():
    satellites, plot_types = get_available_plots()

    selected_satellite = satellites[4] if satellites else None
    selected_plot_type = plot_types[0] if plot_types else None
    plot_html = ""

    if selected_satellite and selected_plot_type:
        plot_filename = f'stats_{selected_plot_type}_{selected_satellite}_{file_label}.html'
        plot_html = get_plot_html(plot_filename)

    return render_template('statistics.html', plot_html=plot_html, satellites=satellites, plot_types=plot_types, PRETTY_NAMES=load_config(), selected_satellite=selected_satellite, selected_plot_type=selected_plot_type)


@app.route('/update_plot', methods=['POST'])
def update_plot():
    selected_satellite = request.form.get('satellite')
    selected_plot_type = request.form.get('plot_type')

    plot_filename = f'stats_{selected_plot_type}_{selected_satellite}_{file_label}.html'
    plot_html = get_plot_html(plot_filename)

    satellites, plot_types = get_available_plots()
    return render_template('statistics.html', plot_html=plot_html, satellites=satellites, plot_types=plot_types, PRETTY_NAMES=load_config(), selected_satellite=selected_satellite, selected_plot_type=selected_plot_type)

def update_feature_name(name):
    name = name.replace("(Omni)", "").replace("(LASP)", "").strip()
    return name

@app.route('/data/visualizations', methods=['GET', 'POST'])
def visualizations():
    satellites, _ = get_available_plots()
    selected_satellite = satellites[4] if satellites else None
    selected_date_start = '2024-05-01'
    selected_date_end = '2024-05-15'
    selected_feature = '|avg B|'
    selection = {'satellite': selected_satellite,
                 'date_start': selected_date_start, 
                 'date_end': selected_date_end, 
                 'additional_feature': selected_feature}


    df = pd.read_parquet(f'{BASE_PATH}/{selected_satellite}.parquet',
                            columns=['orbital_decay', selected_feature])

    df = df.loc[selected_date_start:selected_date_end]

    df['orbital_decay'].interpolate(inplace=True)

    fig = make_subplots(specs=[[{"secondary_y": True}]])

    default_colors = px.colors.qualitative.Plotly
    tc1 = default_colors[3 % len(default_colors)]
    tc2 = default_colors[2 % len(default_colors)]

    fig.add_trace(go.Line(
        x=df.index, y=df[selected_feature], mode='lines', name=update_feature_name(selected_feature), line=dict(color=tc1)
    ), secondary_y=False)

    fig.add_trace(go.Scatter(
        x=df.index, y=df['orbital_decay'], mode='lines', name='Orbital Decay Rate [m/day]', line=dict(color=tc2)
    ), secondary_y=True)

    fig.update_layout(
        title=f'{selected_feature} and Orbital Decay',
        xaxis_title='Time',
        yaxis_title=update_feature_name(selected_feature),
        yaxis2_title="Orbital Decay [m/day]",
        yaxis=dict(title_font_color=tc1, tickfont=dict(color=tc1)),
        yaxis2=dict(overlaying='y', side='right', title_font_color=tc2, tickfont=dict(color=tc2)),
        showlegend=True,
    )

    plot_html = fig.to_html(full_html=False)

    return render_template('visualizations.html', plot_html=plot_html, additional_features=additional_features, satellites=satellites, PRETTY_NAMES=load_config(), selection=selection)


@app.route('/update_vis_plot', methods=['POST'])
def update_vis_plot():
    satellites, _ = get_available_plots()
    selected_satellite = request.form.get('satellite')
    selected_date_start = request.form.get('date_start')
    selected_date_end = request.form.get('date_end')
    selected_feature = request.form.get('additional_feature')
    selection = {'satellite': selected_satellite,
                'date_start': selected_date_start, 
                'date_end': selected_date_end, 
                'additional_feature': selected_feature}

    df = pd.read_parquet(f'{BASE_PATH}/{selected_satellite}.parquet',
                         columns=['orbital_decay', selected_feature])
    
    df = df.loc[selected_date_start:selected_date_end]
    df['orbital_decay'].interpolate(inplace=True)

    fig = make_subplots(specs=[[{"secondary_y": True}]])

    default_colors = px.colors.qualitative.Plotly
    tc1 = default_colors[3 % len(default_colors)]
    tc2 = default_colors[2 % len(default_colors)]

    fig.add_trace(go.Line(
        x=df.index, y=df[selected_feature], mode='lines', name=update_feature_name(selected_feature), line=dict(color=tc1)
    ), secondary_y=False)

    fig.add_trace(go.Scatter(
        x=df.index, y=df['orbital_decay'], mode='lines', name='Orbital Decay Rate [m/day]', line=dict(color=tc2)
    ), secondary_y=True)

    # fig.update_traces(marker=dict(opacity=0.05), selector=dict(mode='markers'))

    fig.update_layout(
        title=f'{selected_feature} and Orbital Decay',
        xaxis_title='Time',
        yaxis_title=update_feature_name(selected_feature),
        yaxis2_title="Orbital Decay [m/day]",
        yaxis=dict(title_font_color=tc1, tickfont=dict(color=tc1)),
        yaxis2=dict(overlaying='y', side='right', title_font_color=tc2, tickfont=dict(color=tc2)),
        showlegend=True,
    )

    plot_html = fig.to_html(full_html=False)

    return render_template('visualizations.html', plot_html=plot_html, additional_features=additional_features, satellites=satellites, PRETTY_NAMES=load_config(), selection=selection)


def get_plot_html(filename):
    file_path = os.path.join(PLOTS_DIR, filename)
    print(file_path)
    try:
        with open(file_path, 'r') as f:
            return f.read()
    except FileNotFoundError:
        return "<p>Plot not found.</p>"


if __name__ == '__main__':
    app.run(debug=True, port=8000)
