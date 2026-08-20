from django.contrib.auth import get_user_model
from django.shortcuts import get_object_or_404
from django.db import transaction
from uuid import UUID
from django.db.models import Max
import logging

from ..tag.sdm import validate_plain_sun

from ..models import Part, PartModel, Factory, InstrumentType, PartBatch, PartNFCIdentity
from .part_dto import CreatePartDTO, UpdatePartDTO
from ..serial_counter.serial_counter_service import SerialCounterService
from haeron_guitar_api.security.vault.vault_factory import get_vault_service
from haeron_guitar_api.security.vault.hkdf import HKDFService
import logging

logger = logging.getLogger(__name__)

User = get_user_model()


class PartService:
    @staticmethod
    @transaction.atomic
    def create(dto: CreatePartDTO) -> Part:
        # TODO Faire la partie du token et de l'auth key

        part_model = PartModel.objects.select_related("part_type").get(pk=dto.part_model_id)
        factory = get_object_or_404(Factory, pk=dto.factory_id)
        instrument_type = get_object_or_404(InstrumentType, pk=dto.instrument_type_id)
        batch = (
            PartBatch.objects.filter(
                part_model=part_model,
                status="active",
            )
            .order_by("-created_at")
            .first()
        )
        owner = None
        if dto.owner_id:
            owner = get_object_or_404(User, uuid=dto.owner_id)

        serial_number = PartService.build_serial_number(factory, part_model, instrument_type, batch)
        if not serial_number:
            raise ValueError("cannot create part")

        part = Part.objects.create(
            serial_number=serial_number,
            part_model=part_model,
            owner=owner,
            is_master=dto.is_master,
            batch=batch,
            production_snapshot=dto.production_snapshot
        )

        SerialCounterService.next(dto.factory_id)

        return part

    @staticmethod
    def build_serial_number(
        factory_p: UUID | Factory, part_model_p: UUID | PartModel, instrument_type_id: UUID, batch: UUID
    ):
        factory = factory_p
        part_model = part_model_p
        instrument_type = instrument_type_id
        if isinstance(factory_p, UUID):
            factory = Factory.objects.get(pk=factory_p)
        if isinstance(part_model_p, UUID):
            part_model = PartModel.objects.prefetch_related("part_type__instrument_types").get(pk=part_model_p)
        if isinstance(instrument_type, UUID):
            instrument_type = get_object_or_404(InstrumentType, pk=instrument_type_id)
        if isinstance(batch, UUID):
            batch = PartBatch.objects.get(pk=batch)
        if not instrument_type:
            raise ValueError("No instrument Type for the id")


        instrument_type_code = instrument_type.code
        if batch is None:
            raise ValueError(
                f"No active batch for part model {part_model.code}"
            )
        batch_code = batch.code

        serial_counter = SerialCounterService.get_or_create_today(factory.uuid)
        serial_value = serial_counter.last_value
        current_year = serial_counter.year
        next_value = serial_value + 1

        return f"{str(factory.code)}{instrument_type_code}-{part_model.code}{str(current_year)}-{str(batch_code)}{str(next_value)}"

    @staticmethod
    def update(part: Part, dto: UpdatePartDTO) -> Part:
        if dto.serial_number is not None:
            part.serial_number = dto.serial_number

        if dto.part_model_id is not None:
            part.part_model = get_object_or_404(PartModel, uuid=dto.part_model_id)

        if dto.owner_id is not None:
            part.owner = get_object_or_404(User, uuid=dto.owner_id)

        if dto.is_master is not None:
            part.is_master = dto.is_master

        part.save()
        return part

    # TODO finish this method
    # FIXME remove test_run Later. 
    @staticmethod
    def provideNFCIdentity(part_serial_number, part_uuid_p: str, nfc_uid_p=None, test_run=False):

        part = (
            Part.objects
            .select_related("batch", "part_model")
            .get(serial_number=part_serial_number)
        )

        if str(part.uuid) != part_uuid_p:
            logger.error("condition does not match")
            return {}

        active_identity = (
            PartNFCIdentity.objects
            .filter(part=part, status="active")
            .first()
        )
        
        if active_identity:
            logger.error("allready provided")
            return {}

        last_revoked_identity = (
            PartNFCIdentity.objects
            .filter(part=part, status="revoked")
            .order_by("-created_at")
            .first()
        )



        new_version = (
            PartNFCIdentity.objects.filter(part=part, nfc_uid=nfc_uid_p).aggregate(Max("key_version"))["key_version__max"]
            or 0
        ) + 1

        part_model_id = part.part_model.uuid
        part_batch_id = part.batch.uuid

        if not test_run:
            vault_service = get_vault_service()
            tag_key = HKDFService.derive_tag_key(
                vault_service.get_secret(
                    vault_service.get_vault_path("domain", part_model_id=part_model_id),
                ),
                vault_service.get_secret(
                    vault_service.get_vault_path("batch", part_model_id=part_model_id, batch_id=part_batch_id)
                ),
                nfc_uid_p,
                new_version,
            )
            
            # get the old key for changing it in provisionning agent
            if new_version > 1:
                old_version = new_version -1
                old_tag_key = HKDFService.derive_tag_key(
                vault_service.get_secret(
                    vault_service.get_vault_path("domain", part_model_id=part_model_id),
                ),
                vault_service.get_secret(
                    vault_service.get_vault_path("batch", part_model_id=part_model_id, batch_id=part_batch_id)
                ),
                nfc_uid_p,
                old_version,
            )
            else: 
                if not last_revoked_identity:
                    old_tag_key = bytes(16)
                # the old key if we change the tag uid. 
                else: 
                    old_tag_key = HKDFService.derive_tag_key(
                    vault_service.get_secret(
                        vault_service.get_vault_path("domain", part_model_id=part_model_id),
                    ),
                    vault_service.get_secret(
                        vault_service.get_vault_path("batch", part_model_id=part_model_id, batch_id=part_batch_id)
                    ),
                    last_revoked_identity.nfc_uid,
                    last_revoked_identity.key_version,
                )

        else: 
            tag_key = bytes(16)
            old_tag_key = bytes(16)

        PartNFCIdentity.objects.create(part=part, batch=part.batch, nfc_uid=nfc_uid_p, key_version=new_version)

        return {"tag_key":tag_key,"old_tag_key": old_tag_key, "new_version": new_version}

    @staticmethod
    def confirmNFCIdentity(part_serial_number: str, part_uuid_p: str, nfc_uid: str):
        print("je suisd ans le part service .")
        try:
            part = (
                Part.objects
                .get(serial_number=part_serial_number)
            )
        except Part.DoesNotExist:
            logger.error(
                "Part not found",
                extra={"serial_number": part_serial_number}
            )
            return {
                "status": "error",
                "message": "La pièce n'existe pas."
            }

        # Vérification de l'identité de la pièce
        if str(part.uuid) != part_uuid_p:
            logger.error(
                "Part UUID does not match",
                extra={
                    "serial_number": part_serial_number,
                    "part_uuid": part_uuid_p,
                }
            )
            return {
                "status": "error",
                "message": "L'identité de la pièce ne correspond pas."
            }

        # Récupération du dernier NFC en attente
        pending_identity = (
            PartNFCIdentity.objects
            .filter(
                part=part,
                status="pending",
            )
            .order_by("-created_at")
            .first()
        )

        if not pending_identity:
            logger.error(
                "No pending NFC identity found",
                extra={
                    "part_uuid": part_uuid_p,
                    "nfc_uid": nfc_uid,
                }
            )
            return {
                "status": "error",
                "message": "Aucun tag NFC en attente de confirmation."
            }

        # Vérification que le NFC reçu correspond bien au NFC en attente
        if pending_identity.nfc_uid != nfc_uid:
            logger.error(
                "NFC UID does not match",
                extra={
                    "expected_nfc_uid": pending_identity.nfc_uid,
                    "provided_nfc_uid": nfc_uid,
                }
            )
            return {
                "status": "error",
                "message": "Le tag NFC ne correspond pas au tag en attente."
            }

        # Confirmation du tag
        pending_identity.status = "active"
        pending_identity.save(update_fields=["status"])

        return {
            "status": "success",
            "message": "Le tag NFC a bien été confirmé."
        }

    @staticmethod
    def revokeNFCIdentity(part_serial_number: str, part_uuid_p: str, nfc_uid: str):
        try:
            part = (
                Part.objects
                .get(serial_number=part_serial_number)
            )
        except Part.DoesNotExist:
            logger.error(
                "Part not found",
                extra={"serial_number": part_serial_number}
            )
            return {
                "status": "error",
                "message": "La pièce n'existe pas."
            }

        # Vérification supplémentaire de l'identité de la pièce
        if str(part.uuid) != part_uuid_p:
            logger.error(
                "Part UUID does not match",
                extra={
                    "serial_number": part_serial_number,
                    "expected_uuid": str(part.uuid),
                    "provided_uuid": part_uuid_p,
                }
            )
            return {
                "status": "error",
                "message": "L'identité de la pièce ne correspond pas."
            }

        # On cherche précisément le tag NFC fourni
        active_identity = (
            PartNFCIdentity.objects
            .filter(
                part=part,
                nfc_uid=nfc_uid,
                status="active",
            )
            .first()
        )

        if not active_identity:
            logger.error(
                "No active NFC identity found",
                extra={
                    "part_uuid": part_uuid_p,
                    "nfc_uid": nfc_uid,
                }
            )
            return {
                "status": "error",
                "message": "Aucun tag NFC actif correspondant n'a été trouvé."
            }

        # Révocation
        active_identity.status = "revoked"
        active_identity.save(update_fields=["status"])

        return {
            "status": "success",
            "message": "Le tag a bien été révoqué."
        }


