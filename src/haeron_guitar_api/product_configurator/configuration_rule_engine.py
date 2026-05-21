class RuleEngine:
    def __init__(self, rules):
        self.rules = rules

    def apply(self, configuration, context):

        for rule in self.rules:
            if self._match(rule, context):
                self._apply(rule, configuration)

        return configuration

    def _match(self, rule, context):
        for condition in rule.conditions.all():
            value = context.get(condition.source_component.key)

            if condition.operator == "eq":
                if value not in condition.values:
                    return False

            if condition.operator == "in":
                if value not in condition.values:
                    return False

        return True

    def _apply(self, rule, configuration):
        for result in rule.results.all():
            component = next(c for c in configuration.components if c.key == result.target_component.key)

            component.allowed_values = result.allowed_values
            component.disabled = False
