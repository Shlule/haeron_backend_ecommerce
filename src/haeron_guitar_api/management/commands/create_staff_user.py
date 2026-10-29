from getpass import getpass

from allauth.account.models import EmailAddress
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from authUser.services.roles import Roles


class Command(BaseCommand):
    help = "Create a staff account for the back-office (e-mail verified, MFA set up at the first login)."

    def add_arguments(self, parser):
        parser.add_argument("username")
        parser.add_argument("email")
        parser.add_argument("--role", default=Roles.ADMIN.value, choices=[r.value for r in Roles if r != Roles.CUSTOMER])

    @transaction.atomic
    def handle(self, *args, username, email, role, **options):
        User = get_user_model()
        if User.objects.filter(username=username).exists() or User.objects.filter(email=email).exists():
            raise CommandError("A user with this username or e-mail already exists.")

        password = getpass("Password: ")
        if not password or password != getpass("Password (again): "):
            raise CommandError("Passwords are empty or do not match.")

        user = User(username=username, email=email)
        user.set_password(password)
        user.save()
        user.groups.add(Group.objects.get_or_create(name=role)[0])
        EmailAddress.objects.create(user=user, email=email, verified=True, primary=True)

        self.stdout.write(self.style.SUCCESS(f"{username} created with the role {role}."))
