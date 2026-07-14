from enum import Enum


class Roles(str, Enum):
    CUSTOMER = "customer"
    OPERATOR = "operator"
    MANAGER = "manager"
    ADMIN = "admin"
    SUPERADMIN = "superadmin"

    @classmethod
    def exists(cls, role: str) -> bool:
        """
        Vérifie si un rôle existe
        """
        return role in cls._value2member_map_

    @classmethod
    def from_value(cls, role: str):
        """
        Retourne le Role correspondant
        """
        try:
            return cls(role)
        except ValueError:
            return None

    @property
    def requires_mfa(self) -> bool:
        """
        Détermine si ce rôle nécessite le MFA
        """
        return self in {
            Roles.MANAGER,
            Roles.ADMIN,
            Roles.SUPERADMIN,
        }
