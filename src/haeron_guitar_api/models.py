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
    parts = models.ForeignKey(
        "Part",
        blank=True,
        null=True,
        help_text="list of Part that a instruent is composed of.",
        on_delete=models.PROTECT,
        related_name="instrument_parts",
    )
    master_part = models.OneToOneField(
        "Part",
        on_delete=models.PROTECT,
        related_name="instrument_masterpart",
        limit_choices_to={"is_master": True},
    )
    instrument_type = models.ForeignKey("InstrumentType", on_delete=models.PROTECT, related_name="instruments")


class PartType(models.Model):
    uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=50, unique=True)
    code = models.CharField(max_length=10, unique=True)
    instrument_types = models.ManyToManyField("InstrumentType", related_name="part_types", blank=True)

    def __str__(self):
        return self.name


class PartModel(AuditMixin):
    uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100)
    part_type = models.ForeignKey("PartType", on_delete=models.PROTECT)
    series = models.ForeignKey("Series", null=True, blank=True, on_delete=models.SET_NULL)
    price = models.DecimalField(max_digits=10, decimal_places=2, default=0.0)
    code = models.CharField(max_length=50, unique=True)

    def __str__(self):
        return f"{self.name} ({self.part_type.name})"


class PartModelOption(AuditMixin):
    uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=100)
    part_model = models.ForeignKey("PartModel", on_delete=models.CASCADE)
    option = models.ForeignKey("Option", on_delete=models.CASCADE)
    price_delta = models.DecimalField(max_digits=10, decimal_places=2, default=0.0)

    class Meta:
        unique_together = ("part_model", "option")


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
    config_snapshot = models.JSONField(default=dict)
    config_hash = models.CharField(max_length=64, db_index=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["cart", "config_hash"], name="uniq_cartItem_config")]


class CartItemOption(models.Model):
    cart_item = models.ForeignKey("CartItem", related_name="cart_item_options", on_delete=models.CASCADE)
    option = models.ForeignKey("PartModelOption", on_delete=models.CASCADE)
    price_delta = models.DecimalField(max_digits=10, decimal_places=2)
