import logging

import stripe
from decouple import config
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from .payment_service import PaymentService

logger = logging.getLogger(__name__)


@csrf_exempt
@require_POST
def stripe_webhook(request):
    """Events sent by Stripe (payment done, page expired, refund). The signature proves they come from Stripe."""
    try:
        event = stripe.Webhook.construct_event(
            request.body, request.META.get("HTTP_STRIPE_SIGNATURE"), config("STRIPE_WEBHOOK_SECRET", default="")
        )
    except (ValueError, TypeError, AttributeError, stripe.SignatureVerificationError) as error:
        logger.warning("Stripe webhook refused: %s", error)
        return HttpResponse(status=400)

    PaymentService.handle_event(event)
    return HttpResponse(status=200)
