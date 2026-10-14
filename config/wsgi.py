from config.bootstrap import configure

configure()  # production settings unless the environment says otherwise

from django.core.wsgi import get_wsgi_application  # noqa: E402

application = get_wsgi_application()
