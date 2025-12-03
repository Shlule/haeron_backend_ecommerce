import strawberry
from strawberry.types import Info
from django.contrib.auth import authenticate
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.validators import validate_email

from rest_framework_simplejwt.tokens import RefreshToken
from django.utils.http import urlsafe_base64_decode
from django.utils.encoding import force_str
from django.contrib.auth.tokens import default_token_generator
from .utils import make_passord_reset, send_password_reset_email
from .types import UserType
User = get_user_model()

def generate_tokens_for_user(user):
    refresh = RefreshToken.for_user(user)
    return {
        "access": str(refresh.access_token),
        "refresh": str(refresh),
    }

@strawberry.type
class TokenType: 
    access: str
    refresh: str

@strawberry.type
class UserQuery:
    @strawberry.field
    def getAllUser(self, info: Info) -> list[UserType]:
        return User.objects.all()
    
@strawberry.type
class UserMutation:
    @strawberry.mutation
    def signup(self, info: Info, username: str, email: str, password:str) -> TokenType:
        if User.objects.filter(username=username).exists(): 
            raise Exception("Username already in use")    
        
        if User.objects.filter(email=email).exists():
            raise Exception("Email already in use")
        
        try:
            validate_email(email)
        except ValidationError as e:
            raise ValidationError("not valid email provided")
        
        user = User(username=username, email=email)
        user.set_password(password)
        user.save()

        # OPTIONNEL : envoyer email de verification via allauth ou custom
        tokens = generate_tokens_for_user(user)
        return TokenType(acess=tokens["access"], refresh=tokens["refresh"])
    
    @strawberry.mutation
    def signin(self, info: Info, username: str, password:str) -> TokenType:
        user = authenticate(username=username, password=password)
        if not user:
            raise Exception("Credentials Invalid")
        
        # OPTIONNEL : Si tu actives 2FA, tu peux ici renvoyer un status 2fa_required et
        # gérer un flow secondaire. Ici on retourne directement tokens.

        tokens = generate_tokens_for_user(user)
        return TokenType(acess=tokens["access"], refresh=tokens["refresh"])

    @strawberry.mutation
    def refresh_token(self, info: Info, refresh:str) -> TokenType: 
        try:
            token = RefreshToken(refresh)
            access = str(token.access_token)
            # optionally rotate
            return TokenType(acess=access, refresh=refresh)
        except Exception as e:
            raise Exception("Invalid refresh token")
            
    @strawberry.mutation
    def request_password_reset(self, info: Info, email:str) -> bool:
        try: 
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return True
        
        uid, token = make_passord_reset(user)
        send_password_reset_email(user, uid, token)
        return True
    
    @strawberry.mutation
    def confirm_password_reset(self, info: Info, uid: str, token: str, new_password: str ) -> bool: 
        try: 
            pk = force_str(urlsafe_base64_decode(uid))
            user = User.objects.get(pk=pk)
        except Exception:
            raise Exception("Invalid uid")
        if not default_token_generator.check_token(user, token):
            raise Exception("Invalid or Expired token")
        user.set_password(new_password)
        user.save()
        return True
    
UserMutation = UserMutation
UserQuery = UserQuer