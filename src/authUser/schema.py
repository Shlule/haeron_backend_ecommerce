import strawberry
from strawberry.types import Info
from django.contrib.auth import authenticate
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.contrib.auth.password_validation import validate_password

from rest_framework_simplejwt.tokens import RefreshToken
from django.utils.http import urlsafe_base64_decode
from django.utils.encoding import force_str
from django.contrib.auth.tokens import default_token_generator
from django.contrib.auth.models import Group
from .utils import make_passord_reset, send_password_reset_email
from .types import UserType

from .input import SignupInput
from .dto import SignupDTO

# les import apres permettent un test avec django allauth
from allauth.account.forms import SignupForm
from allauth.account.forms import ResetPasswordForm
from allauth.account.models import EmailAddress
from allauth.account.adapter import get_adapter
from django.db.models import Q
from allauth.account.utils import setup_user_email


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
    def signup(self, info, input: SignupInput) -> bool:
        request = info.context["request"]

        if User.objects.filter(username=input.user_name).exists():
            raise Exception("Username already in use")
        
        if input.password != input.password_confirmation:
            raise Exception("Passwords do not match")
            
        if input.email != input.email_confirmation:
            raise Exception("Email does not match")

        adapter = get_adapter(request)
        email = adapter.clean_email(input.email)


        if EmailAddress.objects.filter(email=email).exists():
            raise Exception("Email already exists")

        try:
            validate_password(input.password)
        except ValidationError as e:
            raise Exception(e.messages)

        user = adapter.new_user(request)

        customer_group, created = Group.objects.get_or_create(name="customer")
        user.groups.add(customer_group)
        
        user.username = input.user_name
        user.email = adapter.clean_email(input.email)
        user.set_password(input.password)
        user.save()
        setup_user_email(request, user, []) 

        email_address = EmailAddress.objects.get(user=user, email=user.email)
        email_address.send_confirmation(request, signup=True)


        return True

    @strawberry.mutation
    def login(self, info, login: str, password: str) -> TokenType:
        try:
            user = User.objects.get(Q(username=login) | Q(email=login))
        except User.DoesNotExist:
            raise Exception("Invalid credentials")
        user = authenticate(
            info.context["request"],
            username=user.username,
            password=password,
        )
        print(user.password)
        if not user:
            raise Exception("Invalid Credential")

        if not user.emailaddress_set.filter(verified=True).exists():
            raise Exception("Email not verified")

        tokens = generate_tokens_for_user(user)
        return TokenType(**tokens)

    @strawberry.mutation
    def resend_verification_email(self, info: Info, email: str) -> bool:
        email = EmailAddress.objects.get(email=email)
        if email.verified:
            return True

        email.send_confirmation(info.context.request)
        return
        
    @strawberry.mutation
    def reset_password_request(self, info, email: str) -> bool:
        form = ResetPasswordForm(data={"email": email})
        if form.is_valid():
            form.save(info.context.request)
        return True

    @strawberry.mutation
    def confirm_password_reset(
        self,
        info,
        uid: str,
        token: str,
        new_password: str,
    ) -> bool:
        user = User.objects.get(pk=force_str(urlsafe_base64_decode(uid)))

        if not default_token_generator.check_token(user, token):
            raise Exception("Invalid or expired token")

        validate_password(new_password, user)
        user.set_password(new_password)
        user.save()
        return True


    @strawberry.mutation
    def refresh_token(self, info: Info, refresh: str) -> TokenType:
        try:
            token = RefreshToken(refresh)
            access = str(token.access_token)
            # optionally rotate
            return TokenType(access=access, refresh=refresh)
        except Exception as e:
            raise Exception("Invalid refresh token")
            
            
    # @strawberry.mutation
    # def signin(self, info: Info, username: str, password: str) -> TokenType:
    #     user = authenticate(username=username, password=password)
    #     if not user:
    #         raise Exception("Credentials Invalid")

    #     # OPTIONNEL : Si tu actives 2FA, tu peux ici renvoyer un status 2fa_required et
    #     # gérer un flow secondaire. Ici on retourne directement tokens.

    #     tokens = generate_tokens_for_user(user)
    #     return TokenType(access=tokens["access"], refresh=tokens["refresh"])

    # @strawberry.mutation  
    # def reset_password_request(self, info, email: str) -> bool:
    #     request = info.context["request"]
    #     form = ResetPasswordForm(data={"email": email})

    #     if form.is_valid():
    #         form.save(request)

    #     return True
    
    # @strawberry.mutation
    # def confirm_password_reset(
    #     self,
    #     info,
    #     uid: str,
    #     token: str,
    #     new_password: str,
    # ) -> bool:

    #     try:
    #         uid_decoded = force_str(urlsafe_base64_decode(uid))
    #         user = User.objects.get(pk=uid_decoded)
    #     except:
    #         raise Exception("Invalid reset link")

    #     if not default_token_generator.check_token(user, token):
    #         raise Exception("Invalid or expired token")

    #     try:
    #         validate_password(new_password, user)
    #     except ValidationError as e:
    #         raise Exception(e.messages)

    #     user.set_password(new_password)
    #     user.save()

    #     return True


    # @strawberry.mutation
    # def request_password_reset(self, info: Info, email: str) -> bool:
    #     try:
    #         user = User.objects.get(email=email)
    #     except User.DoesNotExist:
    #         return False

    #     uid, token = make_passord_reset(user)
    #     send_password_reset_email(user, uid, token)
    #     return True

    # @strawberry.mutation
    # def confirm_password_reset(self, info: Info, uid: str, token: str, new_password: str) -> bool:
    #     try:
    #         pk = force_str(urlsafe_base64_decode(uid))
    #         user = User.objects.get(pk=pk)
    #     except Exception:
    #         raise Exception("Invalid uid")
    #     if not default_token_generator.check_token(user, token):
    #         raise Exception("Invalid or Expired token")
    #     user.set_password(new_password)
    #     user.save()
    #     return True

UserMutation = UserMutation
UserQuery = UserQuery
