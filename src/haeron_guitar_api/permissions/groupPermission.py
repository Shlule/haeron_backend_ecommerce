from strawberry.permission import BasePermission
from strawberry.types import Info

def HasRoleFactory(role_name):
    class _HasRole(BasePermission):
        message = "don't got the right permission"
        def has_permission(self, source, info: Info, **kwargs):
            user = info.context["user"]
            return user.groups.filter(name=role_name).exists()
    return _HasRole