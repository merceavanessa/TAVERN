from dotenv import load_dotenv
import os
import base64

# Load environment variables from .env
if os.path.exists('.env'):
    load_dotenv() # local development
else:
    load_dotenv('/var/www/leodecay/.env')# production

import base64
from datetime import timedelta
from flask import Flask, render_template, request, jsonify, make_response, session, url_for, redirect, abort, Response
from flask_login import LoginManager, login_required, login_user, current_user, logout_user
from flask_talisman import Talisman
from flask import send_file

from tavern.visualization import *
from tavern.config import config
from tavern.auth import *

# —————————————————————————— APP SETUP ——————————————————————————
app = Flask(__name__, static_folder='static', template_folder='templates')

# Configuration
app.config.update(
    SECRET_KEY=os.environ.get('LEODECAY_SECRET_KEY') or (_ for _ in ()).throw(
        ValueError("LEODECAY_SECRET_KEY not set")),  # signs sessions/cookies

    FLASK_ENV=os.environ.get('LEODECAY_FLASK_ENV', 'development'),  # deprecated, but using it to control debugging
    DEBUG=os.environ.get('LEODECAY_FLASK_ENV') == 'development',  # enable Flask debugger
    FORCE_HTTPS=os.environ.get('FORCE_HTTPS', 'False').lower() == 'true',
    # redirect HTTP → HTTPS (should be True in prod)

    GOOGLE_CLIENT_ID=os.environ.get('LEODECAY_GOOGLE_CLIENT_ID'),  # OAuth app ID from Google Console
    GOOGLE_CLIENT_SECRET=os.environ.get('LEODECAY_GOOGLE_CLIENT_SECRET'),  # OAuth app secret from Google Console

    PORT=int(os.environ.get('LEODECAY_PORT', 8080)),  # port to listen on
    HOST=os.environ.get('LEODECAY_HOST', '127.0.0.1'),  # '127.0.0.1' locally, '0.0.0.0' in prod

    SESSION_COOKIE_SAMESITE="Lax",  # blocks cross-site request forgery
    SESSION_COOKIE_SECURE=os.environ.get('LEODECAY_FLASK_ENV') == 'production',  # HTTPS-only cookies in prod

    PERMANENT_SESSION_LIFETIME=timedelta(hours=24),  # log users out after 24h
    ALLOWED_EMAILS=[e for e in os.environ.get("LEODECAY_ALLOWED_EMAILS", "").split(",") if e] # whitelist of permitted Google accounts
)

app.debug = app.config.get('DEBUG')

