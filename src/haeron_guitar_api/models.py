from django.db import models
import uuid
from django.conf import settings
from django.core.exceptions import ValidationError


class AuditMixin(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="%(class)s_created"
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="%(class)s_updated"
    )

    class Meta:
        abstract = True


class InstrumentHistory(AuditMixin):
    uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    instrument = models.ForeignKey("Instrument", on_delete=models.CASCADE, related_name="history")
    event_type = models.CharField(max_length=100)
    title = models.CharField(max_length=100)
    description = models.TextField()

    class Meta:
        ordering = ["-created_at"]


class InstrumentType(models.Model):
    uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=50, unique=True)
    code = models.CharField(max_length=10, unique=True)

    def __str__(self):
        return self.name


class Instrument(AuditMixin):
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        blank=True,
        null=True,
        help_text="The owner actual of the instrusment",
        on_delete=models.SET_NULL,
    )
    uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    master_part = models.OneToOneField(
        "Part",
        on_delete=models.PROTECT,
        related_name="instrument_masterpart",
        limit_choices_to={"is_master": True},
    )
    instrument_model = models.ForeignKey("InstrumentModel", on_delete=models.PROTECT, related_name="instruments")


class InstrumentModel(models.Model):
    uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100, unique=True)
    instrument_type = models.ForeignKey("InstrumentType", related_name="instrument_models", on_delete=models.CASCADE)
    compatible_parts = models.ManyToManyField("PartModel", through="ComponentCompatibility")


class PartType(models.Model):
    uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=50, unique=True)
    code = models.CharField(max_length=5, unique=True)

    def __str__(self):
        return self.name


class PartModel(AuditMixin):
    uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.CharField(max_length=5, unique=True)
    name = models.CharField(max_length=100)
    price = models.DecimalField(max_digits=10, decimal_places=2, default=0.0)
    part_type = models.ForeignKey("PartType", on_delete=models.PROTECT)
    series = models.ForeignKey("Series", null=True, blank=True, on_delete=models.SET_NULL)

    def __str__(self):
        return f"{self.name} ({self.part_type.name})"


class PartModelOption(AuditMixin):
    uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=20)
    part_model = models.ForeignKey("PartModel", on_delete=models.CASCADE)
    option = models.ForeignKey("Option", on_delete=models.CASCADE)
    price_delta = models.DecimalField(max_digits=10, decimal_places=2, default=0.0)


class PartHistory(AuditMixin):
    uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    part = models.ForeignKey("Part", on_delete=models.CASCADE, related_name="history")
    event_type = models.CharField(max_length=100)
    title = models.CharField(max_length=100)
    description = models.TextField()

    class Meta:
        ordering = ["-created_at"]


class Part(AuditMixin):
    uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, blank=True, null=True, on_delete=models.SET_NULL)
    serial_number = models.CharField(max_length=150, unique=True)
    instrument = models.ForeignKey(
        "Instrument",
        blank=True,
        null=True,
        help_text="the instrument that be associated of this part",
        on_delete=models.PROTECT,
        related_name="instrument_parts",
    )
    part_model = models.ForeignKey("PartModel", on_delete=models.PROTECT)
    batch = models.ForeignKey(
        "PartBatch",
        related_name="parts",
        on_delete=models.PROTECT,
    )
    is_master = models.BooleanField(default=False)
