class ComponentHandlerRegistry:
    _registry = {}

    @classmethod
    def register(cls, source_type):
        def decorator(handler_cls):
            cls._registry[source_type] = handler_cls()
            return handler_cls

        return decorator

    @classmethod
    def get_handler(cls, source_type):
        result = cls._registry.get(source_type)
        if not result:
            raise ValueError(f"No corresponding component Handler with source type {source_type}")
        return result
