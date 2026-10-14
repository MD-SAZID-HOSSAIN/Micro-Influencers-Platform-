"""manage.py, wsgi and celery must fail closed: with nothing configured they pick PRODUCTION settings.

Before this, they defaulted to the development settings, so a deployment that forgot one environment
variable ran with DEBUG on and a SECRET_KEY that is written in the repository (which is also the key
that signs login tokens).
"""
import os
import subprocess
import sys
from pathlib import Path

import pytest

from config.bootstrap import configure

BASE_DIR = Path(__file__).resolve().parents[3]


def _clean_env(tmp_path, **extra):
    """An environment with no settings module and no secret, and a .env that does not exist."""
    env = {k: v for k, v in os.environ.items() if k not in ("DJANGO_SETTINGS_MODULE", "SECRET_KEY")}
    env["DOTENV_PATH"] = str(tmp_path / "does-not-exist.env")
    env.update(extra)
    return env


def _run(args, env):
    return subprocess.run(
        [sys.executable, *args], cwd=BASE_DIR, env=env, capture_output=True, text=True, timeout=120
    )


# ---- the helper ---------------------------------------------------------------------------------


def test_configure_defaults_to_production(monkeypatch, tmp_path):
    monkeypatch.delenv("DJANGO_SETTINGS_MODULE", raising=False)
    monkeypatch.setenv("DOTENV_PATH", str(tmp_path / "missing.env"))

    configure()

    assert os.environ["DJANGO_SETTINGS_MODULE"] == "config.settings.prod"


def test_a_dotenv_file_can_opt_in_to_development(monkeypatch, tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text("DJANGO_SETTINGS_MODULE=config.settings.dev\n", encoding="utf-8")
    monkeypatch.delenv("DJANGO_SETTINGS_MODULE", raising=False)
    monkeypatch.setenv("DOTENV_PATH", str(env_file))

    configure()

    assert os.environ["DJANGO_SETTINGS_MODULE"] == "config.settings.dev"


def test_the_real_environment_always_beats_the_dotenv_file(monkeypatch, tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text("DJANGO_SETTINGS_MODULE=config.settings.dev\n", encoding="utf-8")
    monkeypatch.setenv("DJANGO_SETTINGS_MODULE", "config.settings.prod")
    monkeypatch.setenv("DOTENV_PATH", str(env_file))

    configure()

    assert os.environ["DJANGO_SETTINGS_MODULE"] == "config.settings.prod"


# ---- the real entry points -----------------------------------------------------------------------


@pytest.mark.parametrize(
    "args",
    [
        ["-c", "import config.wsgi"],
        ["-c", "import config.celery as c; c.app.conf.broker_url"],
        ["manage.py", "check"],
    ],
    ids=["wsgi", "celery", "manage.py"],
)
def test_entry_points_refuse_to_start_when_nothing_is_configured(tmp_path, args):
    result = _run(args, _clean_env(tmp_path))

    assert result.returncode != 0
    assert "SECRET_KEY" in result.stderr  # production's own safety check is what stopped it


def test_development_is_still_available_when_asked_for_explicitly(tmp_path):
    env = _clean_env(tmp_path, DJANGO_SETTINGS_MODULE="config.settings.dev")

    result = _run(["manage.py", "check"], env)

    assert result.returncode == 0, result.stderr


def test_the_settings_read_the_same_dotenv_file_as_the_entry_points(tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text("DJANGO_SETTINGS_MODULE=config.settings.dev\nSECRET_KEY=from-the-dotenv-file\n", encoding="utf-8")
    env = _clean_env(tmp_path, DOTENV_PATH=str(env_file))

    script = (
        "import config, django; django.setup(); "  # importing config runs the bootstrap
        "from django.conf import settings; print(settings.DEBUG, settings.SECRET_KEY)"
    )

    result = _run(["-c", script], env)

    assert result.returncode == 0, result.stderr
    assert result.stdout.split() == ["True", "from-the-dotenv-file"]
