from datetime import datetime

# Return the current timetamp.
def timestamp():
    return datetime.timestamp(datetime.now())

# Return a formatted time string e.g. 2023-jan-08 13:55
def sdate(tstamp=None, fmt='%Y-%m-%d %H:%M'):
    if tstamp is None:
        dt = datetime.now()
    else:
        dt = datetime.fromtimestamp(tstamp)
    return dt.strftime(fmt)
