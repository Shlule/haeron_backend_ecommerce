from django.db import IntegrityError
from django.db import transaction
from ..models import Factory
from .factory_dto import CreateFactoryDTO
from uuid import UUID
from typing import List


class FactoryService:
    @staticmethod
    def create(dto: CreateFactoryDTO) -> Factory:
        try:
            factory = Factory.objects.create(name=dto.name, code=dto.code)

        except IntegrityError as e:
            raise ValueError("factory with the same name or code already exists")
        return factory

    @staticmethod
    @transaction.atomic
    def delete(factory_ids: List[UUID]) -> int:
        delete_count, _ = Factory.objects.filter(pk__in=factory_ids).delete()
        return delete_count
