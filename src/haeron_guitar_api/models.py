from django.db import models
import uuid
from django.conf import settings


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
    code = models.CharField(max_length=10, unique=True)
    instrument_types = models.ManyToManyField("InstrumentType", related_name="part_types", blank=True)

    def __str__(self):
        return self.name


class PartModel(AuditMixin):
    uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.CharField(max_length=50, unique=True)
    name = models.CharField(max_length=100)
    price = models.DecimalField(max_digits=10, decimal_places=2, default=0.0)
    part_type = models.ForeignKey("PartType", on_delete=models.PROTECT)
    series = models.ForeignKey("Series", null=True, blank=True, on_delete=models.SET_NULL)

    def __str__(self):
        return f"{self.name} ({self.part_type.name})"


class PartModelOption(AuditMixin):
    uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=100)
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
    auth_key = models.CharField(max_length=200, unique=True)
    is_master = models.BooleanField(default=False)


class Option(AuditMixin):
    uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100)
    description = models.TextField(null=True, blank=True)
    category = models.CharField(max_length=100, null=True, blank=True)


class SerialCounter(models.Model):
    uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    factory = models.ForeignKey("Factory", on_delete=models.CASCADE)
    date = models.DateField()
    last_value = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("factory", "date")


class Series(models.Model):
    uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100, unique=True)
    code = models.CharField(max_length=10, unique=True)


class Factory(models.Model):
    uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.CharField(max_length=10, unique=True)
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
    product_schema = models.ForeignKey("ProductSchema", related_name="product_components", on_delete=models.CASCADE)
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
    instrument_model = models.ForeignKey("InstrumentModel", blank=True, null=True, on_delete=models.CASCADE)
    part_model = models.ForeignKey("PartModel", blank=True, null=True, on_delete=models.CASCADE)
    component = models.ForeignKey("ProductComponent", on_delete=models.CASCADE)

    class Meta:
        unique_together = ("instrument_model", "part_model", "component")


class ProductSchema(models.Model):
    uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=100)


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

    status = models.CharField(
        max_length=30,
        choices=[
            ("draft", "Draft"),
            ("paid", "Paid"),
            ("processing", "Processing"),
            ("completed", "Completed"),
        ],
        default="draft",
    )

    total_price = models.DecimalField(max_digits=10, decimal_places=2)

    created_at = models.DateTimeField(auto_now_add=True)


class OrderItem(models.Model):
    order = models.ForeignKey(Order, related_name="order_items", on_delete=models.CASCADE)

    product_id = models.UUIDField()

    quantity = models.IntegerField()
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)

    config_snapshot = models.JSONField()
    config_hash = models.CharField(max_length=64)


class ConfigurationRule(models.Model):
    uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Scope global ou local
    product_schema = models.ForeignKey("ProductSchema", on_delete=models.CASCADE, related_name="configuration_rules")

    # Optionnel → si la règle cible un composant précis
    target_component = models.ForeignKey(
        "ProductComponent", on_delete=models.CASCADE, related_name="targeted_rules", null=True, blank=True
    )

    name = models.CharField(max_length=255, blank=True)
    priority = models.IntegerField(default=0)

    def __str__(self):
        return self.name or f"Rule {self.uuid}"


class SelectableValue(models.Model):
    VALUE_TYPE_CHOICES = [
        ("option", "PartModelOption"),
        ("product", "Product"),
    ]

    type = models.CharField(max_length=20, choices=VALUE_TYPE_CHOICES)

    part_model_option = models.ForeignKey("PartModelOption", null=True, blank=True, on_delete=models.CASCADE)

    product = models.ForeignKey("Product", null=True, blank=True, on_delete=models.CASCADE)

    def __str__(self):
        if self.type == "option" and self.part_model_option:
            return f"Option: {self.part_model_option}"
        if self.type == "product" and self.product:
            return f"Product: {self.product}"
        return "Invalid SelectableValue"


class ConfigurationCondition(models.Model):
    rule = models.ForeignKey(ConfigurationRule, on_delete=models.CASCADE, related_name="conditions")

    source_component = models.ForeignKey("ProductComponent", on_delete=models.CASCADE, related_name="source_conditions")

    operator = models.CharField(
        max_length=10,
        choices=[
            ("eq", "Equals"),
            ("in", "In"),
            ("neq", "Not equals"),
        ],
        default="in",
    )

    values = models.ManyToManyField("SelectableValue")

    def __str__(self):
        return f"Condition on {self.source_component.key}"


class ConfigurationResult(models.Model):
    rule = models.ForeignKey(ConfigurationRule, on_delete=models.CASCADE, related_name="results")

    target_component = models.ForeignKey("ProductComponent", on_delete=models.CASCADE, related_name="result_rules")

    allowed_values = models.ManyToManyField("SelectableValue")

    def __str__(self):
        return f"Result for {self.target_component.key}"
