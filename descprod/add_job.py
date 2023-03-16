# add_job.py

import sys
import os
import descprod
import pdb

def add_job(jobtype, config, *, descname=None, parent=None, surl=None):
    '''
    Attempts to add a job with the provided characteristics.
    If successful, returns the jsam map for th job.
    Otherwise returns a string with an error message.
    '''
    uid = descprod.get_login() if descname is None else descnam
    jnam = {'jobtype':jobtype, 'config':config}
    jmap = {}
    if parent is not None:
        jmap['parent'] = parent
    if uid is not None:
        jmap['descname'] = uid
    if rl is None:
        url = desc.server_url()
    else:
        url = surl
    url += '/add_job'
    wait_time = 10
    count = 0
    while count < 10:
        try:
            r = requests.post(url, timeout=10, json={'id':jobid, 'descname':user, 'job':info})
            sc = r.status_code
            if sc != 200:
                print(f"Update of job {user}/{jobid} at {surl} failed with HTML code {sc}")
            else:
                rmap = r.json()
                urc = rmap['status']
                if urc:
                    print(f"Update of job {user}/{jobid} at {surl} failed: {rmap['message']}")
                    sc = 1001
                else:
                    print(f"Updated job {jobid} at {surl}")
        except Exception as e:
            print(f"Unable to reach server at {surl}: {str(e)}")
            sc = 999
        sys.stdout.flush()
        time.sleep(wait_time)
    rmap = r.json()
    rc = rmap['status']
    if rc:
        if rc: return f"Unable to add job: Error code is {rc}"
    return r.json()['job']

def add_job_main():
    args = sys.argv[1:]
    do_help = False
    debug = False
    myname = os.path.basename(sys.argv[0])
    uid = None
    parent = None
    surl = None
    config = ""
    while len(args) and args[0][0] == '-':
        flag = args[0]
        args = args[1:]
        if flag == '-h': do_help = True
        elif flag == '-u':
            uid = args[0]
            args = args[1:]
        elif flag == '-p':
            par = args[0]
            args = args[1:]
        elif flag == '-s':
            surl = args[0]
            args = args[1:]
        else:
            print(f"{myname}: Invalid command line flag: {flag}")
            return 1
    if do_help:
        print(f"Usage: {myname} [-h] [-d] [-s SURL] [-u USER] [-p PARENT] JOBTYPE [CONFIG]")
        print(f"     -h - Show this message and exit.")
        print(f"     -u - Username")
        print(f"     -s - Server URL.")
        print(f"     -p - Parent job ID")
        print(f"  JOBTYPE - Job type.")
        print(f"  CONFIG  - Job configuration..")
        return 0
    if len(args):
        jobtype = args[0]
        args = args[1:]
    else:
        print(f"Job type must be provided.")
        return 1
    if len(args):
        config = args[0]
        args = args[1:]
    if debug:
        print(f"{myname}: Running with debugger.")
        pdb.set_trace()
    resp = add_job(jobtype, config, descname=uid, parent=parent, surl=surl)
    if isinstance(resp, str):
        print(f"{myname}: ERROR: {resp}")
        return 1
    jdat = resp
    print(f"{myname}: Started job {jid}:")
    for key in descprod.JobData.data_names:
        if key in jdat:
            val = jdat[key]
            if key[-5:] == '_time':
                val = f"{descprod.sdate(val)} UTC"
            print(f"{key:>16}: {val}")
    return 0