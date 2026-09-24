"""Project package.

The Celery app is imported here so that ``@shared_task`` decorated functions in
any installed app are registered as soon as Django loads.
"""
from social_media.celery import app as celery_app

__all__ = ("celery_app",)
