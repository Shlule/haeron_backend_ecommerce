from datetime import date
from typing import Optional
from uuid import UUID


@strawberry.input
class CartFilterInput:
    id: Optional[str] = None
    user_id: Optional[str] = None
    is_active: Optional[bool] = None

    created_at: Optional[date] = None
    created_after: Optional[date] = None
    created_before: Optional[date] = None

    expires_at: Optional[date] = None
    expires_after: Optional[date] = None
    expires_before: Optional[date] = None


class CreateCartInput:
    user: Optional[UUID] = None
    session_key: Optional[str] = None


@strawberry.input
class MergeCartInput:
    guest_cart_id: UUID
