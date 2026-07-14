import strawberry
from strawberry.types import Info
from django.contrib.auth import get_user_model

from .types import UserType

from .input import SignupInput

# les import apres permettent un test avec django allauth


from .dto import SignupDTO
from .types import TokenType

from .services.email import resend_verification_email, verify_email
from .services.signup import signup_customer, signup_user_with_role
from .services.auth import login_user
from .services.tokens import generate_tokens, revoke_refresh_token, refresh_access_token
from .services.password import request_password_reset, confirm_password_reset
from .services.mfa.mfa_policy import get_mfa_status
from .services.mfa.mfa import verify_totp, start_totp_setup, confirm_totp_setup
from .services.mfa.mfa_challenge import delete_challenge, get_user_from_challenge


User = get_user_model()


@strawberry.type
class LoginResponse:
    success: bool

    access: str | None = None
    refresh: str | None = None

    mfa_required: bool = False
    action: str | None = None
    challenge: str | None = None

@strawberry.type
class SetupMfaType:
    otp_auth_url: str
    secret: str



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
        signup_customer(info.context["request"], dto=dto)
        return True

    @strawberry.mutation
    def signup_with_role(self, info: Info, input: SignupInput, role: str) -> bool:
        request = info.context["request"]
        if not request.user.is_authenticated or not request.user.groups.filter(name="admin").exists():
            raise Exception("Not authorized")
        if role in ("admin", "superadmin"):
            raise Exception("Cannot self-assign this role")
        dto = SignupDTO(
            user_name=input.user_name,
            email=input.email,
            email_confirmation=input.email_confirmation,
            password=input.password,
            password_confirmation=input.password_confirmation,
            phone=input.phone,
        )
        signup_user_with_role(info.context["request"], dto=dto, role_p=role)
        return True

    @strawberry.mutation
    def login(self, info: Info, identifier: str, password: str) -> LoginResponse:

        result = login_user(identifier, password)

        return LoginResponse(
            success=True,
            access=result.access,
            refresh=result.refresh,
            mfa_required=result.mfa_required,
            action=result.action,
            challenge=result.challenge,
        )

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

    # ===========================================
    # MFA
    # ===========================================

   
    @strawberry.mutation
    def setup_mfa(self, challenge: str) -> SetupMfaType:
        user = get_user_from_challenge(challenge)
        if not user:
            raise Exception("Invalid challenge")
        data = start_totp_setup(user)
        return SetupMfaType(secret=data["secret"], otp_auth_url=data["otp_auth_url"])
    

    @strawberry.mutation
    def confirm_mfa_setup(self, challenge: str, code: str) -> TokenType:
        user = get_user_from_challenge(challenge)
        if not user:
            raise Exception("Invalid challenge")
        confirm_totp_setup(user, code)   # active seulement si le code est bon
        delete_challenge(challenge)
        tokens = generate_tokens(user)
        return TokenType(**tokens)


    @strawberry.mutation
    def verify_mfa(self, challenge: str, code: str) -> TokenType:

        user = get_user_from_challenge(challenge)

        if not user:
            raise Exception("Invalid challenge")

        verify_totp(user, code)

        delete_challenge(challenge)

        tokens = generate_tokens(user)

        return TokenType(**tokens)

   

UserMutation = UserMutation
UserQuery = UserQuery
