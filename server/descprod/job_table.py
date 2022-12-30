from descprod import JobData
from pandas import DataFrame

class JobTable:
    """
    Class to hold an format a TABLE of jobs.
    """

    def __init__(self, descname=None):
        self.descname = descname
        self.refresh()

    def refresh(self):
        self.jobs = JobData.get_jobs()
        self.jobids = []
        self.jobtypes = []
        self.configs = []
        self.pids = []
        self.rstats = []
        for job in self.jobs.values():
            self.jobids.append(job.id)
            self.jobtypes.append(job.jobtype)
            self.configs.append(job.config)
            if job.popen is None:
                self.pids.append(None)
                self.rstats.append(None)
            else:
                job.popen.poll()
                self.pids.append(job.popen.pid)
                self.rstats.append(job.popen.returncode)
        self.map = {}
        self.map['id'] = self.jobids
        self.map['jobtype'] = self.jobtypes
        self.map['config'] = self.configs
        self.map['pid'] = self.pids
        self.map['rstat'] = self.rstats
        self.df = DataFrame(self.map)
        
    def to_html(self):
        return self.df.to_html(index=False)
