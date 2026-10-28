from allauth.mfa.adapter import DefaultMFAAdapter


class CustomMFAAdapter(DefaultMFAAdapter):
    def get_totp_issuer(self):
        return "Haeron"

    def get_totp_label(self, user):
        return user.email

    def generate_authenticator_name(self, user, type):
        return f"{type} - {user.email}"
