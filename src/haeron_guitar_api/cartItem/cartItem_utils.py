# TODO - make this used and working  this is util for check if config_snapshot is goog and pricing is right
class CartItemConfigResolver:
    @staticmethod
    def resolve(product_price, options):
        total = product_price
        snapshot = []

        for opt in options:
            total += float(opt.get("price_delta"))
            snapshot.append(
                {
                    "name": opt.get("name"),
                    "value": opt.get("value"),
                    "price_delta": float(opt.get("price_delta")),
                }
            )

        return total, snapshot
