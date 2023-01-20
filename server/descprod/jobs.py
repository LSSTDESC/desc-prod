import os
import shutil
import json
import subprocess
from descprod import timestamp
from descprod import UserData

class JobData:
    """
    Holds the data describing a job.
      usr - User data constructed from DESC user name
      id - Job integer ID
      errmsgs - Error messages
      jobtype - Job type: parsltest, ...
      config - config string for the job
      command - Array holding the job command line for Popen.
      _popen - Popen object. E.g. use poll to see if job has completed.
      pid - process ID
      start_time - start timestamp
      port - parsl worker port
      port_errors - Error messages retrieving the port.
      _return_status - Return status.
      _stop_time - stop timestamp
    """
    dbg = 1
    jindent = 2
    jsep = (',', ': ')
    jobs = {}  # All known jobs indexed by id
    ujobs = {} # Known user jobs indexed by descname and id.
    have_oldjobs = []  # List of users for which old jobs have been retrieved.
    bindir = '/home/descprod/bin'

    @classmethod
    def name_from_id(cls, idx):
        """Return the job name corresponding to an ID."""
        if idx is None: return None
        sidx = str(idx)
        while len(sidx) < 6: sidx = '0' + sidx
        return 'job' + sidx

    @classmethod
    def id_from_name(cls, sidx):
        """Return the job ID corresponding to an name."""
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
        usr = UserData(descname)
        if cls.dbg: print(f"{myname}: Fetching jobs for user {descname}.")
        if descname not in cls.ujobs:
            cls.ujobs[descname] = {}
        if descname not in cls.have_oldjobs:
            topdir = f"{usr.run_dir}"
            if cls.dbg: print(f"{myname}: Looking for old jobs in {topdir}.")
            if os.path.isdir(topdir):
                for jobnam in os.listdir(topdir):
                    jobid = cls.id_from_name(jobnam)
                    if jobid < 0:
                        if cls.dbg: print(f"{myname}:   Skipping bad name {jobnam}.")
                        continue
                    if jobid in cls.jobs:
                        if dbg: print(f"{myname}:   Skipping bad name {jobnam}.")
                        continue
                    jdat = JobData(jobid, descname, False)
            cls.have_oldjobs.append(descname)
        return cls.ujobs[descname]

    def do_error(self, myname, msg, rstat=None):
         """Record an error."""
         errmsg = f"{myname}: ERROR: {msg}"
         self.errmsgs += [errmsg]
         if JobData.dbg: print(errmsg)
         return rstat

    def idname(self):
        """Return the name of the job: jobXXXXXX."""
        return self.name_from_id(self.id)

    def run_dir(self):
        """Return the run directory for this job."""
        return f"{self.usr.run_dir}/{self.idname()}"

    def log_file(self):
        """Return the log file name for this job."""
        return f"{self.run_dir()}/{self.idname()}.log"

    def wrapper_log_file(self):
        """Return the log file name for this job's wrapper."""
        return f"{self.run_dir()}/wrapper.log"

    def status_file(self):
        """Return the status file name for this job."""
        return f"{self.run_dir()}/current-status.txt"

    def job_config_file(self):
        """Return the job config file for this job."""
        return f"{self.run_dir()}/config.json"

    def wrapper_config_file(self):
        """Return the wrapper config file for this job."""
        return f"{self.run_dir()}/wrapper-status.json"

    def archive_file(self):
        """Return the archive file for this job."""
        fnam = f"{self.usr.archive_dir}/{self.idname()}.tz"
        dnam = os.path.dirname(fnam)
        if not os.path.exists(dnam): self.usr.mkdir(dnam)
        return fnam

    def delete_file(self):
        """Return the archive file after deletion for this job."""
        return f"{self.usr.delete_dir}/{self.idname()}.tz"

    def __init__(self, idx, descname, create):
        """
        Create or locate job idx for user descname.
        If create is True, the directory is created.
        """
        self.id = idx
        self.usr = UserData(descname)
        self.errmsgs = []
        self.jobtype = None
        self.config = None
        self.command = None
        self._popen = None
        self.pid = None
        self.start_time = None
        self.port = None
        self.port_errors = []
        self._return_status = None
        self._stop_time = None
        myname = 'JobData.ctor'
        dbg = JobData.dbg
        sidx = JobData.name_from_id(self.id)
        rundir = self.run_dir()
        havedir = os.path.isdir(rundir)
        if create:
            if havedir:
                self.do_error(myname, f"Directory already exists: {rundir}'")
            else:
                self.usr.mkdir(rundir)
        else:
            if not havedir:
                self.do_error(myname, f"Directory not found: {rundir}")
            else:
                jnam = self.job_config_file()
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
                            if 'start_time' in jmap: self.start_time = jmap['start_time']
                            if 'return_status' in jmap: self._return_status = jmap['return_status']
                            if 'stop_time' in jmap: self._stop_time = jmap['stop_time']
                            if 'port' in jmap: self.port = jmap['port']
                            else: self.get_port(-1)
                    except json.decoder.JSONDecodeError:
                        self.do_error(myname, f"Unable to parse config file: {jnam}")
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
        if rstat: return rstat
        self.jobtype = jobtype
        self.config = config
        command = a_command
        if command is None:
            if jobtype == 'parsltest':
               command = f"desc-wfmon-parsltest {config}"
            else:
               return self.do_error(myname, f"Command not found for job type {jobtype}", 16)
        self.command = command
        jmap = {}
        jmap['jobtype'] = self.jobtype
        jmap['config']  = self.config
        jmap['command'] = self.command
        jnam = self.job_config_file()
        with open(jnam, 'w') as jfil:
            json.dump(jmap, jfil, separators=JobData.jsep, indent=JobData.jindent)
        return 0

    def run(self):
        """
        Run the job, i.e. start it with Popen and a wrapper.
        """
        myname = 'JobData.run'
        rstat = 0
        if self.command is None:
            rstat += self.do_error(myname, f"Command is not specified.", 1)
        if not os.path.exists(self.run_dir()):
            rstat += self.do_error(myname, f"Run directory is not present.", 2)
        if rstat: return rstat
        com = ['sudo', '-u', self.usr.descname]
        shell = True
        conda = True
        saveenv = True
        if shell:
            shwcom = ""
            if conda:
                shwcom += 'source /home/descprod/conda/setup.sh; '
            if saveenv:
                shwcom += 'set >descprod-env.log; '
            shwcom += f"descprod-wrap '{self.command}' {self.run_dir()} {self.log_file()} {self.wrapper_config_file()}"
            com += ['bash', '-login', '-c', shwcom]
        else:
            com += ['descprod-wrap', self.command, self.run_dir(), self.log_file(), self.wrapper_config_file()]
        logfil = open(self.wrapper_log_file(), 'w')
        self._popen = subprocess.Popen(com, cwd=self.run_dir(), stdout=logfil, stderr=logfil)
        wmap = self.get_wrapper_info()
        return 0
 
    def get_wrapper_info(self, err=True):
        """
        Fetch the config info written by the wrapper.
        We expect something like:
          "command":       "desc-wfmon-parsltest wq-sleep-ttsk2-ntsk4-nwrk4",
          "run_directory": "/home/descprod/data/rundirs/dladams/job000081",
          "log_file":      "/home/descprod/data/rundirs/dladams/job000081/job000081.log",
          "start_time":    1672871201,
          "pid":           1362,
          "stop_time":     1672871253,
          "return_code":   0
        """
        jnam = self.wrapper_config_file()
        if not os.path.exists(jnam): return None
        with open(jnam, 'r') as jfil:
            jmap = json.load(jfil)
        # If we have the pid for the first time, record it and the start time
        # in the job data and config file.
        if self.pid is None and 'pid' in jmap:
            self.pid = jmap['pid']
            self.start_time = jmap['start_time']
            jnam = self.job_config_file()
            with open(jnam, 'r') as jfil:
                jmap = json.load(jfil)
            jmap.update({'pid':self.pid})
            jmap.update({'start_time':self.start_time})
            with open(jnam, 'w') as jfil:
                json.dump(jmap, jfil, separators=JobData.jsep, indent=JobData.jindent)
                jfil.write('\n')
        return jmap

    def get_port(self, badval=None):
        if self.port is None:
            myname = 'JobData.get_port'
            rundir = self.run_dir()
            com = f"{JobData.bindir}/descprod-get-parsl-port {rundir}"
            (rstat, sout) = subprocess.getstatusoutput(com)
            if rstat:
                self.port_errors.append(f"Unable to retrieve parsl port. {sout}")
                self.port = badval
                return badval
            sport = sout
            try:
                self.port = int(sout)
            except:
                self.port_errors(f"Invalid parsl port: {sout}")
                self.port = badval
                return badval
        return self.port

    def get_return_status(self):
        if self._return_status is not None: return self._return_status
        wmap = self.get_wrapper_info()
        # If we have the return status for the first time, record it and
        # the stop time in the the job data and config file.
        if wmap is not None and 'return_code' in wmap:
           self._return_status = wmap['return_code']
           self._stop_time = wmap['stop_time']
           print(f"Job {self.idname()} ended at {self._stop_time} with status {self._return_status}.")
           jnam = self.job_config_file()
           with open(jnam, 'r') as jfil:
               jmap = json.load(jfil)
           jmap.update({'return_status':self._return_status})
           jmap.update({'stop_time':self._stop_time})
           with open(jnam, 'w') as jfil:
               json.dump(jmap, jfil, indent=JobData.jindent)
           return self._return_status
        return None

    def get_start_time(self):
        return self.start_time

    def get_stop_time(self):
        if self._stop_time is None:
            return None
        return self._stop_time

    def duration(self):
        ts1 = self.get_start_time()
        if ts1 is None: return -999
        ts2 = self.get_stop_time()
        if ts2 is None: ts2 = timestamp()
        dur = ts2 - ts1
        #print(f"Duration: {dur} = {ts2} - {ts1}")
        return dur

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
        if self.usr.descname in JobData.ujobs:
            if self.id in JobData.ujobs[self.usr.descname]:
                del JobData.ujobs[self.usr.descname][self.id]

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
        usrdir = self.usr.run_dir
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
        com = f"cd {usrdir} && tar zcf {arcfil} {jnam}"
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
        del JobData.ujobsjob[self.usr.descname][job.id]
        return None

    def get_status_message(self):
        snam = self.status_file()
        line = ''
        if os.path.isfile(snam):
            with open(snam) as sfil:
                for line in sfil: pass
        return line

