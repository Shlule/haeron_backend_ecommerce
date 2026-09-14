import hashlib
import logging 
from django.utils import timezone
from django.core.cache import cache
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from rest_framework import status
from rest_framework.exceptions import AuthenticationFailed

from .models import EngravingAgent, EngravingEnrollmentToken
from .authentication import EngravingTokenAuthentication


logger = logging.getLogger(__name__)


class EngravingEnrollView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        token = request.data.get("bootstrap_token", "")

        # rate limit basique par IP, pour ne pas laisser un brute-force du token tourner librement
        ip = request.META.get("REMOTE_ADDR")
        rl_key = f"rl:enroll:{ip}"
        if cache.get(rl_key, 0) >= 10:
            raise AuthenticationFailed("Too many attempts")
        cache.set(rl_key, cache.get(rl_key, 0) + 1, timeout=300)

        token_hash = hashlib.sha256(token.encode()).hexdigest()
        try:
            enrollment = EngravingEnrollmentToken.objects.select_related("agent").get(
                token_hash=token_hash, used=False, expires_at__gt=timezone.now()
            )
        except EngravingEnrollmentToken.DoesNotExist:
            raise AuthenticationFailed("Token d'enrôlement invalide ou expiré")

        agent = enrollment.agent
        real_token, real_hash = EngravingAgent.generate_token()
        agent.key_hash = real_hash
        agent.is_active = True
        agent.enrolled_at = timezone.now()
        agent.save()

        enrollment.used = True
        enrollment.save()

        return Response({"agent_token": real_token, "agent_name": agent.name})
