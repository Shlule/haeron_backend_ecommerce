from django.core.management.base import BaseCommand
from django.db import transaction

from haeron_guitar_api.setup_preconfig.common import handle_common
from haeron_guitar_api.setup_preconfig.starlight import handle_starlight




class Command(BaseCommand):
    help = "Initialize the database"

    @transaction.atomic
    def handle(self, *args, **options):
        handle_common()
        handle_starlight()
        

        self.stdout.write(
            self.style.SUCCESS("Database initialized successfully.")
        )