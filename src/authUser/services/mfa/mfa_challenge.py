from django.core.cache import cache
import uuid


def create_mfa_challenge(user):

    challenge = str(uuid.uuid4())

    cache.set(f"mfa:{challenge}", user.id, timeout=300)
    return challenge


def get_user_from_challenge(challenge):

    user_id = cache.get(f"mfa:{challenge}")

    if not user_id:
        return None

    from django.contrib.auth import get_user_model

    User = get_user_model()

    return User.objects.get(id=user_id)


def delete_challenge(challenge):

    cache.delete(f"mfa:{challenge}")
