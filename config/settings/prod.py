from .base import *  # noqa: F401,F403
from .base import SECRET_KEY

DEBUG = False

if not SECRET_KEY:
    raise RuntimeError("SECRET_KEY must be set in the environment for production.")
