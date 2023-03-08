# descprod
import importlib.metadata
__version__ = importlib.metadata.version('desc-prod')

def version():
  print(__version__)
  return 0

from .utils      import timestamp
from .utils      import sdate
from .utils      import sduration
from .utils      import get_login
from .users      import UserData
from .jobs       import JobData
from .job_table  import JobTable
from .get_job    import get_job
from .get_job    import get_job_main
from .start_job  import start_job
from .start_job  import start_job_main
