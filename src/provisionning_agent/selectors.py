from django.db.models import Prefetch
from django.utils import timezone

from dataclasses import fields, is_dataclass
from datetime import date, datetime
from enum import Enum
from typing import Any
from uuid import UUID

from haeron_guitar_api.models import (
    InstrumentHistory,
    Part,
    PartHistory,
)
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
    SecurityMarkDTO,
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

        security_marks=[
            SecurityMarkDTO(
                uuid=str(mark.uuid),
                mark_type=mark.mark_type,
                value=mark.value,
                location=mark.location,
                description=mark.description,
            )
            for mark in part.security_marks.all()
        ],

        history=[
            PartHistoryDTO(
                uuid=str(history.uuid),
                event_type=history.event_type,
                title=history.title,
                description=history.description,
                created_at=history.created_at.isoformat(),
                created_by=(
                    UserSummaryDTO(
                        uuid=str(history.created_by.uuid),
                        name=history.created_by.get_full_name(),
                    )
                    if history.created_by
                    else None
                ),
            )
            for history in part.history.all()
        ],
    )


def build_part_options(part):
    snapshot = part.production_snapshot or {}

    return [
        PartOptionSelectionDTO(
            uuid=item["uuid"],
            option=OptionDTO(
                uuid=item["option"]["uuid"],
                name=item["option"]["name"],
                description=item["option"].get("description"),
                category=item["option"].get("category"),
            ),
            value=item["value"],
        )
        for item in snapshot.get("options", [])
    ]

def build_instrument(instrument):
    parts = getattr(
        instrument,
        "parts_for_verification",
        [],
    )

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

        serial_number=getattr(
            instrument,
            "serial_number",
            None,
        ),

        parts=[
            build_instrument_part(part)
            for part in parts
        ],

        history=[
            InstrumentHistoryDTO(
                uuid=str(history.uuid),
                event_type=history.event_type,
                title=history.title,
                description=history.description,
                created_at=history.created_at.isoformat(),
                created_by=(
                    UserSummaryDTO(
                        uuid=str(history.created_by.uuid),
                        name=history.created_by.get_full_name(),
                    )
                    if history.created_by
                    else None
                ),
            )
            for history in instrument.history.all()
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
            "instrument__instrument_model",
            "instrument__instrument_model__instrument_type",
        )
        .prefetch_related(

            # Security marks de la pièce
            "security_marks",

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
                    .prefetch_related(
                        "security_marks",
                        Prefetch(
                            "history",
                            queryset=(
                                PartHistory.objects
                                .select_related("created_by")
                                .order_by("-created_at")
                            ),
                        ),
                    )
                ),
            ),
        )
        .filter(serial_number=serial_number)
        .first()
    )