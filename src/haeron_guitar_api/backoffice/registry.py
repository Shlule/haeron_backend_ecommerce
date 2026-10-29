"""Tables exposed in the back-office CRUD (see backoffice/schema.py).

Each resource gives a model, a French label, a group for the menu and whether it can be written.
Tables left out on purpose :
- User, PartNFCIdentity, ProvisionningAgent, AgentEnrollmentToken : accounts and NFC keys,
  managed by their own flows (signup, MFA, provisioning agent).
Read only tables are created by business flows that do more than a save
(serial numbers, Vault keys, history, payments) : editing them by hand would break that.
"""

from dataclasses import dataclass, field
from typing import Callable

from django.db import models as django_models

from .. import models
from ..security.vault.vault_factory import get_vault_service


def _provision_part_model_key(part_model):
    # same as PartModelService.create : every part model has its own domain key in Vault
    get_vault_service().post_secret("domain", part_model_id=str(part_model.uuid))


@dataclass
class Resource:
    model: type[django_models.Model]
    label: str
    group: str
    readonly: bool = False
    exclude: list[str] = field(default_factory=list)
    after_create: Callable | None = None

    @property
    def name(self):
        return self.model.__name__


# fields never exposed : audit users and secrets
COMMON_EXCLUDE = ["created_by", "updated_by", "vault_batch_key_path"]

RESOURCES = [
    # catalogue
    Resource(models.InstrumentType, "Types d'instrument", "Catalogue"),
    Resource(models.InstrumentModel, "Modèles d'instrument", "Catalogue"),
    Resource(models.Series, "Séries", "Catalogue"),
    Resource(models.PartType, "Types de pièce", "Catalogue"),
    Resource(models.PartModel, "Modèles de pièce", "Catalogue", after_create=_provision_part_model_key),
    Resource(models.Option, "Options", "Catalogue"),
    Resource(models.PartModelOption, "Valeurs d'option", "Catalogue"),
    # boutique et configurateur
    Resource(models.ProductType, "Types de produit", "Boutique"),
    Resource(models.Product, "Produits", "Boutique"),
    Resource(models.ProductSchema, "Schémas de produit", "Boutique"),
    Resource(models.ProductComponent, "Composants", "Boutique"),
    Resource(models.ProductComponentChoice, "Choix de composant", "Boutique"),
    Resource(models.ComponentCompatibility, "Compatibilités", "Boutique"),
    Resource(models.ConfigurationRule, "Règles", "Configurateur"),
    Resource(models.ConfigurationCondition, "Conditions de règle", "Configurateur"),
    Resource(models.ConfigurationResult, "Résultats de règle", "Configurateur"),
    Resource(models.SelectableValue, "Valeurs de règle", "Configurateur"),
    # production
    Resource(models.Factory, "Ateliers", "Production"),
    Resource(models.EngravingTemplate, "Modèles de gravure", "Production"),
    Resource(models.PartBatch, "Lots de pièces", "Production", readonly=True),
    Resource(models.Part, "Pièces fabriquées", "Production", readonly=True),
    Resource(models.Instrument, "Instruments", "Production", readonly=True),
    Resource(models.PartHistory, "Historique des pièces", "Production", readonly=True),
    Resource(models.InstrumentHistory, "Historique des instruments", "Production", readonly=True),
    Resource(models.PartEngravingMark, "Gravures", "Production", readonly=True),
    Resource(models.EngravingBatch, "Lots de gravure", "Production", readonly=True),
    Resource(models.SerialCounter, "Compteurs de série", "Production", readonly=True),
    # ventes
    Resource(models.Cart, "Paniers", "Ventes", readonly=True),
    Resource(models.CartItem, "Lignes de panier", "Ventes", readonly=True),
    Resource(models.Order, "Commandes", "Ventes", readonly=True),
    Resource(models.OrderItem, "Lignes de commande", "Ventes", readonly=True),
]

REGISTERED = {resource.model: resource for resource in RESOURCES}
