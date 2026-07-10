from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    email = models.EmailField(unique=True)
    email_verified = models.BooleanField(default=False)
    mfa_enabled = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class MFADevice(models.Model):
    user = models.ForeignKey(User)

    type = models.CharField(choices=[("totp", "TOTP"), ("webauthn", "WebAuthn")])

    secret = models.BinaryField()

    confirmed = models.BooleanField()


class ServiceAccount(AbstractUser):
    name = models.CharField(max_length=100)
    cer
