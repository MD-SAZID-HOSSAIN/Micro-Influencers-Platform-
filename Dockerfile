# Production image for the API, the Celery worker and Celery beat (same image, different command).
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    DJANGO_SETTINGS_MODULE=config.settings.prod

WORKDIR /app

# Dependencies first, so code changes do not reinstall them.
COPY requirements/base.txt requirements/base.txt
RUN pip install -r requirements/base.txt

COPY . .

# Never run as root.
RUN useradd --create-home --uid 10001 app && chown -R app:app /app
USER app

EXPOSE 8000

# The probe sends a real Host header because ALLOWED_HOSTS rejects 127.0.0.1 in production.
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import os, urllib.request; host = os.environ['ALLOWED_HOSTS'].split(',')[0]; urllib.request.urlopen(urllib.request.Request('http://127.0.0.1:8000/api/v1/health/', headers={'Host': host}), timeout=4)"

CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3", "--access-logfile", "-"]
