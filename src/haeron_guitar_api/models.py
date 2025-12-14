from django.db import models
import uuid
from ..authUser.models import User


class AuditMixin(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey("User", null=True, blank=True, on_delete=models.PROTECT, related_name="%(class)s_created")
    updated_by = models.ForeignKey("User", null=True, blank=True, on_delete=models.PROTECT, related_name="%(class)s_updated")
    
    class Meta:
        abstract = True
    
class InstrumentHistory(AuditMixin):
    instrument = models.ForeignKey("Instrument", on_delete=models.CASCADE)
    event_type = models.CharField(max_length=100)
    title = models.CharField(max_length=True)
    description = models.TextField()

    class Meta: 
        ordering = ["-created_at"]

class InstrumentType(models.Model):
    name = models.CharField(max_length=50, unique=True)
    code = models.CharField(max_length=50, unique=True)
    def __str__(self):
        return self.name

class Instrument(AuditMixin):
    owner = models.ForeignKey("User", blank=True, null=True, help_text="The owner actual of the instrusment")
    serial_number = models.CharField(max_length=150, unique=True)
    uid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    parts = models.ForeignKey("Part", help_text="list of Part that a instruent is composed of.")
    auth_key = models.TextField(blank=True, null=True, help_text="the public key of the instrument auth and set ownership")

class PartType(models.Model):
    name = models.CharField(max_length=50, unique=True)
    code = models.CharField(max_length=50, unique=True)
    def __str__(self):
        return self.name
    

class PartModel(AuditMixin):
    name = models.CharField(max_length=100)
    part_type = models.ForeignKey("PartType", on_delete=models.PROTECT) 
    series = models.ForeignKey("Series", null=True, blank=True, on_delete=models.SET_NULL)
    compatible_options = models.ManyToManyField("Option", through="PartModelOption", related_name="compatible_part_models") 
    price = models.DecimalField(max_digits=10, decimal_places=2, default=0.0)
    code = models.CharField(max_length=50, unique=True)
    
    def __str__(self):
        return f"{self.name} ({self.part_type.name})"

class PartModelOption(AuditMixin):
    part_model = models.ForeignKey("PartModel", on_delete=models.CASCADE)
    option = models.ForeignKey("Option", on_delete=models.CASCADE)
    price_delta = models.DecimalField(max_digits=10, decimal_places=2, default=0.0)
     
    class Meta: 
        unique_together = ("part_model","option")

class PartHistory(AuditMixin):
    part = models.ForeignKey("Part", on_delete=models.CASCADE)
    event_type = models.CharField(max_length=100)
    title = models.CharField(max_length=100) 
    description = models.TextField()

    class Meta:
        ordering = ["-created_at"]

class Part(AuditMixin):
    owner = models.ForeignKey("User", blank=True, null=True, on_delete=models.SET_NULL)
    serial_number = models.CharField(max_length=150, unique=True)
    part_model = models.ForeignKey("PartModel", on_delete=models.PROTECT)
    auth_key = models.TextField()
    part_history = models.ForeignKey("PartHistory", on_delete=models.PROTECT)


class Option(AuditMixin):
    name = models.CharField(max_length=100)
    description = models.TextField()


class SerialCounter(models.Model):
    key = models.CharField(max_length=150, unique=True)
    last_value = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class Factory(models.Model):
    code = models.CharField(max_length=5, unique=True)  # FR, JP, US
    name = models.CharField(max_length=100)
    city = models.CharField(max_length=100)