# OAuth and Flask-Login
oauth = register_oauth(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# Content Secure Policies
csp = {
    'default-src': ["'self'"],
    'style-src': [
        "'self'",
        "'unsafe-inline'",
        "https://cdn.jsdelivr.net",
        "https://cdnjs.cloudflare.com",
        "https://stackpath.bootstrapcdn.com"
    ],
    'script-src': [
        "'self'",
        "'unsafe-inline'",  # added to allow inline scripts from plotly
        "https://code.jquery.com",
        "https://cdn.jsdelivr.net",
        "https://stackpath.bootstrapcdn.com"
    ],
    'font-src': [
        "'self'",
        "https://cdnjs.cloudflare.com",
        "https://cdn.jsdelivr.net"
    ],
    'img-src': ["'self'", "data:"],
    'connect-src': [
        "'self'",
        "https://cdn.plot.ly",  # added for plotly animations
    ],
    'frame-src': ["'self'", "blob:", "data:"]
}

# Security headers (CSP, HSTS, etc.)
Talisman(app, strict_transport_security=True, content_security_policy=csp,
         force_https=os.environ.get('FORCE_HTTPS', 'False').lower() == 'true')


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


# —————————————————————————— OAUTH ROUTES ——————————————————————————

@app.route('/login')
def login():
    """Redirect to Google login."""
    # force Google to show account picker to avoid automatic login due to browser knowledge of google account
    redirect_uri = url_for('authorize', _external=True)
    return oauth.google.authorize_redirect(
        redirect_uri,
        prompt='select_account'
    )


@login_manager.user_loader
def load_user(user_id):
    user_data = session.get('user')
    if not user_data:
        return None
    if str(user_data['id']) != str(user_id):  # str() on BOTH sides
        print("ID MISMATCH:", repr(user_data['id']), "vs", repr(user_id))
        return None

    return User(user_data['id'], user_data['email'], user_data['name'])


@app.route('/authorize')
def authorize():
    token = oauth.google.authorize_access_token()
    user_info = token.get('userinfo')

    if not user_info:
        return "Login failed: could not retrieve user info.", 401

    email = user_info["email"]

    if email not in app.config.get("ALLOWED_EMAILS"):
        return render_template('unauthorized.html', email=email), 403

    user = User(str(user_info["sub"]), email, user_info.get("name"))

    session.permanent = True
    session['user'] = {
        'id': str(user.id),
        'email': user.email,
        'name': user.name,
    }
    login_user(user, remember=True)

    next_page = session.pop('next', None)
    return redirect(next_page or url_for('index'))


@app.route('/logout')
def logout():
    logout_user()
    session.clear()
    session.modified = True  # force Flask to rewrite the cookie
    response = make_response(redirect(url_for('index')))
    response.delete_cookie(app.config.get('SESSION_COOKIE_NAME', 'session'))
    return response


# —————————————————————————— DATA ROUTES ——————————————————————————

# ——————— INDEX ———————
@app.route('/')
def index():
    selected_decay_feature = config.get_active_decay_feature()
    return render_template('index.html',
                           decay_feature_options=config.decay_feature_options,
                           selected_decay_feature=selected_decay_feature,
                           feature_names=config.feature_names,
                           current_user=current_user)


# Control which feature is used throughout the app as orbital decay rate (for dynamic plots only)
@app.route('/api/decay_feature', methods=['GET'])
def get_decay_feature_api():
    response = make_response(jsonify({'decay_feature': config.get_active_decay_feature()}))
    return response


@app.route('/set_decay_feature', methods=['POST'])
def set_decay_feature():
    session['decay_feature'] = request.form.get('decay_feature', config.decay_feature)
    selected_decay_feature = config.get_active_decay_feature()
    return render_template('index.html',
                           decay_feature_options=config.decay_feature_options,
                           selected_decay_feature=selected_decay_feature,
                           feature_names=config.feature_names)


# ——————— Decay Rate Statistics ———————
@app.route('/data/statistics', methods=['GET', 'POST'])
@login_required
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
@login_required
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
@login_required
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
@login_required
def response_times():
    satellites, plot_types, corthr_options, extra24htime_options, cor_column_options = get_available_response_time_plots()

    if request.method == 'GET':
        selected_satellite = 'all_satellites'
        selected_plot_type = plot_types[0]
        selected_corthr = corthr_options[1]
        selected_extra24htime = extra24htime_options[0]
        selected_cor_column = cor_column_options[0]
    else:
        selected_satellite = request.form.get('satellite')
        selected_plot_type = request.form.get('plot_type')
        selected_corthr = request.form.get('corthr')
        selected_extra24htime = request.form.get('extra24htime')
        selected_cor_column = request.form.get('cor_column')

    if selected_satellite and selected_plot_type:
        extra_text = config.event_filtering_map.get(selected_extra24htime, '')

    plot_filename = f'alignment_corr_{selected_cor_column}_combined_{selected_satellite}_Bzthr-0_cor-thr-{selected_corthr}_{extra_text}.html'
    plot_html = get_plot_html(plot_filename, plot_dir=config.alignments_path)

    return render_template('response_times.html',
                           has_data = plot_html != None,
                           plot_html=plot_html,
                           satellites=satellites,
                           plot_types=plot_types,
                           PRETTY_NAMES=config.satellite_info,
                           PRETTY_COLUMN_DICT=config.feature_names,
                           selected_satellite=selected_satellite,
                           selected_plot_type=selected_plot_type,
                           cor_column_options=cor_column_options,
                           corthr_options=corthr_options,
                           extra24htime_options=extra24htime_options,
                           selected_cor_column=selected_cor_column,
                           selected_corthr=selected_corthr,
                           selected_extra24htime=selected_extra24htime)

# ——————— Correlation-Based Alignments ———————
@app.route('/data/alignments', methods=['GET', 'POST'])
@login_required
def alignments():
    satellites, cor_column_options, event_class_options, event_id_options, extra24htime_options, cor_thr_options, event_id_map = get_available_alignment_plots()

    if request.method == 'GET':
        selected_satellite = satellites[0]
        selected_cor_column = cor_column_options[0]
        selected_event_class = event_class_options[0]
        selected_event = event_id_options[0]
        selected_cor_thr = cor_thr_options[0]
        selected_extra24htime = extra24htime_options[0]
    else:
        selected_satellite = request.form.get('satellite')
        selected_cor_column = request.form.get('cor_column')
        selected_event_class = request.form.get('event_class')
        selected_event = request.form.get('event')
        selected_cor_thr = request.form.get('cor_thr')
        selected_extra24htime = request.form.get('extra24htime')

    print(selected_cor_thr)

    extra_text = config.event_filtering_map.get(selected_extra24htime, '')

    plot_url = url_for('alignments_png',
                       cor_column=selected_cor_column,
                       event_class=selected_event_class,
                       event=selected_event,
                       satellite=selected_satellite,
                       cor_thr=selected_cor_thr,
                       extra_text=extra_text)

    return render_template('alignments.html',
                           event_id_map=event_id_map,
                           plot_url=plot_url,
                           satellites=satellites,
                           PRETTY_NAMES=config.satellite_info,
                           PRETTY_COLUMN_DICT=config.feature_names,
                           selected_satellite=selected_satellite,
                           cor_column_options=cor_column_options,
                           cor_thr_options=cor_thr_options,
                           selected_cor_thr=selected_cor_thr,
                           event_class_options=event_class_options,
                           event_id_options=event_id_options,
                           extra24htime_options=extra24htime_options,
                           selected_cor_column=selected_cor_column,
                           selected_event_class=selected_event_class,
                           selected_event=selected_event,
                           selected_extra24htime=selected_extra24htime)

# ——————— Serve alignment correlation PNGs ———————
@app.route('/data/alignments/png')
@login_required
def alignments_png():
    cor_column = request.args.get('cor_column')
    event_class = request.args.get('event_class')
    event = request.args.get('event')
    satellite = request.args.get('satellite')
    cor_thr = request.args.get('cor_thr')
    extra_text = request.args.get('extra_text', '')

    plot_filename = f'correlation_{cor_column}_event_{event_class}_{event}_sat_{satellite}_bzthr_0_cor_{cor_thr}{extra_text}.png'
    plot_path = os.path.join(config.alignments_cor_path, plot_filename)

    if not os.path.exists(plot_path):
        abort(404)

    return send_file(plot_path, mimetype='image/png')

# ——————— Space Weather Events ———————
@app.route('/data/space_weather_events', methods=['GET', 'POST'])
@login_required
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
@login_required
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
@login_required
def spatial_analysis():
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
    print(f"Starting TAVERN app on {app.config['HOST']}:{app.config['PORT']} with debug={app.debug}")
    app.run(host=app.config['HOST'], port=app.config['PORT'], debug=app.debug)
