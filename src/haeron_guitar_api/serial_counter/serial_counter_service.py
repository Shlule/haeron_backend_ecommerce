from ast import List
from django.db import transaction
from django.utils import timezone
from ..models import SerialCounter, Factory
from uuid import UUID


class SerialCounterService:
    @staticmethod
    @transaction.atomic()
    def next(factory_id: UUID) -> int:
        today = timezone.localdate()

        counter, created = SerialCounter.objects.select_for_update().get_or_create(
            factory=factory_id,
            date=today,
            defaults={"value": 0},
        )

        counter.last_value += 1
        counter.save(update_fields=["last_value"])

        return counter.last_value

    @staticmethod
    def get_or_create_today(factory_id: UUID) -> SerialCounter:
        factory = Factory.objects.get(pk=factory_id)
        today = timezone.localdate()

        counter, created = SerialCounter.objects.get_or_create(factory=factory, date=today)

        return counter

    @staticmethod
    def update_last_value(counter_id: UUID, value: int) -> bool:
        counter = SerialCounter.objects.get(pk=counter_id)
        counter.last_value = value
        counter.save()
        return True

    @staticmethod
    def delete(counter_ids: list[UUID]) -> bool:
        SerialCounter.objects.filter(pk__in=counter_ids).delete()
        return True
