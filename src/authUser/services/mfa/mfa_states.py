from enum import Enum


class MFAStatus(str, Enum):
    NOT_REQUIRED = "not_required"
    SETUP_REQUIRED = "setup_required"
    REQUIRED = "required"
    VERIFIED = "verified"
    FAILED = "failed"
