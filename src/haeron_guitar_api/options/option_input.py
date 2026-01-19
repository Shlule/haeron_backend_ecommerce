import strawberry


@strawberry.input
class CreateOptionInput:
    name: str
    description: str