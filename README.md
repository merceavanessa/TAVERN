# TAVERN: Tracking Atmospheric Variability from solar Eruptions and Radiation using a Network of Satellites

This repository contains the TAVERN project, a Flask-based web application designed for tracking, visualizing, and analyzing atmospheric variability caused by solar events. To analyze impacts, the project uses low-Earth orbit satellite orbit data in conjunction with different space weather datasets and catalogs. It is a web application with different data analysis tools for both static and dynamic data. The purpose of this repository is to provide transparency into the data and methods used for this analysis.

The app will also be soon available at [todo: add link to the hosted app]. 

## Project Structure

The project is organized as a standard Flask application:

-   `app.py`: The main entry point and routing for the Flask application.
-   `tavern/`: The source files containing the application's background logic (mostly minor data processing and plotly visualizations).
-   `templates/`: HTML templates for rendering the web pages.
-   `static/`: Static assets (css stylesheets, JavaScript files etc.).
-   `data/`: Directory for storing application data (previously-generated visualizations).
-   `notebooks/`: Jupyter notebooks used for generating the static visualizations or for data analysis.
-   `configs/`: Configuration files for the application.
-   `requirements.txt`: A list of Python dependencies required for the project.
-   `LICENSE`: The project license.