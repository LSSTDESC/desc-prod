
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
    def is_admin(self):
        return self.descname in UserData.admins
