from django.core.management.base import BaseCommand
from django.db import transaction

from haeron_guitar_api.setup_preconfig.starlight_product import handle_starlight_product


class Command(BaseCommand):
    help = "Create (or complete) the configurable Starlight product on an existing database"

    @transaction.atomic
    def handle(self, *args, **options):
        handle_starlight_product()

        self.stdout.write(self.style.SUCCESS("Starlight configurable product ready."))
