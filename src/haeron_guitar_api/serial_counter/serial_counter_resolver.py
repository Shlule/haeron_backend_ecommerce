import strawberry
from uuid import UUID
from typing import List, Optional
from .serial_counter_service import SerialCounterService
from .serial_counter_input import SerialCounterFilterInput
from .serial_counter_filter import SerialCounterFilterSet

from ..models import SerialCounter
from ..types import SerialCounterGQLType


@strawberry.type
class SerialCounterQuery:
    @strawberry.field
    def get_serial_counter_by_id(self, uuid: UUID) -> SerialCounterGQLType:
        return SerialCounter.objects.get(uuid)

    @strawberry.field
    def get_all_serial_counter() -> SerialCounterGQLType:
        return SerialCounter.objects.all()

    @strawberry.field
    def serial_counters(self, filters: Optional[SerialCounterFilterInput] = None) -> list[SerialCounterGQLType]:

        qs = SerialCounter.objects.all()

        if filters:
            filterset = SerialCounterFilterSet(data=filters.__dict__, queryset=qs)

            if filterset.is_valid():
                qs = filterset.qs

        return qs


@strawberry.type
class SerialCounterMutation:
    @strawberry.mutation
    def get_or_create_today_serial(self, factory_id: str) -> SerialCounterGQLType:
        return SerialCounterService.get_or_create_today(factory_id=factory_id)

    @strawberry.mutation
    def serial_counter_next(self, factory_id: str) -> int:
        return SerialCounterService.next(factory_id=factory_id)

    @strawberry.mutation
    def delete_serials(self, serial_ids: List[UUID]) -> int:
        delete_count = SerialCounterService.delete(serial_ids)
        return delete_count


SerialCounterMutation = SerialCounterMutation
SerialCounterQuery = SerialCounterQuery
