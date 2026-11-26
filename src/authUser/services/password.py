from django.contrib.auth import get_user_model
from allauth.account.forms import ResetPasswordForm, ResetPasswordKeyForm, UserTokenForm

from .tokens import revoke_user_refresh_tokens


User = get_user_model()


def request_password_reset(request, email):

    form = ResetPasswordForm(data={"email": email})

    if form.is_valid():
        form.save(request)

    return True


def confirm_password_reset(key, new_password, password_confirmation):
    """key : the one of the e-mail link ("<uidb36>-<token>"). allauth checks that it belongs to the user and has not
    expired or been used (the password change makes it invalid) before anything changes."""
    uidb36, _, token = (key or "").partition("-")
    token_form = UserTokenForm(data={"uidb36": uidb36, "key": token})
    if not token_form.is_valid():
        raise Exception("Invalid reset link")
    user = token_form.reset_user

    form = ResetPasswordKeyForm(
        data={
            "password1": new_password,
            "password2": password_confirmation,
        },
        user=user,
    )

    if not form.is_valid():
        raise Exception(" ".join(m for errors in form.errors.values() for m in errors))

    form.save()
    revoke_user_refresh_tokens(user)

    return True
