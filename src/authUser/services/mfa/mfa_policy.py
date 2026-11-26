from authUser.services.roles import Roles
from allauth.mfa.models import Authenticator
from .mfa_states import MFAStatus


def user_requires_mfa(user):
    group_names = user.groups.values_list("name", flat=True)
    roles = [Roles.from_value(name) for name in group_names]
    return any(role and role.requires_mfa for role in roles)


def user_has_mfa(user):

    return Authenticator.objects.filter(user=user, type=Authenticator.Type.TOTP).exists()


def get_mfa_status(user):
    # MFA set up (by choice for a customer, imposed for staff): the code is always asked
    if user_has_mfa(user):
        return MFAStatus.REQUIRED

    # the role imposes MFA but it was never set up
    if user_requires_mfa(user):
        return MFAStatus.SETUP_REQUIRED

    return MFAStatus.NOT_REQUIRED
