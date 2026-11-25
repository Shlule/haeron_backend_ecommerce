"""The file of a supplier invoice (PDF or photo) : sent and read outside GraphQL, so a scanned invoice of a few MB
does not go through the JSON body. Same access as the finances : managers only."""

from django.core.exceptions import ValidationError
from django.http import HttpResponse
from rest_framework import status
from rest_framework.parsers import MultiPartParser
from rest_framework.permissions import BasePermission, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .purchasing_service import PurchasingService

FINANCE_ROLES = ("superadmin", "admin")  # same as backoffice/schema.py


class IsFinanceManager(BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.groups.filter(name__in=FINANCE_ROLES).exists())


class PurchaseInvoiceFileView(APIView):
    permission_classes = [IsAuthenticated, IsFinanceManager]
    parser_classes = [MultiPartParser]

    def get(self, request, invoice_id):
        found = PurchasingService.file(invoice_id)
        if found is None:
            return Response({"detail": "Aucun fichier pour cette facture."}, status=status.HTTP_404_NOT_FOUND)
        content, name, content_type = found
        response = HttpResponse(content, content_type=content_type or "application/octet-stream")
        response["Content-Disposition"] = f'inline; filename="{name.replace(chr(34), "")}"'
        response["X-Content-Type-Options"] = "nosniff"
        return response

    def post(self, request, invoice_id):
        uploaded = request.FILES.get("file")
        if uploaded is None:
            return Response({"detail": "Fichier manquant (champ « file »)."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            PurchasingService.attach_file(invoice_id, uploaded)
        except ValidationError as error:
            return Response({"detail": " ".join(error.messages)}, status=status.HTTP_400_BAD_REQUEST)
        return Response({"ok": True})
