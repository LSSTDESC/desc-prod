# check_job_schema.py

# Script to check the schema in the descprod job table.

import sys
import os
import descprod

def check_job_schema(a_dofix):
    res = descprod.JobData.db_table(check_schema=True)
    if res:
        print("Job schema are OK.")
        return 0
    dofix = a_dofix
    if dofix is None:
        line = input("Problem found with job schema. Do you want to fix?> ")
        dofix = line[0] in ['y', 'Y']
    if not dofix:
        print("Not attempting to fix bad schema.")
        return 2
    print("Attempting to fix schema.")
    res = descprod.JobData.db_table(add_schema=True)
    res = descprod.JobData.db_table(check_schema=True)
    if res:
        print("Job schema are now OK.")
        return 0
    print("Job schema still have problems.")
    return 3

def check_job_schema_main():
    dohelp = False
    dofix = None
    rstat = 0
    myname = os.path.basename(sys.argv[0])
    for arg in sys.argv[1:]:
        if arg == '-h': dohelp = True
        elif arg == '-y': dofix = True
        elif arg == '-n': dofix = False
        else:
            print(f"{myname}: Invalid argument: {arg}")
            dohelp = True
            rstat = 1
    if dohelp:
        print(f"Usage: {myname} [-h|-f|-n]")
        print(f"Checks the schema in the job table.")
        print(f"  -h: Show help (this message")
        print(f"  -f: Try to fix table if any schema are missing.")
        print(f"  -n: Do not try to fix table if schema are missing.")
        return rstat
    return check_job_schema(dofix)
