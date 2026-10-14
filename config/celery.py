from celery import Celery

from config.bootstrap import configure

configure()  # production settings unless the environment says otherwise

app = Celery("config")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()
