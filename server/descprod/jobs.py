import os
import shutil
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
      _popen - Popen object. E.g. se poll to see if job has completed.
      _return_status - Return status.
      pid - process ID
    """
    dbg = 1
    runbas = '/home/descprod/data/rundirs'   # Active runs are here
    delbas = '/home/descprod/data/deleted'   # Deleted runs are here (but may be removed any time)
    arcbas = '/home/descprod/data/archive'   # Runs trnsferred to and from archive are here
    jobs = {}  # All known jobs indexed by id
    ujobs = {} # Known user jobs indexed by descname and id.
    have_oldjobs = []  # List of users for which old jobs have been retrieved.

    @classmethod
    def name_from_id(cls, idx):
        if idx is None: return None
        sidx = str(idx)
        while len(sidx) < 6: sidx = '0' + sidx
        return 'job' + sidx

    @classmethod
    def id_from_name(cls, sidx):
        if len(sidx) < 9: return -1
        if sidx[0:3] != 'job': return -2
        rem = sidx[3:]
        while rem[0] == '0' and len(rem) > 1: rem = rem[1:]
        return int(rem)

    @classmethod
    def get_user_job(cls, descname, idx):
        myname = 'JobData.get_user_job'
        if descname not in cls.ujobs: return None
        if idx not in cls.ujobs[descname]: return None
        return cls.ujobs[descname][idx]

    @classmethod
    def get_jobs(cls, descname=None):
        myname = 'JobData.get_jobs'
        if descname is None: return cls.jobs
        if cls.dbg: print(f"{myname}: Fetching jobs for user {descname}.")
        if descname not in cls.ujobs:
            cls.ujobs[descname] = {}
        if descname not in cls.have_oldjobs:
            topdir = f"{cls.runbas}/{descname}"
            if cls.dbg: print(f"{myname}: Looking for old jobs in {topdir}.")
            if os.path.isdir(topdir):
                for jobnam in os.listdir(topdir):
                    jobid = cls.id_from_name(jobnam)
                    if jobid < 0:
                        if dbg: print(f"{myname}:   Skipping bad name {jobnam}.")
                        continue
                    if jobid in cls.jobs:
                        if dbg: print(f"{myname}:   Skipping bad name {jobnam}.")
                        continue
                    jdat = JobData(jobid, descname, False)
            cls.have_oldjobs.append(descname)
        return cls.ujobs[descname]

    @classmethod
    def checkdirs(cls):
        """Make sure the run directories are all present."""
        myname = 'JobData.checkdirs'
        for dnam in [cls.runbas, cls.delbas, cls.arcbas]:
            if not os.path.isdir(dnam):
                print(f"{myname}: INFO: Creating directory {dnam}")
                os.mkdir(dnam)

    def do_error(self, myname, msg, rstat=None):
         errmsg = f"{myname}: ERROR: {msg}"
         self.errmsgs += [errmsg]
         if JobData.dbg: print(errmsg)
         return rstat

    def idname(self):
        """Return the name of the job: jobXXXXXX."""
        return self.name_from_id(self.id)

    def run_dir(self):
        """Return the run directory for this job."""
        return f"{self.runbas}/{self.descname}/{self.idname()}"

    def archive_file(self):
        """Return the archive file for this job."""
        fnam = f"{self.arcbas}/{self.descname}/{self.idname()}.tz"
        dnam = os.path.dirname(fnam)
        if not os.path.exists(dnam): os.mkdir(dnam)
        return fnam

    def delete_file(self):
        """Return the archive file after deletion for this job."""
        return f"{self.delbas}/{self.idname()}.tz"

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
        self._popen = None
        self.pid = None
        self._return_status = None
        myname = 'JobData.ctor'
        dbg = JobData.dbg
        self.checkdirs()
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
                jnam = f"{rundir}/config.json"
                if not os.path.exists(jnam):
                    self.do_error(myname, f"Config file not found: {jnam}")
                else:
                    try:
                        with open(jnam, 'r') as jfil:
                            jmap = json.load(jfil)
                            self.jobtype = jmap['jobtype']
                            self.config = jmap['config']
                            self.command = jmap['command']
                            if 'pid' in jmap: self.pid = jmap['pid']
                            if 'return_status' in jmap: self._return_status = jmap['return_status']
                    except json.decoder.JSONDecodeError:
                        self.do_error(myname, f"Unable to parse config file: {jnam}")
                self.rundir = rundir
        JobData.jobs[idx] = self
        if descname not in JobData.ujobs:
            JobData.ujobs[descname] = {}
        JobData.ujobs[descname][idx] = self

    def configure(self, jobtype, config, a_command=None):
        """
        Configure a job: assign a job type and a configuration string.
        Optionally a command to be passed to Popen may be provided.
        If not the command is constructed from the job type and config.
        """
        myname = 'JobData.configure'
        rstat = 0
        if self.jobtype is not None:
            rstat += self.do_error(myname, f"Job type is already set: {self.jobtype}", 1)
        if self.config is not None:
            rstat += self.do_error(myname, f"Job config is already set: {self.config}", 2)
        if self.pid is not None:
            rstat += self.do_error(myname, f"Job has already been started. Process ID: {self.pid}", 4)
        if self.get_return_status() is not None:
            rstat += self.do_error(myname, f"Job has already completed. Return status: {self.get_return_status()}", 8)
        if self.rundir is None:
            rstat += self.do_error(myname, f"Run directory is not set.", 16)
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
        self.lognam = f"{self.rundir}/{self.idname()}.log"
        self.stanam = f"{self.rundir}/current-status.txt"
        if True:   # Create README for desc-wfmon
            rout = open(f"{self.rundir}/README.txt", 'w')
            rout.write(f"{self.idname()}\n")
            rout.close()
        jmap = {}
        jmap['jobtype'] = self.jobtype
        jmap['config']  = self.config
        jmap['rundir']  = self.rundir
        jmap['command'] = self.command
        jnam = f"{self.rundir}/config.json"
        with open(jnam, 'w') as jfil:
            json.dump(jmap, jfil)
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
        self._popen = subprocess.Popen(self.command, cwd=self.rundir, stdout=logfil, stderr=logfil)
        self.pid = self._popen.pid
        jnam = f"{self.rundir}/config.json"
        with open(jnam, 'r') as jfil:
            jmap = json.load(jfil)
        jmap.update({'pid':self.pid})
        with open(jnam, 'w') as jfil:
            json.dump(jmap, jfil)
        return 0
 
    def get_return_status(self):
        if self._return_status is not None: return self._return_status
        if self._popen is None: return None
        self._return_status = self._popen.poll()
        if self._return_status is not None:
            jnam = f"{self.rundir}/config.json"
            with open(jnam, 'r') as jfil:
                jmap = json.load(jfil)
            jmap.update({'return_status':self._return_status})
            with open(jnam, 'w') as jfil:
                json.dump(jmap, jfil)
        return self._return_status

    def dropdown_content(self, baseurl):
        q = '"'
        txt = f"<a href={q}{baseurl}/archivejob?id={self.id}{q}>Archive job {self.id}</a>"
        txt += '<br>'
        txt += f"<a href={q}{baseurl}/deletejob?id={self.id}{q}>Delete job {self.id}</a>"
        return txt

    def is_active(self):
        return os.path.exists(self.run_dir())

    def is_archived(self):
        return os.path.exists(self.archive_file())

    def is_deletedd(self):
        if os.path.exists(self.run_dir()): return False
        if os.path.exists(self.archive_file()): return False
        return True

    def deactivate(self):
        """Deactivate this job: remove from jobs and ujobs."""
        myname = 'JobData.deactivate'
        if self.id in JobData.jobs:
            del JobData.jobs[self.id]
        if self.descname in JobData.ujobs:
            if self.id in JobData.ujobs[self.descname]:
                del JobData.ujobs[self.descname][self.id]

    def archive(self, force=False, if_present=False):
        """
        Archive this job.
        Returns the archive file name if successful.
        Otherwise returns None.
          force - Remake the arcive if it already exists
          if_present - No error if rundir is missing
        """
        myname = 'JobData.archive'
        rundir = self.run_dir()
        runbas = os.path.dirname(rundir)
        arcfil = self.archive_file()
        jnam = self.idname()
        if os.path.exists(arcfil):
            if not force: return arcfil
            if os.path.exists(rundir): os.rm(arcfil)
        if not os.path.exists(rundir):
            if if_present: return None
            msg = f"Run directory not found: {rundir}"
            self.do_error(myname, msg)
            return None
        com = f"cd {runbas} && tar zcf {arcfil} {jnam}"
        (rstat, sout) = subprocess.getstatusoutput(com)
        if rstat or not os.path.exists(arcfil):
            msg = f"Archive command failed: {com}"
            if os.path.exists(arcfil):
                os.remove(arcfil)
            self.do_error(myname, msg)
            return None
        print(f"XXX {os.path.exists(arcfil)} {os.path.exists(rundir)} {rundir}")
        if os.path.exists(arcfil) and os.path.exists(rundir):
            shutil.rmtree(rundir)
            self.deactivate()
        return arcfil

    def delete(self):
        """Delete this job."""
        myname = 'JobData.delete'
        rundir = self.run_dir()
        arcfil = self.archive()
        delfil = self.delete_file()
        if os.path.exists(rundir):
            shutil.rmtree(rundir)
            self.deactivate()
        if os.path.exists(arcfil) and not os.path.exists(delfil):
            os.rename(arcfil, delfil)
        else:
            os.remove(arcfil)
        if os.path.exists(delfil): return delfil
        del JobData.jobs[job.id]
        del JobData.ujobsjob[descname][job.id]
        return None
