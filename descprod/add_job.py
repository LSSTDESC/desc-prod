# add_job.py

import sys
import os
import time
import descprod
import requests
import pdb

def add_job(jobtype, config, howfig, parent, *, descname=None, surl=None, ntry=1):
    '''
    Attempts to add a job with the provided characteristics.
    If successful, returns the jsam map for th job.
    Otherwise returns a string with an error message.
    '''
    uid = descprod.get_login() if descname is None else descname
    jnam = {'jobtype':jobtype, 'config':config}
    pjmap = {}
    if jobtype is None: return f"Invalid jobtype."
    if config is None: return f"Invalid config."
    if howfig is None: return f"Invalid howfig."
    if parent is None: return f"Invalid parent."
    if uid is None: return f"Invalid descname."
    pjmap['jobtype'] = jobtype
    pjmap['config'] = config
    pjmap['howfig'] = howfig
    pjmap['parent'] = parent
    pjmap['descname'] = uid
    if surl is None:
        url = descprod.server_url()
    else:
        url = surl
    url += '/add_child_job'
    wait_time = 10
    count = 0
    jmap = {}
    while count < ntry:
        try:
            r = requests.post(url, timeout=100, json=pjmap)
            sc = r.status_code
            if sc != 200:
                print(f"Add of job {jobtype} {config} {howfig} at {surl} failed with HTML code {sc}")
            else:
                rmap = r.json()
                if 'job' in rmap: jmap = rmap['job']
                urc = rmap['status']
                if 'message' in rmap:
                    umsg = rmap['message']
                elif jmap is None:
                    umsg = f"Job not found in server reponse."
                else:
                    umsg = f"Added job {jmap['descname']}/{jmap['id']}"
                if urc:
                    print(f"Add of job {jobtype} {config} {howfig} at {surl} failed with status {urc}: {umsg}")
                    sc = 1000 + urc
                elif jmap is None:
                    print(umsg)
                else:
                    print(f"Success: {umsg}")
                    break
        except Exception as e:
            print(f"Unable to reach server at {url}: {str(e)}")
            sc = 999
        sys.stdout.flush()
        time.sleep(wait_time)
        count += 1
    if jmap is None:
        return 'Add job failed.'
    return jmap

def add_job_main():
    args = sys.argv[1:]
    do_help = False
    debug = False
    myname = os.path.basename(sys.argv[0])
    uid = None
    parent = None
    surl = None
    config = ""
    howfig = ""
    ntry = 1
    jfilnam = ''
    while len(args) and args[0][0] == '-':
        flag = args[0]
        args = args[1:]
        if flag == '-h': do_help = True
        elif flag == '-u':
            uid = args[0]
            args = args[1:]
        elif flag == '-p':
            parent = args[0]
            args = args[1:]
        elif flag == '-s':
            surl = args[0]
            args = args[1:]
        elif flag == '-n':
            ntry = int(args[0])
            args = args[1:]
        elif flag == '-o':
            jfilnam = args[0]
            args = args[1:]
        else:
            print(f"{myname}: Invalid command line flag: {flag}")
            return 1
    if do_help:
        print(f"Usage: {myname} [-h] [-d] [-s SURL] [-u USER] [-p PARENT] JOBTYPE [CONFIG [HOWFIG]]")
        print(f"     -h - Show this message and exit.")
        print(f"     -u - Username")
        print(f"     -s - Server URL.")
        print(f"     -p - Parent job ID")
        print(f"     -n - Number of tries.")
        print(f"     -o - Nam of output json file.")
        print(f"  JOBTYPE - Job type.")
        print(f"  CONFIG  - Job configuration.")
        print(f"  CONFIG  - Job howfig.")
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
    if len(args):
        howfig = args[0]
        args = args[1:]
    if parent is None:
        print(f"Parent must be provided.")
        return 1
    if debug:
        print(f"{myname}: Running with debugger.")
        pdb.set_trace()
    resp = add_job(jobtype, config, howfig, parent, descname=uid, surl=surl, ntry=ntry)
    if isinstance(resp, str):
        print(f"{myname}: ERROR: {resp}")
        return 1
    jmap = resp
    #print(f"{myname}: Started job {jmap.id()}:")
    dofil = bool(len(jfilnam))
    if dofil:
        fout = open(jfilnam, 'w')
        fout.write("{\n")
    sep = ''
    for key in descprod.JobData.data_names:
        if key in jmap:
            val = jmap[key]
            if key[-5:] == '_time':
                val = f"{descprod.sdate(val)} UTC"
            print(f"{key:>16}: {val}")
            if dofil:
                if len(sep):
                    fout.write(sep)
                else:
                    sep = ",\n"    
                qkey=f"\"{key}\""
                fout.write(f"{qkey:>18}: \"{val}\"")
    if dofil:
        fout.write("\n}\n")
        fout.close()
    return 0
