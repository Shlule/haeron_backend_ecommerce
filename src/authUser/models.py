from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    email = models.EmailField("email address", unique=True, null=False, blank=False)
    is_email_verified = models.BooleanField(default=False)
    is_2fs_enabled = models.BooleanField(default=False)

    def __str__(self):
        return self.username
