import strawberry
from uuid import UUID

from ..models import SerialCounter
from ..types import SerialCounterGQLType

@strawberry.type
class SerialCounterQuery:
    @strawberry.field
    def get_serial_counter(self, uuid:UUID) -> SerialCounterGQLType:
        return SerialCounter.objects.get(uuid)
    
class SerialCounterMutation:
    @strawberry.mutation
    def create_SerialCounter(self, key:str) -> SerialCounterGQLType:
        return SerialCounter.objects.create(key=key)
    
SerialCounterMutation = SerialCounterMutation
SerialCounterQuery = SerialCounterQuery