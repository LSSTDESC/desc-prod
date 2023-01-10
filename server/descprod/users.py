
class UserData:
    """
    Holds the data for each user.
    """
    users = {} # Dictonary of active users indexed by descname.
    admins = ['dladams']
    @classmethod
    def get(cls, descname):
        if descname not in cls.users:
            cls.users[descname] = cls(descname)
        return cls.users[descname]
    def __init__(self, descname):
        self.descname = descname
        if descname is None: return None
        self.home_dir = f"/users/{descname}"
        self.run_dir = f"{self.home_dir}/rundirs"
        self.archive_dir = f"{self.home_dir}/archives"
        self.delete_dir = f"{self.home_dir}/deleted"
    def is_admin(self):
        return self.descname in UserData.admins
