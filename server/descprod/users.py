import os
import pwd
import json
import subprocess

class UserData:
    """
    Holds the data for each user.
    """
    users = {} # Dictonary of active users indexed by descname.
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

    def is_admin(self):
        return self.descname in UserData.admins

    def check_dirs(self):
        """
        Check the linux user is defined has has consistent uid/gid and
        check the run, archive and delete directories are present.
        If missing the user and directories are created.
        Returns a list of error messages on failure.
        Success returns an empty list.
        """
        myname = 'UserData:check_dirs'
        errmsgs = []
        if self.descname == 'nologin': return  errmsgs
        if self.uid is not None:
            # Fetch the linux user data.
            try:
                pwi = pwd.getpwnam(descname)
            # If absent, add the linux user.
            except KeyError:
                com = ['descprod-adduser', self.usr.descname]
                # Fetch the persistent map and add group to the command if present.
                jmap = None
                jpwi = None
                jnam = '/etc/linux_users.json'
                if os.path.exists(jnam):
                    with open(jnam, 'r') as jfil:
                        jmap = json.load(jfil)
                    if self.descname in jmap:
                        jpwi = jmap[self.descname]
                        uid = jpwi['pw_uid']
                        com.append(self.uid)
                # Run the command to add the user.
                ret = subprocess.run(com)
                if ret.returncode:
                    errmsgs.append(f"{myname}: ERROR: Unable to create user {self.descname}")
                    return errmsgs
                pwi = pwd.getpwnam(descname)
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
                        errmsgs.append(f"{myname}:   {pwi}")
                        errmsgs.append(f"{myname}:   {jwi}")
                        return errmsgs
            self.uid = pwi['pw_uid']
            self.gid = pwi['pw_gid']
        # Check the directories.
        if not os.path.isdir(self.home_dir):
            errmsgs.append(f"{myname}: Home directory not found: {self.home_dir}")
            return errmsgs
        if not os.path.isdir(self.run_dir):
            #os.mkdir(self.run_dir)
            if self.mkdir(self.run_dir):
                errmsgs.append(f"{myname}: Unable to create run directory not found: {self.run_dir}")
            else if not os.path.isdir(self.run_dir):
                errmsgs.append(f"{myname}: Run directory not found: {self.run_dir}")
        if not os.path.isdir(self.archive_dir):
            os.mkdir(self.archive_dir)
            if not os.path.isdir(self.archive_dir):
                errmsgs.append(f"{myname}: Archive directory not found: {self.archive_dir}")
        if not os.path.isdir(self.delete_dir):
            os.mkdir(self.delete_dir)
            if not os.path.isdir(self.delete_dir):
                errmsgs.append(f"{myname}: Delete directory not found: {self.delete_dir}")
        return errmsgs

    def run(self, com, saveout=True):
        """Run a command as the user descname."""
        pre = ['sudo', 'sudo', '-u', self.descname]
        if isinstance(com, list):
            coms = com
        else:
            coms = [com]
        runcom = pre + coms
        return subprocess.run(runcom, capture_output=saveout)

    def mkdir(self), dir):
        return self.run('mkdir', dir)
