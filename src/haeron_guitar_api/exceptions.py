class PartIdentityMismatch(Exception): pass
class PartIdentityAlreadyProvisioned(Exception): pass

class NFCVerificationError(Exception):
    """Exception de base pour tout échec de vérification d'un tag NFC."""
    pass

class UnknownTag(NFCVerificationError):
    """Aucune identité active trouvée pour cet UID."""
    pass

class ReplayDetected(NFCVerificationError):
    """Le compteur de lecture a déjà été vu — rejeu probable."""
    pass

class InvalidCMAC(NFCVerificationError):
    """Le CMAC fourni par le tag ne correspond pas à celui recalculé."""
    pass