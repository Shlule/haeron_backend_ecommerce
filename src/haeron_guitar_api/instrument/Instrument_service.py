from ..models import Instrument, Factory, Part
from .instrument_dto import CreateInstrumentDTO


def create_instrument(dto: CreateInstrumentDTO) -> Instrument:
    instrument_type = Factory.objects.get(pk=dto.instrument_type_id)
    master_part = Part.objects.get(pk=dto.master_part_id)
    parts = Part.objects.filter(pk__in=dto.parts_id)

    if not master_part.is_master:
        raise ValueError("the designated part cannot be a master part.")

    if master_part in parts:
        raise ValueError("the master part do not be repeted inside parts")

    instrument = Instrument.objects.create(
        instrument_type=instrument_type, master_part=master_part, owner_id=dto.owner_id
    )

    instrument.parts.set(parts)

    return instrument
