import hashlib
import logging
import uuid as uuid_lib
from django.utils import timezone
from django.core.cache import cache
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from rest_framework import status
from rest_framework.exceptions import AuthenticationFailed, ValidationError

from .models import ProvisionningAgent, AgentEnrollmentToken, AgentType
from .authentication import AgentTokenAuthentication
from .permissions import agent_type_permission

from haeron_guitar_api.part.part_service import PartService
from provisionning_agent.engraving_service import EngravingService
from .selectors import get_part_for_verification, build_verification_response, verification_response_to_dict
from haeron_guitar_api.models import Part, PartEngravingMark, PartNFCIdentity

logger = logging.getLogger(__name__)

ALLOWED_CONFIRM_STATUSES = {"confirmed", "failed"}
VALID_MARK_TYPES = {choice[0] for choice in PartEngravingMark._meta.get_field("mark_type").choices}
MAX_CONFIRM_BATCH_SIZE = 1000


def _refuse(code, detail: str) -> Response:
    """Refusal with its reason, shown by the agent."""
    logger.warning("Provisioning refusé : %s", detail)
    return Response({"detail": detail}, status=code)


def _parse_uuid(value, field_name: str) -> uuid_lib.UUID:
    """Convertit en UUID ou lève un 400 (au lieu d'un 500 sur valeur mal formée)."""
    try:
        return uuid_lib.UUID(str(value))
    except (ValueError, AttributeError, TypeError):
        raise ValidationError({field_name: f"UUID invalide : {value!r}"})


# ============================================================
# Enrôlement — commun à tous les agents, pas de cloisonnement ici
# ============================================================

class AgentEnrollView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        token = request.data.get("bootstrap_token", "")

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

        return Response({"agent_token": real_token, "agent_name": agent.name, "agent_type": agent.agent_type})


# ============================================================
# NFC — réservé aux agents agent_type="nfc_provisioning"
# ============================================================

class ProvisionIdentityView(APIView):
    authentication_classes = [AgentTokenAuthentication]
    permission_classes = [agent_type_permission(AgentType.NFC_PROVISIONING)]

    def post(self, request):
        agent: ProvisionningAgent = request.user
        serial_number = request.data.get("serial_number")
        nfc_uid = request.data.get("nfc_uid")
        initial_counter = request.data.get("initial_counter")
        if not serial_number or not nfc_uid:
            raise ValidationError({"detail": "serial_number et nfc_uid sont obligatoires."})
        part_uuid = _parse_uuid(request.data.get("part_uuid"), "part_uuid")

        # the refusals are checked here, so the agent gets a clear reason and not a 500
        part = Part.objects.filter(serial_number=serial_number).first()
        if part is None:
            return _refuse(status.HTTP_404_NOT_FOUND, f"Aucune pièce avec le numéro de série {serial_number}.")
        if part.uuid != part_uuid:
            return _refuse(
                status.HTTP_400_BAD_REQUEST,
                f"Le numéro de série {serial_number} et l'UUID {part_uuid} ne désignent pas la même pièce.",
            )
        active = PartNFCIdentity.objects.filter(part=part, status="active").first()
        if active is not None:
            return _refuse(
                status.HTTP_409_CONFLICT,
                f"La pièce {serial_number} a déjà un tag actif (UID {active.nfc_uid}) : révoque-le avant de reprogrammer.",
            )
        if part.batch_id is None:
            return _refuse(status.HTTP_409_CONFLICT, f"La pièce {serial_number} n'a pas de lot : pas de clé possible.")

        # rewrite = this physical tag was already written (its keys and file settings are no longer the factory ones).
        # A new tag replacing a broken one is not a rewrite, even if the part had a tag before.
        already_provisioned = PartNFCIdentity.objects.filter(nfc_uid=nfc_uid).exists()
        try:
            result = PartService.provideNFCIdentity(
                serial_number, str(part_uuid), nfc_uid_p=nfc_uid, initial_counter=initial_counter
            )
        except Exception as e:
            logger.exception("Clé NFC impossible à générer pour %s", serial_number)
            return _refuse(
                status.HTTP_500_INTERNAL_SERVER_ERROR,
                f"Clé NFC impossible à générer ({e.__class__.__name__}) : vérifie Vault et les clés du modèle et du lot.",
            )
        tag_key = result.get("tag_key")
        old_tag_key = result.get("old_tag_key")
        if tag_key is None or old_tag_key is None:
            return _refuse(status.HTTP_409_CONFLICT, f"Le backend a refusé de générer une clé pour {serial_number}.")

        logger.info("Identité NFC générée pour part %s par agent %s", serial_number, agent.name)
        return Response(
            {
                "tag_key": tag_key.hex(),
                "old_tag_key": old_tag_key.hex(),
                "version": result.get("version"),
                "is_rewrite": already_provisioned,
            }
        )


class ConfirmProvisionningView(APIView):
    authentication_classes = [AgentTokenAuthentication]
    permission_classes = [agent_type_permission(AgentType.NFC_PROVISIONING)]

    def post(self, request):
        agent: ProvisionningAgent = request.user
        serial_number = request.data["serial_number"]
        part = request.data["part_uuid"]
        nfc_uid = request.data["nfc_uid"]

        result = PartService.confirmNFCIdentity(serial_number, part, nfc_uid)
        return Response(result, status=status.HTTP_200_OK)


