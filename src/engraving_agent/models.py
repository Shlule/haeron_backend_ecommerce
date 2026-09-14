from django.db import models
from django.conf import settings
import secrets, hashlib


class EngravingAgent(models.Model):
    name = models.CharField(max_length=100)
    key_hash = models.CharField(max_length=64, null=True, blank=True)  # vide tant que non enrôlé
    is_active = models.BooleanField(default=False)  # actif seulement après enrôlement réussi
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)
    enrolled_at = models.DateTimeField(null=True)
    last_seen = models.DateTimeField(null=True)

    @staticmethod
    def generate_token():
        token = secrets.token_urlsafe(32)
        return token, hashlib.sha256(token.encode()).hexdigest()


class EngravingEnrollmentToken(models.Model):
    agent = models.OneToOneField(EngravingAgent, on_delete=models.CASCADE)
    token_hash = models.CharField(max_length=64)
    expires_at = models.DateTimeField()
    used = models.BooleanField(default=False)
    