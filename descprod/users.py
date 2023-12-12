import os
import pwd
import json
import subprocess

class UserData:
    """
    Holds the data for each user.
    """
    users = {} # Dictionary of active users indexed by descname.
    admins = ['dladams']
    jindent = 2
    jsep = (',', ': ')

    @classmethod
    def get(cls, descname):
        if descname not in cls.users:
            cls.users[descname] = cls(descname)
        return cls.users[descname]

    def __init__(self, descname='nologin'):
        self.descname = descname
        self.uid = None
        self.gid = None
        if descname is None: return None
        self.home_dir = f"/users/{descname}"
        self.run_dir = f"{self.home_dir}/rundirs"
        self.archive_dir = f"{self.home_dir}/archives"
        self.delete_dir = f"{self.home_dir}/deleted"
        self.jobtype = ''
        self.config = ''
        self.howfig = ''

    def __str__(self):
        if self.descname is None:
            return '<Unauthenticated>'
        return self.descname

    def is_admin(self):
        return self.descname in UserData.admins

    def check_dirs(self):
        """
        Check the linux user is defined has has consistent uid/gid and
        check the run, archive and delete directories are present.
        If missing the user and directories are created.
        Returns a tuple (rstat, msgs) with rsat = 0 for success and
        msgs a list of ERROR and INFO messsages.
        """
        myname = 'UserData:check_dirs'
        errmsgs = []
        if self.descname == 'nologin': return  (0, errmsgs)
        if self.uid is None:
            # Fetch the linux user data.
            try:
                pwi = list(pwd.getpwnam(self.descname))
                errmsgs.append(f"{myname}: INFO: Found existing user {self.descname}")
            # If absent, add the linux user.
            except KeyError:
                com = ['descprod-adduser', self.descname]
                # Fetch the persistent map and add group to the command if present.
                jmap = {}
                jpwi = None
                jnam = '/home/descprod/local/etc/linux_users.json'
                if os.path.exists(jnam):
                    with open(jnam, 'r') as jfil:
                        jmap = json.load(jfil)
                    if self.descname in jmap:
                        jpwi = jmap[self.descname]
                        suid = str(jpwi[2])
                        com.append(suid)
                        errmsgs.append(f"{myname}: INFO: Keeping uid {suid}")
                # Run the command to add the user.
                print(com)
                ret = subprocess.run(com, capture_output=True)
                if ret.returncode:
                    errmsgs.append(f"{myname}: ERROR: Unable to create user {self.descname}")
                    for line in ret.stdout.decode().split('\n'):
                        if len(line): errmsgs.append(f"{myname}:   INFO: {line}")
                    for line in ret.stderr.decode().split('\n'):
                        if len(line): errmsgs.append(f"{myname}:   ERROR: {line}")
                    return (1, errmsgs)
                pwi = list(pwd.getpwnam(self.descname))
                errmsgs.append(f"{myname}: INFO: Added linux user {self.descname}")
                # If the user was not in the persistent map, add him or her.
                # We want the user and group IDs to stay the same.
                if jpwi is None:
                    jmap[self.descname] = pwi
                    with open(jnam, 'w') as jfil:
                        json.dump(jmap, jfil, separators=UserData.jsep, indent=UserData.jindent)
                # otherwise makew sure the new and old data are consistent.
                else:
                    if pwi != jpwi:
                        errmsgs.append(f"{myname}: ERROR: Current and archived user data differ:")
                        errmsgs.append(f"{myname}: ERROR:   {pwi}")
                        errmsgs.append(f"{myname}: ERROR:   {jpwi}")
                        return (2, errmsgs)
            self.uid = pwi[2]
            self.gid = pwi[3]
        errmsgs.append(f"{myname}: INFO: User {self.descname} has uid {self.uid} and gid {self.gid}")
        # Check the directories.
        if not os.path.isdir(self.home_dir):
            errmsgs.append(f"{myname}: ERROR: Home directory not found: {self.home_dir}")
            return (3, errmsgs)
        self.check_and_make_dir(    self.run_dir,     'run', myname, errmsgs)
        self.check_and_make_dir(self.archive_dir, 'archive', myname, errmsgs)
        self.check_and_make_dir( self.delete_dir,  'delete', myname, errmsgs)
        rstat = 0
        for line in errmsgs:
             if line.find('ERROR')>=0: ++rstat
        return (rstat, errmsgs)

    def run(self, com, saveout=True, shell=True):
        """Run a command as the user descname in a bash login shell."""
        pre = ['sudo', 'sudo', '-u', self.descname]
        if shell:
            pre += ['bash', '-login', '-c']
        if isinstance(com, list):
            coms = com
            shcom = ' '.join(com)
        else:
            coms = com.split()
            shcom = com
        if shell:
            runcom = pre + [shcom]
        else:
            runcom = pre + coms
        return subprocess.run(runcom, capture_output=saveout)

    def mkdir(self, dnam):
        """
        Create a directory and return (rstat, msgs).
        For sucess rstat is 0.
        Error message prepended with pfx are in msgs.
        """
        ret = self.run(['mkdir', dnam])
        rstat = ret.returncode
        errmsgs = []
        if rstat:
            errmsgs.append(f"COMMAND: {ret.args}")
            for line in ret.stdout.decode().split('\n'):
                if len(line): errmsgs.append(f"STDOUT: {line}")
            for line in ret.stderr.decode().split('\n'):
                if len(line): errmsgs.append(f"STDERR: {line}")
        return (rstat, errmsgs)

    def check_and_make_dir(self, dnam, lab, myname, errmsgs):
        if not os.path.isdir(dnam):
            ret = self.mkdir(dnam)
            if ret[0]:
                errmsgs.append(f"{myname}: ERROR: Unable to create {lab} directory: {dnam}")
                for line in ret[1]:
                    errmsgs.append(f"{myname}:   {line}")
            else:
                if not os.path.isdir(self.run_dir):
                    errmsgs.append(f"{myname}: ERROR: After creation, {lab} directory not found: {dnam}")
