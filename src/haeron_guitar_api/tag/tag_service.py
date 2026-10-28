
import hmac
import logging
from django.db import transaction

from ..models import PartNFCIdentity
from .exceptions import UnknownTag, ReplayDetected, InvalidCMAC
from .sdm_crypto import recompute_sdm_cmac  # à écrire, voir plus bas

logger = logging.getLogger(__name__)


def verify_tag_read(nfc_uid: str, counter: int, cmac: str) -> PartNFCIdentity:
    with transaction.atomic():
        try:
            # select_for_update : verrouille la ligne pendant la transaction, évite
            # que deux lectures quasi simultanées du même tag passent la vérification
            # de compteur avant que l'une des deux n'ait eu le temps de le mettre à jour
            identity = PartNFCIdentity.objects.select_for_update().get(
                nfc_uid=nfc_uid, status="active"
            )
        except PartNFCIdentity.DoesNotExist:
            raise UnknownTag(f"Aucune identité active pour UID {nfc_uid}")

        if counter <= identity.last_seen_counter:
            logger.warning("Rejeu détecté pour tag %s (counter=%s)", nfc_uid, counter)
            raise ReplayDetected(f"Compteur rejoué pour tag {nfc_uid}")

        expected_cmac = recompute_sdm_cmac(identity, counter)

        if not hmac.compare_digest(bytes.fromhex(cmac), bytes.fromhex(expected_cmac)):
            raise InvalidCMAC(f"CMAC invalide pour tag {nfc_uid}")

        identity.last_seen_counter = counter
        identity.save(update_fields=["last_seen_counter"])

    return identity