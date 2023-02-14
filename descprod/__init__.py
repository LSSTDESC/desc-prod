# descprod
import importlib.metadata
__version__ = importlib.metadata.version('desc-prod')

def version():
  return __version__

from .utils      import timestamp
from .utils      import sdate
from .utils      import sduration
from .users      import UserData
from .jobs       import JobData
from .job_table  import JobTable
