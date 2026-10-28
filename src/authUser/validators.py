from django.core.exceptions import ValidationError
import re

class PasswordValidator:
    def validate(self, password, user=None):
        if not re.search(r"[A-Z]", password):
            raise ValidationError("Le mot de passe doit contenir au moins une majuscule.")
        if not re.search(r"[a-z]", password):
            raise ValidationError("Le mot de passe doit contenir au moins une minuscule.")
        if not re.search(r"\d", password):
            raise ValidationError("Le mot de passe doit contenir au moins un chiffre.")
        if not re.search(r"[!@#$%^&*()_+=\-{}\[\]:;\"'<>,.?/]", password):
            raise ValidationError("Le mot de passe doit contenir au moins un caractère spécial.")

    def get_help_text(self):
        return "Le mot de passe doit contenir au moins une majuscule, une minuscule, un chiffre et un caractère spécial."