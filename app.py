import base64
from flask import Flask, render_template, request, jsonify, make_response, session
from flask_debugtoolbar import DebugToolbarExtension

from tavern.visualization import *
from tavern.config import config
import os

# —————————————————————————— APP SETUP ——————————————————————————
app = Flask(__name__)
app.debug = config.debug
# app.config['SECRET_KEY'] = os.environ.get('TAVERN_KEY') or os.urandom(24)
app.config['SECRET_KEY'] = 'dummy local'
toolbar = DebugToolbarExtension(app)

# —————————————————————————— RENDER UTILS ——————————————————————————
def render_selected_template(satellites, selected_date_end, selected_date_start, selected_feature, selected_satellite):
    selection = {
        'satellite': selected_satellite,
        'date_start': selected_date_start,
        'date_end': selected_date_end,
        'additional_feature': selected_feature
    }
    plot_html = create_time_series_visualization(
        selected_satellite,
        selected_date_start,
        selected_date_end,
        selected_feature
    )

    return render_template('decay_rates_space_weather.html',
                           plot_html=plot_html,
                           additional_features=config.additional_features,
                           satellites=satellites,
                           PRETTY_NAMES=config.satellite_info,
                           selection=selection,
                           PRETTY_COLUMN_DICT=config.feature_names)

# —————————————————————————— SESSION ——————————————————————————

@app.before_request
def set_session_decay_feature():
    """Ensure decay_feature is set in session."""
    if 'decay_feature' not in session:
        session['decay_feature'] = config.decay_feature

# —————————————————————————— ROUTES ——————————————————————————
@app.route('/api/theme')
def get_theme():
    """
    Return the configured theme with a cookie for faster future loads.
    The cookie allows the browser to read the theme immediately on next visit.
    Quite buggy for transitions - not fond of the implementation, currently defaulting to light theme.
    """
    response = make_response(jsonify({'theme': config.theme}))
    response.set_cookie(
        'tavern-theme-config',
        config.theme,
        max_age=31536000,  # 1 year in seconds
        samesite='Lax',
        secure=False  # Set to True if using HTTPS
    )
    return response

# ——————— INDEX ———————
@app.route('/')
def index():
    selected_decay_feature = config.get_active_decay_feature()
    return render_template('index.html',
                           decay_feature_options=config.decay_feature_options,
                           selected_decay_feature=selected_decay_feature,
                           feature_names=config.feature_names)


# Control which feature is used throughout the app as orbital decay rate (for dynamic plots only)
@app.route('/api/decay_feature', methods=['GET'])
def get_decay_feature_api():
    """Return the current decay feature."""
    response = make_response(jsonify({'decay_feature': config.get_active_decay_feature()}))
    return response

@app.route('/set_decay_feature', methods=['POST'])
def set_decay_feature():
    """Update the decay feature selection."""
    session['decay_feature'] = request.form.get('decay_feature', config.decay_feature)
    selected_decay_feature = config.get_active_decay_feature()
    return render_template('index.html',
                          decay_feature_options=config.decay_feature_options,
                          selected_decay_feature=selected_decay_feature,
                          feature_names=config.feature_names)

# ——————— Decay Rate Statistics ———————
@app.route('/data/statistics', methods=['GET', 'POST'])
def statistics():
    satellites, plot_types = get_available_plots()
    plot_html = ""

    if request.method == 'GET':
        selected_satellite = satellites[4] if satellites else None
        selected_plot_type = plot_types[0] if plot_types else None
    else:
        selected_satellite = request.form.get('satellite')
        selected_plot_type = request.form.get('plot_type')

    if selected_satellite and selected_plot_type:
            plot_filename = f'stats_{selected_plot_type}_{selected_satellite}_{config.file_label}.html'
            plot_html = get_plot_html(plot_filename)

    return render_template('statistics.html',
                          plot_html=plot_html,
                          satellites=satellites,
                          plot_types=plot_types,
                          PRETTY_NAMES=config.satellite_info,
                          selected_satellite=selected_satellite,
                          selected_plot_type=selected_plot_type)

# todo - plot statistics of decay by hp30 (kde plot)

@app.route('/update_plot_statistics', methods=['GET', 'POST'])
def update_plot():
    selected_satellite = request.form.get('satellite')
    selected_plot_type = request.form.get('plot_type')

    plot_filename = f'stats_{selected_plot_type}_{selected_satellite}_{config.file_label}.html'
    plot_html = get_plot_html(plot_filename)

    satellites, plot_types = get_available_plots()
    return render_template('statistics.html',
                          plot_html=plot_html,
                          satellites=satellites,
                          plot_types=plot_types,
                          PRETTY_NAMES=config.satellite_info,
                          selected_satellite=selected_satellite,
                          selected_plot_type=selected_plot_type)

# ——————— Decay Rates & Space Weather ———————
# Compare orbital decay rates to a second feature.
@app.route('/data/decay_rates_space_weather', methods=['GET', 'POST'])
def decay_rates_space_weather():
    satellites, _ = get_available_plots()

    if request.method == 'GET':
        selected_satellite = satellites[4] if satellites else None
        selected_date_start = '2024-05-01'
        selected_date_end = '2024-05-15'
        selected_feature = '|avg B|'
    else:
        selected_satellite = request.form.get('satellite')
        selected_date_start = request.form.get('date_start')
        selected_date_end = request.form.get('date_end')
        selected_feature = request.form.get('additional_feature')

    return render_selected_template(satellites, selected_date_end, selected_date_start, selected_feature,
                                    selected_satellite)

