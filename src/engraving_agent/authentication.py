import hashlib
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed
from django.utils import timezone
from .models import EngravingAgent


class EngravingTokenAuthentication(BaseAuthentication):
    def authenticate(self, request):
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return None
        cleaned_token = auth_header.removeprefix("Bearer ").strip(" ")
        token_hash = hashlib.sha256(cleaned_token.encode()).hexdigest()
        try:
            agent = EngravingAgent.objects.get(key_hash=token_hash, is_active=True)
        except EngravingAgent.DoesNotExist:
            raise AuthenticationFailed("Invalid agent token")
        agent.last_seen = timezone.now()
        agent.save(update_fields=["last_seen"])
        return (agent, None)