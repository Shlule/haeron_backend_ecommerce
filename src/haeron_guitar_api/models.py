from django.db import models
import uuid
from ..authUser.models import User


class AuditMixin(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        abstract = True
    
class InstrumentHistory(models.Model):
    instrument = models.ForeignKey("Instrument", on_delete=models.CASCADE)
    event_type = models.CharField(max_length=100)
    title = models.CharField(max_length=True)
    description = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)
    user = models.ForeignKey("User", null=True, blank=True, on_delete=models.SET_NULL)

class InstrumentType(models.Model):
    name = models.CharField(max_length=50, unique=True)

class Instrument(models.Model):
    owner = models.ForeignKey("User", blank=True, null=True, help_text="The owner actual of the instrusment")
    serial_number = models.CharField(max_length=150, unique=True)
    uid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    parts = models.ForeignKey("Part", help_text="list of Part that a instruent is composed of.")
    auth_key = models.TextField(blank=True, null=True, help_text="the public key of the instrument auth and set ownership")

class PartType(models.Model):
    name = models.CharField(max_length=50, unique=True)
    def __str__(self):
        return self.name
    
class PartModel(models.Model):
    name = models.CharField(max_length=100)
    part_type = models.ForeignKey("PartType", on_delete=models.PROTECT) 
    series = models.ForeignKey("Series", null=True, blank=True, on_delete=models.SET_NULL)
    compatible_options = models.ManyToManyField("Option", through="PartModelOption", related_name="compatible_part_models") 
    price = models.DecimalField(max_digits=10, decimal_places=2, default=0.0)
    
    def __str__(self):
        return f"{self.name} ({self.part_type.name})"

class PartModelOption(models.Model):
    part_model = models.ForeignKey("PartModel", on_delete=models.CASCADE)
    option = models.ForeignKey("Option", on_delete=models.CASCADE)
    price_delta = models.DecimalField(max_digits=10, decimal_places=2, default=0.0)
     
    class Meta: 
        unique_together = ("part_model","option")

class PartHistory(models.Model):
    part = models.ForeignKey("Part", on_delete=models.CASCADE)
    event_type = models.CharField(max_length=100)
    title = models.CharField(max_length=100) 
    description = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)
    user = models.ForeignKey("User", null=True, blank=True, on_delete=models.SET_NULL)


class Part(models.Model):
    owner = models.ForeignKey("User", blank=True, null=True, on_delete=models.SET_NULL)
    serial_number = models.CharField(max_length=150, unique=True)
    part_model = models.ForeignKey("PartModel", on_delete=models.PROTECT)
    auth_key = models.TextField()
    part_history = models.ForeignKey("PartHistory", on_delete=models.PROTECT)


class Option(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField()