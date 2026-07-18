from django.contrib.auth import get_user_model
from django.shortcuts import get_object_or_404
from django.db import transaction
from uuid import UUID, uuid4

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

        part_model = PartModel.objects.prefetch_related("part_type__instrument_types").get(pk=dto.part_model_id)
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
            auth_key=dto.auth_key,
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

        part_type = part_model.part_type
        part_type_code = part_type.code
        if not part_type.instrument_types.filter(pk=instrument_type.uuid).exists():
            raise ValueError("Cannot create serial number")

        instrument_type_code = instrument_type.code
        batch_code = batch.code

        serial_value = SerialCounterService.get_or_create_today(factory.uuid).last_value
        next_value = serial_value + 1

        return f"{str(factory.code)}{instrument_type_code}-{part_type_code}{part_model.code}-{str(batch_code)}{str(next_value)}"

    @staticmethod
    def update(part: Part, dto: UpdatePartDTO) -> Part:
        if dto.serial_number is not None:
            part.serial_number = dto.serial_number

        if dto.auth_key is not None:
            part.auth_key = dto.auth_key

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
    def provideNFCIdentity(part_serial_number, part_p: Part):

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

        part_model_id = part.part_model.uuid
        part_batch_id = part.batch.uuid

        vault_service = get_vault_service()
        tag_id = uuid4()
        tag_key = HKDFService.derive_tag_key(
            vault_service.get_secret(
                vault_service.get_vault_path("domain", part_model_id=part_model_id),
            ),
            vault_service.get_secret(
                vault_service.get_vault_path("batch", part_model_id=part_model_id, batch_id=part_batch_id)
            ),
            tag_id,
        )

        return tag_id, tag_key
