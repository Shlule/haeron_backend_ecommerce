from allauth.account.models import EmailAddress
from allauth.account.models import EmailConfirmationHMAC
from django.contrib.auth import get_user_model


def resend_verification_email(request, email):

    try:
        email_address = EmailAddress.objects.get(email=email)

    except EmailAddress.DoesNotExist:
        return False

    if email_address.verified:
        raise Exception("Email already verified")

    email_address.send_confirmation(request)

    return True


User = get_user_model()


def verify_email(request, key):

    confirmation = EmailConfirmationHMAC.from_key(key)

    if confirmation is None:
        return False

    confirmation.confirm(request)

    user = confirmation.email_address.user

    user.email_verified = True
    user.save(update_fields=["email_verified"])

    return True
