import os
import stripe
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from decouple import config

from haeron_guitar_api.models import Order


@csrf_exempt
def stripe_webhook(request):
    payload = request.body
    sig_header = request.META.get("HTTP_STRIPE_SIGNATURE")

    try:
        event = stripe.Webhook.construct_event(payload, sig_header, config("STRIPE_WEBHOOK_SECRET"))

    except Exception as e:
        print("Webhook error:", e)
        return HttpResponse(status=400)

    # 🔥 debug important
    print("EVENT TYPE:", event["type"])

    if event["type"] != "payment_intent.succeeded":
        return HttpResponse(status=200)

    intent = event["data"]["object"]

    order_id = None

    try:
        order_id = intent.metadata["order_id"]
    except Exception:
        order_id = None

    if order_id:
        Order.objects.filter(id=order_id).update(status="paid")

    return HttpResponse(status=200)
