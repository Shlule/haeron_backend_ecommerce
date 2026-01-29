from django.contrib.auth.tokens import default_token_generator
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from django.utils.encoding import force_bytes, force_str
from django.contrib.auth import get_user_model
from django.core.mail import send_mail
from django.conf import settings

User = get_user_model()

def make_passord_reset(user):
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    token = default_token_generator.make_token(user)
    return uid, token

def send_password_reset_email(user, uid, token):
    reset_link = f"https://ton-frontend/path-reset?uid={uid}&token={token}"
    subject = "Réinitialisation de votre mot de passe"
    message = f"Bonjour {user.username},\n\nUtilisez ce lien pour réinitialiser votre mot de passe : {reset_link}\n\nSi vous n'avez pas demandé cette réinitialisation, ignorez ce message."
    send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [user.email])