from typing import List
from uuid import UUID
from django.db import IntegrityError, transaction
from ..models import Option
from .option_dto import CreateOptionDTO


class OptionService:
    @staticmethod
    def create(dto: CreateOptionDTO) -> Option:
        try:
            option = Option.objects.create(
                name=dto.name,
                description=dto.description,
            )
            return option
        except IntegrityError as e:
            raise ValueError("Cannot create the option")

    @staticmethod
    @transaction.atomic
    def delete(option_ids: List[UUID]) -> bool:
        delete_count, _ = Option.objects.filter(pk__in=option_ids).delete()
        return delete_count
