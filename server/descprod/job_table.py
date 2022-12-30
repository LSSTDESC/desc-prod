from descprod import JobData
from pandas import DataFrame

class JobTable
    """
    Class to hold an format a TABLE of jobs.
    """

    def __init(self, descname=None):
        self.descname = descname
        self.refresh()

    def refresh(self):
        self.jobs = JobData.get_jobs()
        self.jobids = []
        self.jobtypes = []
        self.configs = []
        for job in self.jobs.values():
            self.jobids.append(job.id)
            self.jobtypes.append(job.jobtype)
            self.configs.append(job.config)
        self.map = {}
        self.map['id'] = self.jobids
        self.map['jobtype'] = self.jobtypes
        self.map['config'] = self.configs
        delf.df = DataFrame(self.map)
        