# ——————— Atmospheric Response Times ———————
@app.route('/data/response_times', methods=['GET', 'POST'])
def response_times():
    satellites, plot_types, bzthr_options, corthr_options, extra24htime_options = get_available_response_time_plots()

    if request.method == 'GET':
        selected_satellite = 'all_satellites'
        selected_plot_type = plot_types[0]
        selected_bzthr = bzthr_options[0]
        selected_corthr = corthr_options[1]
        selected_extra24htime = extra24htime_options[0]
    else:
        selected_satellite = request.form.get('satellite')
        selected_plot_type = request.form.get('plot_type')
        selected_bzthr = request.form.get('bzthr')
        selected_corthr = request.form.get('corthr')
        selected_extra24htime = request.form.get('extra24htime')

    if selected_satellite and selected_plot_type:
        extra_text = config.event_filtering_map.get(selected_extra24htime, '')

    plot_filename = f'alignment_corr_combined_{selected_satellite}_Bzthr-{selected_bzthr}_cor-thr-{selected_corthr}{extra_text}.html'
    plot_html = get_plot_html(plot_filename, plot_dir=config.alignments_path)

    # hide line of text from tspan in plot_html starting with "Shifts counted"
    plot_html = plot_html.replace('<text x="40" y="80" font-size="14" fill="white">Shifts counted',
                                  '<text x="40" y="80" font-size="14" fill="white" style="display:none;">Shifts counted')
    return render_template('response_times.html',
                           plot_html=plot_html,
                           satellites=satellites,
                           plot_types=plot_types,
                           PRETTY_NAMES=config.satellite_info,
                           selected_satellite=selected_satellite,
                           selected_plot_type=selected_plot_type,
                           bzthr_options=bzthr_options,
                           corthr_options=corthr_options,
                           extra24htime_options=extra24htime_options,
                           selected_bzthr=selected_bzthr,
                           selected_corthr=selected_corthr,
                           selected_extra24htime=selected_extra24htime)

# ——————— Space Weather Events ———————
@app.route('/data/space_weather_events', methods=['GET', 'POST'])
def space_weather_events():
    satellites, _ = get_available_plots()
    overlays = ['None', 'Geomagnetic Storms', 'ICMEs', 'IP Shocks']

    if request.method == 'GET':
        selected_satellite = satellites[-3] if satellites else None
        selected_overlay = overlays[0]
        selected_additional_features = ['F10.7', 'SymH']
    else:
        selected_satellite = request.form.get('satellite')
        selected_overlay = request.form.get('overlay')
        selected_additional_features = request.form.getlist('selected_columns[]')

    print(selected_overlay)
    plot_html = get_data_plot_html(selected_additional_features, selected_overlay, selected_satellite)

    return render_template('space_weather_events.html',
                          plot_html=plot_html,
                          satellites=satellites,
                          overlays=overlays,
                          PRETTY_NAMES=config.satellite_info,
                          selected_satellite=selected_satellite,
                          selected_overlay=selected_overlay,
                          selected_columns=selected_additional_features,
                          PRETTY_COLUMN_DICT=config.feature_names,
                          columns=config.additional_features)

# ——————— Orbit Decay Tracks ———————
@app.route('/data/orbit_decay_tracks', methods=['GET', 'POST'])
def orbit_decay_tracks():
    """Render the orbit decay tracks page with available dates and altitude options."""
    dates, altitude_options, selected_date, selected_altitude = get_available_orbit_tracks()
    plot_html = ""

    if request.method == 'POST':
        selected_date = request.form.get('date')
        selected_altitude = request.form.get('altitude')

    if selected_date and selected_altitude:
        plot_filename = f'orbital_decay_tracks_sc_{selected_altitude}_600_km_{selected_date}.html'
        plot_html = get_plot_html(plot_filename, plot_dir=config.orbit_plots_path)

    return render_template('orbit_decay_tracks.html',
                          plot_html=plot_html,
                          dates=dates,
                          altitude_options=altitude_options,
                          selected_date=selected_date,
                          selected_altitude=selected_altitude)

# ——————— Spatial Analysis ———————
@app.route('/data/spatial_analysis', methods=['GET', 'POST'])
def spatial_analysis():
    """Render the spatial decay page with available satellites and filter options."""
    satellites, exclude_options, selected_satellite, selected_exclude = get_available_spatial_decay_plots()
    plot_html = ""

    if request.method == 'POST':
        selected_satellite = request.form.get('satellite')
        selected_exclude = request.form.get('exclude_may_oct')

    pdf_path = get_spatial_decay_pdf_path(selected_satellite, selected_exclude)
    if pdf_path and os.path.exists(pdf_path):
        try:
            with open(pdf_path, 'rb') as f:
                pdf_data = base64.b64encode(f.read()).decode()
            plot_html = f'<iframe src="data:application/pdf;base64,{pdf_data}" width="100%" height="800px" style="border: none;"></iframe>'
        except Exception as e:
            plot_html = f"<p>Error loading PDF: {str(e)}</p>"
    
    # Map satellite codes to pretty names
    satellite_display = []
    for sat in satellites:
        if sat in config.satellite_info:
            satellite_display.append((sat, config.satellite_info[sat].get('name', sat)))
        else:
            satellite_display.append((sat, sat))

    return render_template('spatial_analysis.html',
                          plot_html=plot_html,
                          satellites=satellite_display,
                          exclude_options=exclude_options,
                          selected_satellite=selected_satellite,
                          selected_exclude=selected_exclude)

# —————————————————————————— APP RUN ——————————————————————————
if __name__ == '__main__':
    print(f"Starting TAVERN app on {config.host}:{config.port} with debug={config.debug}")
    app.run(host=config.host, port=config.port, debug=config.debug)
