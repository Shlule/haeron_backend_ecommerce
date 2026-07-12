from enum import Enum


class Roles(str, Enum):
    CUSTOMER = "customer"
    OPERATOR = "operator"
    MANAGER = "manager"
    ADMIN = "admin"
    SUPERADMIN = "superadmin"
