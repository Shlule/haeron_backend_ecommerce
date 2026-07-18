import strawberry

from authUser.schema import UserMutation, UserQuery
from haeron_guitar_api.factory.factory_resolver import FactoryQuery, FactoryMutation
from haeron_guitar_api.instrument.instrument_resolver import InstrumentMutation, InstrumentQuery
from haeron_guitar_api.instrument_history.instrument_history_resolver import InstrumentHistoryQuery, InstrumentHistoryMutation
from haeron_guitar_api.intrumentType.instrumentType_resolver import InstrumentTypeMutation, InstrumentTypeQuery
from haeron_guitar_api.option.option_resolver import OptionMutation, OptionQuery
from haeron_guitar_api.partModel_option.part_model_option_resolver import PartModelOptionQuery, PartModelOptionMutation
from haeron_guitar_api.partModel.part_model_resolver import PartModelQuery, PartModelMutation
from haeron_guitar_api.partType.partType_resolver import PartTypeQuery, PartTypeMutation
from haeron_guitar_api.part_history.part_history_resolver import PartHistoryQuery, PartHistoryMutation
from haeron_guitar_api.part.part_resolver import PartMutation, PartQuery
from haeron_guitar_api.serial_counter.serial_counter_resolver import SerialCounterQuery,SerialCounterMutation


import os
from django.conf import settings
from strawberry.extensions import QueryDepthLimiter, MaxAliasesLimiter, MaxTokensLimiter
from strawberry.extensions import DisableIntrospection

extensions = [
    QueryDepthLimiter(max_depth=10),      # bloque les queries imbriquées à l'infini
    MaxAliasesLimiter(max_alias_count=15), # bloque le abus d'alias (N requêtes déguisées en 1)
    MaxTokensLimiter(max_token_count=1000),# proxy simple de "complexité" via la taille du document
]

if not settings.DEBUG:
    extensions.append(DisableIntrospection())

schema = strawberry.Schema(
    query=UserQuery,
    mutation=UserMutation,
    extensions=extensions,
)

@strawberry.type
class Query(UserQuery,
            InstrumentQuery,
            InstrumentTypeQuery,
            FactoryQuery,
            OptionQuery,
            PartModelOptionQuery,
            InstrumentHistoryQuery,
            PartModelQuery,
            PartTypeQuery,
            PartHistoryQuery,
            PartQuery,
            SerialCounterQuery,
            ):
    pass

@strawberry.type
class Mutation(UserMutation,
                InstrumentMutation,
                InstrumentTypeMutation,
                FactoryMutation,
                OptionMutation,
                PartHistoryMutation,
                PartModelMutation,
                PartTypeMutation, 
                PartMutation,
                InstrumentHistoryMutation,
                PartModelOptionMutation,
                SerialCounterMutation,
                ):
    pass

schema = strawberry.Schema(query=Query, mutation=Mutation)
