from dataclasses import dataclass
from typing import Optional


@dataclass
class SignupDTO:
    user_name: str
    email: str
    email_confirmation: str
    password: str
    password_confirmation: str
    phone: Optional[str] = None