logger = logging.getLogger(__name__)

# FIXME - remove le test_run 
def verify_part_authenticity(serial_number: str, nfc_uid_hex: str, ctr_hex: str, cmac_hex: str, test_run=False) -> bool:
    with transaction.atomic():
        try:
            identity = (
                PartNFCIdentity.objects.select_for_update()
                .select_related("part__part_model", "batch")
                .get(nfc_uid=nfc_uid_hex, status="active")
            )
        except PartNFCIdentity.DoesNotExist:
            return False

        if identity.part.serial_number != serial_number:
            return False

        if not test_run:
            vault_service = get_vault_service()
            domain_key = vault_service.get_secret(
                vault_service.get_vault_path("domain", part_model_id=identity.part.part_model.uuid)
            )
            batch_key = vault_service.get_secret(
                vault_service.get_vault_path(
                    "batch", part_model_id=identity.part.part_model.uuid, batch_id=identity.batch.uuid
                )
            )
            tag_key = HKDFService.derive_tag_key(
                domain_key, batch_key, str(identity.tag_id), key_version=identity.key_version
            )
        else: 
            tag_key = bytes(16)

        try:
            result = validate_plain_sun(
                bytes.fromhex(nfc_uid_hex),
                bytes.fromhex(ctr_hex),
                bytes.fromhex(cmac_hex),
                tag_key,
            )
        except ValueError:
            return False

        if result["read_ctr"] <= identity.last_seen_counter:
            return False  # rejeu détecté


    #TODO - use the last_verified at. 
        identity.last_seen_counter = result["read_ctr"]
        identity.save(update_fields=["last_seen_counter"])

    return True
