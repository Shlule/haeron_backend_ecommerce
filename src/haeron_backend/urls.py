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

from .schema import schema

from rest_framework_simplejwt.authentication import JWTAuthentication
from django.contrib.auth.models import AnonymousUser


def get_context(request):
    user = AnonymousUser()
    try:
        auth = JWTAuthentication()
        header = auth.get_header(request)
        if header is not None:
            validated_token = auth.get_validated_token(header)
            user = auth.get_user(validated_token)
    except Exception:
        pass

    return {"request": request, "user": user}


class AuthGraphQLView(GraphQLView):
    def get_context(self, request, response):
        return get_context(request)


urlpatterns = [
    path("admin/", admin.site.urls),
    path("graphql/", csrf_exempt(AuthGraphQLView.as_view(schema=schema))),
    path("accounts/", include("allauth.account.urls")),
    path("api/token/resfresh/", TokenRefreshView.as_view(), name="token)refresh"),
]
