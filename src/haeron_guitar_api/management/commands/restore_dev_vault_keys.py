"""Gives back their keys to the part models and batches of the local database after the local Vault restarted.

The Vault of compose.dev.yaml runs in dev mode : it is kept in memory, so its keys are lost when Docker stops,
while the local Postgres keeps its data. The back-office then fails with "Clé du modèle illisible dans Vault
(VaultSecretNotFound)". This command writes a new key for every part model and batch that has none.

New keys mean new hidden codes and new NFC tag keys : fine for test data, never for real parts. So the command
only runs against a Vault on this computer (127.0.0.1 or localhost).
"""

from urllib.parse import urlparse

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from haeron_guitar_api.models import PartBatch, PartModel
from haeron_guitar_api.security.vault.vault_execptions import VaultSecretNotFound
from haeron_guitar_api.security.vault.vault_factory import get_vault_service

LOCAL_HOSTS = {"127.0.0.1", "localhost", "::1"}


class Command(BaseCommand):
    help = "Writes a new key in the local Vault for every part model and batch that lost its key (dev Vault only)."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="Only list the missing keys.")

    def handle(self, *args, dry_run=False, **options):
        host = urlparse(settings.VAULT_ADDR).hostname
        if host not in LOCAL_HOSTS:
            raise CommandError(
                f"Vault {settings.VAULT_ADDR} n'est pas le Vault local : nouvelles clés refusées "
                "(elles rendraient faux les codes cachés et les puces NFC des vraies pièces). Lance-la avec .\\local.ps1."
            )
        vault = get_vault_service()

        def missing(path):
            try:
                vault.get_secret(path)
                return False
            except VaultSecretNotFound:
                return True

        created = 0
        for part_model in PartModel.objects.order_by("name"):
            if missing(vault.get_vault_path("domain", part_model_id=str(part_model.uuid))):
                self.stdout.write(f"modèle de pièce {part_model.name} ({part_model.code})")
                if not dry_run:
                    vault.post_secret("domain", part_model_id=str(part_model.uuid))
                created += 1
        for batch in PartBatch.objects.select_related("part_model").order_by("part_model__name", "code"):
            path = vault.get_vault_path("batch", part_model_id=batch.part_model_id, batch_id=batch.uuid)
            if missing(path):
                self.stdout.write(f"lot {batch.code} de {batch.part_model.name}")
                if not dry_run:
                    batch.vault_batch_key_path = vault.post_secret("batch", part_model_id=batch.part_model_id, batch_id=batch.uuid)
                    batch.save(update_fields=["vault_batch_key_path"])
                created += 1

        if not created:
            self.stdout.write(self.style.SUCCESS("Aucune clé manquante."))
        elif dry_run:
            self.stdout.write(self.style.WARNING(f"{created} clé(s) manquante(s), rien n'a été écrit (--dry-run)."))
        else:
            self.stdout.write(self.style.SUCCESS(f"{created} clé(s) recréée(s) dans le Vault local."))
