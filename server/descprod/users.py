class UserData:
    """
    Holds the data for each user.
    """
    users = {} # Dictonary of active users indexed by descname.
    @classmethod
    def get(cls, descname):
        if descname not in cls.users:
            cls.users[descname] = cls(descname)
        return cls.users[descname]
    def __init__(self, descname):
        self.descname = descname
        self.jobs = {}   # Dictionary of jobs indexed by job ID
