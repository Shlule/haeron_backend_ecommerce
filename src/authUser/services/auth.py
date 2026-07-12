from django.contrib.auth import authenticate
from django.contrib.auth import get_user_model
from django.db.models import Q
import logging

logger = logging.getLogger(__name__)

User = get_user_model()


def authenticate_user(identifier, password):
    try:
        user = User.objects.get(Q(username=identifier) | Q(email=identifier))

    except User.DoesNotExist:
        return None

    user = authenticate(username=user.username, password=password)

    if not user:
        return None

    if not user.emailaddress_set.filter(verified=True).exists():
        logger.info("email non verifier")
        return None

    return user
