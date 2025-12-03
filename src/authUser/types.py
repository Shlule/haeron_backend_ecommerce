import strawberry_django 
from strawberry import auto

from . import models
    
@strawberry_django.type(models.User)
class UserType:
    email: str
    password: str