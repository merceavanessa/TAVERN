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
FLAGS_CME_DIR = '/Users/vanessa/PhD/Dev/SELAnalysis/SpaceWeatherImpact/data/2023-01-01_2024-12-31/flags_david/'
flag_files = {
    # 'IP Shocks Database': 'shocks_GFOC.csv', - todo
    'Richardson & Cane': 'RC_icmecat_GFOC.csv', # (rounded to next hour)
    'Helio4Cast': 'helio4cast_icmecat_GFOC.csv', # (at Wind)'
}

PLOTS_DIR_ALIGNMENTS = '/Users/vanessa/PhD/Dev/SELAnalysis/SpaceWeatherImpact/notebooks/2023-01-01_2024-12-31/plots/alignments/'
PLOTS_DIR_STORMS = '/Users/vanessa/PhD/Dev/SELAnalysis/SpaceWeatherImpact/notebooks/2023-01-01_2024-12-31/plots/storms/'
CONFIG_PATH = '/Users/vanessa/PhD/Dev/SELAnalysis/SpaceWeatherImpact/data/2023-01-01_2024-12-31/configs/POD/config.json'
additional_features = ['SymH (Omni)', 'AsyD (Omni)', 'SymD (Omni)', 'AsyH (Omni)',
                       'F10.7 (LASP)', 'F30 (LASP)', 'Kp (LASP)', 'ap (LASP)',
                       '|avg B|', 'Bz GSE', 'Flow Speed (km/s',
                       'Proton density (n/cc)', 'Temperature (K)', 'Alpha/Proton Ratio',
                       'Flow pressure (nPa)', 'Electric Field (Mv/m)', 'Plasma beta',
                       'Alfven mach number', 'Magnetosonic mach number', 'Vz Velocity (km/s)',
                       'Approximate Distance to SEL (Re)', 'activity_level'
                       ]
pretty_dict = {
    'orbital_decay': 'Orbital Decay (m/day)',
    'AsyH (Omni)': 'AsyH (nT)\n(magnitude of the asymmetric horizontal geomagnetic response)',
    'SymH (Omni)': 'SymH (nT)\n(magnitude of the symmetric horizontal geomagnetic response)',
    'AsyD (Omni)': 'AsyD (nT)\n(magnitude of the asymmetric east-west geomagnetic response)',
    'SymD (Omni)': 'SymD (nT)\n(magnitude of the symmetric east-west geomagnetic response)',
    'F10.7 (LASP)': 'Solar Radio Flux F10.7 (sfu)',
    'F30 (LASP)': 'Solar Radio Flux F30 (sfu)',
    'Kp (LASP)': 'Planetary K-index',
    'ap (LASP)': 'Planetary A-index',
    '|avg B|': 'Average Solar Wind Magnetic Field Magnitude (nT)',
    'Bz GSE': 'Z-component of Solar Wind Magnetic Field in GSE (nT)',
    'By GSE': 'Y-component of Solar Wind Magnetic Field in GSE (nT)',
    'Flow Speed (km/s': 'Solar Wind Flow Speed (km/s)',
    'Proton density (n/cc)': 'Solar Wind Proton Density (particles/cm³)',
    'Temperature (K)': 'Solar Wind Temperature (K)',
    'Alpha/Proton Ratio': 'Solar Wind Alpha to Proton Ratio',
    'Flow pressure (nPa)': 'Solar Wind Flow Pressure (nPa)',
    'Electric Field (Mv/m)': 'Solar Wind Electric Field (mV/m)',
    'Plasma beta': 'Solar Wind Plasma Beta',
    'Alfven mach number': 'Solar Wind Alfvén Mach Number',
    'Magnetosonic mach number': 'Solar Wind Magnetosonic Mach Number',
    'Vz Velocity (km/s)': 'Z-component Solar Wind Plasma Velocity (km/s)',
    'Vy Velocity (km/s)': 'Y-component Solar Wind Plasma Velocity (km/s)',
    'Approximate Distance to SEL (Re)': 'Approximate Distance of the Wind satellite to the Sun-Earth Line (Re)',
    'activity_level': 'Geomagnetic Activity Level',
}
column_dict_cmes = {
    'Disturbance_time': 'Disturbance storm time',
    'ICME_Start': 'ICME start time',
    'ICME_End': 'ICME end time',
    'icme_start_time': 'ICME start time',
    'mo_start_time': 'Magnetic Obstacle start time',
    'mo_end_time': 'Magnetic Obstacle end time'
}

