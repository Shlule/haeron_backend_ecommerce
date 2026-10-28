from django.core.exceptions import ValidationError
from jsonschema import validate as validate_schema


class BaseProductTypeHandler:
    # TODO - correct this class
    CONFIG_SCHEMA = None

    def validate(self, component, config: dict, product):
        if not isinstance(config, dict):
            raise ValidationError("Configuration must be an object")

        if self.CONFIG_SCHEMA:
            validate_schema(config, self.CONFIG_SCHEMA)

        return self._validate_business(component, config, product=None)

    def resolve(self, component, config, product=None):
        self.validate(component, config, product)
        return self._resolve(component, config, product)

    def _resolve(component, config, product):
        raise NotImplementedError

    def _validate_business(self, config):
        raise NotImplementedError

    def build_snapshot(self, data):
        raise NotImplementedError

    def calculate_price(self, data):
        raise NotImplementedError
