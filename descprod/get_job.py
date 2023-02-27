# get_job.py

import sys
import os

def get_job(idx):
     import requests
     url = 'https://www.descprod.org/get_job'
     r = requests.post(url, json={'id':idx, 'descname':'dladams'})
     sc = r.status_code
     if sc == 200:
         return r.json()
     return f"Web service returned status {sc}"

def get_job_main():
    sarg = sys.argv[1] if len(sys.argv) > 1 else '-h'
    myname = os.path.basename(sys.argv[0])
    if sarg == '-h':
        print(f"Usage: {myname} JOBID")
        return 0
    try:
        jid = int(sarg)
    except:
        print(f"{myname}: Invalid job ID: {sarg}")
        return 1
    resp = get_job(jid)
    if isinstance(resp, str):
        print(f"{myname}: ERROR: {resp}")
        return 1
    print(resp)
    return 0
