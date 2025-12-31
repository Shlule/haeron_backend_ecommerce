import strawberry

from authUser.schema import UserMutation, UserQuery
from haeron_guitar_api.instruments.instrument_resolver import InstrumentMutation, InstrumentQuery
from haeron_guitar_api.intrumentTypes.instrumentType_resolver import InstrumentTypeMutation, InstrumentTypeQuery
from haeron_guitar_api.factories.factory_resolver import FactoryMutation, FactoryQuery


@strawberry.type
class Query(UserQuery, InstrumentQuery, InstrumentTypeQuery, FactoryQuery):
    pass

@strawberry.type
class Mutation(UserMutation, InstrumentMutation, InstrumentTypeMutation, FactoryMutation):
    pass

schema = strawberry.Schema(query=Query, mutation=Mutation)