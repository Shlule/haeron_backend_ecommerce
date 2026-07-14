import logging
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group

from allauth.account.adapter import get_adapter
from allauth.account.utils import setup_user_email
from django.contrib.auth.password_validation import validate_password
from allauth.account.models import EmailAddress
from django.core.exceptions import ValidationError

from .roles import Roles
from ..dto import SignupDTO

logger = logging.getLogger(__name__)
User = get_user_model()


def verify_email_password(request, dto: SignupDTO):
    if User.objects.filter(username=dto.email).exists():
        raise Exception("Username already in use")

    if dto.password != dto.password_confirmation:
        raise Exception("Passwords do not match")

    if dto.email != dto.email_confirmation:
        raise Exception("Email does not match")

    adapter = get_adapter(request)
    email = adapter.clean_email(dto.email)

    if EmailAddress.objects.filter(email=email).exists():
        raise Exception("Email already exists")

    try:
        validate_password(dto.password)
    except ValidationError as e:
        raise Exception(e.messages)
    return adapter


def signup_customer(request, dto: SignupDTO):
    adapter = verify_email_password(request, dto)

    user = adapter.new_user(request)

    customer_group, created = Group.objects.get_or_create(name=Roles.CUSTOMER.value)

    user.username = dto.user_name
    user.email = adapter.clean_email(dto.email)
    user.set_password(dto.password)
    user.save()
    user.groups.add(customer_group)
    setup_user_email(request, user, [])

    email_address = EmailAddress.objects.get(user=user, email=user.email)
    email_address.send_confirmation(request, signup=True)

    return True


def signup_user_with_role(request, dto: SignupDTO, role_p:str = None) -> bool:
    adapter = verify_email_password(request, dto)

    user = adapter.new_user(request)
    if isinstance(role_p, str):
        role = Roles.from_value(role_p)
    if not role:
        logger.error("%s roles does not exist", role_p)
        return False

    group, created = Group.objects.get_or_create(name=role.value)

    user.username = dto.user_name
    user.email = adapter.clean_email(dto.email)
    user.set_password(dto.password)
    user.save()
    user.groups.add(group)
    setup_user_email(request, user, [])

    email_address = EmailAddress.objects.get(user=user, email=user.email)
    email_address.send_confirmation(request, signup=True)
