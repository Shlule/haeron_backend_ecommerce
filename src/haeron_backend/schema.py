import strawberry

from src.authUser.schema import UserMutation, UserQuery
from src.haeron_guitar_api.schema import ApiMutation, ApiQuery


@strawberry.type
class Query(UserQuery, ApiQuery):
    pass

@strawberry.type
class Mutation(UserMutation, ApiMutation):
    pass

schema = strawberry.Schema(query=Query, mutation=Mutation)