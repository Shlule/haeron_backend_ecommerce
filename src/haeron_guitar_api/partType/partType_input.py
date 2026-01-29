import strawberry

@strawberry.input
class CreatePartTypeInput:
    code:str
    name:str

    