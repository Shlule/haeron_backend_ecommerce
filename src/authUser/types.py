import strawberry


@strawberry.type
class AccountType:
    username: str
    email: str
    # new address waiting for the click on its confirmation link
    pending_email: str | None
    mfa_enabled: bool
    # staff roles must keep MFA
    mfa_required: bool


@strawberry.type
class TokenType:
    access: str
    refresh: str
