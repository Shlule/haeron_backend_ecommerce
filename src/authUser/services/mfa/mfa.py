from authUser.models import User
from allauth.mfa.models import Authenticator
from .mfa_challenge import get_user_from_challenge, delete_challenge
from ..tokens import generate_tokens
from allauth.mfa.adapter import get_adapter
import pyotp
from django.core.cache import cache


def user_has_mfa(user):
    return Authenticator.objects.filter(user=user, type=Authenticator.Type.TOTP).exists()

def disable_mfa(user: User):
    Authenticator.objects.filter(user=user, type=Authenticator.Type.TOTP).delete()
    return True


def start_totp_setup(user):
    """Génère un secret temporaire, PAS encore persisté en Authenticator."""
    secret = pyotp.random_base32()
    # secret en attente, lié au user, expire si jamais confirmé (10 min)
    cache.set(f"totp_pending:{user.id}", secret, timeout=600)

    adapter = get_adapter()
    otp_auth_url = pyotp.totp.TOTP(secret).provisioning_uri(
        name=adapter.get_totp_label(user),
        issuer_name=adapter.get_totp_issuer(),
    )
    return {"secret": secret, "otp_auth_url": otp_auth_url}

def confirm_totp_setup(user, code):
    """Vérifie le code fourni, et seulement alors crée l'Authenticator."""
    secret = cache.get(f"totp_pending:{user.id}")
    if not secret:
        raise Exception("No pending TOTP setup or it expired, please restart")

    if not pyotp.TOTP(secret).verify(code, valid_window=1):
        raise Exception("Invalid code")

    adapter = get_adapter()
    Authenticator.objects.create(
        user=user,
        type=Authenticator.Type.TOTP,
        data={"secret": adapter.encrypt(secret)},
    )
    cache.delete(f"totp_pending:{user.id}")
    return True


def get_user_totp(user):
    return Authenticator.objects.filter(user=user, type=Authenticator.Type.TOTP).first()


def verify_totp(user, code):
    authenticator = get_user_totp(user)
    if not authenticator:
        raise Exception("MFA not configured")
    adapter = get_adapter()
    secret = adapter.decrypt(authenticator.data["secret"])
    if not pyotp.TOTP(secret).verify(code, valid_window=1):
        raise Exception("Invalid MFA code")
    return True


def verify_login_mfa(challenge, code):

    user = get_user_from_challenge(challenge)

    if not user:
        raise Exception("Invalid challenge")

    verify_totp(user, code)

    delete_challenge(challenge)

    return generate_tokens(user)