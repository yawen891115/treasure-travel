# Private single-host web service; train artifacts separately and mount them read-only.
FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements-web.txt .
RUN pip install --no-cache-dir -r requirements-web.txt
RUN groupadd --gid 10001 app && useradd --uid 10001 --gid app --no-create-home app
COPY --chown=app:app . .
RUN mkdir -p /app/web_data && chown app:app /app/web_data
RUN DJANGO_DEBUG=1 DJANGO_SECRET_KEY=build-only AGENT_BACKEND=offline MAPS_MODE=offline python web/manage.py collectstatic --noinput
USER 10001:10001
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/healthz', timeout=3)"
# Run migrations explicitly before rollout. Do not race migrations in every worker start.
CMD ["gunicorn", "--chdir", "web", "travel_site.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "2", "--worker-class", "sync", "--timeout", "120", "--graceful-timeout", "30", "--access-logfile", "-", "--error-logfile", "-"]
