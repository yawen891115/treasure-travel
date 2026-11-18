"""Entry point for gunicorn: gunicorn --chdir web travel_site.wsgi:application"""

import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "travel_site.settings")
application = get_wsgi_application()
