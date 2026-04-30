"""
YAML configuration loader for static sensor definitions.
Runtime configuration is read from environment variables.
"""
import yaml


def load_sensors(sensors_file: str) -> list:
    """
    Load sensor definitions from a YAML file.

    Args:
        sensors_file: Path to the sensors YAML file.

    Returns:
        List of sensor definition dicts.

    Raises:
        Exception: If the file cannot be read or parsed.
    """
    try:
        with open(sensors_file, 'r') as f:
            config = yaml.load(f, Loader=yaml.FullLoader)
        sensors = config.get('sensors', [])
        if not isinstance(sensors, list):
            raise ValueError("'sensors' key must be a list")
        return sensors
    except Exception as e:
        raise Exception(f'Error loading sensors file {sensors_file}: {e}')
