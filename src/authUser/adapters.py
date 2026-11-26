from allauth.account.adapter import DefaultAccountAdapter
from decouple import config


class AccountAdapter(DefaultAccountAdapter):
    """The e-mail links open the shop pages, which call the GraphQL API (there are no allauth HTML pages)."""

    def shop_url(self, path):
        return config("SHOP_URL", default="http://localhost:3000").rstrip("/") + path

    def get_email_confirmation_url(self, request, emailconfirmation):
        return self.shop_url(f"/compte/confirmer/{emailconfirmation.key}")

    def get_reset_password_from_key_url(self, key):
        return self.shop_url(f"/compte/nouveau-mot-de-passe/{key}")
