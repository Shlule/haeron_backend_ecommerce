from dataclasses import dataclass

@dataclass(slots=True)
class CreateInstrumentTypeDTO:
    name: str
    code: str