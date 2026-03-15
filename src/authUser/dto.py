from dataclasses import dataclass

@dataclass
class SignupDTO:
    username: str
    email: str
    email2: str
    password: str
    password2: str
    phone: str

