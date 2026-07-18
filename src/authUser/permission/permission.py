# permissions.py
from strawberry.permission import BasePermission
from strawberry.types import Info


class IsAuthenticated(BasePermission):
    message = "Authentication required"

    def has_permission(self, source, info: Info, **kwargs) -> bool:
        return info.context["request"].user.is_authenticated


def HasRole(*roles):
    class _HasRole(BasePermission):
        message = f"Requires role: {', '.join(roles)}"

        def has_permission(self, source, info: Info, **kwargs):
            user = info.context["request"].user
            return (
                user.is_authenticated
                and user.groups.filter(name__in=roles).exists()
            )

    return _HasRole