"""Decides which Django settings a process starts with. Used by manage.py, wsgi and celery.

The default is PRODUCTION. A process that forgets to say which settings it wants must not quietly
come up in development mode (DEBUG on, and a SECRET_KEY that is written in the repository), so
development is something you ask for: put ``DJANGO_SETTINGS_MODULE=config.settings.dev`` in your
``.env`` (the example file already does) or export it.

``DOTENV_PATH`` points at a different env file; it exists mainly so tests can run without one.
"""
import os
from pathlib import Path

import environ

BASE_DIR = Path(__file__).resolve().parent.parent
DEFAULT_SETTINGS_MODULE = "config.settings.prod"


def load_dotenv() -> None:
    """Read the .env file if there is one. Variables that are already set always win."""
    path = Path(os.environ.get("DOTENV_PATH") or BASE_DIR / ".env")
    if path.is_file():
        environ.Env.read_env(str(path))  # does not overwrite variables already in the environment


def configure() -> None:
    load_dotenv()
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", DEFAULT_SETTINGS_MODULE)
