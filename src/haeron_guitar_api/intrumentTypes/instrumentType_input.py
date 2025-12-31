import strawberry


@strawberry.input
class CreateInstrumentTypeInput:
    code: str
    name: str
