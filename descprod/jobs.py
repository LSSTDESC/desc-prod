import os
import socket
import shutil
import stat
import json
import subprocess
import time
from descprod import timestamp
from descprod import UserData
import mysql.connector
from mysql.connector import errorcode

def wait_for_path(path, exists, ntry=10, dtry=0.2):
    """
    Wait for a file path to exist or not exist and return if it exists.
      exists - If true (false), wait for the path to exist (not exist).
      ntry - Maximum number of cycles to wait.
      dtry - Time to wait each cycle.
    """
    for i in range(ntry):
        path_exists = os.path.exists(path)
        if exists:
            if path_exists: break
        else:
            if not path_exists: break
    return path_exists
    
class JobData:
    """
    Holds the data describing a job.
      # State data held in data and DB:
                index - Job integer ID, unique to the site.
               parent - ID of the parent job if there is one.
              jobtype - Job type: parsltest, ...
               config - config string for the job
               howfig - how config string for the job
              session - sessiin where job was created
              archive - Archive index, 0 if not archived
                  pid - process ID
          create_time - job creation timestamp
           start_time - start timestamp
          update_time - heartbeat timestamp
            stop_time - stop timestamp
        return_status - Return status.
                 port - parsl worker port
             progress - One-line report of job progress.
      # Derived data
      usr - User data constructed from DESC user name
      errmsgs - Error messages
      _popen - Popen object. E.g. use poll to see if job has completed.
      port_errors - Error messages retrieving the port.
    """
    # If any data fields are added, call
    #   descprod-check-job-schema -y
    # at each site to add them to the DB.
    data_names =   [ 'id', 'parent', 'descname', 'jobtype',  'config',  'howfig', 'session', 'archive']
    data_dbtypes = ['int',    'int',  'varchar', 'varchar', 'varchar', 'varchar',     'int',    'int']
    data_names +=   [   'host',  'rundir', 'pid', 'create_time', 'start_time', 'update_time', 'stop_time', 'return_status', 'port', 'progress']
    data_dbtypes += ['varchar', 'varchar', 'int',         'int',        'int',         'int',       'int',           'int',  'int',  'varchar']
    data_nchars = {'descname':64, 'jobtype':128, 'config':512, 'howfig':512, 'host':128, 'rundir':256, 'progress':256}
    data_dbcons = {'id':'NOT NULL', 'descname':'NOT NULL'}
    dbg = 1
    jindent = 2          # json indentation
    jsep = (',', ': ')   # json separators
    jobs = {}  # All known jobs indexed by id
    ujobs = {} # Known user jobs indexed by descname and id.
    have_oldjobs = []  # List of users for which old jobs have been retrieved.
    bindir = '/home/descprod/bin'   # Where local commands are found
    connections = {}   # Pool of named mysql connectors
    _default_table_name = None # Current table name (set to descprod if None)
    _db_name = None    # Current db name (set to jobdata if None)
    flush = True       # Whether to flush all print statements
    class runopts:     # parameters for lcoal job submission
        use_shell = True                 # Submit jobs in a new shell
        use_sudo = False                 # Sudo to current user to launch jobs
        setup_conda = False              # Setup the local conda base
        setup_parsl = False              # Use the local parsl setup: ~deschome/local/etc/setup_parsl.sh
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
    def get_user_job(cls, descname, idx, usedb=False):
        '''
        Fetch a user job from the current cache.
        If the job is not found and usedb is true, then construct it from the DB data.
        '''
        myname = 'JobData.get_user_job'
        if descname in cls.ujobs:
            if idx in cls.ujobs[descname]:
                return cls.ujobs[descname][idx]
        if usedb:
            cur, con = cls.db_query_where(f"id={idx} AND descname='{descname}'")
            if cur is None: return None
            rows = cur.fetchall()
            nrow = len(rows)
            if nrow == 0: return None
            if nrow > 1:
                raise Exception(f"DB query for ID {idx} user {descname}' has too many ({nrow}) matches.")
            return JobData(idx, descname, source='db')
        return None

    @classmethod
    def get_jobs_from_disk(cls, descname=None):
        """"Retrieve a user's jobs from the local disk."""
        myname = 'JobData.get_jobs_from_disk'
        if descname is None: return cls.jobs
        usr = UserData(descname)
        if cls.dbg: print(f"{myname}: Fetching jobs for user {descname}.", flush=cls.flush)
        if descname not in cls.ujobs:
            cls.ujobs[descname] = {}
        if descname not in cls.have_oldjobs:
            topdir = f"{usr.run_dir}"
            if cls.dbg: print(f"{myname}: Looking for old jobs in {topdir}.", flush=cls.flush)
            if os.path.isdir(topdir):
                for jobnam in os.listdir(topdir):
                    jobid = cls.id_from_name(jobnam)
                    if jobid < 0:
                        if cls.dbg: print(f"{myname}:   Skipping bad name {jobnam}.", flush=cls.flush)
                        continue
                    if jobid in cls.jobs:
                        if dbg: print(f"{myname}:   Skipping bad name {jobnam}.", flush=cls.flush)
                        continue
                    print(f"{myname}:   Fetching job {jobnam}.", flush=cls.flush)
                    jdat = JobData(jobid, descname, "disk")
            cls.have_oldjobs.append(descname)
        return cls.ujobs[descname]

    @classmethod
    def get_jobs_from_db(cls, descname=None, arcs=None):
        """"Retrieve a user's jobs from the job DB."""
        myname = 'JobData.get_jobs_from_db'
        msg = ''   # Blank for success
        if descname not in cls.ujobs:
            cls.ujobs[descname] = {}
        sqry = f"descname='{descname}'"
        if type(arcs) is list:
            sarcs = str(arcs).replace('[', '(').replace(']', ')')
            sqry += f" AND ( archive IN {sarcs}"
            if 0 in arcs:
                sqry += " OR archive IS NULL"
            sqry += " )"
        cur, con = cls.db_query_where(sqry, cols='id')
        myjobs = cls.ujobs[descname]
        if cur is None:
            msg = f"Job DB query failed: {sqry}"
            print(f"{myname}: {msg}", flush=cls.flush)
            return {}, msg
        jdats = []
        njobsel = 0
        for row in cur.fetchall():
            idx = row[0]
            njobsel += 1
            if idx not in myjobs:
                jdat = JobData(idx, descname, 'db')
                jdats.append(jdat)
        if len(jdats):
            print(f"{myname}: Fetched {len(jdats)} new jobs for user {descname} from DB", flush=cls.flush)
        if njobsel == 0:
            print(f"{myname}: WARNING: No jobs matched query {sqry}")
        return myjobs, msg

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
        except Exception as e:
            print(f"{myname}: Unable to access mysql server: {e}", flush=cls.flush)
            return None
        curmy = conmy.cursor()
        con = None
        try:
            con = mysql.connector.connect(database=db_name)
        except mysql.connector.Error as err:
            if err.errno == errorcode.ER_ACCESS_DENIED_ERROR:
                print(f"{myname}: Unable to access mysql DB {db_name}.", flush=cls.flush)
            elif err.errno == errorcode.ER_BAD_DB_ERROR:
                if create_db:
                    print(f"{myname}: Creating DB {db_name}", flush=cls.flush)
                    com = f"CREATE DATABASE {db_name}"
                    cur = conmy.cursor()
                    cur.execute(com)
                    conmy.commit()
                    con = mysql.connector.connect(database=db_name)
                else:
                    print(f"{myname}: Database not found: {db_name}", flush=cls.flush)
            else:
                print(err)
        if cname is not None and con is not None: cls.connections[cname] = con
        return con

    @classmethod
    def db_table(cls, table_name=None, *, create_table=False, drop_table=False, db_name=None,
                 create_db=False, check_schema=False, add_schema=False, drop_column='', verbose=0):
        """
        Manipulate a job table in the DB.
          db_name - Database name [descprod]
            table_name - Job table name [descprod]
             create_db - if True, creates the database
            drop_table - if True, deletes the table
          create_table - if True, creates the table
             create_db - if True, creates the database
          check_schema - If True, check that all expected fields are present
            add_schema - If True, add any missing fields
           drop_column - if not blank, delete column drop_column
        Returns if the table exists.
        """
        myname = 'JobData.db_table'
        tnam = cls.current_table_name(table_name)
        dbnam = cls.db_name(db_name)
        con = cls.connect_db(create_db=create_db)
        if con is None:
            print(f"{myname}: Unable to connect to DB {dbnam}", flush=cls.flush)
            #raise Exception(f"{myname}: Unable to connect to DB {dbnam}")
            return None
        cur = con.cursor()
        check_query = f"SHOW TABLES LIKE '{tnam}'"
        cur.execute(check_query)
        haveit = bool(len(cur.fetchall()))
        if drop_table and haveit:
            print(f"{myname}: Dropping table {tnam}", flush=cls.flush)
            cls.connections.clear()
            com = f"DROP TABLE {tnam}"
            cur.execute(com)
            con.commit()
            haveit = cls.db_table()
            print(f"{myname}: Drop was successful.", flush=cls.flush)
        if len(drop_column) and haveit:
            print(f"{myname}: Dropping table {tnam}", flush=cls.flush)
            cls.connections.clear()
            com = f"ALTER TABLE {tnam}"
            cur.execute(com)
            com = f"DROP {drop_column}"
            cur.execute(com)
            con.commit()
            haveit = cls.db_table()
            print(f"{myname}: Drop of column {drop_column} was successful.", flush=cls.flush)
        if create_table and not haveit:
            print(f"{myname}: Creating table {tnam}", flush=cls.flush)
            cls.connections.clear()
            com = f"CREATE TABLE {tnam} ("
            for (nam, typ) in zip(cls.data_names, cls.data_dbtypes):
                nchar = cls.data_nchars.get(nam, 0)
                if nchar:
                    assert(typ == 'varchar')
                    flen = f"({nchar})"
                else:
                    assert(typ != 'varchar')
                    flen = ''
                constraint = cls.data_dbcons.get(nam, '')
                fcon = f" {constraint}" if len(constraint) else ''
                com += f" {nam} {typ}{flen} {fcon},"
            com += 'PRIMARY KEY (id) )'
            if verbose:
                print(f"{myname}: {com}", flush=cls.flush)
            cur.execute(com)
            con.commit()
            haveit = cls.db_table()
            print(f"{myname}: Create was successful.", flush=cls.flush)
        if (check_schema or add_schema) and haveit:
            print(f"{myname}: Checking schema in {tnam}", flush=cls.flush)
            cls.connections.clear()
            com = f"DESCRIBE {tnam}"
            cur.execute(com)
            schema = {}
            for ent in cur.fetchall():
                nam = ent[0]
                if nam in cls.data_names:
                    schema[nam] = ent
                else:
                    print("WARNING: DB column {name} is not part of JobData.")
            where = "FIRST"
            for (nam, typ) in zip(cls.data_names, cls.data_dbtypes):
                nchar = cls.data_nchars.get(nam, 0)
                if nchar:
                    assert(typ == 'varchar')
                    typ += f"({nchar})"
                else:
                    assert(typ != 'varchar')
                    flen = ''
                jdesc = f"{nam}, {typ}{flen}"
                if nam in schema:
                    dbdesc = str(schema[nam])
                    dbtyp = schema[nam][1].decode()
                    if dbtyp != typ:
                        dbdesc += f" ***** TYPE MISMATCH: {typ} != {dbtyp} *****"
                        if check_schema: haveit = False
                elif add_schema:
                    coldef = f"{dbtyp}"
                    constraint = cls.data_dbcons.get(nam, '')
                    if len(constraint):
                        coldef += f" {constraint}"
                    com = f"ALTER TABLE {tnam} ADD {nam} {coldef} {where}"
                    cur.execute(com)
                    con.commit()
                    dbdesc = f"***** Added column {nam} to DB table {tnam} *****"
                else:
                    dbdesc = "***** NOT FOUND *****"
                    if check_schema: haveit = False
                print(f"{jdesc:>30}: {dbdesc}", flush=cls.flush)
                where = f"AFTER {nam}"
        return haveit

    @classmethod
    def db_query(cls, query, *, verbose=0, display=False):
        """
        Query the job table table_name in DB db_name.
        Return a cursor with the results of query.
        Connection is cached until the next call so caller can use the cursor.
          query - query to perform, e.g. SELECT * FROM mytable WHERE descname='someone'
          verbose - display the query
          display - Display the rows and return the count
        """
        myname = 'JobData.db_query'
        con = None
        com = query
        if verbose > 1: print(f"{myname}: {com}", flush=cls.flush)
        con = cls.connect_db(cname ='query')
        if con is None:
            print(f"{myname}: Unable to connect to DB.", flush=cls.flush)
            return None
        cur = con.cursor()
        try:
            cur.execute(com)
        except mysql.connector.errors.ProgrammingError:
            print(f"{myname}: SQL syntax error in: {com}", flush=cls.flush)
            display = False
            return None
        if display:
            count = 0
            for row in [cur.fetchall()]:
                print(row, flush=cls.flush)
                count += 1
            if count == 0: print('***** No matches found *****', flush=cls.flush)
            return None
        return cur, con

    @classmethod
    def db_query_where(cls, where='*', *, table_name=None, cols='*', verbose=0, display=False):
        """
        Query the job table table_name in DB db_name.
        Returns the result of the query SELECT * from {table_name} where {where}
        If a query is provided, a cursor with the results is returned.
        Connection is cached until the next call so caller can use the cursor.
          where - where of query to perform. Blank returns all
          table_name - Table name if query is fixed
          cols - comm-separated list of column names to return
          verbose - display the query
          display - Display the rows and return the count
        """
        myname = 'JobData.db_query_where'
        tnam = cls.current_table_name(table_name)
        haveit = cls.db_table(tnam)
        if haveit is None or not haveit:
            print(f"{myname}: Job table not found: {tnam}", flush=cls.flush)
            return None
        com = f"SELECT {cols} FROM {tnam}"
        if len(where): com += f" WHERE {where}"
        return JobData.db_query(com, verbose=verbose, display=display)

    @classmethod
    def db_count_where(cls, where='*', *, table_name=None, verbose=0):
        """
        Query the job table table_name in DB db_name.
        Returns the count of the query SELECT * from {table_name} where {where}
        If a query is provided, a cursor with the results is returned.
        Connection is cached until the next call so caller can use the cursor.
          where - where of query to perform. Blank returns all
          table_name - Table name if query is fixed
          verbose - display the query
        """
        myname = 'JobData.db_count_where'
        tnam = cls.current_table_name(table_name)
        haveit = cls.db_table(tnam)
        if haveit is None or not haveit:
            return 0
        com = f"SELECT COUNT(*) FROM {tnam}"
        if len(where): com += f" WHERE {where}"
        cur, con = JobData.db_query(com, verbose=verbose)
        if cur is None: return None
        return cur.fetchone()[0]

    @classmethod
    def db_delete_where(cls, where, *, table_name=None, verbose=0):
        """
        Delete rows from the job table table_name in DB db_name.
        Connection is cached until the next call so caller can use the cursor.
          where - where of query to perform. Blank returns all
          table_name - Table name if query is fixed
          verbose - display the query
        Returns the number of rows deleted.
        """
        myname = 'JobData.db_count_delete'
        tnam = cls.current_table_name(table_name)
        haveit = cls.db_table(tnam)
        if haveit is None or not haveit:
            return 0
        com = f"DELETE FROM {tnam}"
        if len(where): com += f" WHERE {where}"
        cur, con = JobData.db_query(com, verbose=verbose)
        if cur is None: return None
        ndel = cur.rowcount
        con = JobData.connections['query']
        con.commit()
        return ndel

    @classmethod
    def get_db_table_schema(cls, *, table_name=None, field='Field', verbose=0):
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
        myname = 'JobData.get_db_table_schema'
        tnam = cls.current_table_name(table_name)
        if not cls.db_table():
            print(f"{myname}: Table not found: {tnam}", flush=cls.flush)
            return []
        con = cls.connect_db()
        cur = con.cursor()
        cur.execute(f"DESCRIBE {tnam}")
        vals = []
        fmap = {'Field':0, 'Type':1, 'Null':2, 'Key':3, 'Default':4, 'Extra':5}
        if field not in fmap:
            print(f"{myname}: Invalid field name: {field}", flush=cls.flush)
        fidx = fmap[field]
        for col in cur.fetchall():
            val = col[fidx]
            if verbose > 1: print(f"{myname}: {col}", flush=cls.flush)
            vals.append(val)
        return vals

    @classmethod
    def db_row(cls, job_id, table_name=None):
        """Fetcha a job description from a DB table."""
        myname = 'JobData.db_row'
        tnam = cls.current_table_name(table_name)
        if not cls.db_table():
            print(f"{myname}: Table not found: {tnam}", flush=cls.flush)
            return []
        cur, con = cls.db_query(f"SELECT * FROM {tnam} WHERE id = {job_id}")
        if cur is None: return None
        return cur.fetchone()

    def db_insert(self, *, table_name=None, verbose=0):
        """Insert this job into a DB table."""
        myname = 'JobData.db_insert'
        if not self.usedb: return 0
        tnam = self.current_table_name(table_name)
        if not self.db_table():
            print(f"{myname}: Table not found: {tnam}", flush=cls.flush)
            return 1
        idx = self.index()
        oldrow = self.db_row(idx)
        if oldrow is not None:
            print(f"{myname}: Job {idx} is already in table {tnam}:", flush=cls.flush)
            print(f"{myname}: {oldrow}", flush=cls.flush)
            return 2
        cnams = self.get_db_table_schema()
        ctyps = self.get_db_table_schema(field='Type')
        if len(cnams) < 5:
            print(f"{myname}: Unable to find schema for table {tnam}", flush=cls.flush)
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
        if verbose > 1: print(f"{myname}: {com}", flush=cls.flush)
        cur.execute(com)
        con.commit()
        self.job_table_name = tnam
        self.nset_db = 0
        self.stale_vars.difference_update(cnams)

    def db_update(self, *, verbose=0):
        """Update this job in its DB table."""
        myname = 'JobData.db_update'
        if not self.usedb: return 0
        tnam = self.job_table_name
        if not self.db_table(table_name=tnam):
            print(f"{myname}: Table not found: {tnam}", flush=self.flush)
            return 1
        idx = self.index()
        cnams = self.get_db_table_schema()
        ctyps = self.get_db_table_schema(field='Type')
        if len(cnams) < 5:
            print(f"{myname}: Unable to find schema for table {tnam}", flush=self.flush)
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
            if verbose > 1: print(f"{myname}: {com}", flush=self.flush)
            cur.execute(com)
        con.commit()
        self.nset_db = 0
        self.stale_vars.difference_update(upcnams)

    def do_error(self, myname, msg, rstat=None):
        """Record an error."""
        errmsg = f"{myname}: ERROR: {msg}"
        self.errmsgs += [errmsg]
        if JobData.dbg: print(errmsg, flush=self.flush)
        return rstat

    def idname(self):
        """Return the name of the job: jobXXXXXX."""
        return self.name_from_id(self.index())

    def server_rundir(self):
        """Return the run directory if this job is run on the server."""
        return f"{self.usr.run_dir}/{self.idname()}"

    def log_file(self):
        """Return the log file name for this job."""
        return f"{self.rundir()}/{self.idname()}.log"

    def wrapper_log_file(self):
        """Return the log file name for this job's wrapper."""
        return f"{self.rundir()}/wrapper.log"

    def status_file(self):
        """Return the status file name for this job."""
        return f"{self.rundir()}/current-status.txt"

    def job_config_file(self):
        """Return the job config file for this job."""
        return f"{self.rundir()}/config.json"

    def wrapper_config_file(self):
        """Return the wrapper config file for this job."""
        return f"{self.rundir()}/wrapper-status.json"

    def archive_file(self):
        """Return the archive file for this job."""
        fnam = f"{self.usr.archive_dir}/{self.idname()}.tz"
        dnam = os.path.dirname(fnam)
        if not os.path.exists(dnam): self.usr.mkdir(dnam)
        return fnam

    def delete_file(self):
        """Return the archive file after deletion for this job."""
        return f"{self.usr.delete_dir}/{self.idname()}.tz"

    def set_data(self, nam, val, *, set_stale=True):
        """Set a job property."""
        myname = 'JobData.set_data'
        if nam not in self.data_names:
            print(f"{myname}: ERROR: Invalid data name: {nam}", flush=self.flush)
            return 1
        oldval = self.data(nam)
        if val != oldval:
            self._data[nam] = val
            self.nset += 1
            self.nset_db += 1
            if set_stale: self.stale_vars.add(nam)
        return 0

    def set_rundir(self, rundir):
        self.set_data('host', socket.getfqdn())
        self.set_data('rundir', rundir)

    def has_data(self, nam):
        """Return if data exists."""
        return nam in self._data

    def data(self, nam):
        """Retrieve a job property."""
        if self.has_data(nam): return self._data[nam]
        return None

    def index(self):         return self.data('id')      # python uses object.id()
    def parent(self):        return self.data('parent')
    def descname(self):      return self.data('descname')
    def jobtype(self):       return self.data('jobtype')
    def config(self):        return self.data('config')
    def howfig(self):        return self.data('howfig')
    def session(self):       return self.data('session')
    def archive(self):       return self.data('archive')
    def host(self):          return self.data('host')
    def rundir(self):        return self.data('rundir')
    def pid(self):           return self.data('pid')
    def create_time(self):   return self.data('create_time')
    def start_time(self):    return self.data('start_time')
    def update_time(self):   return self.data('update_time')
    def stop_time(self):     return self.get_stop_time()
    def port(self):          return self.data('port')
    def return_status(self): return self.get_return_status()
    def progress(self):      return self.get_progress()

    def popen(self):
        '''Return the popen object if the jobs has bee started locally. Otherwise None.'''
        return self._popen

    def jmap(self):
        """Write the data to a json map."""
        myname = 'JobData.jmap'
        jmap = {}
        for nam in self.data_names:
            val = self.data(nam)
            if val is not None:
                jmap[nam] = val
        return jmap

    def jmap_update(self, jmap):
        """
        Update the job dat using a json map.
        Returns a string error message which is empty for success.
        """
        myname = 'JobData.jmap_update'
        if 'id' not in jmap:
            return f"Map does not contain the job ID."
            pass
        else:
            if jmap['id'] != self.index(): return f"IDs do not match: {jmap['id']} != {self.index()}"
        if 'descname' not in jmap:
            return f"Map does not contain the user name."
            pass
        else:
            if jmap['descname'] != self.descname(): return f"User names do not match: {jmap['descname']} != {self.descname()}"
        for nam in self.data_names:
            if nam in jmap: self.set_data(nam, jmap[nam])
        self.db_update()
        return ''

    def __init__(self, a_idx, a_descname, source=None, usedb=True, rundir=None):
        """
        Create or locate job idx for user descname.
          source:
            None - A new job is created
              db - from the current DB table
            disk - From the user's local rundir
        If usedb, the job's data are recorded and updated the job DB.
        If not None, rundir is used as the run directory.
        """
        self._data = {}       # All persistent data is stored here.
        self.usedb = usedb
        self.nset = 0               # Number of variable sets
        self.nset_db = 0            # Number variable sets since last DB synchronization
        self.stale_vars = set()     # Names of variables not sychronized to DB
        self.job_table_name = None  # Name of the table where this job resides
        self.set_data('id', a_idx)
        self.set_data('descname', a_descname)
        self.set_data('progress', 'Created.')
        now = int(time.time())
        self.set_data('create_time', now)
        self.set_data('update_time', now)
        if rundir is not None: self.set_rundir(rundir)
        idx = self.index()
        descname = self.descname()
        self.usr = UserData(descname)
        self.errmsgs = []
        self._popen = None
        self.port_errors = []
        myname = 'JobData.ctor'
        dbg = JobData.dbg
        sidx = JobData.name_from_id(idx)
        dbinsert = usedb
        if source is None or source == 'None' or source == 'none':
            if self.usedb and self.db_count_where(f"id = {idx}"):
                self.do_error(myname, f"DB entry already exists for id {idx}")
        elif source == 'db':
            dbinsert = False
            cur, con = self.db_query_where(f"id={idx} AND descname='{descname}'")
            if cur is None:
                self.do_error(myname, f"DB query for ID {idx} user {descname}' failed.")
            else:
                rows = cur.fetchall()
                nrow = len(rows)
                if nrow == 0:
                    self.do_error(myname, f"DB query for ID {idx} user {descname}' has no matches.")
                elif nrow > 1:
                    self.do_error(myname, f"DB query for ID {idx} user {descname}' has too many ({nrow}) matches.")
                else:
                    self.stale_vars = set()
                    dbnams = self.get_db_table_schema()
                    row = rows[0]
                    for (nam,val) in zip(dbnams, row):
                        self.set_data(nam, val, set_stale=False)
                    self.job_table_name = self.current_table_name()
        elif source == 'disk':
            if not havedir:
                self.do_error(myname, f"Directory not found: {rundir}")
            else:
                fnams = [self.job_config_file(), self.wrapper_config_file()]
                ok = False
                for fnam in fnams:
                    error_prefix = ''     # Error prefix for the file
                    emsgs = []            # Supplementary error messages
                    if os.path.exists(fnam):
                        try:
                            with open(fnam, 'r') as jfil:
                                jmap = json.load(jfil)
                                rmsg = self.jmap_update(jmap)
                                if len(rmsg):
                                    error_prefix = "Unable to parse file"
                                    emsgs.append(f"{rmsg}")
                                    emsgs.append(f"Map contents:")
                                    for key, val in jmap.items(): emsgs.append(f":   {key}: {val}")
                                else:
                                    print(f"{myname}: Loaded job data from {fnam}", flush=self.flush)
                                    ok = True
                        except json.decoder.JSONDecodeError:
                            error_prefix = "JSON file decode error"
                    else:
                        error_prefix = "File not found"
                    if len(error_prefix):
                        self.do_error(myname, f"{error_prefix}: {fnam}")
                        for msg in emsgs:
                            print(f"{myname}: {msg}", flush=self.flush)
                if not ok:
                    self.do_error(myname, f"Unable to read any of the json config files:")
                    for fnam in fnams: print(f"{myname}:  {fnam}", flush=self.flush)
        else:
             self.do_error(myname, f"Invalid source option: {source}")
        JobData.jobs[idx] = self
        print(f"{myname}: Inserting job {idx} for user {descname}", flush=self.flush)
        if descname not in JobData.ujobs:
            JobData.ujobs[descname] = {}
        JobData.ujobs[descname][idx] = self
        if dbinsert: self.db_insert()

    def configure(self, jobtype, config, howfig, sid, parent=None):
        """
        Configure a job: assign a job type and a configuration string.
        """
        myname = 'JobData.configure'
        rstat = 0
        if self.jobtype() is not None:
            rstat += self.do_error(myname, f"Job type is already set: {self.jobtype()}", 1)
        if self.config() is not None:
            rstat += self.do_error(myname, f"Job config is already set: {self.config()}", 2)
        if self.howfig() is not None:
            rstat += self.do_error(myname, f"Job howfig is already set: {self.howfig()}", 2)
        if self.pid() is not None:
            rstat += self.do_error(myname, f"Job has already been started. Process ID: {self.pid()}", 4)
        if self.get_return_status() is not None:
            rstat += self.do_error(myname, f"Job has already completed. Return status: {self.get_return_status()}", 8)
        if rstat: return rstat
        self.set_data('jobtype', jobtype)
        self.set_data('config', config)
        self.set_data('howfig', howfig)
        self.set_data('session', sid)
        self.set_data('archive', sid)
        if parent is not None:
            self.set_data('parent', parent)
        self.set_data('progress', 'Ready.')
        self.db_update()
        return 0

    def ready_to_run(self):
        '''
        Check if a job is ready to run.
        If so, return blank. Otherwise return a message explaining
        why the job is not ready to run.
        '''
        needs = ['id', 'descname', 'jobtype', 'config', 'howfig', 'create_time', 'update_time', 'progress']
        nots = ['pid', 'start_time', 'stop_time', 'return_status']
        for nam in needs:
            if not self.has_data(nam):
                return f"Job does not have {nam}."
        for nam in nots:
            if self.has_data(nam):
                return f"Job already has {nam}."
        if self.progress() != 'Ready.':
            return f"""Job is not ready to run (progress is "{self.progress()}"."""
        return ''

    def registered_howtypes(self):
        '''Return the list of registered howtypes.'''
        return ['pmb', 'pmbs']

    def command(self):
        '''Construct the shell command from the jobtype and config.'''
        jobtype = self.jobtype()
        config = self.config()
        howfig = self.howfig()
        use_howtype = False
        if len(howfig):
            howtype = howfig.split('-')[0]
            use_howtype = howtype in self.registered_howtypes()
        if use_howtype:
            return f"runapp-{howtype}"
        return f"runapp-{jobtype} {config} {howfig}"

    def run(self, rundir=None, server=None):
        """
        Run the job, i.e. start it with Popen and a wrapper.
        If rundir is not supplied, then job is run on the server rundir.
        """
        myname = 'JobData.run'
        rstat = 0
        scom = self.command()
        if scom is None:
            rstat += self.do_error(myname, f"Command is not specified.", 1)
        if rundir is None:
            rundir = self.server_rundir()
            self.usr.mkdir(rundir)
            remote = False
        else:
            if os.path.exists(rundir):
                rstat += self.do_error(myname, f"Run directory already exists: {rundir}", 2)
            else:
                try:
                    os.mkdir(rundir)
                except Exception as e:
                    rstat += self.do_error(myname, f"Could not create run directory: {rundir}: {e}.", 3)
            remote = True
        if rstat: return rstat
        fwrapbas = 'descprod-wrap'
        fwrapsrc = shutil.which(fwrapbas)
        if len(fwrapsrc) == 0:
            self.do_error(myname, f"Unable to find wrapper: {fwrapbas}", 3)
            return 4
        fwrapdst = f"{rundir}/{fwrapbas}"
        try:
            shutil.copyfile(fwrapsrc, fwrapdst)
            wrapstat = os.stat(fwrapdst).st_mode | stat.S_IEXEC
            os.chmod(fwrapdst, wrapstat)
        except Exception as e:
            self.do_error(myname, [e, f"Unable to copy wrapper: {fwrapsrc} to {fwrapdst}"], 4)
            return 5
        self.set_rundir(rundir)
        #print(self.jmap(), flush=self.flush)
        jnam = self.job_config_file()
        with open(jnam, 'w') as jfil:
            json.dump(self.jmap(), jfil, separators=JobData.jsep, indent=JobData.jindent)
        runopts = JobData.runopts
        com = []
        if not remote and runopts.use_sudo:
            com = ['sudo', '-u', self.usr.descname]
        shell = runopts.use_shell
        lognam = self.wrapper_log_file()
        if shell:
            shwcom = ""
            if runopts.setup_conda:
                shwcom += 'source /home/descprod/conda/setup.sh; '
            if runopts.setup_parsl:
                shwcom += 'source /home/descprod/local/etc/setup_parsl.sh; '
            if len(runopts.env_file):
                shwcom += f"set >{runopts.env_file}; "
            shwcom += f"{fwrapdst} '{scom}' {self.rundir()} {self.log_file()} {self.wrapper_config_file()} {self.index()} {self.descname()}"
            shwcom += f" >{lognam} 2>&1"
            if server is not None: shwcom += f" {server}"
            com += ['bash', '-login', '-c', shwcom]
            #com += ['bash', '-c', shwcom]  # Apri 3, 2023. Now able to run command without descprod.
        else:
            com += ['{fwrapdst}', scom, self.rundir(), self.log_file(), self.wrapper_config_file(), self.index(), self.descname()]
            if server is not None: com += ["{server}"]
        #logfil = open(self.wrapper_log_file(), 'w')
        #print(shwcom, logfil, flush=self.flush)
        rundir = self.rundir()
        #self._popen = subprocess.Popen(com, cwd=rundir, stdout=logfil, stderr=logfil)
        self._popen = subprocess.Popen(com, cwd=rundir)
        noisy= True
        if noisy:
            print(f"JobData.run: Started subprocess.")
            print(f"JobData.run:    Command: {com}")
            print(f"JobData.run:    Run dir: {rundir}")
            print(f"JobData.run:   Log file: {lognam}")
        self.set_data('progress', 'Running.', flush=self.flush)
        self.db_update()
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
          "return_status": 0
          "progress": "This job is done."
        """
        myname = 'JobData.get_wrapper_info'
        jnam = self.wrapper_config_file()
        if not os.path.exists(jnam): return None
        jmap = {}
        with open(jnam, 'r') as jfil:
            try:
                jmap = json.load(jfil)
            except:
                print(f"{myname}: Unable to read {jnam}", flush=self.flush)
        self.jmap_update(jmap)
        # If we have the pid for the first time, record it and the start time
        # in the job data and config file.
        if self.pid() is None and 'pid' in jmap:
            self.set_data('pid', jmap['pid'])
            self.set_data('start_time', jmap['start_time'])
            self.db_update()
            jnam = self.job_config_file()
            with open(jnam, 'r') as jfil:
                try:
                    jmap = json.load(jfil)
                except json.JSONDecodeError as e:
                    print(f"{myname}: ERROR: Json decode error reading {jnam}.", flush=self.flush)
                    return None
            jmap.update({'pid':self.pid()})
            jmap.update({'start_time':self.start_time()})
            with open(jnam, 'w') as jfil:
                json.dump(jmap, jfil, separators=JobData.jsep, indent=JobData.jindent)
                jfil.write('\n')
            self.db_update()
        return jmap

    def get_port(self, badval=None):
        myname = 'JobData.get_port'
        if 'port' not in self._data:
            rundir = self.rundir()
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
            self.db_update()
        else:
            port = self.data('port')
        return self.port()

    def get_return_status(self):
        myname = 'JobData.get_return_status'
        rs = self.data('return_status')
        if rs is None:
            self.get_wrapper_info()
        return self.data('return_status')

    def get_stop_time(self):
        self.get_return_status()
        return self.data('stop_time')

    def get_progress(self):
        self.get_return_status()
        return self.data('progress')

    def duration(self):
        ts1 = self.start_time()
        if ts1 is None: return -999
        ts2 = self.stop_time()
        if ts2 is None: ts2 = timestamp()
        dur = ts2 - ts1
        #print(f"Duration: {dur} = {ts2} - {ts1}", flush=self.flush)
        return dur

    def dropdown_content(self, baseurl):
        q = '"'
        isready = len(self.ready_to_run()) == 0
        txt = ''
        if isready:
            txt += f"<a href={q}{baseurl}/startjob?id={self.index()}{q}>Start job {self.index()}</a>"
            txt += '<br>'
        txt += f"<a href={q}{baseurl}/archivejob?id={self.index()}{q}>Archive job {self.index()}</a>"
        txt += '<br>'
        txt += f"<a href={q}{baseurl}/deletejob?id={self.index()}{q}>Delete job {self.index()}</a>"
        txt += '<br>'
        txt += f"<a href={q}{baseurl}/copyjob?id={self.index()}{q}>Copy job {self.index()}</a>"
        return txt

    def is_active(self):
        return self.rundir() is not None

    def is_archived(self):
        return os.path.exists(self.archive_file())

    def is_deleted(self):
        if os.path.exists(self.rundir()): return False
        if os.path.exists(self.archive_file()): return False
        return True

    def deactivate(self):
        """Deactivate this job: remove from jobs and ujobs."""
        myname = 'JobData.deactivate'
        jid = self.index()
        uid = self.usr.descname
        sid = f"{uid}/{jid}"
        if self.index() in JobData.jobs:
            print(f"{myname}: Removing {sid} from JobData.jobs", flush=self.flush)
            del JobData.jobs[jid]
        if uid in JobData.ujobs:
            if jid in JobData.ujobs[uid]:
                print(f"{myname}: Removing {sid} from JobData.ujobs", flush=self.flush)
                del JobData.ujobs[uid][jid]

    def set_archive(self, aval=1):
        """
        Archive this job.
        """
        self.set_data('archive', aval)
        self.db_update()
        return 0

    def old_archive(self, force=False, if_present=False):
        """
        Archive this job.
        Returns the archive file name if successful.
        Otherwise returns None.
          force - Remake the archive if it already exists
          if_present - No error if rundir is missing
        """
        myname = 'JobData.archive'
        rundir = self.rundir()
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
        if rstat:
            msg = f"Archive command failed with error {rstat}: {com}"
            if os.path.exists(arcfil):
                os.remove(arcfil)
            self.do_error(myname, msg)
            return None
        arc_exists = wait_for_path(arcfil, True)
        if not arc_exists:
            self.do_error(myname, msg)
            return None
        if arc_exists and os.path.exists(rundir):
            shutil.rmtree(rundir)
            if wait_for_path(rundir, False):
                msg = f"WARNING: Run dir removal failed: {rundir}"
                self.do_error(myname, msg)
            self.deactivate()
        return arcfil

    def delete(self):
        """Delete this job."""
        uid = self.usr.descname
        jid = self.index()
        sid = f"{uid}/{jid}"
        dbg = 1
        myname = 'JobData.delete'
        rundir = self.rundir()
        ret = None
        if rundir is not None and os.path.exists(rundir):
            print(f"{myname}: Deleting run directory for job {sid}", flush=self.flush)
            arcfil = self.set_archive()
            delfil = self.delete_file()
            if os.path.exists(rundir):
                if dbg: print(f"Removing dir {rundir}", flush=self.flush)
                shutil.rmtree(rundir)
            if arcfil is not None:
                if os.path.exists(arcfil) and not os.path.exists(delfil):
                    if dbg: print(f"Renaming archive {arcfil}", flush=self.flush)
                    os.rename(arcfil, delfil)
                    ret = delfil
                else:
                    if dbg: print(f"Removing archive {arcfil}", flush=self.flush)
                    os.remove(arcfil)
        if self.db_count_where(f"id={jid}"):
            print(f"{myname}: Deleting DB entry for job {sid}", flush=self.flush)
            ndel = self.db_delete_where(f"id={jid}")
            if ndel != 1:
                print(f"{myname}: ERROR: Deleted row count {ndel} != one", flush=self.flush)
        self.deactivate()
        return ret
        return 0

