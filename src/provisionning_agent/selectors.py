from django.db.models import Prefetch
from django.utils import timezone

from dataclasses import fields, is_dataclass
from datetime import date, datetime
from enum import Enum
from typing import Any
from uuid import UUID

from haeron_guitar_api.models import (
    InstrumentEquipment,
    InstrumentHistory,
    Part,
    PartHistory,
)
from haeron_guitar_api.production.equipment_service import EquipmentService
from haeron_guitar_api.production.hidden_mark_service import is_private_event
from .verification_dto import (
    VerificationResponseDTO,
    VerificationInfoDTO,
    PartOptionSelectionDTO,
    OptionDTO,
    NFCVerificationDTO,
    PartIdentityDTO,
    PartModelDTO,
    PartTypeDTO,
    PartBatchDTO,
    EquipmentDTO,
    PartHistoryDTO,
    UserSummaryDTO,
    InstrumentDTO,
    InstrumentModelDTO,
    InstrumentTypeDTO,
    InstrumentHistoryDTO,
)


def verification_response_to_dict(obj: Any) -> Any:
    if is_dataclass(obj):
        return {
            field.name: verification_response_to_dict(
                getattr(obj, field.name)
            )
            for field in fields(obj)
        }

    if isinstance(obj, dict):
        return {
            str(key): verification_response_to_dict(value)
            for key, value in obj.items()
        }

    if isinstance(obj, (list, tuple)):
        return [
            verification_response_to_dict(value)
            for value in obj
        ]

    if isinstance(obj, UUID):
        return str(obj)

    if isinstance(obj, (datetime, date)):
        return obj.isoformat()

    if isinstance(obj, Enum):
        return obj.value

    return obj

def build_verification_response(part):
    return VerificationResponseDTO(
        verification=VerificationInfoDTO(
            status="success",
            verified_at=timezone.now().isoformat(),
            nfc=NFCVerificationDTO(
                method="ntag424_dna",
            ),
        ),
        part=build_part_identity(part),
        instrument=(
            build_instrument(part.instrument)
            if part.instrument
            else None
        ),
    )

def build_part_identity(part):
    return PartIdentityDTO(
        uuid=str(part.uuid),
        serial_number=part.serial_number,
        is_master=part.is_master,

        part_model=PartModelDTO(
            uuid=str(part.part_model.uuid),
            code=part.part_model.code,
            name=part.part_model.name,
            part_type=PartTypeDTO(
                uuid=str(part.part_model.part_type.uuid),
                name=part.part_model.part_type.name,
                code=part.part_model.part_type.code,
            ),
        ),

        batch=PartBatchDTO(
            uuid=str(part.batch.uuid),
            name=part.batch.name,
            code=part.batch.code,
            status=part.batch.status,
        ),

        options=build_part_options(part),

        history=[
            PartHistoryDTO(
                uuid=str(history.uuid),
                event_type=history.event_type,
                title=history.title,
                description=history.description,
                created_at=history.created_at.isoformat(),
                created_by=(
                    UserSummaryDTO(
                        uuid=str(history.created_by.pk),
                        name=history.created_by.get_full_name(),
                    )
                    if history.created_by
                    else None
                ),
            )
            for history in part.history.all()
            # where the hidden code is engraved stays in the workshop
            if not is_private_event(history.title)
        ],
    )


def build_part_options(part):
    """Options the part was made with. The production snapshot gives {id, name, value} for each one
    (older snapshots gave {uuid, option: {...}, value})."""
    snapshot = part.production_snapshot or {}

    options = []
    for item in snapshot.get("options", []):
        option = item.get("option") if isinstance(item.get("option"), dict) else {}
        options.append(
            PartOptionSelectionDTO(
                uuid=str(item.get("uuid") or item.get("id") or ""),
                option=OptionDTO(
                    uuid=str(option.get("uuid") or item.get("id") or ""),
                    name=option.get("name") or item.get("name", ""),
                    description=option.get("description"),
                    category=option.get("category"),
                ),
                value=item.get("value", ""),
            )
        )
    return options

def build_instrument(instrument):
    parts = instrument.instrument_parts.all()

    return InstrumentDTO(
        uuid=str(instrument.uuid),

        instrument_model=InstrumentModelDTO(
            uuid=str(instrument.instrument_model.uuid),
            name=instrument.instrument_model.name,
            instrument_type=InstrumentTypeDTO(
                uuid=str(
                    instrument.instrument_model.instrument_type.uuid
                ),
                name=instrument.instrument_model.instrument_type.name,
                code=instrument.instrument_model.instrument_type.code,
            ),
        ),

        # an instrument carries the serial number of its master piece
        serial_number=instrument.master_part.serial_number,

        parts=[
            build_instrument_part(part)
            for part in parts
        ],

        equipment=[EquipmentDTO(**row) for row in EquipmentService.public(instrument)],

        history=[
            InstrumentHistoryDTO(
                uuid=str(history.uuid),
                event_type=history.event_type,
                title=history.title,
                description=history.description,
                created_at=history.created_at.isoformat(),
                created_by=(
                    UserSummaryDTO(
                        uuid=str(history.created_by.pk),
                        name=history.created_by.get_full_name(),
                    )
                    if history.created_by
                    else None
                ),
            )
            for history in instrument.history.all()
            if not is_private_event(history.title)
        ],
    )

def build_instrument_part(part):
    return PartIdentityDTO(
        uuid=str(part.uuid),
        serial_number=part.serial_number,
        is_master=part.is_master,

        part_model=PartModelDTO(
            uuid=str(part.part_model.uuid),
            code=part.part_model.code,
            name=part.part_model.name,
            part_type=PartTypeDTO(
                uuid=str(part.part_model.part_type.uuid),
                name=part.part_model.part_type.name,
                code=part.part_model.part_type.code,
            ),
        ),

        batch=PartBatchDTO(
            uuid=str(part.batch.uuid),
            name=part.batch.name,
            code=part.batch.code,
            status=part.batch.status,
        ),
    )

def get_part_for_verification(serial_number: str):
    return (
        Part.objects
        .select_related(
            "part_model",
            "part_model__part_type",
            "batch",

            "instrument",
            "instrument__master_part",
            "instrument__instrument_model",
            "instrument__instrument_model__instrument_type",
        )
        .prefetch_related(

            # Équipement monté sur l'instrument (mécaniques, micros…)
            Prefetch(
                "instrument__equipment",
                queryset=InstrumentEquipment.objects.filter(removed_at__isnull=True),
            ),

            # History de la pièce
            Prefetch(
                "history",
                queryset=(
                    PartHistory.objects
                    .select_related("created_by")
                    .order_by("-created_at")
                ),
            ),

            # History de l'instrument
            Prefetch(
                "instrument__history",
                queryset=(
                    InstrumentHistory.objects
                    .select_related("created_by")
                    .order_by("-created_at")
                ),
            ),

            # Parts de l'instrument
            Prefetch(
                "instrument__instrument_parts",
                queryset=(
                    Part.objects
                    .select_related(
                        "part_model",
                        "part_model__part_type",
                        "batch",
                    )
                    .order_by("-is_master", "created_at")
                ),
            ),
        )
        .filter(serial_number=serial_number)
        .first()
    )
