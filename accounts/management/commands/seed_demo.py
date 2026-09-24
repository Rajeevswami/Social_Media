"""Seed a small demo dataset for local development.

    python manage.py seed_demo            # creates 4 users + posts
    python manage.py seed_demo --flush    # wipe demo data first

Everything goes through the real service layer, so seeded posts are moderated
by the AI service exactly like real ones.
"""
from __future__ import annotations

from django.core.management.base import BaseCommand

from accounts.models import User
from posts.models import Post
from posts.services import create_post
from social.models import Comment, Follow, Like
from social.services import add_comment, toggle_follow, toggle_like

DEMO_PASSWORD = "DemoPass!234"

USERS = [
    ("rajeev", "rajeev@example.com", "Rajeev", "Building things with Django and too much chai."),
    ("ananya", "ananya@example.com", "Ananya", "Photographer. Monsoon enthusiast."),
    ("vikram", "vikram@example.com", "Vikram", "Backend dev. Postgres apologist."),
    ("meera", "meera@example.com", "Meera", "Designer. Coffee, grids, repeat."),
]

POSTS = [
    ("Shipped the new feed today. Small steps, real momentum. #build", True),
    ("Monsoon + cutting chai = perfect debugging weather.", True),
    ("Postgres index went from 900ms to 12ms. I am unbeatable today.", True),
    ("Redesigned the profile page. Less noise, more breathing room.", True),
    ("You are all idiots and losers, this app is trash", False),
]


class Command(BaseCommand):
    help = "Seed demo users, posts, follows and comments."

    def add_arguments(self, parser) -> None:
        parser.add_argument("--flush", action="store_true", help="Delete demo data first.")

    def handle(self, *args, **options):
        if options["flush"]:
            self.stdout.write("Flushing demo data…")
            Comment.objects.all().delete()
            Like.objects.all().delete()
            Follow.objects.all().delete()
            Post.objects.all().delete()
            User.objects.filter(username__in=[u[0] for u in USERS]).delete()

        people = []
        for username, email, display_name, bio in USERS:
            user, created = User.objects.get_or_create(
                username=username,
                defaults={"email": email, "display_name": display_name, "bio": bio},
            )
            if created:
                user.set_password(DEMO_PASSWORD)
                user.save()
                self.stdout.write(f"created @{username}")
            people.append(user)

        rajeev, ananya, vikram, meera = people
        for follower, followee in [(rajeev, ananya), (rajeev, vikram), (ananya, rajeev), (meera, rajeev)]:
            toggle_follow(follower, followee)

        created_posts = []
        for author, (content, _safe) in zip(
            [rajeev, ananya, vikram, meera, rajeev], POSTS, strict=True
        ):
            post = create_post(author=author, content=content)
            created_posts.append(post)
            self.stdout.write(f"post #{post.id} by @{author.username} -> {post.moderation_status}")

        if len(created_posts) >= 3:
            add_comment(ananya, created_posts[0], "Love the incremental approach!")
            add_comment(vikram, created_posts[0], "Ship it.")
            for post in created_posts[:3]:
                toggle_like(ananya, post)
                toggle_like(vikram, post)

        self.stdout.write(
            self.style.SUCCESS(
                f"Seeded {len(people)} users, {len(created_posts)} posts. "
                f"Log in as rajeev / {DEMO_PASSWORD}"
            )
        )
