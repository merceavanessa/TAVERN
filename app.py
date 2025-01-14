from flask import Flask, render_template, request
from flask_caching import Cache
import os
import json
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from flask_debugtoolbar import DebugToolbarExtension
import gc
import plotly.colors as pc
import plotly.express as px

# SETTINGS
PLOTS_DIR = './data'
CONFIG_PATH = './configs/config.json'
additional_features = ['mean_altitude',
                       'SymH (Omni)', 'AsyD (Omni)', '|avg B|', 'Flow Speed (km/s',
                       'Proton density (n/cc)', 'Temperature (K)', 'Alpha/Proton Ratio',
                       'Flow pressure (nPa)', 'Electric Field (Mv/m)', 'Plasma beta',
                       'Alfven mach number', 'Magnetosonic mach number', 'Vz Velocity (km/s)',
                       'Bz GSE',
                       'Approximate Distance to SEL (Re)', 'F10.7 (LASP)', 'Kp (LASP)', 'ap (LASP)',
                       'Dst (nT) (LASP)']

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

# Function to get available satellites and plot types


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

    return sorted(list(satellites)), sorted(list(plot_types))

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
        plot_filename = f'stats_{selected_plot_type}_{selected_satellite}_2023-2024.html'
        plot_html = get_plot_html(plot_filename)

    return render_template('statistics.html', plot_html=plot_html, satellites=satellites, plot_types=plot_types, PRETTY_NAMES=load_config(), selected_satellite=selected_satellite, selected_plot_type=selected_plot_type)


@app.route('/update_plot', methods=['POST'])
def update_plot():
    selected_satellite = request.form.get('satellite')
    selected_plot_type = request.form.get('plot_type')
    plot_filename = f'stats_{selected_plot_type}_{selected_satellite}_2023-2024.html'

    plot_html = get_plot_html(plot_filename)

    satellites, plot_types = get_available_plots()
    return render_template('statistics.html', plot_html=plot_html, satellites=satellites, plot_types=plot_types, PRETTY_NAMES=load_config(), selected_satellite=selected_satellite, selected_plot_type=selected_plot_type)


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

    df = pd.read_parquet(f'./data/dataframes/{selected_satellite}.parquet',
                         columns=['orbital_decay', selected_feature, 'res_std'])
    df = df.loc[selected_date_start:selected_date_end]
    df['res_std2'] = ((df['res_std'] - df['res_std'].mean()
                       ) / df['res_std'].std()) * 10

    fig = make_subplots(specs=[[{"secondary_y": True}]])

    fig.add_trace(go.Scatter(
        x=df.index, y=df[selected_feature], mode='lines', name=selected_feature), secondary_y=False)

    fig.add_trace(go.Scatter(x=df.index, y=df['orbital_decay'] - df['res_std2'], mode='lines',
                               line=dict(width=0), showlegend=False), secondary_y=True)
    fig.add_trace(go.Scatter(x=df.index, y=df['orbital_decay'] + df['res_std2'],
                  mode='lines', line=dict(width=0), fill='tonexty', 
                  name='σ * 3 '), secondary_y=True)

    fig.add_trace(go.Scatter(
        x=df.index, y=df['orbital_decay'], mode='lines', name='Orbital Decay'), secondary_y=True)
    
    fig.update_traces(marker=dict(opacity=0.05), selector=dict(mode='markers'))
    
    default_colors = px.colors.qualitative.Plotly
    tc1 = default_colors[0 % len(default_colors)]
    tc2 = default_colors[3 % len(default_colors)]

    fig.update_layout(
        title=f'{selected_feature} and Orbital Decay',
        xaxis_title='Time',
        yaxis_title=selected_feature,
        yaxis2_title='Orbital Decay',
        yaxis=dict(title_font_color=tc1, tickfont=dict(color=tc1)),
        yaxis2=dict(overlaying='y', side='right', title_font_color=tc2, tickfont=dict(color=tc2)),
        showlegend=True,
    )

    fig.update_layout(
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(0,0,0,0)',
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


    df = pd.read_parquet(f'./data/dataframes/{selected_satellite}.parquet',
                         columns=['orbital_decay', selected_feature, 'res_std'])
    df = df.loc[selected_date_start:selected_date_end]
    df['res_std2'] = ((df['res_std'] - df['res_std'].mean()
                       ) / df['res_std'].std()) * 3

    tc1 = 'lightyellow' #default_colors[0 % len(default_colors)]
    tc2 = 'lightblue' #default_colors[3 % len(default_colors)]

    fig = make_subplots(specs=[[{"secondary_y": True}]])

    # set name to selected_feature without _ and with pascal case, with 'LASP' removed
    name = selected_feature.replace('_', ' ').title().replace('LASP', '') 
    if name == 'Mean Altitude':
        name = 'Mean Altitude, reduced <br> by Earth\'s radius'
    fig.add_trace(go.Scatter(
        x=df.index, y=df[selected_feature], mode='lines', name=name, line=dict(width=6), marker=dict(color=tc1, size=30)), secondary_y=False)

    fig.add_trace(go.Scatter(x=df.index, y=df['orbital_decay'] - df['res_std2'], mode='lines',
                               line=dict(width=0), showlegend=False), secondary_y=True)
    fig.add_trace(go.Scatter(x=df.index, y=df['orbital_decay'] + df['res_std2'],
                  mode='lines', line=dict(width=0), fill='tonexty', 
                  name='σ * 3 '), secondary_y=True)

    fig.add_trace(go.Scatter(
        x=df.index, y=df['orbital_decay'], mode='lines', name='Orbital Decay', line=dict(width=6), marker=dict(color=tc2, size=30)), secondary_y=True)
    
    fig.update_traces(marker=dict(opacity=0.05),
                      selector=dict(mode='markers'))
    
    default_colors = px.colors.qualitative.Plotly
    fontsize = 50
    fig.update_layout( 
        # title=f'{selected_feature} and Orbital Decay',
        xaxis_title='Time',
        yaxis_title=name,
        yaxis2_title="Orbital Decay Rate <br> (m day⁻¹)",
        yaxis=dict(title_font_color=tc1, tickfont=dict(color=tc1, size=fontsize)),
        yaxis2=dict(overlaying='y', side='right', title_font_color=tc2, tickfont=dict(color=tc2, size=fontsize)),
        xaxis=dict(title_font_color='white', tickfont=dict(color='white', size=fontsize)),
        showlegend=False, #True
    )

    fig.update_yaxes(nticks=3, secondary_y=False)

    fig.update_layout(
        yaxis_title_font_size=fontsize,
        yaxis2_title_font_size=fontsize,
        xaxis_title_font_size=fontsize,
        xaxis_title_font_color='white'
    )

    fig.update_layout(
        legend=dict(
            font=dict(
                size=fontsize,
                color='white',
                family='Arial Black'
            )
        )
    )

    fig.update_layout(
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(0,0,0,0)',
    )


    fig.update_layout(
        # margin=dict(l=800, r=0, t=0, b=250),
        # colorway=px.colors.qualitative.Pastel,
        autosize=False,
        # width=3300, height=1200,
        # legend=dict(
        #     yanchor="top",
        #     y=0.99,
        #     xanchor="right",
        #     x=0.99,
        #     bgcolor='rgba(0,0,0,0)'
        # ),
        barmode='group',
        font=dict(size=100, color='white', family='Arial Black'),
        # plot_bgcolor='rgba(0,0,0,0.1)',
        # paper_bgcolor='rgba(0,0,0,0)',
        # paper_bgcolor='rgba(0,0,0,0)',
    )


    # change fig size
    fig.update_layout(
        width=1600,
        height=900,
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
