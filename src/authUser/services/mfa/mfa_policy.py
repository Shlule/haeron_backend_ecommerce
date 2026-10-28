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

    # Cas 1
    # Le rôle n'impose pas MFA

    if not user_requires_mfa(user):
        return MFAStatus.NOT_REQUIRED

    # Cas 2
    # MFA obligatoire mais jamais configuré

    if not user_has_mfa(user):
        return MFAStatus.SETUP_REQUIRED

    # Cas 3
    # MFA existe, attente du code

    return MFAStatus.REQUIRED
