import strawberry

@strawberry.input
class SignupInput:
    user_name: str
    email: str
    email_confirmation: str
    password: str
    password_confirmation: str
    phone: str
