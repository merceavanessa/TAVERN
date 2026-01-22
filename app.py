from flask import Flask, render_template, request
from flask_debugtoolbar import DebugToolbarExtension

from tavern.plotting_utils import plot_time_series_with_storms
from tavern.visualization import *

# APP START
app = Flask(__name__)
app.debug = config.debug

app.config['SECRET_KEY'] = os.environ.get('TAVERN_KEY') or os.urandom(24)
toolbar = DebugToolbarExtension(app)

# ROUTES
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/data/responsetimes', methods=['GET', 'POST'])
def responsetimes():
    satellites, plot_types, bzthr_options, corthr_options, extra24htime_options = get_available_response_time_plots()

    selected_satellite = 'all_satellites'
    selected_plot_type = plot_types[0]
    selected_bzthr = bzthr_options[0]
    selected_corthr = corthr_options[1]
    selected_extra24htime = extra24htime_options[0]
    plot_html = ""

    if selected_satellite and selected_plot_type:
        extra_text = config.event_filtering_map.get(selected_extra24htime, '')
        plot_filename = f'alignment_corr_combined_{selected_satellite}_Bzthr-{selected_bzthr}_cor-thr-{selected_corthr}{extra_text}.html'
        plot_html = get_plot_html(plot_filename, plot_dir=config.alignments_path)

    # hide line of text from tspan in plot_html starting with "Shifts counted"
    plot_html = plot_html.replace('<text x="40" y="80" font-size="14" fill="white">Shifts counted', '<text x="40" y="80" font-size="14" fill="white" style="display:none;">Shifts counted')
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

@app.route('/update_plot_responsetime', methods=['POST'])
def update_plot_responsetime():
    selected_satellite = request.form.get('satellite')
    selected_plot_type = request.form.get('plot_type')
    selected_bzthr = request.form.get('bzthr')
    selected_corthr = request.form.get('corthr')
    selected_extra24htime = request.form.get('extra24htime')

    extra_text = config.event_filtering_map.get(selected_extra24htime, '')
    plot_filename = f'alignment_corr_combined_{selected_satellite}_Bzthr-{selected_bzthr}_cor-thr-{selected_corthr}{extra_text}.html'
    plot_html = get_plot_html(plot_filename, plot_dir=config.alignments_path)

    satellites, plot_types, bzthr_options, corthr_options, extra24htime_options = get_available_response_time_plots()

    plot_html = plot_html.replace('<text x="40" y="80" font-size="14" fill="white">Shifts counted', '<text x="40" y="80" font-size="14" fill="white" style="display:none;">Shifts counted')
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

@app.route('/data/geomagnetic_storms', methods=['GET', 'POST'])
def geomagnetic_storms():
    satellites, _ = get_available_plots()
    overlays = ['None', 'Geomagnetic Storms', 'ICMEs']
    selected_satellite = satellites[-3] if satellites else None
    selected_overlay = overlays[0] if overlays else None
    selected_additional_features = ['F10.7 (LASP)', 'SymH (Omni)']

    plot_html = get_data_plot_html(selected_additional_features, selected_overlay, selected_satellite)

    return render_template('geomagnetic_storms.html', 
                          plot_html=plot_html, 
                          satellites=satellites, 
                          overlays=overlays, 
                          PRETTY_NAMES=config.satellite_info, 
                          selected_satellite=selected_satellite, 
                          selected_overlay=selected_overlay, 
                          selected_columns=selected_additional_features, 
                          PRETTY_COLUMN_DICT=config.feature_names, 
                          columns=config.additional_features)


def get_data_plot_html(selected_additional_features, selected_overlay, selected_satellite):
    af = selected_additional_features.copy()
    if 'Kp (LASP)' not in af:
        af += ['Kp (LASP)']
    df = pd.read_parquet(f'{config.data_path}/{selected_satellite}.parquet', columns=af + ['orbital_decay'])
    df = set_activity_level(df, config.geomagnetic_storm_levels)
    plot_html = plot_time_series_with_storms(df, satellite=selected_satellite,
                                             cols_to_plot=selected_additional_features, overlay=selected_overlay)
    del df
    return plot_html


@app.route('/update_plot_geomagnetic_storms', methods=['POST'])
def update_plot_geomagnetic_storms():
    selected_satellite = request.form.get('satellite')
    selected_overlay = request.form.get('overlay')
    selected_additional_features = request.form.getlist('selected_columns[]')

    plot_html = get_data_plot_html(selected_additional_features, selected_overlay, selected_satellite)

    satellites, _ = get_available_plots()
    overlays = ['None', 'Geomagnetic Storms', 'ICMEs']

    return render_template('geomagnetic_storms.html', 
                          plot_html=plot_html, 
                          satellites=satellites, 
                          overlays=overlays, 
                          PRETTY_NAMES=config.satellite_info, 
                          selected_satellite=selected_satellite, 
                          selected_overlay=selected_overlay, 
                          selected_columns=selected_additional_features, 
                          PRETTY_COLUMN_DICT=config.feature_names, 
                          columns=config.additional_features)

@app.route('/data/statistics', methods=['GET', 'POST'])
def statistics():
    satellites, plot_types = get_available_plots()

    selected_satellite = satellites[4] if satellites else None
    selected_plot_type = plot_types[0] if plot_types else None
    plot_html = ""

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

@app.route('/update_plot', methods=['POST'])
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

@app.route('/data/visualizations', methods=['GET', 'POST'])
def visualizations():
    satellites, _ = get_available_plots()
    selected_satellite = satellites[4] if satellites else None
    selected_date_start = '2024-05-01'
    selected_date_end = '2024-05-15'
    selected_feature = '|avg B|'

    return render_selected_template(satellites, selected_date_end, selected_date_start, selected_feature,
                                    selected_satellite)

@app.route('/update_vis_plot', methods=['POST'])
def update_vis_plot():
    satellites, _ = get_available_plots()
    selected_satellite = request.form.get('satellite')
    selected_date_start = request.form.get('date_start')
    selected_date_end = request.form.get('date_end')
    selected_feature = request.form.get('additional_feature')

    return render_selected_template(satellites, selected_date_end, selected_date_start, selected_feature, selected_satellite)

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

    return render_template('visualizations.html',
                           plot_html=plot_html,
                           additional_features=config.additional_features,
                           satellites=satellites,
                           PRETTY_NAMES=config.satellite_info,
                           selection=selection,
                           PRETTY_COLUMN_DICT=config.feature_names)

if __name__ == '__main__':
    app.run(debug=True, port=config.port)
