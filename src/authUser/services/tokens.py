from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.token_blacklist.models import OutstandingToken, BlacklistedToken
from django.contrib.auth import get_user_model
User = get_user_model()



def generate_tokens(user):
    refresh = RefreshToken.for_user(user)
    return {"access": str(refresh.access_token), "refresh": str(refresh)}


def revoke_user_refresh_tokens(user):

    tokens = OutstandingToken.objects.filter(user=user)

    for token in tokens:
        BlacklistedToken.objects.get_or_create(token=token)


def revoke_refresh_token(token):
    refresh = RefreshToken(token)
    refresh.blacklist()


def refresh_access_token(refresh: str):

    try:
        token = RefreshToken(refresh)

        return {
            "access": str(token.access_token),
            "refresh": refresh,
        }

    except Exception:
        return None
