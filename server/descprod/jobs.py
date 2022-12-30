import os
import json
import subprocess

class JobData:
    """
    Holds the data describing a job.
      descname - DESC user name
      id - Job integer ID
      rundir - Run directory
      errmsgs - Error messages
      jobtype - Job type: parsltest, ...
      config - config string for the job
      command - Array holding the job command line for Popen.
      lognam - Name of the job log file.
      stanam - Name of the job status file (last line is status)
      popen - Popen object. E.g. se poll to see if job has completed.
      return_code - Set when job finishes. 0 for success.
    """
    dbg = 1
    runbas = '/home/descprod/data/rundirs'
    jobs = {}  # Known jobs indexed by id
    ujobs = {} # Known jobs indexed by descname and id.

    @classmethod
    def name_from_id(cls, idx):
        if idx is None: return None
        sidx = str(idx)
        while len(sidx) < 6: sidx = '0' + sidx
        return 'job' + sidx

    @classmethod
    def id_from_name(cls, sidx):
        rem = sidx[3:]
        while rem[0] == '0' and len(rem) > 1: rem = rem[1:]
        return int(rem)

    @classmethod
    def get_jobs(cls, descname=None):
        if descname is None: return cls.jobs
        if descname not in cls.ujobs:
            return []
        return cls.ujobs[descname]

    def do_error(self, myname, msg, rstat=None):
         errmsg = f"{myname}: ERROR: {msg}"
         self.errmsgs += [errmsg]
         if JobData.dbg: print(errmsg)
         return rstat

    def idname(self):
        return self.name_from_id(self.id)

    def __init__(self, idx, descname, create):
        """
        Create or locate job idx for user descname.
        If create is True, the directory is created.
        """
        self.id = idx
        self.descname = descname
        self.rundir = None
        self.errmsgs = []
        self.jobtype = None
        self.config = None
        self.command = None
        self.lognam = None
        self.stanam = None
        self.return_status = None
        myname = 'JobData.ctor'
        dbg = JobData.dbg
        sidx = JobData.name_from_id(self.id)
        usrdir = f"{self.runbas}/{self.descname}"
        rundir = f"{usrdir}/{sidx}"
        havedir = os.path.isdir(rundir)
        if create:
            if havedir:
                self.do_error(myname, f"Directory already exists: {rundir}'")
            else:
                if not os.path.isdir(usrdir): os.mkdir(usrdir)
                os.mkdir(rundir)
                self.rundir = rundir
        else:
            if not havedir:
                self.do_error(myname, f"Directory not found: {rundir}")
            else:
                # Add code here to populate job description
                self.rundir = rundir
        JobData.jobs[idx] = self
        if descname not in JobData.ujobs:
            JobData.ujobs[descname] = {}
        JobData.ujobs[descname][idx] = self

    def configure(self, jobtype, config, a_command=None):
        """
        Configure a job: assigne a job type and a configuration string.
        Optionally a command to be passed to Popen may be provided.
        If not the command is constructed from the job type and config.
        """
        myname = 'JobData.configure'
        rstat = 0
        if self.jobtype is not None:
            rstat += self.do_error(myname, f"Job type is already set: {self.jobtype}", 1)
        if self.config is not None:
            rstat += self.do_error(myname, f"Job config is already set: {self.config}", 2)
        if self.return_status is not None:
            rstat += self.do_error(myname, f"Job has already run. Return status: {self.return_status}", 4)
        if self.rundir is None:
            rstat += self.do_error(myname, f"Run directory is not set", 8)
        if rstat: return rstat
        self.jobtype = jobtype
        self.config = config
        command = a_command
        if command is None:
            if jobtype == 'parsltest':
               command = ['desc-wfmon-parsltest', config]
            else:
               return self.do_error(myname, f"Command not found for job type {jobtype}", 16)
        self.command = command
        self.lognam = f"{self.rundir}/job{self.idname()}.log"
        self.stanam = f"{self.rundir}/current-status.txt"
        if True:   # Create README for desc-wfmon
            rout = open(f"{self.rundir}/README.txt", 'w')
            rout.write(f"{self.idname()}\n")
            rout.close()
        dcfg = {}
        dcfg['jobtype'] = self.jobtype
        dcfg['config']  = self.config
        dcfg['rundir']  = self.rundir
        dcfg['command'] = self.command
        jnam = f"{self.rundir}/config.json"
        with open(jnam, 'w') as jfil:
            json.dump(dcfg, jfil)
        return 0

    def run(self):
        """
        Run the job, i.e. start it with Popen.
        """
        myname = 'JobData.run'
        rstat = 0
        if self.rundir is None:
            rstat += self.do_error(myname, f"Run directory is not specified.", 1)
        if self.lognam is None:
            rstat += self.do_error(myname, f"Log file is not specified.", 2)
        if self.command is None:
            rstat += self.do_error(myname, f"Command is not specified.", 4)
        if rstat: return rstat
        if JobData.dbg: print(f"{myname}: Opening {self.lognam}")
        logfil = open(self.lognam, 'w')
        self.popen = subprocess.Popen(self.command, cwd=self.rundir, stdout=logfil, stderr=logfil)
        return 0
 
