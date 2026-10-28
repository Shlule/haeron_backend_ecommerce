# this calss is onnly use for product configuration at this time
from pprint import pprint


class ConfigurationNormalizer:
    @staticmethod
    def normalize(snapshot):
        result = {}

        for component in snapshot:
            component_key = component.get("component", None)
            for option in component.get("options", {}):
                print(option)
                if not option.get("name") or not component_key:
                    key = f"{component_key}.{option.get('name')}"
                    result[key] = option
        return result
