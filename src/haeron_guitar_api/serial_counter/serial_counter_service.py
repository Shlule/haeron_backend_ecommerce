from django.db import transaction
from django.utils import timezone
from ..models import SerialCounter

class SerialCounterService:

    @staticmethod
    @transaction
    def next(factory) -> int:
        today = timezone.localdate()
        
        counter, created = SerialCounter.objects.select_for_update().get_or_create(
            factory=factory,
            date=today,
            defaults={"value": 0},
        )

        counter.value += 1
        counter.save(update_fields=["value"])

        return counter.value