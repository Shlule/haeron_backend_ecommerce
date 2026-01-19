import strawberry

from authUser.schema import UserMutation, UserQuery
from haeron_guitar_api.instruments.instrument_resolver import InstrumentMutation, InstrumentQuery
from haeron_guitar_api.intrumentTypes.instrumentType_resolver import InstrumentTypeMutation, InstrumentTypeQuery
from haeron_guitar_api.factories.factory_resolver import FactoryMutation, FactoryQuery
from haeron_guitar_api.options.option_resolver import OptionMutation, OptionQuery
from haeron_guitar_api.partModel_Options.part_model_option_resolver import PartModelOptionQuery, PartModelOptionQuery


@strawberry.type
class Query(UserQuery,
            InstrumentQuery,
            InstrumentTypeQuery,
            FactoryQuery,
            OptionQuery,
            PartModelOptionQuery,
            ):
    pass

@strawberry.type
class Mutation(UserMutation,
                InstrumentMutation,
                InstrumentTypeMutation,
                FactoryMutation,
                OptionMutation,
                PartModelOptionQuery,
                ):
    pass

schema = strawberry.Schema(query=Query, mutation=Mutation)