BASE_PATH = '/Users/vanessa/PhD/Dev/SELAnalysis/SpaceWeatherImpact/data/2023-01-01_2024-12-31/processed/'
file_label = '2023-01-01_2024-12-31'

geomagnetic_storm_levels = {
    "G0 (Quiet to Unsettled)": (0.0, 4.99999),
    "G1 (Minor)": (5.0, 5.99999),
    "G2 (Moderate)": (6.0, 6.99999),
    "G3 (Strong)": (7.0, 7.99999),
    "G4 (Severe)": (8.0, 8.999999),
    "G5 (Extreme)": (9.0, 9.99999)
}

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


def set_activity_level(df):
    df['activity_level'] = df['Kp (LASP)'].apply(lambda kp: next((level for level, (low, high) in geomagnetic_storm_levels.items() if low <= kp <= high), 'Unknown'))

    #  propagate backward the strongest activity levels until the transition to quiet level to the left and right e.g. G1 G3 G2 G5 G1 -> G1 strong G5 G5 G5 G1
    activity = df['activity_level'].values
    for level in ["G5 (Extreme)", "G4 (Severe)", "G3 (Strong)", "G2 (Moderate)", "G1 (Minor)"]:
        is_not_quiet = activity != 'G0 (Quiet to Unsettled)'
        is_level = activity == level
        regions = np.flatnonzero(np.diff(np.concatenate(([0], is_not_quiet.view(np.int8), [0]))))
        for start, end in zip(regions[::2], regions[1::2]):
            if is_level[start:end].any():
                activity[start:end] = level
    df['activity_level'] = activity

    # if less than N points of one activity level between two stronger activity levels, propagate the stronger activity level to those points
    N = 3 * 60 * 3 # 3 hours
    activity = df['activity_level'].values
    regions = np.flatnonzero(np.diff(np.concatenate(([0], activity != activity[0],
        [0]))))
    for start, end in zip(regions[::2], regions[1::2]):
        if end - start < N:
            left_level = activity[start - 1] if start > 0 else None
            right_level = activity[end] if end < len(activity) else None
            if left_level == right_level and left_level is not None and left_level != 'G0 (Quiet to Unsettled)':
                activity[start:end] = left_level
    df['activity_level'] = activity

    # median_symH = abs(df['SymH (Omni)'].median())
    # threshold_symH = 5
    # df.loc[(df['SymH (Omni)'].abs() > threshold_symH) & (df['activity_level']=='G0 (Quiet to Unsettled)'), 'activity_level'] = np.nan
    # df['activity_level'] = df['activity_level'].ffill().bfill()

    df = annotate_geomagnetic_storm_events(df)
    df['decay_level'] = df['orbital_decay'].rank(pct=True)
    return df

def annotate_geomagnetic_storm_events(df):
    for i, level in enumerate(geomagnetic_storm_levels.keys()):
        if 'G0' in level:
            continue

        activity = df['activity_level'].values
        is_level = activity == level
        regions = np.flatnonzero(np.diff(np.concatenate(([0], is_level.view(np.int8), [0]))))
        event_count = len(regions) // 2
        data_samples_per_region = [regions[i + 1] - regions[i] for i in range(0, len(regions), 2)]
        df.loc[df['activity_level'] == level, 'event_number'] = np.repeat(np.arange(1, event_count + 1),
                                                                          data_samples_per_region)
        df.loc[df['activity_level'] == level, 'unique_event_id'] = [int(f'{i}{n}') for n in
                                                                    np.repeat(np.arange(1, event_count + 1),
                                                                              data_samples_per_region)]

    return df

