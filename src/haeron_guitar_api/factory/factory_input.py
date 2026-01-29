import strawberry


@strawberry.input
class CreateFactoryInput:
    code: str
    name: str