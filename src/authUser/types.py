import strawberry
import strawberry_django
from strawberry import auto

from . import models


@strawberry_django.type(models.User)
class UserType:
    email: str
    username: str
    is_email_verified: bool


@strawberry.type
class TokenType:
    access: str
    refresh: str
