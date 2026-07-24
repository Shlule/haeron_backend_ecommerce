from django.contrib.auth import get_user_model
from django.shortcuts import get_object_or_404
from django.db import transaction
from uuid import UUID, uuid4
from django.db.models import Max
import logging

from ..tag.sdm import validate_plain_sun
# from .binding import compute_binding_hash

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
    @staticmethod
    def provideNFCIdentity(part_serial_number, part_p: Part, nfc_uid_p=None):

        part = (
            Part.objects.select_related("batch", "part_model")
            .prefetch_related("part_entities")
            .get(serial_number=part_serial_number)
        )
        if part != part_p:
            logger.error("condition does not match")
            return

        active_identity = next(
            (identity for identity in part.part_identities.all() if identity.status == "active"),
            None,
        )

        if active_identity:
            logger.error("aleready provided")
            return

        nfc_uid = nfc_uid_p if nfc_uid_p else uuid4()

        new_version = (
            PartNFCIdentity.objects.filter(part=part, nfc_uid=nfc_uid).aggregate(Max("key_version"))["key_version__max"]
            or 0
        ) + 1

        part_model_id = part.part_model.uuid
        part_batch_id = part.batch.uuid

        vault_service = get_vault_service()
        tag_key = HKDFService.derive_tag_key(
            vault_service.get_secret(
                vault_service.get_vault_path("domain", part_model_id=part_model_id),
            ),
            vault_service.get_secret(
                vault_service.get_vault_path("batch", part_model_id=part_model_id, batch_id=part_batch_id)
            ),
            nfc_uid,
            new_version,
        )

        PartNFCIdentity.objects.create(part=part, batch=part.batch, key_version=new_version)

        return nfc_uid, tag_key

    @staticmethod
    def confirmNFCIdentity(part_serial_number, part_p: Part, nfc_uid):
        pass


logger = logging.getLogger(__name__)


def verify_part_authenticity(serial_number: str, nfc_uid_hex: str, ctr_hex: str, cmac_hex: str) -> bool:
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

        # ... vérification binding_hash comme vu précédemment ...

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

        identity.last_seen_counter = result["read_ctr"]
        identity.save(update_fields=["last_seen_counter"])

    return True
