"""
Configuration module for the TAVERN application.
Handles loading and providing access to configuration settings.
"""
import json
import os

class Config:
    """Configuration class for the TAVERN application."""
    
    def __init__(self):
        """Initialize the configuration by loading settings from JSON files."""
        print(os.getcwd())
        self.general_settings = self._load_config('./configs/config_local.json' if '/Users/vanessa/PhD/' in os.getcwd() else './configs/config.json')
        self.display_settings = self._load_config('./configs/display_config.json')
        # print current path
        # Extract commonly used settings for easier access
        self.flag_files = self.general_settings['flag_files']
        self.analysis_folder = self.general_settings['analysis_folder']
        self.plots_path = self.general_settings['paths']['static_plots']
        self.alignments_path = self.general_settings['paths']['alignments']
        self.data_path = self.general_settings['paths']['data']
        self.orbit_plots_path = self.general_settings['paths'].get('orbit_plots', None)
        self.file_label = self.general_settings['file_label']
        self.flags_path = self.general_settings['paths']['flags']
        self.debug = self.general_settings.get('debug', False)
        self.port = self.general_settings.get('port', 8000)
        self.host = self.general_settings.get('host', '')
        self.theme = self.general_settings.get('theme', 'dark')
        self.feature_names = self.display_settings['feature_names']
        self.event_catalog_feature_names = self.display_settings['event_catalog_feature_names']
        self.geomagnetic_storm_levels = self.display_settings['storm_levels']
        self.additional_features = self.display_settings['features_to_display']
        self.satellite_info = self.display_settings['satellite_info']
        
        # Define event filtering map
        self.event_filtering_map = {
            'included': '_with_24h_extratime',
            'not-included': '',
            'before and after': '_with_24h_extratime_bothways'
        }
    
    def _load_config(self, config_path):
        """
        Load configuration from a JSON file.
        
        Args:
            config_path (str): Path to the configuration file
            
        Returns:
            dict: Configuration settings
        """
        try:
            with open(config_path, 'r') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError) as e:
            print(f"Error loading configuration from {config_path}: {e}")
            return {}

# singleton instance
config = Config()