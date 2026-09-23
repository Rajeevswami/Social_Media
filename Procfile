web: gunicorn social_media.wsgi --bind 0.0.0.0:$PORT --workers 3 --threads 2
worker: celery -A social_media worker -l info -Q default,ai --concurrency 2
beat: celery -A social_media beat -l info
