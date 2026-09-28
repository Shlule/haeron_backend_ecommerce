from dataclasses import dataclass
from typing import Optional
from dataclasses import field

@dataclass(slots=True)
class VerificationResponseDTO:
    verification: "VerificationInfoDTO"
    part: "PartIdentityDTO"
    instrument: Optional["InstrumentDTO"]
    
@dataclass(slots=True)
class NFCVerificationDTO:
    method: str
    uid: Optional[str] = None
    counter: Optional[int] = None
    key_version: Optional[int] = None


@dataclass(slots=True)
class VerificationInfoDTO:
    status: str
    verified_at: str
    nfc: NFCVerificationDTO
    

@dataclass(slots=True)
class OptionDTO:
    uuid: str
    name: str
    description: Optional[str]
    category: Optional[str]


@dataclass(slots=True)
class PartOptionSelectionDTO:
    uuid: str
    option: OptionDTO
    value: str

@dataclass(slots=True)
class PartTypeDTO:
    uuid: str
    name: str
    code: str


@dataclass(slots=True)
class PartModelDTO:
    uuid: str
    code: str
    name: str
    part_type: "PartTypeDTO"

@dataclass(slots=True)
class PartBatchDTO:
    uuid: str
    name: str
    code: str
    status: str

@dataclass(slots=True)
class SecurityMarkDTO:
    uuid: str
    mark_type: str
    value: str
    location: Optional[str]
    description: Optional[str]

@dataclass(slots=True)
class UserSummaryDTO:
    uuid: str
    name: str


@dataclass(slots=True)
class PartHistoryDTO:
    uuid: str
    event_type: str
    title: str
    description: str
    created_at: str
    created_by: Optional["UserSummaryDTO"]


@dataclass(slots=True)
class InstrumentHistoryDTO:
    uuid: str
    event_type: str
    title: str
    description: str
    created_at: str
    created_by: Optional["UserSummaryDTO"]



@dataclass(slots=True)
class PartIdentityDTO:
    uuid: str

    serial_number: str

    is_master: bool

    part_model: PartModelDTO

    batch: PartBatchDTO

    options: list["PartOptionSelectionDTO"] = field(default_factory=list)

    security_marks: list["SecurityMarkDTO"] = field(default_factory=list)

    history: list["PartHistoryDTO"] = field(default_factory=list)


@dataclass(slots=True)
class InstrumentTypeDTO:
    uuid: str
    name: str
    code: str


@dataclass(slots=True)
class InstrumentModelDTO:
    uuid: str
    name: str
    instrument_type: "InstrumentTypeDTO"


@dataclass(slots=True)
class InstrumentDTO:
    uuid: str

    instrument_model: InstrumentModelDTO

    serial_number: Optional[str]

    parts: list["PartIdentityDTO"] = field(default_factory=list)

    history: list["InstrumentHistoryDTO"] = field(default_factory=list)