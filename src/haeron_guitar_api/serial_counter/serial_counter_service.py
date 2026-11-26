from django.db import transaction
from django.utils import timezone
from ..models import SerialCounter, Factory
from uuid import UUID


class SerialCounterService:
    """One counter per workshop, part model and year (see SerialCounter)."""

    @staticmethod
    @transaction.atomic
    def reserve(factory_id: UUID, part_model_id: UUID) -> tuple[int, int]:
        """Take the next number for this part model : the counter row stays locked until the end of the
        transaction, so two parts made at the same time never get the same number."""
        year = timezone.now().year
        SerialCounter.objects.get_or_create(factory_id=factory_id, part_model_id=part_model_id, year=year)
        counter = SerialCounter.objects.select_for_update().get(
            factory_id=factory_id, part_model_id=part_model_id, year=year
        )
        counter.last_value += 1
        counter.save(update_fields=["last_value", "updated_at"])
        return counter.last_value, counter.year

    @staticmethod
    def next(factory_id: UUID, part_model_id: UUID) -> int:
        return SerialCounterService.reserve(factory_id, part_model_id)[0]

    @staticmethod
    def get_or_create_today(factory_id: UUID, part_model_id: UUID) -> SerialCounter:
        factory = Factory.objects.get(pk=factory_id)
        year = timezone.now().year

        counter, _ = SerialCounter.objects.get_or_create(factory=factory, part_model_id=part_model_id, year=year)

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
