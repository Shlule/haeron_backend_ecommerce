from django.contrib.auth import authenticate
from django.db.models import Q
from ..services.mfa.mfa_policy import get_mfa_status
from ..services.mfa.mfa_challenge import create_mfa_challenge
from ..services.mfa.mfa_states import MFAStatus
from .tokens import generate_tokens
from authUser.models import User


from dataclasses import dataclass


@dataclass
class LoginResult:
    user: object | None = None
    access: str | None = None
    refresh: str | None = None

    mfa_required: bool = False
    action: str | None = None
    challenge: str | None = None


def authenticate_user(identifier, password):
    try:
        user = User.objects.get(Q(username=identifier) | Q(email=identifier))

    except User.DoesNotExist:
        return None

    user = authenticate(username=user.username, password=password)

    if not user:
        return None

    if not user.emailaddress_set.filter(verified=True).exists():
        raise ValueError("please verified Email")

    return user


def login_user(identifier, password):

    user = authenticate_user(identifier, password)

    if not user:
        raise Exception("Invalid credentials")

    mfa_status = get_mfa_status(user)

    if mfa_status == MFAStatus.NOT_REQUIRED:
        tokens = generate_tokens(user)

        return LoginResult(user=user, access=tokens["access"], refresh=tokens["refresh"])

    if mfa_status == MFAStatus.SETUP_REQUIRED:
        return mfa_setup_required(user)

    if mfa_status == MFAStatus.REQUIRED:
        return mfa_verification_required(user)


def mfa_setup_required(user):
    challenge = create_mfa_challenge(user)

    return LoginResult(user=user, mfa_required=True, action="setup", challenge=challenge)


def mfa_verification_required(user):

    challenge = create_mfa_challenge(user)

    return LoginResult(
        user=user,
        mfa_required=True,
        action="verify",
        challenge=challenge,
    )
