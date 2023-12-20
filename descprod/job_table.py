from descprod import sdate
from descprod import sduration
from descprod import JobData
from pandas import DataFrame

class JobTable:
    """
    Class to hold an format a TABLE of jobs.
    """

    def __init__(self, descname, arcs):
        self.descname = descname
        self.archives = arcs
        self.refresh()

    def refresh(self):
        self.jobs, self.error_message = JobData.get_jobs_from_db(self.descname, self.archives)
        if len(self.error_message): return
        self.archives = []
        self.jobids = []
        self.parents = []
        self.jobtypes = []
        self.configs = []
        self.howfigs = []
        self.sids = []
        self.pids = []
        self.hosts = []
        self.rundirs = []
        self.starts = []
        self.durations = []
        self.rstats = []
        self.errmsgs = []
        self.stamsgs = []
        self.ports = []
        for job in self.jobs.values():
            self.archives.append(job.archive())
            self.jobids.append(job.index())
            self.parents.append(job.parent())
            self.jobtypes.append(job.jobtype())
            self.configs.append(job.config())
            howfig = job.howfig()
            if howfig is None: howfig = ''
            self.howfigs.append(howfig)
            pid = job.pid()
            #if pid is None: pid = -1
            self.pids.append(pid)
            sid = job.session()
            self.sids.append(sid)
            host = job.host()
            if host is None or host == 'NULL': host = ''
            self.hosts.append(host)
            rundir = job.rundir()
            if not rundir or rundir == 'NULL': rundir = ''
            self.rundirs.append(rundir)
            rstat = job.return_status()
            #if rstat is None: rstat = -1
            self.rstats.append(rstat)
            errmsg = ''
            if len(job.errmsgs): errmsg = job.errmsgs[-1]
            self.errmsgs.append(errmsg)
            self.stamsgs.append(job.progress())
            stim = job.start_time()
            if stim is None: stim = job.create_time()
            sstim = sdate(stim, default='time-not-found')
            self.starts.append(sstim)
            self.durations.append(job.duration())
            self.ports.append(job.port())
        self.map = {}
        self.map['archive'] = self.archives
        self.map['id'] = self.jobids
        self.map['parent'] = self.parents
        self.map['jobtype'] = self.jobtypes
        self.map['config'] = self.configs
        self.map['howfig'] = self.howfigs
        self.map['pid'] = self.pids
        self.map['sid'] = self.sids
        self.map['start'] = self.starts
        self.map['duration'] = self.durations
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
        txt += '    <th>Archive</th>\n'
        txt += '    <th>ID</th>\n'
        txt += '    <th>Parent</th>\n'
        txt += '    <th>Type</th>\n'
        txt += '    <th>Configuration</th>\n'
        txt += '    <th>Howfig</th>\n'
        txt += '    <th>Session</th>\n'
        txt += '    <th>Create/start time</th>\n'
        txt += '    <th>Duration</th>\n'
        txt += '    <th>Host</th>\n'
        txt += '    <th>Run directory</th>\n'
        txt += '    <th>PID</th>\n'
        txt += '    <th>Port</th>\n'
        txt += '    <th>Rstat</th>\n'
        txt += '    <th style="text-align:left"></th>\n'
        txt += '  </tr>\n'
        txt += '<tbody>\n'
        usemenu = baseurl is not None
        for row in range(len(self.jobs)):
            archive = self.archives[row]
            jid = self.jobids[row]
            job = self.jobs[jid]
            sjid = str(jid)
            clsarg = ''
            if usemenu:
                clsarg = ' class="dropdown"'
                sjid = ''
                sjid += '<div>'
                sjid += f"""<button class="dropbtn">{jid}</button>"""
                sjid += '<div class="dropdown-content">'
                sjid += f"{job.dropdown_content(baseurl)}"
                sjid += '</div>'
                sjid += '</div>'
            parent = self.parents[row]
            sparent = '' if parent is None else str(parent)
            rstat = self.rstats[row]
            srstat = '' if rstat is None else str(rstat)
            host = self.hosts[row]
            rundir = self.rundirs[row]
            pid = self.pids[row]
            spid = '' if pid is None else str(pid)
            sid = self.sids[row]
            ssid = '' if sid is None else str(sid)
            port = self.ports[row]
            sport = '' if port is None else str(port)
            sport = '' if port is None or port <= 0 else str(port)
            stamsg = self.stamsgs[row]
            errmsg = self.errmsgs[row]
            msg = stamsg if len(stamsg) else errmsg if len(errmsg) else ''
            txt += f"    <td>{archive}</td>{eol}"
            txt += f"    <td{clsarg}>{sjid}</td>{eol}"
            txt += f"    <td>{sparent}</td>{eol}"
            txt += f"    <td>{self.jobtypes[row]}</td>{eol}"
            txt += f"    <td>{self.configs[row]}</td>{eol}"
            txt += f"    <td>{self.howfigs[row]}</td>{eol}"
            txt += f"    <td>{ssid}</td>{eol}"
            txt += f"    <td>{self.starts[row]}</td>{eol}"
            txt += f"    <td>{str(sduration(self.durations[row]))}</td>{eol}"
            txt += f"    <td>{host}</td>{eol}"
            txt += f"    <td>{rundir}</td>{eol}"
            txt += f"    <td>{spid}</td>{eol}"
            txt += f"    <td>{sport}</td>{eol}"
            txt += f"    <td>{srstat}</td>{eol}"
            txt += f"""    <td style="text-align:left">{msg}</td>{eol}"""
            txt +=  '  </tr>\n'
        txt += '</tbody>\n'
        txt += '</table>\n'
        return txt
