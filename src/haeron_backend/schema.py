import strawberry

from authUser.schema import UserMutation, UserQuery
from haeron_guitar_api.instruments.instrument_resolver import InstrumentMutation, InstrumentQuery


@strawberry.type
class Query(UserQuery, InstrumentQuery):
    pass

@strawberry.type
class Mutation(UserMutation, InstrumentMutation):
    pass

schema = strawberry.Schema(query=Query, mutation=Mutation)