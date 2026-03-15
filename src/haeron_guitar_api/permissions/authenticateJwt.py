# permissions.py
from strawberry.types import Info
from strawberry.permission import BasePermission
from pprint import pprint
class IsAuthenticated(BasePermission):
    message = "you must be authenticate"

    def has_permission(self, source, info: Info, **kwargs):
        user = info.context["user"]
        print('_'*50)
        pprint(user)
        return user.is_authenticated