# get_job.py

import sys
import os
import descprod

def get_job(jid, dnam=None):
     import requests
     url = 'https://www.descprod.org/get_job'
     descname = os.getlogin() if dnam is None else dnam
     r = requests.post(url, json={'id':jid, 'descname':descname})
     sc = r.status_code
     if sc == 200:
         return r.json()
     return f"Web service returned status {sc}"

def get_job_main():
    sjid = sys.argv[1] if len(sys.argv) > 1 else '-h'
    dnam = sys.argv[2] if len(sys.argv) > 2 else None
    myname = os.path.basename(sys.argv[0])
    if sjid == '-h':
        print(f"Usage: {myname} JOBID [USERNAME]")
        print(f"Returns the job data for ID JID and user USERNAME")
        return 0
    try:
        jid = int(sjid)
    except:
        print(f"{myname}: Invalid job ID: {sjid}")
        return 1
    resp = get_job(jid, dnam)
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
