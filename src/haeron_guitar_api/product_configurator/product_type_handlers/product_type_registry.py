class ProductTypeHandlerRegistry:
    _registry = {}

    @classmethod
    def register(cls, product_type_code):
        def decorator(handler_cls):
            cls._registry[product_type_code] = handler_cls()
            return handler_cls

        return decorator

    @classmethod
    def get_handler(cls, product_type_code):
        return cls._registry.get(product_type_code)
