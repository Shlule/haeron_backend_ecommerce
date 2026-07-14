from django.utils.http import urlsafe_base64_decode
from django.utils.encoding import force_str
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.tokens import default_token_generator
from allauth.account.forms import ResetPasswordForm, ResetPasswordKeyForm
from django.contrib.auth import logout

from .tokens import revoke_user_refresh_tokens


User = get_user_model()


def request_password_reset(request, email):

    form = ResetPasswordForm(data={"email": email})

    if form.is_valid():
        form.save(request)

    return True


def confirm_password_reset(uid, key, new_password):

    try:
        uid_decoded = force_str(urlsafe_base64_decode(uid))
        user = User.objects.get(pk=uid_decoded)

    except (User.DoesNotExist, ValueError, TypeError):
        raise Exception("Invalid reset link")

    form = ResetPasswordKeyForm(
        data={
            "password1": new_password,
            "password2": new_password,
        },
        user=user,
    )

    if not form.is_valid():
        raise Exception(form.errors)

    form.save()
    revoke_user_refresh_tokens(user)

    return True
