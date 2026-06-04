import json
import os
from flask import session, has_request_context

class Config:
    """Configuration class for the TAVERN application."""
    
    def __init__(self):
        """Initialize the configuration by loading settings from JSON files."""
        self.general_settings = self._load_config('./configs/config.json')
        self.display_settings = self._load_config('./configs/display_config.json')
        self.flag_files = self.general_settings['flag_files']
        self.plots_path = self.general_settings['paths']['static_plots']
        self.alignments_path = self.general_settings['paths']['alignments']
        self.data_path = self.general_settings['paths']['data']
        self.orbit_plots_path = self.general_settings['paths'].get('orbit_plots', None)
        self.spatial_decay_plots_path = self.general_settings['paths'].get('spatial_decay_plots', None)
        self.file_label = self.general_settings['file_label']
        self.flags_path = self.general_settings['paths']['flags']
        self.feature_names = self.display_settings['feature_names']
        self.event_catalog_feature_names = self.display_settings['event_catalog_feature_names']
        self.geomagnetic_storm_levels = self.display_settings['storm_levels']
        self.additional_features = self.display_settings['features_to_display']
        self.satellite_info = self.display_settings['satellite_info']
        self.decay_feature = self.display_settings['default_decay_feature']
        self.decay_feature_options = self.display_settings['decay_feature_options']
        
        self.event_filtering_map = {
            'included': '_with_24h_extratime',
            'not-included': '',
            'before and after': '_with_24h_extratime_bothways'
        }

    def get_active_decay_feature(self):
        """Get decay feature, preferring session over default.
        Returns:
            str: The active decay feature to use
        """
        if has_request_context():
            return session.get('decay_feature', self.decay_feature)
        return self.decay_feature

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