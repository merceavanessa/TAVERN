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
import numpy as np
from scipy.stats import t

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

    plot_types.add('boxplot-day')  # Add boxplot as a default plot type

    return sorted(list(satellites)), sorted(list(plot_types))


def plot_daily_boxplot(df_all_stats, satellite, year, month):
    print (df_all_stats.index.Day)
    df_all_stats_days = df_all_stats[(df_all_stats.index.Month == month) & (df_all_stats.index.Year == year)]
    df_all_stats_days = df_all_stats_days.pivot(index='Day', columns='Function', values='orbital_decay_c')
    df_all_stats_days = df_all_stats_days.reset_index()
    df_all_stats_days = df_all_stats_days.sort_values(by='Day')
    df_all_stats_days = df_all_stats_days.set_index('Day')

    fig = go.Figure()
    for i, day in enumerate(df_all_stats_days.index):
        df_day = df_all_stats_days[df_all_stats_days.index == day]
        fig.add_trace(go.Box(y=df_day['orbital_decay_c'], name=day))

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

    if selected_plot_type=='boxplot-day':

        df = pd.read_parquet(f'./data/dataframes/{selected_satellite}.parquet',
                            columns=['orbital_decay_c'])
        df.index = pd.to_datetime(df.index)
        plot_daily_boxplot(df, selected_satellite, 2024, 5)

        plot_filename = f'stats_{selected_plot_type}_{selected_satellite}_2024-05.html'
        plot_html = get_plot_html(plot_filename)

    if selected_satellite and selected_plot_type:
        plot_filename = f'stats_{selected_plot_type}_{selected_satellite}_2023-2024.html'
        plot_html = get_plot_html(plot_filename)

    return render_template('statistics.html', plot_html=plot_html, satellites=satellites, plot_types=plot_types, PRETTY_NAMES=load_config(), selected_satellite=selected_satellite, selected_plot_type=selected_plot_type)


