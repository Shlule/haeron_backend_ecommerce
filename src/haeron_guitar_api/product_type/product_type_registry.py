class ProductTypeHandlerRegistry:
    _handlers = {}

    @classmethod
    def register(cls, product_type, handler):
        cls._handlers[product_type] = handler

    @classmethod
    def get_handler(cls, product_type):
        handler = cls._handlers.get(product_type)
        if not handler:
            raise ValueError(f"No handler for type {product_type}")
        return handler()