class PartSecurityMark(models.Model):
    uuid = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False
    )

    part = models.ForeignKey(
        "Part",
        related_name="security_marks",
        on_delete=models.CASCADE
    )

    mark_type = models.CharField(
        max_length=50,
        choices=[
            ("laser_engraving", "Laser engraving"),
            ("qr_code", "QR Code"),
        ]
    )

    value = models.CharField(
        max_length=255,
        help_text="The visible identifier"
    )

    location = models.CharField(
        max_length=255,
        help_text="Physical location of the mark"
    )

    description = models.TextField(
        blank=True,
        help_text="Additional information about the mark"
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

class PartBatch(models.Model):
    uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    part_model = models.ForeignKey("PartModel", on_delete=models.CASCADE, related_name="batches")

    name = models.CharField(max_length=100)
    code = models.CharField(max_length=5)

    vault_batch_key_path = models.CharField(max_length=255)

    status = models.CharField(
        max_length=20,
        choices=[
            ("active", "Active"),
            ("ended", "Ended"),
            ("revoked", "Revoked"),
        ],
        default="active",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    ended_at = models.DateTimeField(null=True, blank=True)


class PartNFCIdentity(models.Model):
    part = models.ForeignKey("Part", related_name="part_identies", on_delete=models.CASCADE)
    nfc_uid = models.CharField(max_length=32, db_index=True, help_text="NFC tag UID")
    batch = models.ForeignKey("PartBatch", on_delete=models.PROTECT)
    key_version = models.IntegerField(default=1)
    status = models.CharField(
        max_length=20,
        choices=[("active", "Active"),("pending", "Pending"), ("revoked", "Revoked"), ("rotated", "Rotated"), ("error", "error")],
        default="pending",
    )
    binding_hash = models.CharField(max_length=128, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    revoked_at = models.DateTimeField(null=True, blank=True)


class Option(AuditMixin):
    uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100)
    description = models.TextField(null=True, blank=True)
    category = models.CharField(max_length=100, null=True, blank=True)


class SerialCounter(models.Model):
    uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    factory = models.ForeignKey("Factory", on_delete=models.CASCADE)
    year = models.PositiveIntegerField()
    last_value = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [
            ("factory", "year")
        ]


class Series(models.Model):
    uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100, unique=True)
    code = models.CharField(max_length=5, unique=True)


class Factory(models.Model):
    uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.CharField(max_length=5, unique=True)
    name = models.CharField(max_length=100)


class Product(models.Model):
    uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    product_type = models.ForeignKey("ProductType", related_name="type_products", on_delete=models.PROTECT)
    product_schema = models.ForeignKey(
        "ProductSchema", related_name="schema_products", on_delete=models.SET_NULL, null=True
    )
    instrument_model = models.ForeignKey(
        "InstrumentModel", related_name="products", null=True, blank=True, on_delete=models.SET_NULL
    )


class ProductType(models.Model):
    uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.CharField(max_length=50, unique=True)


class ProductComponent(models.Model):
    uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    # manytoMany because the component can be shared between schema . multiple schema can get a neck component and a schema get multiple component
    # such as neck body etc.
    product_schemas = models.ManyToManyField("ProductSchema", related_name="product_components", blank=True, null=True)
    key = models.CharField(max_length=50)
    source_type = models.CharField(
        max_length=30,
        choices=[
            ("custom_piece", "Custom Piece"),
            ("product_choice", "Product Choice"),
            ("fixed", "Fixed"),
            ("product_configurable", "Configurable Product"),
        ],
    )
    fixed_product = models.ForeignKey("Product", null=True, blank=True, on_delete=models.PROTECT)
    # required = models.BooleanField(default=True)


class ProductComponentChoice(models.Model):
    uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    component = models.ForeignKey(
        "ProductComponent", related_name="product_component_choices", on_delete=models.CASCADE
    )
    product = models.ForeignKey("Product", on_delete=models.CASCADE)


# caution in case we want to retrieve a parMoel from a product be sure that the instrument_model is not empty
# because we get the partmodel thanks to this class
class ComponentCompatibility(models.Model):
    instrument_model = models.ForeignKey("InstrumentModel", blank=True, null=True, on_delete=models.SET_NULL)
    part_model = models.ForeignKey("PartModel", blank=True, null=True, on_delete=models.SET_NULL)
    component = models.ForeignKey(
        "ProductComponent", related_name="component_compatibilities", on_delete=models.CASCADE
    )

    # class Meta:
    #     unique_together = ("instrument_model", "part_model", "component")


class ProductSchema(models.Model):
    uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=50)


class Cart(models.Model):
    uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.CASCADE)
    session_key = models.CharField(max_length=255, null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    last_activity_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)


