"""« Mon compte » of the shop: the logged-in user changes his name, e-mail, password and MFA."""
from allauth.account.adapter import get_adapter
from allauth.account.forms import ChangePasswordForm
from allauth.account.models import EmailAddress
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError

from .mfa.mfa import confirm_totp_setup, disable_mfa, start_totp_setup, verify_totp
from .mfa.mfa_policy import user_has_mfa, user_requires_mfa
from .tokens import generate_tokens, revoke_user_refresh_tokens

User = get_user_model()


def pending_email(user):
    address = EmailAddress.objects.filter(user=user, verified=False).exclude(email=user.email).first()
    return address.email if address else None


def update_username(user, username):
    username = (username or "").strip()
    try:
        User._meta.get_field("username").run_validators(username)
    except ValidationError as e:
        raise Exception(" ".join(e.messages))
    if not username or User.objects.filter(username__iexact=username).exclude(pk=user.pk).exists():
        raise Exception("Username already in use")
    user.username = username
    user.save(update_fields=["username", "updated_at"])
    return user


def change_password(user, current_password, new_password, password_confirmation):
    form = ChangePasswordForm(
        data={"oldpassword": current_password, "password1": new_password, "password2": password_confirmation},
        user=user,
    )
    if not form.is_valid():
        raise Exception(" ".join(m for errors in form.errors.values() for m in errors))
    form.save()
    # the other sessions are logged out, this one gets new tokens
    revoke_user_refresh_tokens(user)
    return generate_tokens(user)


def request_email_change(request, user, password, email, email_confirmation):
    if not user.check_password(password):
        raise Exception("Invalid password")
    if email != email_confirmation:
        raise Exception("Email does not match")
    email = get_adapter(request).clean_email(email)
    if email.lower() == user.email.lower():
        raise Exception("This is already your email")
    if (
        EmailAddress.objects.filter(email__iexact=email).exclude(user=user).exists()
        or User.objects.filter(email__iexact=email).exclude(pk=user.pk).exists()
    ):
        raise Exception("Email already exists")

    # one change at a time: a new request replaces the one waiting for its confirmation
    EmailAddress.objects.filter(user=user, verified=False).exclude(email=user.email).delete()
    address = EmailAddress.objects.create(user=user, email=email, primary=False, verified=False)
    # the address changes when the link sent to it is opened (ACCOUNT_CHANGE_EMAIL)
    address.send_confirmation(request)
    return True


def start_mfa_setup(user):
    if user_has_mfa(user):
        raise Exception("MFA already enabled")
    return start_totp_setup(user)


def enable_mfa(user, code):
    if user_has_mfa(user):
        raise Exception("MFA already enabled")
    return confirm_totp_setup(user, code)


def remove_mfa(user, code):
    if user_requires_mfa(user):
        raise Exception("MFA is required for your role")
    verify_totp(user, code)
    return disable_mfa(user)
