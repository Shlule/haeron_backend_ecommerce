from typing import Optional
import strawberry


@strawberry.input
class OptionFilterInput:
    id: Optional[str] = None
    category: Optional[str] = None


@strawberry.input
class CreateOptionInput:
    name: str
    description: str