class CartItem(models.Model):
    uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    cart = models.ForeignKey("Cart", blank=True, related_name="cart_items", null=True, on_delete=models.CASCADE)
    product = models.ForeignKey("Product", blank=True, null=True, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    created_at = models.DateField(auto_now_add=True)
    config_snapshot = models.JSONField(default=dict, null=True, blank=True)
    config_hash = models.CharField(max_length=64, db_index=True, blank=True, null=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["cart", "config_hash"], name="uniq_cartItem_config")]


class Order(models.Model):
    uuid = models.UUIDField(default=uuid.uuid4, unique=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)

    # this key is provided by the front end th goal is to avoid genreating multiple order if
    # user emit multiple request because low frequency network
    idempotency_key = models.UUIDField()

    status = models.CharField(
        max_length=30,
        choices=[
            ("pending", "Pending"),
            ("paid", "Paid"),
            ("processing", "Processing"),
            ("shipped", "Shipped"),
            ("completed", "Completed"),
            ("cancelled", "Cancelled"),
        ],
        default="pending",
    )

    # blankable and nullable because we fill this fields with calculation of order itemPrice.
    total_price = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)


class OrderItem(models.Model):
    order = models.ForeignKey(Order, related_name="order_items", on_delete=models.CASCADE)

    product_id = models.UUIDField()
    product_name = models.CharField(max_length=255)

    quantity = models.IntegerField()
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)

    config_snapshot = models.JSONField()
    config_hash = models.CharField(max_length=64)


# this is use for Rule Engine and put relation between partModelOption on productCOmponentChoice
# this is link with ConfigurationCondition and ConfigurationResult and participate for the rule engine


# the rule engine is a mecanism for put rule configuration for the product. so if partModeloption of component neck is blue
# then le possibilitie for the option matrial of component body is aluminium and mapple.
class SelectableValue(models.Model):
    part_model_option = models.ForeignKey("PartModelOption", null=True, blank=True, on_delete=models.CASCADE)

    product_component_choice = models.ForeignKey(
        "ProductComponentChoice", null=True, blank=True, on_delete=models.CASCADE
    )


class ConfigurationRule(models.Model):
    uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255, blank=True)

    # make sure to have only one of this field fill
    # Scope global -> peut etre optionnel
    target_schema = models.ForeignKey(
        "ProductSchema", blank=True, null=True, on_delete=models.CASCADE, related_name="targeted_rules"
    )

    # Optionnel → si la règle cible un composant précis
    target_component = models.ForeignKey(
        "ProductComponent", on_delete=models.CASCADE, related_name="targeted_rules", null=True, blank=True
    )

    # Optionnel -> si la regel est lier a un piece physique

    target_part_model = models.ForeignKey(
        "partModel", on_delete=models.CASCADE, related_name="targeted_rules", null=True, blank=True
    )

    def clean(self):

        scopes = [
            self.target_schema,
            self.target_component,
            self.target_part_model,
        ]

        filled = sum(1 for s in scopes if s is not None)

        if filled != 1:
            raise ValidationError("Exactly one scope must be defined.")


class ConfigurationCondition(models.Model):
    rule = models.ForeignKey("ConfigurationRule", on_delete=models.CASCADE, related_name="conditions")

    source_component = models.ForeignKey("ProductComponent", on_delete=models.CASCADE)
    source_option = models.ForeignKey("Option", on_delete=models.CASCADE)
    operator = models.CharField(
        max_length=10,
        choices=[
            ("eq", "Equals"),
            ("neq", "Not equals"),
            ("in", "In"),
        ],
    )

    # cela est peut etre pas necessaire car  on peut faire dirrectement un recherche sur le partmodel
    # source_values = models.ManyToManyField("SelectableValue", related_name="condition_sources")

    compare_values = models.ManyToManyField("SelectableValue", related_name="condition_targets")


class ConfigurationResult(models.Model):
    rule = models.ForeignKey("ConfigurationRule", on_delete=models.CASCADE, related_name="results")

    target_component = models.ForeignKey("ProductComponent", on_delete=models.CASCADE)
    target_option = models.ForeignKey("Option", on_delete=models.CASCADE)
    target_values = models.ManyToManyField("SelectableValue", related_name="result_targets")

    # values = models.ManyToManyField("SelectableValue", related_name="result_values")
