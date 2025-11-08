import datetime
import pytz
import tzlocal

def get_timezone_aware_local_time():
    """Gets the timezone aware local time."""
    now = datetime.datetime.now()
    timezone = tzlocal.get_localzone()
    local_time = pytz.timezone(str(timezone)).localize(now, is_dst=False)
    return local_time

if __name__ == "__main__":
    local_time = get_timezone_aware_local_time()
    print(local_time)
