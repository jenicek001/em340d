#!/usr/bin/env python
"""
Environment variable substitution for YAML configuration files
Supports Docker-style ${VARIABLE:default} syntax
"""
import os
import re
import yaml

def substitute_env_vars(text):
    """
    Substitute environment variables in text using ${VAR:default} syntax.
    
    Examples:
        ${MQTT_BROKER} - Required variable, will raise error if not set
        ${MQTT_BROKER:localhost} - Variable with default value
        ${MQTT_PORT:1883} - Numeric default
    """
    def replace_var(match):
        var_expr = match.group(1)
        if ':' in var_expr:
            var_name, default_value = var_expr.split(':', 1)
            return os.getenv(var_name, default_value)
        else:
            var_name = var_expr
            value = os.getenv(var_name)
            if value is None:
                raise ValueError(f"Required environment variable '{var_name}' is not set")
            return value
    
    # Match ${VAR} or ${VAR:default}
    pattern = r'\$\{([^}]+)\}'
    return re.sub(pattern, replace_var, text)

def load_yaml_with_env(config_file):
    """
    Load YAML configuration file with environment variable substitution.
    """
    try:
        with open(config_file, 'r') as f:
            content = f.read()
        
        # Substitute environment variables
        content = substitute_env_vars(content)
        
        # Parse YAML
        config = yaml.load(content, Loader=yaml.FullLoader)
        return config
        
    except Exception as e:
        raise Exception(f'Error loading YAML file {config_file}: {e}')

# Backward compatibility function
def load_config(config_file):
    """Load configuration with environment variable support"""
    return load_yaml_with_env(config_file)
