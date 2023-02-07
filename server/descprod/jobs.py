import os
import shutil
import json
import subprocess
from descprod import timestamp
from descprod import UserData
import mysql.connector
from mysql.connector import errorcode

class JobData:
    """
    Holds the data describing a job.
      # State data held in DB:
        index() - Job integer ID, unique to the site.
        jobtype() - Job type: parsltest, ...
        config() - config string for the job
        command() - Array holding the job command line for Popen.
        pid() - process ID
        start_time() - start timestamp
        port() - parsl worker port
        return_status() - Return status.
        stop_time() - stop timestamp
      # Derived data
      usr - User data constructed from DESC user name
      errmsgs - Error messages
      _popen - Popen object. E.g. use poll to see if job has completed.
      port_errors - Error messages retrieving the port.
    """
    dbg = 1
    jindent = 2
    jsep = (',', ': ')
    jobs = {}  # All known jobs indexed by id
    ujobs = {} # Known user jobs indexed by descname and id.
    have_oldjobs = []  # List of users for which old jobs have been retrieved.
    bindir = '/home/descprod/bin'
    connections = {}   # Pool of mysql connectors
    _default_table_name = None # Current table name
    _db_name = None    # Current db name
    class runopts:
        use_shell = True                 # Submit jobs in a new shell
        use_sudo = True                  # Sudo to current user to launch jobs
        setup_conda = True               # Setup the local conda base
        setup_parsl = True               # Use the local parsl setup: ~deschome/local/etc/setup_parsl.sh
        env_file = 'descprod-env.log'    # env is dumped to this file

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

    @classmethod
    def db_name(cls, new_name=None):
        """
        Return the current db name.
        If new_name is provided, it is first assigned as the current value.
        If no value has been set or new_name is '', the default 'descprod' is used.
        """
        if new_name is not None:
            cls._db_name = new_name
        if cls._db_name is None or len(cls._db_name) == 0:
            cls._db_name = 'descprod'
        return cls._db_name

    @classmethod
    def current_table_name(cls, new_name=None):
        """
        Return the current db table name.
        If new_name is provided, it is first assigned as the current value.
        If no value has been set or new_name is '', the default 'jobdata' is used.
        """
        if new_name is not None:
            cls._default_table_name = new_name
        if cls._default_table_name is None or len(cls._default_table_name) == 0:
            cls._default_table_name = 'jobdata'
        return cls._default_table_name

    @classmethod
    def connect_db(cls, *, cname=None, db_name=None, create_db=False):
        """
        Return a connection to the named or current database.
        If cname is provided, the connection is cached.
        """
        myname = 'JobData.connect_db'
        if db_name is None: db_name = cls.db_name()
        conmy = None
        try:
            conmy = mysql.connector.connect(port=3306)
        except:
            print(f"{myname}: Unable to access mysql server.")
            return None
        curmy = conmy.cursor()
        con = None
        try:
            con = mysql.connector.connect(database=db_name)
        except mysql.connector.Error as err:
            if err.errno == errorcode.ER_ACCESS_DENIED_ERROR:
                print(f"{myname}: Unable to access mysql DB {db_name}.")
            elif err.errno == errorcode.ER_BAD_DB_ERROR:
                if create_db:
                    print(f"{myname}: Creating DB {db_name}")
                    com = f"CREATE DATABASE {db_name}"
                    cur = conmy.cursor()
                    cur.execute(com)
                    conmy.commit()
                    con = mysql.connector.connect(database=db_name)
                else:
                    print(f"{myname}: Database not found: {db_name}")
            else:
                print(err)
        if cname is not None and con is not None: cls.connections[cname] = con
        return con

    @classmethod
    def have_table(cls, table_name=None, create_table=False, drop_table=False, db_name=None, create_db=False):
        """Return if a table exists."""
        myname = 'JobData.have_table'
        tnam = cls.current_table_name(table_name)
        dbnam = cls.db_name(db_name)
        con = cls.connect_db(create_db=create_db)
        if con is None:
            print(f"{myname}: Unable to connect to DB {dbnam}")
            return None
        cur = con.cursor()
        check_query = f"SHOW TABLES LIKE '{tnam}'"
        cur.execute(check_query)
        haveit = bool(len(cur.fetchall()))
        if drop_table and haveit:
            print(f"{myname}: Dropping table {tnam}")
            com = f"DROP TABLE {tnam}"
            cur.execute(com)
            con.commit()
            haveit = cls.have_table()
        if create_table and not haveit:
            print(f"{myname}: Creating table {tnam}")
            com = (
              f"CREATE TABLE {tnam} ( "
              f"id int NOT NULL, "
              f"descname varchar(64) NOT NULL, "
              f"jobtype varchar(128), "
              f"config varchar(512), "
              f"command varchar(256), "
              f"pid int, "
              f"start_time int, "
              f"port int, "
              f"return_status int, "
              f"stop_time int, "
              f"PRIMARY KEY (id) )"
            )
            cur.execute(com)
            con.commit()
            haveit = cls.have_table()
        return haveit

    @classmethod
    def db_query(cls, query='*', table_name=None, fix=True, verbose=0):
        """
        Query a job table table_name in DB db_name.
        If no query is provided, returns whether the table exists.
        If a query is provided, a cursor with the results is returned.
        If fix and "SELECT" does not appear in the query, "SELECT " is prepended.
        If fix and "FROM" does not appear in the query, " FROM <table_name>" is appended.
        Connection is cached until the next call so caller can use the cursor.
        """
        myname = 'JobData.db_query'
        tnam = cls.current_table_name(table_name)
        haveit = cls.have_table(tnam)
        if haveit is None or not haveit:
            print(f"{myname}: Job table not found: {table_name}")
            return None
        com = query
        if fix:
            if com.find('SELECT') == -1: com = 'SELECT ' + com
            if com.find('FROM') == -1: com = f"{com} FROM {table_name}"
        if verbose > 1: print(f"{myname}: {com}")
        con = cls.connect_db(cname ='query')
        cur = con.cursor()
        cur.execute(query)
        return cur

    @classmethod
    def get_table_schema(cls, *, table_name=None, field='Field', verbose=0):
        """
        Return info about the table schema with a value or None for each column.
        Value to return is specified by field:
          Field - Column name
          Type - Data type
          Null - Can be null?
          Key - Is use in key?
          Default - Default value?
          Extra - User defined?
        """
        myname = 'JobData.get_table_schema'
        tnam = cls.current_table_name(table_name)
        if not cls.have_table():
            print(f"{myname}: Table not found: {tnam}")
            return []
        con = cls.connect_db()
        cur = con.cursor()
        cur.execute(f"DESCRIBE {tnam}")
        vals = []
        fmap = {'Field':0, 'Type':1, 'Null':2, 'Key':3, 'Default':4, 'Extra':5}
        if field not in fmap:
            print(f"{myname}: Invalid field name: {field}")
        fidx = fmap[field]
        for col in cur.fetchall():
            val = col[fidx]
            if verbose > 1: print(f"{myname}: {col}")
            vals.append(val)
        return vals

    def db_row(self, key, table_name=None):
        """Fetcha job description from a DB table."""
        myname = 'JobData.db_row'
        tnam = self.current_table_name(table_name)
        if not self.have_table():
            print(f"{myname}: Table not found: {tnam}")
            return []
        cur = self.db_query(f"SELECT * FROM {tnam} WHERE id = {self.index()}")
        return cur.fetchone()

    def db_insert(self, *, table_name=None, verbose=0):
        """Insert this job into a DB table."""
        myname = 'JobData.db_insert'
        tnam = self.current_table_name(table_name)
        if not self.have_table():
            print(f"{myname}: Table not found: {tnam}")
            return 1
        idx = self.index()
        oldrow = self.db_row(idx)
        if oldrow is not None:
            print(f"{myname}: Job {idx} is already in table {tnam}:")
            print(f"{myname}: {oldrow}")
            return 2
        cnams = self.get_table_schema()
        ctyps = self.get_table_schema(field='Type')
        if len(cnams) < 5:
            print(f"{myname}: Unable to find schema for table {tnam}")
            return 3
        cvals = []
        scnams = ''
        scvals = ''
        first = True
        for icol in range(len(cnams)):
            cnam = cnams[icol]
            if cnam == 'idx': jnam = 'id'
            else: jnam = cnam
            jval = self.data(jnam)
            if jval is None: jval = 'NULL'
            cvals.append(jval)
            if first: first = False
            else:
                scnams += ', '
                scvals += ', '
            scnams += cnam
            styp = ctyps[icol].decode('utf-8')
            addquote = styp.find('varchar') >= 0
            if addquote: scvals += "'"
            scvals += str(jval)
            if addquote: scvals += "'"
        con = self.connect_db()
        cur = con.cursor()
        com = f"INSERT INTO {tnam} ({scnams}) VALUES ({scvals})"
        if verbose > 1: print(f"{myname}: {com}")
        cur.execute(com)
        con.commit()
        self.job_table_name = tnam
        self.nset_db = 0
        self.stale_vars.difference_update(cnams)

    def db_update(self, *, verbose=0):
        """Update this job in its DB table."""
        myname = 'JobData.db_update'
        tnam = self.job_table_name
        if not self.have_table(table_name=tnam):
            print(f"{myname}: Table not found: {tnam}")
            return 1
        idx = self.index()
        cnams = self.get_table_schema()
        ctyps = self.get_table_schema(field='Type')
        if len(cnams) < 5:
            print(f"{myname}: Unable to find schema for table {tnam}")
            return 3
        coms = []
        upcnams = set()
        for icol in range(len(cnams)):
            cnam = cnams[icol]
            if cnam not in self.stale_vars: continue
            upcnams.add(cnam)
            jnam = cnam
            jval = self.data(jnam)
            if jval is None: jval = 'NULL'
            styp = ctyps[icol].decode('utf-8')
            if styp.find('varchar') >= 0: squot = "'"
            else: squot = ''
            cval = f"{squot}{jval}{squot}"
            com = f"UPDATE {tnam} SET {cnam} = {cval} WHERE id = {idx}"
            coms.append(com)
        con = self.connect_db()
        cur = con.cursor()
        for com in coms:
            if verbose > 1: print(f"{myname}: {com}")
            cur.execute(com)
        con.commit()
        self.nset_db = 0
        self.stale_vars.difference_update(upcnams)

    def do_error(self, myname, msg, rstat=None):
        """Record an error."""
        errmsg = f"{myname}: ERROR: {msg}"
        self.errmsgs += [errmsg]
        if JobData.dbg: print(errmsg)
        return rstat

    def idname(self):
        """Return the name of the job: jobXXXXXX."""
        return self.name_from_id(self.index())

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

    def set_data(self, nam, val):
        """Set a job property."""
        oldval = self.data(nam)
        if val != oldval:
            self._data[nam] = val
            self.nset += 1
            self.nset_db += 1
            self.stale_vars.add(nam)

    def data(self, nam):
        """Retrieve a job property."""
        if nam in self._data: return self._data[nam]
        return None

    def index(self):         return self.data('id')      # python uses object.id()
    def descname(self):      return self.data('descname')
    def jobtype(self):       return self.data('jobtype')
    def config(self):        return self.data('config')
    def pid(self):           return self.data('pid')
    def start_time(self):    return self.data('start_time')
    def port(self):          return self.data('port')
    def command(self):       return self.data('command')
    def return_status(self): return self.get_return_status()
    def stop_time(self):     return self.get_stop_time()

    def jmap_update(self, jmap):
        """Update the job dat using a json map."""
        myname = 'JobData.jmap_update'
        if 'id' not in jmap:
            #return (1, f"Map does not containe the job ID.")
            pass
        else:
            if jmap['id'] != self.index(): return (2, f"IDs do not match: {jmap['id']} != {self.index()}")
        if 'descname' not in jmap:
            #return (3, f"Map does not containe the user name.")
            pass
        else:
            if jmap['descname'] != self.descname(): return (3, f"User names do not match: {jmap['descname']} != {self.descname()}")
        for nam in ['jobtype', 'config', 'command', 'pid', 'start_time', 'port', 'return_status', 'stop_time']:
            if nam in jmap: self.set_data(nam, jmap[nam])
        return (0, '')

    def __init__(self, a_idx, a_descname, create):
        """
        Create or locate job idx for user descname.
        If create is True, the directory is created.
        """
        self._data = {}       # All persistent data is stored here.
        self.nset = 0               # Number of variable sets
        self.nset_db = 0            # Number variable sets since last DB synchronization
        self.stale_vars = set()     # Names of variables not sychronized to DB
        self.job_table_name = None  # Name of the table where this job resides
        self.set_data('id', a_idx)
        self.set_data('descname', a_descname)
        idx = self.index()
        descname = self.descname()
        self.usr = UserData(descname)
        self.errmsgs = []
        self._popen = None
        self.port_errors = []
        myname = 'JobData.ctor'
        dbg = JobData.dbg
        sidx = JobData.name_from_id(idx)
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
                            rs, rmsg = self.jmap_update(jmap)
                            if rs:
                                print(f"{myname}: Update from file {jnam} failed.")
                                print(f"{myname}: {rmsg}")
                                print(f"{myname}: Map contents:")
                                for key, val in jmap.items(): print(f"{myname}:   {key}: {val}")
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
        if self.jobtype() is not None:
            rstat += self.do_error(myname, f"Job type is already set: {self.jobtype()}", 1)
        if self.config() is not None:
            rstat += self.do_error(myname, f"Job config is already set: {self.config()}", 2)
        if self.pid() is not None:
            rstat += self.do_error(myname, f"Job has already been started. Process ID: {self.pid()}", 4)
        if self.get_return_status() is not None:
            rstat += self.do_error(myname, f"Job has already completed. Return status: {self.get_return_status()}", 8)
        if rstat: return rstat
        self.set_data('jobtype', jobtype)
        self.set_data('config', config)
        command = a_command
        if command is None:
            if jobtype == 'parsltest':
               command = f"desc-wfmon-parsltest {config}"
            else:
               return self.do_error(myname, f"Command not found for job type {jobtype}", 16)
        self.set_data('command', command)
        jmap = {}
        jmap['jobtype'] = self.jobtype()
        jmap['config']  = self.config()
        jmap['command'] = self.command()
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
        if self.command() is None:
            rstat += self.do_error(myname, f"Command is not specified.", 1)
        if not os.path.exists(self.run_dir()):
            rstat += self.do_error(myname, f"Run directory is not present.", 2)
        if rstat: return rstat
        runopts = JobData.runopts
        com = ['sudo', '-u', self.usr.descname] if runopts.use_sudo else []
        shell = runopts.use_shell
        if shell:
            shwcom = ""
            if runopts.setup_conda:
                shwcom += 'source /home/descprod/conda/setup.sh; '
            if runopts.setup_parsl:
                shwcom += 'source /home/descprod/local/etc/setup_parsl.sh; '
            if len(runopts.env_file):
                shwcom += f"set >{runopts.env_file}; "
            shwcom += f"descprod-wrap '{self.command()}' {self.run_dir()} {self.log_file()} {self.wrapper_config_file()}"
            com += ['bash', '-login', '-c', shwcom]
        else:
            com += ['descprod-wrap', self.command(), self.run_dir(), self.log_file(), self.wrapper_config_file()]
        logfil = open(self.wrapper_log_file(), 'w')
        print(shwcom, logfil)
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
        myname = 'JobData.get_wrapper_info'
        jnam = self.wrapper_config_file()
        if not os.path.exists(jnam): return None
        with open(jnam, 'r') as jfil:
            jmap = json.load(jfil)
        # If we have the pid for the first time, record it and the start time
        # in the job data and config file.
        if self.pid() is None and 'pid' in jmap:
            self.set_data('pid', jmap['pid'])
            self.set_data('start_time', jmap['start_time'])
            jnam = self.job_config_file()
            with open(jnam, 'r') as jfil:
                try:
                    jmap = json.load(jfil)
                except json.JSONDecodeError as e:
                    print(f"{myname}: ERROR: Json decode error reading {jnam}.")
                    return None
            jmap.update({'pid':self.pid()})
            jmap.update({'start_time':self.start_time()})
            with open(jnam, 'w') as jfil:
                json.dump(jmap, jfil, separators=JobData.jsep, indent=JobData.jindent)
                jfil.write('\n')
        return jmap

    def get_port(self, badval=None):
        myname = 'JobData.get_port'
        if 'port' not in self._data:
            rundir = self.run_dir()
            com = f"{JobData.bindir}/descprod-get-parsl-port {rundir}"
            (rstat, sout) = subprocess.getstatusoutput(com)
            if rstat:
                self.port_errors.append(f"Unable to retrieve parsl port. {sout}")
                port = badval
                return badval
            try:
                port = int(sout)
            except:
                self.port_errors(f"Invalid parsl port: {sout}")
                port = badval
                return badval
            self.set_data('port', badval)
        else:
            port = self.data('port')
        return self.port()

    def get_return_status(self):
        myname = 'JobData.get_return_status'
        rs = self.data('return_status')
        if rs is not None: return rs
        wmap = self.get_wrapper_info()
        # If we have the return status for the first time, record it and
        # the stop time in the the job data and config file.
        if wmap is not None and 'return_code' in wmap:
           self.set_data('return_status', wmap['return_code'])
           self.set_data('stop_time', wmap['stop_time'])
           print(f"Job {self.idname()} ended at {self.stop_time()} with status {self.return_status()}.")
           jnam = self.job_config_file()
           with open(jnam, 'r') as jfil:
               try:
                   jmap = json.load(jfil)
               except json.JSONDecodeError:
                   print(f"{myname}: Unable to decode json file {jnam}.")
                   jmap = {}
           jmap.update({'return_status':self.return_status()})
           jmap.update({'stop_time':self.stop_time()})
           with open(jnam, 'w') as jfil:
               json.dump(jmap, jfil, indent=JobData.jindent)
           return self.return_status()
        return None

    def get_stop_time(self):
        self.get_return_status()
        return self.data('stop_time')

    def duration(self):
        ts1 = self.start_time()
        if ts1 is None: return -999
        ts2 = self.stop_time()
        if ts2 is None: ts2 = timestamp()
        dur = ts2 - ts1
        #print(f"Duration: {dur} = {ts2} - {ts1}")
        return dur

    def dropdown_content(self, baseurl):
        q = '"'
        txt = f"<a href={q}{baseurl}/archivejob?id={self.index()}{q}>Archive job {self.index()}</a>"
        txt += '<br>'
        txt += f"<a href={q}{baseurl}/deletejob?id={self.index()}{q}>Delete job {self.index()}</a>"
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
        if self.index() in JobData.jobs:
            del JobData.jobs[self.index()]
        if self.usr.descname in JobData.ujobs:
            if self.index() in JobData.ujobs[self.usr.descname]:
                del JobData.ujobs[self.usr.descname][self.index()]

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
        del JobData.jobs[job.index()]
        del JobData.ujobsjob[self.usr.descname][job.index()]
        return None

    def get_status_message(self):
        snam = self.status_file()
        line = ''
        if os.path.isfile(snam):
            with open(snam) as sfil:
                for line in sfil: pass
        return line

