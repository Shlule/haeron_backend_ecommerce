import hashlib
import logging 
from django.utils import timezone
from django.core.cache import cache
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework import status
from rest_framework.exceptions import AuthenticationFailed, PermissionDenied, NotFound

from .models import ProvisionningAgent, AgentEnrollmentToken
from .authentication import AgentTokenAuthentication

from haeron_guitar_api.part.part_service import PartService
from haeron_guitar_api.models import Part
from .selectors import get_part_for_verification, build_verification_response, verification_response_to_dict

logger = logging.getLogger(__name__)


class AgentEnrollView(APIView):
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
            enrollment = AgentEnrollmentToken.objects.select_related("agent").get(
                token_hash=token_hash, used=False, expires_at__gt=timezone.now()
            )
        except AgentEnrollmentToken.DoesNotExist:
            raise AuthenticationFailed("Token d'enrôlement invalide ou expiré")

        agent = enrollment.agent
        real_token, real_hash = ProvisionningAgent.generate_token()
        agent.key_hash = real_hash
        agent.is_active = True
        agent.enrolled_at = timezone.now()
        agent.save()

        enrollment.used = True
        enrollment.save()

        return Response({"agent_token": real_token, "agent_name": agent.name})


class ProvisionIdentityView(APIView):
    authentication_classes = [AgentTokenAuthentication]
    permission_classes = []

    def post(self, request):
        agent: ProvisionningAgent = request.user
        serial_number = request.data["serial_number"]
        part = request.data["part_uuid"]
        
        print(")"*50)
        print(request.data)
        print(part)

        # quota atomique, comme vu précédemment — avant d'appeler le service,
        # pour ne jamais dériver une clé sans qu'elle compte dans le quota
        #TODO - a mettre en place pour plus tard
        # with transaction.atomic():
        #     updated = ProvisioningAgent.objects.filter(
        #         pk=agent.pk, tags_provisioned__lt=F("tag_quota")
        #     ).update(tags_provisioned=F("tags_provisioned") + 1)
        #     if not updated:
        #         raise PermissionDenied("Quota de provisioning atteint pour cet agent")

        # try:
        tag_id, tag_key = PartService.provideNFCIdentity(serial_number, part)
        # except PartIdentityAlreadyProvisioned:
        #     # idempotence : l'agent a peut-être retenté après une coupure réseau
        #     existing = part.part_identities.filter(status__in=("pending", "active")).first()
        #     return Response({"tag_id": str(existing.tag_id), "already_provisioned": True})
        # except PartIdentityMismatch as e:
        #     raise PermissionDenied(str(e))

        # logger.info("Identité NFC générée pour part %s par agent %s", serial_number, agent.name)

        if tag_id and tag_key:
            return Response({"tag_id": str(tag_id), "tag_key": tag_key.hex()})
        return None
# class GetPartInfo(APIView):
#     authentication_classes = [AgentTokenAuthentication]
#     permission_classes= []
    
#     def get(self, request, serial_number):
#         part = Part.objects.filter(serial_number = serial_number).first()
#         return Response({
#                     "uuid": str(part.uuid),
#                     "serial_number": part.serial_number,
#                     "part_model": str(part.part_model.uuid),
#                     "batch": str(part.batch.uuid),
#                 })

class GetPartInfo(APIView):
    authentication_classes = [AgentTokenAuthentication]
    permission_classes = []

    def get(self, request, serial_number):
        part = get_part_for_verification(serial_number)
        if part is None:
            return Response(
                {
                    "status": "failed",
                    "detail": "Part not found.",
                },
                status=status.HTTP_404_NOT_FOUND,
            )


        response_dto = build_verification_response(
            part=part,
        )

        return Response(
            verification_response_to_dict(response_dto),
            status=status.HTTP_200_OK,
        )