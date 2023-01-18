from descprod import sdate
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
        self.jobs = JobData.get_jobs(self.descname)
        self.jobids = []
        self.jobtypes = []
        self.configs = []
        self.pids = []
        self.starts = []
        self.rstats = []
        self.errmsgs = []
        self.stamsgs = []
        for job in self.jobs.values():
            self.jobids.append(job.id)
            self.jobtypes.append(job.jobtype)
            self.configs.append(job.config)
            pid = job.pid
            #if pid is None: pid = -1
            self.pids.append(pid)
            rstat = job.get_return_status()
            #if rstat is None: rstat = -1
            self.rstats.append(rstat)
            errmsg = ''
            if len(job.errmsgs): errmsg = job.errmsgs[-1]
            self.errmsgs.append(errmsg)
            self.stamsgs.append(job.get_status_message())
            sstim = sdate(job.get_start_time())
            self.starts.append[sstim]
        self.map = {}
        self.map['id'] = self.jobids
        self.map['jobtype'] = self.jobtypes
        self.map['config'] = self.configs
        self.map['pid'] = self.pids
        self.map['start'] = self.starts
        self.map['rstat'] = self.rstats
        self.map['msg'] = self.errmsgs
        self.df = DataFrame(self.map)
        
    def to_html(self, baseurl=None):
        """
        Return the table in html.
        If baseurl is provided the table includes a dropdown menu to archive
        or delete jobs.
        """
        #return self.df.to_html(index=False, border=0, classes=['dropdown'])
        eol = '\n'
        txt = '<table border ="0" class="dataframe">\n'
        txt += '<thead>\n'
        txt += '  <tr style="text-align:right;">\n'
        txt += '    <th>ID</th>\n'
        txt += '    <th>Type</th>\n'
        txt += '    <th>Configuration</th>\n'
        txt += '    <th>PID</th>\n'
        txt += '    <th>Rstat</th>\n'
        txt += '    <th style="text-align:left"></th>\n'
        txt += '  </tr>\n'
        txt += '<tbody>\n'
        usemenu = baseurl is not None
        for row in range(len(self.jobs)):
            jid = self.jobids[row]
            job = self.jobs[jid]
            sid = str(jid)
            clsarg = ''
            if usemenu:
                clsarg = ' class="dropdown"'
                sid = ''
                sid += '<div>'
                sid += f"""<button class="dropbtn">{jid}</button>"""
                sid += '<div class="dropdown-content">'
                sid += f"{job.dropdown_content(baseurl)}"
                sid += '</div>'
                sid += '</div>'
            rstat = self.rstats[row]
            srstat = '' if rstat is None else str(rstat)
            pid = self.pids[row]
            spid = '' if pid is None else str(pid)
            stamsg = self.stamsgs[row]
            errmsg = self.errmsgs[row]
            msg = stamsg if len(stamsg) else errmsg if len(errmsg) else ''
            txt += f"""    <td{clsarg}>{sid}</td>{eol}"""
            txt += f"    <td>{self.jobtypes[row]}</td>{eol}"
            txt += f"    <td>{self.configs[row]}</td>{eol}"
            txt += f"    <td>{spid}</td>{eol}"
            txt += f"    <td>{srstat}</td>{eol}"
            txt += f"""    <td style="text-align:left">{msg}</td>{eol}"""
            txt +=  '  </tr>\n'
        txt += '</tbody>\n'
        txt += '</table>\n'
        return txt
