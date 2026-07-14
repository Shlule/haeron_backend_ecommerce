# permissions.py
import strawberry
from strawberry.permission import BasePermission
from strawberry.types import Info


class IsAuthenticated(BasePermission):
    message = "Authentication required"

    def has_permission(self, source, info: Info, **kwargs) -> bool:
        return info.context["request"].user.is_authenticated


class HasRole(BasePermission):
    def __init__(self, *roles):
        self.roles = roles
        self.message = f"Requires role: {', '.join(roles)}"

    def has_permission(self, source, info: Info, **kwargs) -> bool:
        request = info.context["request"]
        return (
            request.user.is_authenticated
            and request.user.groups.filter(name__in=self.roles).exists()
        )