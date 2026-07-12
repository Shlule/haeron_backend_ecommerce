from pprint import pprint
import strawberry
from strawberry.types import Info
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password

from rest_framework_simplejwt.tokens import RefreshToken
from django.utils.http import urlsafe_base64_decode
from django.utils.encoding import force_str
from django.contrib.auth.tokens import default_token_generator
from .types import UserType

from .input import SignupInput

# les import apres permettent un test avec django allauth
from allauth.account.forms import ResetPasswordForm
from allauth.account.models import EmailAddress


from .input import SignupInput
from .dto import SignupDTO
from .types import TokenType

from .services.email import resend_verification_email, verify_email
from .services.signup import signup_user
from .services.auth import authenticate_user
from .services.tokens import generate_tokens, revoke_refresh_token, refresh_access_token
from .services.password import request_password_reset, confirm_password_reset


User = get_user_model()


# @strawberry.type
# class TokenType:
#     access: str
#     refresh: str


@strawberry.type
class UserQuery:
    @strawberry.field
    def getAllUser(self, info: Info) -> list[UserType]:
        return User.objects.all()


@strawberry.type
class UserMutation:
    @strawberry.mutation
    def signup(self, info: Info, input: SignupInput) -> bool:
        dto = SignupDTO(
            user_name=input.user_name,
            email=input.email,
            email_confirmation=input.email_confirmation,
            password=input.password,
            password_confirmation=input.password_confirmation,
            phone=input.phone,
        )
        signup_user(info.context["request"], dto=dto)
        return True

    @strawberry.mutation
    def login(self, info: Info, identifier: str, password: str) -> TokenType:
        user = authenticate_user(identifier, password)

        if not user:
            raise Exception("Cannot Connect")

        tokens = generate_tokens(user)
        return TokenType(**tokens)

    @strawberry.mutation
    def logout(self, info: Info, refresh: str) -> bool:
        revoke_refresh_token(refresh)
        return True

    @strawberry.mutation
    def reset_password(self, info: Info, email: str) -> bool:
        return request_password_reset(info.context["request"], email)

    @strawberry.mutation
    def refresh_token(self, refresh: str) -> TokenType:

        tokens = refresh_access_token(refresh)

        if tokens is None:
            raise Exception("Invalid refresh token")

        return TokenType(**tokens)

    @strawberry.mutation
    def confirm_password_reset(self, uid: str, key: str, new_password: str) -> bool:
        return confirm_password_reset(uid=uid, key=key, new_password=new_password)

    @strawberry.mutation
    def resend_verification_email(self, info: Info, email: str) -> bool:

        return resend_verification_email(info.context["request"], email)

    @strawberry.mutation
    def verify_email(self, info: Info, key: str) -> bool:

        return verify_email(info.context["request"], key)

    # @strawberry.type
    # class UserMutation:
    #     @strawberry.mutation
    #     def signup(self, info, input: SignupInput) -> bool:
    #         request = info.context["request"]

    #         if User.objects.filter(username=input.user_name).exists():
    #             raise Exception("Username already in use")

    #         if input.password != input.password_confirmation:
    #             raise Exception("Passwords do not match")

    #         if input.email != input.email_confirmation:
    #             raise Exception("Email does not match")

    #         adapter = get_adapter(request)
    #         email = adapter.clean_email(input.email)

    #         if EmailAddress.objects.filter(email=email).exists():
    #             raise Exception("Email already exists")

    #         try:
    #             validate_password(input.password)
    #         except ValidationError as e:
    #             raise Exception(e.messages)

    #         user = adapter.new_user(request)

    #         customer_group, created = Group.objects.get_or_create(name="customer")
    #         user.groups.add(customer_group)

    #         user.username = input.user_name
    #         user.email = adapter.clean_email(input.email)
    #         user.set_password(input.password)
    #         user.save()
    #         setup_user_email(request, user, [])

    #         email_address = EmailAddress.objects.get(user=user, email=user.email)
    #         email_address.send_confirmation(request, signup=True)

    #         return True

    # @strawberry.mutation
    # def login(self, info, login: str, password: str) -> TokenType:
    #     try:
    #         user = User.objects.get(Q(username=login) | Q(email=login))
    #     except User.DoesNotExist:
    #         raise ValueError("Invalid credentials")
    #     user = authenticate(
    #         info.context["request"],
    #         username=user.username,
    #         password=password,
    #     )
    #     if not user:
    #         raise PermissionError("Invalid Credential")

    #     if not user.emailaddress_set.filter(verified=True).exists():
    #         raise ValueError("Email not verified")

    #     tokens = generate_tokens_for_user(user)
    #     return TokenType(**tokens)

    # @strawberry.mutation
    # def resend_verification_email(self, info: Info, email: str) -> bool:
    #     email = EmailAddress.objects.get(email=email)
    #     if email.verified:
    #         return True

    #     email.send_confirmation(info.context.request)
    #     return

    # @strawberry.mutation
    # def reset_password_request(self, info, email: str) -> bool:
    #     form = ResetPasswordForm(data={"email": email})
    #     if form.is_valid():
    #         form.save(info.context.request)
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
    #     except (User.DoesNotExist, ValueError, TypeError):
    #         raise Exception("Invalid reset link")
    #     if not default_token_generator.check_token(user, token):
    #         raise Exception("Invalid or expired token")

    #     validate_password(new_password, user)
    #     user.set_password(new_password)
    #     user.save()
    #     return True

    # @strawberry.mutation
    # def refresh_token(self, info: Info, refresh: str) -> TokenType:
    #     try:
    #         token = RefreshToken(refresh)
    #         access = str(token.access_token)
    #         # optionally rotate
    #         return TokenType(access=access, refresh=refresh)
    #     except Exception as e:
    #         raise Exception("Invalid refresh token")


UserMutation = UserMutation
UserQuery = UserQuery
