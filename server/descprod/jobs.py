class JobData:
    """
    Holds the data describing a job.
      descname - DESC user name
      id - Job integer ID
      rundir - Run directory
      errmsgs - Error messages
    """
    dbg = 1
    runbas = '/home/descprod/data/rundirs'

    @classmethod
    def name_from_id(cls, idx):
        sidx = str(idx)
        while len(sidx) < 6: sidx = '0' + sidx
        return 'job' + sidx

    @classmethod
    def id_from_name(cls, sidx):
        rem = sidx[3:]
        while rem[0] == '0' and len(rem) > 1: rem = rem[1:]
        return int(rem)

    def __init__(self, idx, descname, create=None):
        self.id = idx
        self.descname = descname
        self.rundir = None
        self.errmsgs = []
        myname = 'JobData.ctor'
        dbg = JobData.dbg
        sidx = JobData.name_from_id(self.id)
        rundir = f"{self.runbas}/{self.descname}/{sidx}"
        havedir = os.path.isdir(rundir)
        if create:
            if havedir:
                 errmsg = f"{myname}: ERROR: Directory already exists: {rundir}"
                 self.errmsgs += [errmsg]
                 if dbg: print(errmsg)
            os.mkdir(rundir)
        self.rundir = rundir
