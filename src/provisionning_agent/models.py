from django.db import models
from django.conf import settings
import secrets, hashlib


class AgentType(models.TextChoices):
    NFC_PROVISIONING = "nfc_provisioning", "NFC Provisioning"
    ENGRAVING = "engraving", "Engraving"
    # futur: ajoutez ici tout nouveau type d'agent (ex: "packaging", "quality_control", ...)


class ProvisionningAgent(models.Model):
    name = models.CharField(max_length=100)
    key_hash = models.CharField(max_length=64, null=True, blank=True)  # vide tant que non enrôlé
    agent_type = models.CharField(
        max_length=30,
        choices=AgentType.choices,
        default=AgentType.NFC_PROVISIONING,
        help_text="Détermine les routes que cet agent a le droit d'appeler.",
    )

    is_active = models.BooleanField(default=False)  # actif seulement après enrôlement réussi
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)
    enrolled_at = models.DateTimeField(null=True)
    last_seen = models.DateTimeField(null=True)

    def __str__(self):
        return f"{self.name} ({self.agent_type})"

    @staticmethod
    def generate_token():
        token = secrets.token_urlsafe(32)
        return token, hashlib.sha256(token.encode()).hexdigest()


class AgentEnrollmentToken(models.Model):
    agent = models.OneToOneField(ProvisionningAgent, on_delete=models.CASCADE)
    token_hash = models.CharField(max_length=64)
    expires_at = models.DateTimeField()
    used = models.BooleanField(default=False)
    