@app.route('/update_plot', methods=['POST'])
def update_plot():
    selected_satellite = request.form.get('satellite')
    selected_plot_type = request.form.get('plot_type')

    if selected_plot_type=='boxplot-day':
        df = pd.read_parquet(f'./data/dataframes/{selected_satellite}.parquet',
                            columns=['orbital_decay_c'])
        df.index = pd.to_datetime(df.index)
        plot_daily_boxplot(df, selected_satellite, 2024, 5)

        plot_filename = f'stats_{selected_plot_type}_{selected_satellite}_2024-05.html'
        plot_html = get_plot_html(plot_filename)
    else:
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
                            columns=['orbital_decay_c', selected_feature, 'res_std_c', 'se_orbital_decay', 'res_c'])
        
    df = df.loc[selected_date_start:selected_date_end]
    df['z_score'] = ((df['res_std_c'] - df['res_std_c'].mean()
                       ) / df['res_std_c'].std()) * 3
    
    df['z_score'].fillna(0, inplace=True)
    df['orbital_decay_c'].interpolate(inplace=True)#.fillna(0, inplace=True)


    t_value = t.ppf(0.95, df=len(df) - 2)
    fig = make_subplots(specs=[[{"secondary_y": True}]])

    fig.add_trace(go.Scatter(
        x=df.index, y=df[selected_feature], mode='lines', name=selected_feature), secondary_y=False)
    print(df['se_orbital_decay'].std())
    fig.add_trace(go.Scatter(x=df.index, y= df['orbital_decay_c'] - t_value * df['se_orbital_decay'],#, mode='lines',
                               line=dict(width=0), showlegend=False), secondary_y=True)
    fig.add_trace(go.Scatter(x=df.index, y= df['orbital_decay_c'] + t_value * df['se_orbital_decay'],#,
                  mode='lines', line=dict(width=0), fill='tonexty', 
                  name='95% confidence interval'), secondary_y=True)
    
    print(df['res_std_c'].mean(), df['res_c'].mean())
    
    fig.add_trace(go.Scatter(
        x=df.index, y=df['orbital_decay_c'], mode='lines', name='Orbital Decay'), secondary_y=True)
    
    se_mean = df['se_orbital_decay'].mean()  # Mean of SE
    se_std = df['se_orbital_decay'].std()  # Standard deviation of SE
    rmse = np.sqrt(np.mean(df['res_c']**2))

    # The standard deviation of the residuals is around 14.47 m; RMSE = 14.52 m, indicating a moderate fit. 
    # However, the mean residual is close to zero, suggesting that the model accounts for most of the variability in the data.
    # The SE is 0.93 +- 0.039m, indicating that the model fits are within 0.93m of the true values 95% of the time.
    # This shows that while the model fits well for most data points, there's substantial variability (or noise) in the residuals
    print('rmse',rmse)

    default_colors = px.colors.qualitative.Plotly
    tc1 = default_colors[0 % len(default_colors)]
    tc2 = default_colors[3 % len(default_colors)]

    fig.add_annotation(
        x=df.index[len(df)-2880],  #
        y=df['orbital_decay_c'].max()+30,  
        text=f"SE: {se_mean:.3f} ± {se_std:.3f} m ",  
        font=dict(color=tc2),  
        align="center",
        borderpad=4, 
        bordercolor=tc2, 
        borderwidth=1,
        showarrow=False
    )

    fig.add_annotation(
        x=df.index[len(df)-2880], 
        y=df['orbital_decay_c'].max(), 
        text=f"RMSE: {rmse:.3f} m <br> Mean Residual: {df['res_c'].mean():.3f} ", 
        font=dict(color=tc2),  
        align="center",  
        borderpad=4,
        bordercolor=tc2, 
        borderwidth=1, 
        showarrow=False,
    )


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
                         columns=['orbital_decay_c', selected_feature, 'res_std_c', 'se_orbital_decay', 'res_c'])
    
    df = df.loc[selected_date_start:selected_date_end]
    df['z_score'] = ((df['res_std_c'] - df['res_std_c'].mean()
                       ) / df['res_std_c'].std()) * 3

    df['orbital_decay_c'].interpolate(inplace=True) #fillna(0, inplace=True)
    df['se_orbital_decay'].fillna(0, inplace=True)

    fig = make_subplots(specs=[[{"secondary_y": True}]])

    t_value = t.ppf(0.95, df=len(df) - 2)

    fig.add_trace(go.Scatter(
        x=df.index, y=df[selected_feature], mode='lines', name=selected_feature), secondary_y=False)
    print(df['se_orbital_decay'].std())
    fig.add_trace(go.Scatter(x=df.index, y= df['orbital_decay_c'] - t_value * df['se_orbital_decay'],#, mode='lines',
                               line=dict(width=0), showlegend=False), secondary_y=True)
    fig.add_trace(go.Scatter(x=df.index, y= df['orbital_decay_c'] + t_value * df['se_orbital_decay'],#,
                  mode='lines', line=dict(width=0), fill='tonexty', 
                  name='95% confidence interval'), secondary_y=True)
    
    print(df['res_std_c'].mean(), df['res_c'].mean())
    
    fig.add_trace(go.Scatter(
        x=df.index, y=df['orbital_decay_c'], mode='lines', name='Orbital Decay'), secondary_y=True)
    
    se_mean = df['se_orbital_decay'].mean()  # Mean of SE
    se_std = df['se_orbital_decay'].std()  # Standard deviation of SE

    # The standard deviation of the residuals is around 14.47 m; RMSE = 14.52 m, indicating a moderate fit. 
    # However, the mean residual is close to zero, suggesting that the model accounts for most of the variability in the data.
    # The SE is 0.93 +- 0.039m, indicating that the model fits are within 0.93m of the true values 95% of the time.
    # This shows that while the model fits well for most data points, there's substantial variability (or noise) in the residuals
    rmse = np.sqrt(np.mean(df['res_c']**2))
    print('rmse',rmse)

    default_colors = px.colors.qualitative.Plotly
    tc1 = default_colors[0 % len(default_colors)]
    tc2 = default_colors[3 % len(default_colors)]

    fig.add_annotation(
        x=df.index[len(df)-2880],  # Position annotation at the middle of the x-axis (or any other point)
        y=df['orbital_decay_c'].max()+30,  # Position it at the top (or any other position)
        text=f"SE: {se_mean:.3f} ± {se_std:.3f} m ",  # Display the SE as "x ± y"
        font=dict(color=tc2),  # Font size and color
        align="center",  # Align the text
        # bgcolor="white",  # Background color of the annotation
        borderpad=4,  # Padding around the text
        bordercolor=tc2,  # Border color
        borderwidth=1, # Border width
        showarrow=False,  # Do not show an arrow
    )

    fig.add_annotation(
        x=df.index[len(df)-2880],  # Position annotation at the middle of the x-axis (or any other point)
        y=df['orbital_decay_c'].max(),  # Position it at the top (or any other position)
        text=f"RMSE: {rmse:.3f} m <br> Mean Residual: {df['res_c'].mean():.3f} ",  # Display the SE as "x ± y"
        font=dict(color=tc2),  # Font size and color
        align="center",  # Align the text
        borderpad=4,  # Padding around the text
        bordercolor=tc2,  # Border color
        borderwidth=1, # Border width
        showarrow=False,  # Do not show an arrow
    )

    fig.update_traces(marker=dict(opacity=0.05), selector=dict(mode='markers'))


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
