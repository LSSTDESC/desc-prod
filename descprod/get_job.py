# get_job.py

import sys
import os
import pwd
import descprod

def server_url():
    return 'https://www.descprod.org'

def get_job(jid, dnam=None, a_url=None):
    import requests
    descname = descprod.get_login() if dnam is None else dnam
    surl = server_url() if a_url is None else a_url
    url = f"{surl}/get_job"
    try:
        r = requests.post(url, json={'id':jid, 'descname':descname})
    except Exception as e:
        return f"Unable to reach server at {surl}: {str(e)}"
    sc = r.status_code
    if sc != 200:
        return f"Server returned HTML error {sc}"
    rmap = r.json()
    rc = rmap['status']
    if rc:
        return rmap['message']
    return rmap

def get_job_main():
    sjid = sys.argv[1] if len(sys.argv) > 1 else '-h'
    dnam = sys.argv[2] if len(sys.argv) > 2 else None
    surl = sys.argv[3] if len(sys.argv) > 3 else None
    myname = os.path.basename(sys.argv[0])
    if sjid == '-h':
        print(f"Usage: {myname} JOBID [USERNAME] [URL]")
        print(f"Displays the data for a job")
        print(f"  JOBID - Job ID.")
        print(f"  USERNAME - DESC user name. Default is the local username.")
        print(f"       URL - Sever URL. Default is {server_url()}.")
        return 0
    try:
        jid = int(sjid)
    except:
        print(f"{myname}: Invalid job ID: {sjid}")
        return 1
    resp = get_job(jid, dnam, surl)
    if isinstance(resp, str):
        print(f"{myname}: ERROR: {resp}")
        return 1
    rs = resp['status']
    if rs:
        print(f"{myname}: ERROR: {resp['message']}")
        return 2
    jdat = resp['job']
    for key in descprod.JobData.data_names:
        if key in jdat:
            val = jdat[key]
            if key[-5:] == '_time':
                val = f"{descprod.sdate(val)} UTC"
            print(f"{key:>16}: {val}")
    return 0
