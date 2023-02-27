from datetime import datetime

# Return the current timetamp.
def timestamp():
    return datetime.timestamp(datetime.now())

# Return a formatted time string e.g. 2023-jan-08 13:55
def sdate(tstamp=None, fmt='%Y-%m-%d %H:%M:%S'):
    if tstamp is None:
        dt = datetime.now()
    else:
        dt = datetime.fromtimestamp(tstamp)
    return dt.strftime(fmt)

# Return a formatted time durations: HH:MM:SS
def sduration(dur, near=False):
    if dur <= 0.0: return '0:00'
    rem = dur
    nh = int(rem/3600)
    rem -= 3600*nh
    nm = int(rem/60)
    rem -= 60*nm
    doff = 0.499999 if near else 0.0
    ns = int(rem+doff)
    sd = ''
    if nh > 0:
        sd += f"{nh}:"
        if nm < 10:
            sd+= '0'
    sd += f"{nm}:"
    if ns < 10: sd += '0'
    sd += f"{ns}"
    return sd
