# get_job.py

import sys
import os
import descprod

def start_job(jid, dnam):
    '''
    Attempts to start descprod job with ID jid.
    If successful, returns the jsam map for th job.
    Otherwise returns a string with an error message.
    '''
    descname = os.getlogin() if dnam is None else dnam
    jmap = descprod.get_job(jid, descname)
    if isinstance(jmap, str):
        return jmap
    job = descprod.JobData(jid, descname, usedb=False)
    emsg = job.jmap_update(jmap)
    if len(emsg):
        return emsg
    return job.jmap()

def start_job_main():
    sjid = sys.argv[1] if len(sys.argv) > 1 else '-h'
    myname = os.path.basename(sys.argv[0])
    dnam = sys.argv[2] if len(sys.argv) > 2 else None
    if sjid == '-h':
        print(f"Usage: {myname} JOBID")
        return 0
    try:
        jid = int(sjid)
    except:
        print(f"{myname}: Invalid job ID: {sjid}")
        return 1
    resp = start_job(jid, dnam)
    if isinstance(resp, str):
        print(f"{myname}: ERROR: {resp}")
        return 1
    rs = resp['status']
    if rs:
        print(f"{myname}: ERROR: {resp['message']}")
        return 2
    jdat = resp['job']
    print(f"{myname}: Started job {jid}:")
    for key in descprod.JobData.data_names:
        if key in jdat:
            val = jdat[key]
            if key[-5:] == '_time':
                val = f"{descprod.sdate(val)} UTC"
            print(f"{key:>16}: {val}")
    return 0
