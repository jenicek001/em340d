import logging
import logging.handlers
import os
import sys

_LOG_LEVEL_MAP = {
    'DEBUG': logging.DEBUG,
    'INFO': logging.INFO,
    'WARNING': logging.WARNING,
    'ERROR': logging.ERROR,
    'CRITICAL': logging.CRITICAL,
}

log_level_str = os.getenv('LOG_LEVEL', 'INFO').upper()
log_level = _LOG_LEVEL_MAP.get(log_level_str, logging.INFO)

log_to_console = os.getenv('LOG_TO_CONSOLE', 'true').lower() in ('1', 'true', 'yes')
log_to_file = os.getenv('LOG_TO_FILE', 'true').lower() in ('1', 'true', 'yes')
log_file = os.getenv('LOG_FILE', '/app/logs/em340d.log')
log_rotate = os.getenv('LOG_ROTATE', 'true').lower() in ('1', 'true', 'yes')
try:
    log_rotate_size = int(os.getenv('LOG_ROTATE_SIZE', '1048576'))
except ValueError:
    print('Warning: invalid LOG_ROTATE_SIZE, using default 1048576', file=sys.stderr)
    log_rotate_size = 1048576

try:
    log_rotate_count = int(os.getenv('LOG_ROTATE_COUNT', '5'))
except ValueError:
    print('Warning: invalid LOG_ROTATE_COUNT, using default 5', file=sys.stderr)
    log_rotate_count = 5

log = logging.getLogger()
log.setLevel(log_level)

if log_to_file:
    try:
        log_dir = os.path.dirname(log_file)
        if log_dir:
            os.makedirs(log_dir, exist_ok=True)
        if log_rotate:
            file_handler = logging.handlers.RotatingFileHandler(
                log_file, maxBytes=log_rotate_size, backupCount=log_rotate_count
            )
        else:
            file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s: %(message)s'))
        log.addHandler(file_handler)
    except OSError as e:
        print(f'Warning: could not open log file {log_file}: {e}', file=sys.stderr)

if log_to_console:
    stream_handler = logging.StreamHandler(stream=sys.stdout)
    stream_handler.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] %(message)s'))
    log.addHandler(stream_handler)
