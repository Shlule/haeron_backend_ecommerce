# this calss is onnly use for product configuration at this time
from pprint import pprint


class ConfigurationNormalizer:
    @staticmethod
    def normalize(snapshot):
        result = {}

        pprint(snapshot)
        for component in snapshot:
            component_key = component.get("component", None)
            for option in component.get("options", {}):
                print(option)
                if not option.get("name") or not component_key:
                    key = f"{component_key}.{option.get('name')}"
                    result[key] = option
        return result
        # for component in snapshot.get("options", {}):
        #   component_key = component.get("component", None)
        #     for option in component.get("options", None):
        #         if not option.get("option", None) or not component_key:
        #             continue
        #         key = f"{component_key}.{option.get('option', None)}"
        #         result[key] = {"id": option["value_id"], "name": ["name"]}
        # return result
