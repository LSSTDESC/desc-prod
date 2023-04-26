# start_job.py

import sys
import os
import descprod
import pdb

def start_job(jid, dnam, url):
    '''
    Attempts to start descprod job with ID jid.
    If successful, returns the jsam map for th job.
    Otherwise returns a string with an error message.
    '''
    descname = descprod.get_login() if dnam is None else dnam
    resp = descprod.get_job(jid, descname, url)
    if isinstance(resp, str):
        return resp
    job = descprod.JobData(jid, descname, usedb=False)
    try:
        jmap = resp["job"]
    except:
        return f"Unable to find job in {resp} (type {type(resp)})"
    emsg = job.jmap_update(jmap)
    if len(emsg):
        return emsg
    cmsg = job.ready_to_run()
    if len(cmsg):
        return f"Job cannot be started. {cmsg}"
    rundir = f"{os.getcwd()}/{job.idname()}"
    print(f"Starting job {jid} for {descname} in {rundir}")
    rs = job.run(rundir=rundir, server=url)
    if rs:
        return f"Job start failed with error {rs}: {job.errmsgs[-1]}"
    return job

def start_job_main():
    args = sys.argv[1:]
    do_help = False
    debug = False
    wait = False
    myname = os.path.basename(sys.argv[0])
    while len(args) and args[0][0] == '-':
        flag = args[0]
        args = args[1:]
        if flag == '-h': do_help = True
        elif flag == '-d': debug = True
        elif flag == '-w': wait = True
        else:
            print(f"{myname}: Invalid command line flag: {flag}")
            return 1
    if len(args):
        sjid = args[0]
        uid = args[1] if len(args) > 1 else None
        url = args[2] if len(args) > 2 else None
    else:
       do_help = True
    if do_help:
        print(f"Usage: {myname} [-h] [-d] JOBID USER URL")
        print(f"     -h - Show this message and exit.")
        print(f"     -d - Run with debugger.")
        print(f"     -w - Wait for job to complete before exiting.")
        print(f"  JOBID - Job ID.")
        print(f"   USER - DESC username.")
        print(f"    URL - server URL [{descprod.server_url()}]")
        return 0
    try:
        jid = int(sjid)
    except:
        print(f"{myname}: Invalid job ID: {sjid}")
        return 1
    if debug:
        print(f"{myname}: Running with debugger.")
        pdb.set_trace()
    resp = start_job(jid, uid, url)
    if isinstance(resp, str):
        print(f"{myname}: ERROR: {resp}")
        return 1
    job = resp
    jdat = job.jmap()
    print(f"{myname}: Started job {jid}:")
    for key in descprod.JobData.data_names:
        if key in jdat:
            val = jdat[key]
            if key[-5:] == '_time':
                val = f"{descprod.sdate(val)} UTC"
            print(f"{key:>16}: {val}")
    if wait:
        print(f"{myname}: Waiting for process {job.popen().pid} to complete.")
        timeout = None
        job.popen().wait(timeout)
        rc = job.popen().returncode
        print(f"{myname}: Process return code: {rc}")
    return 0
