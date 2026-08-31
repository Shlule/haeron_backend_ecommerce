from django.db import connection
from django.db.migrations.executor import MigrationExecutor

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from rest_framework import status

class LivenessState(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def get(self, requests):
        return Response({"status": "ok"})
    
class ReadinessState(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def get(self, request):
        try:
            # 1. Vérification de la connexion DB
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                cursor.fetchone()

            # 2. Vérification des migrations
            executor = MigrationExecutor(connection)
            plan = executor.migration_plan(
                executor.loader.graph.leaf_nodes()
            )

            if plan:
                return Response(
                    {
                        "status": "not_ready",
                        "database": "ok",
                        "migrations": "pending",
                    },
                    status=status.HTTP_503_SERVICE_UNAVAILABLE,
                )

            return Response(
                {
                    "status": "ready",
                    "database": "ok",
                    "migrations": "ok",
                },
                status=status.HTTP_200_OK,
            )

        except Exception as e:
            return Response(
                {
                    "status": "not_ready",
                    "database": "error",
                    "migrations": "unknown",
                },
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )