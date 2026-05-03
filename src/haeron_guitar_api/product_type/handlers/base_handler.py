from django.core.exceptions import ValidationError
from jsonschema import validate as validate_schema


class BaseProductHandler:
    CONFIG_SCHEMA = None

    def validate(self, config: dict):
        if not isinstance(config, dict):
            raise ValidationError("Configuration must be an object")

        if self.CONFIG_SCHEMA:
            validate_schema(config, self.CONFIG_SCHEMA)

        return self._validate_business(config)

    def _validate_business(self, config):
        raise NotImplementedError

    def build_snapshot(self, data):
        raise NotImplementedError

    def calculate_price(self, data):
        raise NotImplementedError