class RevokeProvisionningView(APIView):
    authentication_classes = [AgentTokenAuthentication]
    permission_classes = [agent_type_permission(AgentType.NFC_PROVISIONING)]

    def post(self, request):
        agent: ProvisionningAgent = request.user
        serial_number = request.data["serial_number"]
        part = request.data["part_uuid"]
        nfc_uid = request.data["nfc_uid"]

        result = PartService.revokeNFCIdentity(serial_number, part, nfc_uid)
        return Response(result, status=status.HTTP_200_OK)


# ============================================================
# Gravure — réservé aux agents agent_type="engraving"
# ============================================================

class EngravingFetchView(APIView):
    """
    POST /agents/engraving/fetch/
    Réserve les pièces à graver et les retourne groupées par template
    (un groupe = un CSV LightBurn côté agent).

    Body (tous optionnels) : {"mark_type": "...", "part_model_uuid": "...", "limit": 50}
    """
    authentication_classes = [AgentTokenAuthentication]
    permission_classes = [agent_type_permission(AgentType.ENGRAVING)]

    def post(self, request):
        agent: ProvisionningAgent = request.user

        mark_type = request.data.get("mark_type") or None
        if mark_type is not None and mark_type not in VALID_MARK_TYPES:
            raise ValidationError({"mark_type": f"Valeur invalide : {mark_type!r}. Attendu : {sorted(VALID_MARK_TYPES)}"})

        part_model_uuid = request.data.get("part_model_uuid")
        if part_model_uuid is not None:
            part_model_uuid = _parse_uuid(part_model_uuid, "part_model_uuid")

        limit = request.data.get("limit")
        if limit is not None:
            try:
                limit = int(limit)
            except (TypeError, ValueError):
                raise ValidationError({"limit": "Doit être un entier."})
            if limit < 1:
                raise ValidationError({"limit": "Doit être >= 1."})

        grouped = EngravingService.reserve_pending_marks(
            mark_type=mark_type, part_model_uuid=part_model_uuid, limit=limit,
        )

        keys = {}  # Vault read once per part model for the hidden codes
        templates_payload = [
            {
                "template_uuid": str(template.uuid),
                "template_name": template.name,
                "mark_type": template.mark_type,
                "location": template.location,
                "lightburn_project_path": template.lightburn_project_path,
                "variable_columns": template.variable_columns,
                "marks": [
                    {
                        "mark_uuid": str(mark.uuid),
                        "part_uuid": str(mark.part_id),
                        "serial_number": mark.part.serial_number,
                        "mark_type": mark.mark_type,
                        "value": EngravingService.engraving_value(mark, keys),
                        "location": mark.location,
                    }
                    for mark in marks
                ],
            }
            for template, marks in grouped.items()
            if marks
        ]

        total_marks = sum(len(t["marks"]) for t in templates_payload)
        logger.info("Fetch gravure par agent %s : %d marque(s) réservée(s)", agent.name, total_marks)

        return Response({"templates": templates_payload})


class EngravingConfirmView(APIView):
    """
    POST /agents/engraving/confirm/
    Body : {"results": [{"mark_uuid": "...", "status": "confirmed"|"failed", "description": "..."}]}
    """
    authentication_classes = [AgentTokenAuthentication]
    permission_classes = [agent_type_permission(AgentType.ENGRAVING)]

    def post(self, request):
        agent: ProvisionningAgent = request.user

        raw_results = request.data.get("results")
        if not isinstance(raw_results, list) or not raw_results:
            raise ValidationError({"results": "Doit être une liste non vide."})
        if len(raw_results) > MAX_CONFIRM_BATCH_SIZE:
            raise ValidationError({"results": f"Maximum {MAX_CONFIRM_BATCH_SIZE} résultats par appel."})

        results = []
        for i, item in enumerate(raw_results):
            if not isinstance(item, dict):
                raise ValidationError({"results": f"Élément {i} : objet attendu."})

            mark_uuid = _parse_uuid(item.get("mark_uuid"), f"results[{i}].mark_uuid")

            item_status = item.get("status")
            if item_status not in ALLOWED_CONFIRM_STATUSES:
                raise ValidationError({f"results[{i}].status": f"Doit être l'un de {sorted(ALLOWED_CONFIRM_STATUSES)}."})

            description = item.get("description") or ""
            if not isinstance(description, str):
                raise ValidationError({f"results[{i}].description": "Doit être une chaîne."})

            results.append({"mark_uuid": str(mark_uuid), "status": item_status, "description": description})

        outcomes = EngravingService.confirm_marks(results)

        n_ok = sum(1 for o in outcomes if o["ok"])
        logger.info("Confirm gravure par agent %s : %d/%d résultat(s) appliqué(s)", agent.name, n_ok, len(outcomes))

        return Response({"results": outcomes})


# ============================================================
# Vérification publique — inchangée, aucun agent impliqué
# ============================================================

class VerifyPart(APIView):
    authentication_classes = []
    permission_classes = []

    def post(self, request):
        serial_number = request.data.get("serial_number")
        cmac = request.data.get("cmac")
        nfc_uid = request.data.get("nfc_uid")
        tag_counter = request.data.get("tag_counter")

        part = get_part_for_verification(serial_number)
        if part is None:
            return Response({"status": "failed", "detail": "Part not found."}, status=status.HTTP_404_NOT_FOUND)

        part_validation = PartService.verify_part_authenticity(serial_number, nfc_uid, tag_counter, cmac)
        if not part_validation:
            return Response({"status": "failed", "detail": "Validation failed"}, status=status.HTTP_404_NOT_FOUND)

        response_dto = build_verification_response(part=part)
        return Response(verification_response_to_dict(response_dto), status=status.HTTP_200_OK)