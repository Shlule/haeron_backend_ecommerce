# this calss is onnly use for product configuration at this time


class ConfigurationNormalizer:
    # transform the snapshot produce by the handlers into a flat dict readable by the rule engine
    # {"<component_key>.<option_name>": "<part_model_option_id>", "<component_key>": "<product_id>"}
    @staticmethod
    def normalize(snapshot):
        result = {}

        for component in snapshot:
            component_key = component.get("component", None)
            if not component_key:
                continue

            for option in component.get("options", []):
                if option.get("name"):
                    result[f"{component_key}.{option.get('name')}"] = option.get("id")

            # product_choice / product_configurable : the selected product is the value of the component
            if component.get("type") in ("product_choice", "product_configurable") and component.get("product_id"):
                result[component_key] = component.get("product_id")

        return result