def plot_time_series_with_storms(df, satellite, cols_to_plot, overlay='Geomagnetic Storms', rs='3H'):
    fig = make_subplots(
        rows=len(cols_to_plot) + 1, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.02,
        subplot_titles=(pretty_dict.get('orbital_decay', 'Orbital Decay'),) + tuple(
            pretty_dict.get(col, col) for col in cols_to_plot),
    )

    if overlay == 'Geomagnetic Storms':
        unique_event_ids = df['unique_event_id'].dropna().unique()
        storm_strengths = {}
        for storm_id in unique_event_ids:
            storm_strength = df[df['unique_event_id'] == storm_id]['activity_level'].iloc[0]
            storm_strengths[storm_id] = storm_strength

    df = df.resample(rs).mean(numeric_only=True)

    config = load_config()
    fig.update_layout(
        title=f"Orbital decay against {overlay} for {config[satellite]['name']}." if overlay != 'None' else f"Orbital decay and additional features for {config[satellite]['name']}." if len(cols_to_plot) > 0 else f"Orbital decay for {config[satellite]['name']}.",
        title_x=0.5,
        font=dict(size=20),
        height=600 * (len(cols_to_plot) + 1)
        # height=250 * (len(cols_to_plot) + 1) if len(cols_to_plot) > 0 else 300
    )

    for annotation in fig.layout.annotations:
        annotation.font = dict(size=20)

    # fig.update_traces(showlegend=False)

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

            # storm_end = storm_times[-1]
            # print(storm_start, storm_end, storm_strength)
            # fig.add_vrect(
            #     x0=storm_start,
            #     x1=storm_end + pd.Timedelta(hours=24),
            #     fillcolor="red" if 'G4' in storm_strength or 'G5' in storm_strength else "orange" if 'G2' in storm_strength or 'G3' in storm_strength else "yellow",
            #     opacity=0.15,
            #     layer="below",
            #     xref="x"
            # )

            # fig.add_trace(
            #     go.Scatter(
            #         x=[None],
            #         y=[None],
            #         mode='markers',
            #         marker=dict(
            #             size=10,
            #             color="red" if 'G4' in level or 'G5' in level else "orange" if 'G2' in level or 'G3' in level else "yellow",
            #             opacity=0.35
            #         ),
            #         name=level,
            #         legendgroup=level,
            #         showlegend=True,
            #     )
            # )

            fig.update_layout(legend_title_text='Geomagnetic Storm Levels')

    elif 'ICME' in overlay:
        c=0
        colors = pc.sequential.Reds[::int(len(pc.sequential.Reds)/3)]
        colors += pc.sequential.Blues[::int(len(pc.sequential.Blues)/3)]

        for flag, filename in flag_files.items():
            cme_df = pd.read_csv(os.path.join(FLAGS_CME_DIR, flag_files[flag]))
            start_time_name = 'Disturbance_time' if 'Disturbance_time' in cme_df.columns else 'icme_start_time'
            cme_start_name = 'ICME_Start' if 'ICME_Start' in  cme_df.columns else 'mo_start_time'
            cme_end_name = 'ICME_End' if 'ICME_End' in  cme_df.columns else 'mo_end_time'

            cme_df[start_time_name] = pd.to_datetime(cme_df[start_time_name])
            cme_df[cme_start_name] = pd.to_datetime(cme_df[cme_start_name])
            cme_df[cme_end_name] = pd.to_datetime(cme_df[cme_end_name])

            # for col in [start_time_name, cme_start_name, cme_end_name]: - todo - too cluttered?
            for col in [cme_start_name]:
                for i, row in cme_df.iterrows():
                    fig.add_trace(
                        go.Scatter(
                            x=[row[col], row[col]],
                            y=[df['orbital_decay'].min(), df['orbital_decay'].max()],
                            mode='lines',
                            line=dict(color=colors[c], width=3, dash='dash'),
                            opacity=0.35,
                            name= f"{column_dict_cmes[col]} ({flag})",
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
                        name=f"{column_dict_cmes[col]} ({flag})",
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
            name=pretty_dict.get('orbital_decay', 'Orbital Decay'),
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
                    name=pretty_dict.get(col, col),
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

def get_available_response_time_plots():
    satellites = set()
    plot_types = set()
    Bzthr_options = ['0', '9999']
    corthr_options = ['0.7', '0.8', '0.9']
    extra24htime = ['included', 'not-included', 'before and after']

    for filename in os.listdir(PLOTS_DIR_ALIGNMENTS):
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

    return sorted(list(satellites)), sorted(list(plot_types)), Bzthr_options, corthr_options, extra24htime

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

@app.route('/data/responsetimes', methods=['GET', 'POST'])
def responsetimes():
    satellites, plot_types, Bzthr_options, corthr_options, extra24htime_options = get_available_response_time_plots()

    selected_satellite = 'all_satellites'
    selected_plot_type = plot_types[0]
    selected_bzthr = Bzthr_options[0]
    selected_corthr = corthr_options[1]
    selected_extra24htime = extra24htime_options[0]
    plot_html = ""

    if selected_satellite and selected_plot_type:
        extra_text = '_with_24h_extratime' if selected_extra24htime == 'included' else '' if selected_extra24htime == 'not-included' else '_with_24h_extratime_bothways'

        plot_filename = f'alignment_corr_combined_{selected_satellite}_Bzthr-{selected_bzthr}_cor-thr-{selected_corthr}{extra_text}.html'
        print(plot_filename)

        plot_html = get_plot_html(plot_filename, plot_dir=PLOTS_DIR_ALIGNMENTS)

    pretty_names = load_config()
    pretty_names['all_satellites'] = {'name' : 'All Satellites'}

    return render_template('response_times.html', plot_html=plot_html, satellites=satellites, plot_types=plot_types, PRETTY_NAMES=pretty_names, selected_satellite=selected_satellite, selected_plot_type=selected_plot_type, Bzthr_options=Bzthr_options, corthr_options=corthr_options, extra24htime_options=extra24htime_options, selected_bzthr=selected_bzthr, selected_corthr=selected_corthr, selected_extra24htime=selected_extra24htime)

@app.route('/update_plot_responsetime', methods=['POST'])
def update_plot_responsetime():
    selected_satellite = request.form.get('satellite')
    selected_plot_type = request.form.get('plot_type')
    selected_bzthr = request.form.get('bzthr')
    selected_corthr = request.form.get('corthr')
    selected_extra24htime = request.form.get('extra24htime')

    extra_text = '_with_24h_extratime' if selected_extra24htime == 'included' else '' if selected_extra24htime == 'not-included' else '_with_24h_extratime_bothways'
    plot_filename = f'alignment_corr_combined_{selected_satellite}_Bzthr-{selected_bzthr}_cor-thr-{selected_corthr}{extra_text}.html'
    print(plot_filename)

    plot_html = get_plot_html(plot_filename, plot_dir=PLOTS_DIR_ALIGNMENTS)

    satellites, plot_types, Bzthr_options, corthr_options, extra24htime_options = get_available_response_time_plots()
    pretty_names = load_config()
    pretty_names['all_satellites'] = {'name' : 'All Satellites'}

    return render_template('response_times.html', plot_html=plot_html, satellites=satellites, plot_types=plot_types, PRETTY_NAMES=pretty_names, selected_satellite=selected_satellite, selected_plot_type=selected_plot_type, Bzthr_options=Bzthr_options, corthr_options=corthr_options, extra24htime_options=extra24htime_options, selected_bzthr=selected_bzthr, selected_corthr=selected_corthr, selected_extra24htime=selected_extra24htime)

@app.route('/data/geomagnetic_storms', methods=['GET', 'POST'])
def geomagnetic_storms():
    satellites, _ = get_available_plots()
    overlays = ['None', 'Geomagnetic Storms', 'ICMEs']
    selected_satellite = satellites[-3] if satellites else None
    selected_overlay = overlays[0] if overlays else None
    selected_additional_features = ['F10.7 (LASP)', 'SymH (Omni)']

    af = selected_additional_features.copy()
    if 'Kp (LASP)' not in af:
       af += ['Kp (LASP)']

    df = pd.read_parquet(f'{BASE_PATH}/{selected_satellite}.parquet', columns= af + ['orbital_decay'])
    df = set_activity_level(df)

    plot_html = plot_time_series_with_storms(df, satellite=selected_satellite, cols_to_plot=selected_additional_features, overlay=selected_overlay)
    del df

    return render_template('geomagnetic_storms.html', plot_html=plot_html, satellites=satellites, overlays=overlays, PRETTY_NAMES=load_config(), selected_satellite=selected_satellite, selected_overlay=selected_overlay, selected_columns=selected_additional_features, PRETTY_COLUMN_DICT=pretty_dict, columns=additional_features)

@app.route('/update_plot_geomagnetic_storms', methods=['POST'])
def update_plot_geomagnetic_storms():
    selected_satellite = request.form.get('satellite')
    selected_overlay = request.form.get('overlay')
    selected_additional_features = request.form.getlist('selected_columns[]')

    af = selected_additional_features.copy()
    if 'Kp (LASP)' not in af:
        af += ['Kp (LASP)']

    df = pd.read_parquet(f'{BASE_PATH}/{selected_satellite}.parquet', columns= af + ['orbital_decay'])
    df = set_activity_level(df)

    plot_html = plot_time_series_with_storms(df, satellite=selected_satellite, cols_to_plot=selected_additional_features, overlay=selected_overlay)
    del df
    satellites, _ = get_available_plots()
    overlays = ['None', 'Geomagnetic Storms', 'ICMEs']

    return render_template('geomagnetic_storms.html', plot_html=plot_html, satellites=satellites, overlays=overlays, PRETTY_NAMES=load_config(), selected_satellite=selected_satellite, selected_overlay=selected_overlay, selected_columns=selected_additional_features, PRETTY_COLUMN_DICT=pretty_dict, columns=additional_features)

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


    c = ['orbital_decay', 'Kp (LASP)', selected_feature] if selected_feature != 'Kp (LASP)' else ['orbital_decay', 'Kp (LASP)']
    if selected_feature == 'activity_level':
        c.remove(selected_featxre)
    df = pd.read_parquet(f'{BASE_PATH}/{selected_satellite}.parquet',
                            columns=c)

    df = df.loc[selected_date_start:selected_date_end]

    df['orbital_decay'].interpolate(inplace=True)
    df = set_activity_level(df)

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
        title=f'{pretty_dict[selected_feature]} and Orbital Decay',
        xaxis_title='Time',
        yaxis_title=update_feature_name(selected_feature),
        yaxis2_title="Orbital Decay [m/day]",
        yaxis=dict(title_font_color=tc1, tickfont=dict(color=tc1)),
        yaxis2=dict(overlaying='y', side='right', title_font_color=tc2, tickfont=dict(color=tc2)),
        font=dict(size=18),
        showlegend=True
    )

    plot_html = fig.to_html(full_html=False)

    return render_template('visualizations.html', plot_html=plot_html, additional_features=additional_features, satellites=satellites, PRETTY_NAMES=load_config(), selection=selection, PRETTY_COLUMN_DICT=pretty_dict)

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

    c = ['orbital_decay', 'Kp (LASP)', selected_feature] if selected_feature != 'Kp (LASP)' else ['orbital_decay',
                                                                                                  'Kp (LASP)']
    if selected_feature == 'activity_level':
        c.remove(selected_feature)

    df = pd.read_parquet(f'{BASE_PATH}/{selected_satellite}.parquet',
                         columns=c)

    df = df.loc[selected_date_start:selected_date_end]
    df['orbital_decay'].interpolate(inplace=True)
    df = set_activity_level(df)

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
        title=f'{pretty_dict[selected_feature]} and Orbital Decay',
        xaxis_title='Time',
        yaxis_title=update_feature_name(selected_feature),
        yaxis2_title="Orbital Decay [m/day]",
        yaxis=dict(title_font_color=tc1, tickfont=dict(color=tc1)),
        yaxis2=dict(overlaying='y', side='right', title_font_color=tc2, tickfont=dict(color=tc2)),
        font = dict(size=18),
        showlegend=True
    )

    plot_html = fig.to_html(full_html=False)

    return render_template('visualizations.html', plot_html=plot_html, additional_features=additional_features, satellites=satellites, PRETTY_NAMES=load_config(), selection=selection, PRETTY_COLUMN_DICT=pretty_dict)


def get_plot_html(filename, plot_dir=PLOTS_DIR):
    file_path = os.path.join(plot_dir, filename)
    print(file_path)
    try:
        with open(file_path, 'r') as f:
            return f.read()
    except FileNotFoundError:
        return "<p>Plot not found.</p>"


if __name__ == '__main__':
    app.run(debug=True, port=8000)
