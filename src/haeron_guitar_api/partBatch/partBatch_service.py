import uuid
from django.db import transaction
from django.shortcuts import get_object_or_404

from haeron_guitar_api.models import PartModel, PartBatch
from haeron_guitar_api.security.vault.vault_service import VaultService
from haeron_guitar_api.security.vault.vault_factory import get_vault_service


class PartBatchService:
    @staticmethod
    @transaction.atomic
    def create(part_model_id: str, name: str) -> PartBatch:

        part_model = get_object_or_404(PartModel, pk=part_model_id)

        batch = PartBatch.objects.create(
            part_model=part_model,
            name=name,
            status="active",
        )

        vault_path = get_vault_service.post_sercret("batch", part_model_id=part_model.uuid, batch_id=batch.uuid)

        batch.vault_batch_key_path = vault_path
        batch.save(update_fields=["vault_batch_key_path"])

        return batch

    # ----------------------------------------------------
    # VAULT LAYER
    # ----------------------------------------------------

    @staticmethod
    def _provision_batch_key(part_model: PartModel, batch: PartBatch) -> str:

        path = get_vault_service.post_secret("batch", part_model_id=part_model.uuid, batch_id=batch.uuid)

        return path

    @staticmethod
    def get_batch_key(batch: PartBatch) -> bytes:
        part_model_id = batch.part_model.uuid

        path = get_vault_service.get_vault_path("batch", part_model_id=part_model_id, batch_id=batch.uuid)
        secret = get_vault_service.get_secret(path)
        return bytes.fromhex(secret["key"])

    @staticmethod
    @transaction.atomic
    def revoke(batch_id: str) -> PartBatch:

        batch = get_object_or_404(PartBatch, pk=batch_id)

        batch.status = "revoked"
        batch.save(update_fields=["status"])

        get_vault_service.delete_secret(batch.vault_batch_key_path)

        return batch

    @staticmethod
    @transaction.atomic
    def rotate(batch_id: str) -> PartBatch:

        batch = get_object_or_404(PartBatch, pk=batch_id)

        old_path = batch.vault_batch_key_path

        new_path = f"secret/batch/{batch.part_model.uuid}/{batch.uuid}/v2"

        new_key = get_vault_service.generate_random_key()

        VaultService.write_secret(
            path=new_path,
            data={
                "batch_key": new_key.hex(),
                "rotated_from": old_path,
            },
        )

        batch.vault_batch_key_path = new_path
        batch.save(update_fields=["vault_batch_key_path"])

        return batch
