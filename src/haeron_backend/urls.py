"""
URL configuration for haeron_backend project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""

from django.contrib import admin
from django.urls import path, include
from rest_framework_simplejwt.views import TokenRefreshView
from strawberry.django.views import GraphQLView
from django.views.decorators.csrf import csrf_exempt
from haeron_guitar_api.payments.stripe_webhook import stripe_webhook

from .schema import schema

from rest_framework_simplejwt.authentication import JWTAuthentication
from django.contrib.auth.models import AnonymousUser

from .views import LivenessState, ReadinessState
from provisionning_agent.views import AgentEnrollView, ConfirmProvisionningView, RevokeProvisionningView, ProvisionIdentityView, VerifyPart


def get_context(request):
    user = AnonymousUser()
    try:
        
        auth = JWTAuthentication()
        header = auth.get_header(request)
        raw_token = auth.get_raw_token(header)
        if header is not None:
            validated_token = auth.get_validated_token(raw_token)
            user = auth.get_user(validated_token)
            request.user = user
    except Exception:
        pass

    return {"request": request}


class AuthGraphQLView(GraphQLView):
    def get_context(self, request, response):
        return get_context(request)


urlpatterns = [
    path("admin/", admin.site.urls),
    path("graphql/", csrf_exempt(AuthGraphQLView.as_view(schema=schema))),
    path("api/token/resfresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("api/payments/stripe/webhook/", stripe_webhook, name="stripe_webhook"),
    path("agents/enroll/", AgentEnrollView.as_view(), name="agent-enroll"),
    path("agents/provision-identity/", ProvisionIdentityView.as_view(), name="provision_identity"),
    path("agents/confirm-identity/", ConfirmProvisionningView.as_view(), name="confirm_identity"),
    path("agents/revoke-identity/", RevokeProvisionningView.as_view(), name="revoke_identity"),
    path("api/verify-part/", VerifyPart.as_view(), name="verifying if th part is authentique" ),
    path("health/live/", LivenessState.as_view(), name="health-live"),
    path("health/ready/", ReadinessState.as_view(), name="health-ready"),
    # path("accounts/", include("allauth.urls")),
    # path("accounts/mfa", include("allauth.mfa.urls")),
]
