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

# There is deliberately NO Docker HEALTHCHECK here. This one image also runs the Celery worker and
# beat, which listen on no port; a web probe baked into the image would mark them unhealthy for good.
# The probe lives on the `web` service in docker-compose.yml. On another platform, point its HTTP
# health check at GET /api/v1/health/ on the web container only (send a Host header from ALLOWED_HOSTS).

CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3", "--access-logfile", "-"]
