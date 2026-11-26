from dataclasses import dataclass


@dataclass
class CustomerDTO:
    """Contact and delivery address given at checkout."""

    email: str
    first_name: str
    last_name: str
    address: str
    postal_code: str
    city: str
    country: str = "FR"
    phone: str = ""
