"""Failed attempts (password, MFA code) are counted per account: after 5 in 5 minutes the account refuses any try,
so a password or a 6-digit code cannot be found by trying them all."""
from django.core.cache import cache

# shortcut: Django's default cache lives in the process (like the MFA challenges), fine with the single backend
# pod/worker of today; switch CACHES to the Redis of the cluster before running several.
MAX_FAILURES = 5
WINDOW_SECONDS = 300


def check(key):
    if cache.get(key, 0) >= MAX_FAILURES:
        raise Exception("Too many attempts, try again in a few minutes")


def failed(key):
    # the window starts at the first failure
    cache.add(key, 0, WINDOW_SECONDS)
    try:
        cache.incr(key)
    except ValueError:  # expired between add and incr
        cache.set(key, 1, WINDOW_SECONDS)


def reset(key):
    cache.delete(key)
