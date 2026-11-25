"""Hidden code engraved from the back-office, without the engraving agent.

1. code_to_engrave : shows the code to the person who engraves it (once the mark is engraved and checked, the code
   is never shown again) ; the history keeps who asked for it and when.
2. confirm_engraving : once engraved, the code is read on the part and typed, with where it was engraved (free text,
   kept on the part) : the mark is confirmed only if the code is the right one, so a mistake or an unreadable
   engraving is caught before the part leaves the workshop.
The code itself only comes from the serial number and the key of the part model : the place does not change it.
"""

import secrets

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import F, Q
from django.utils import timezone

from ..models import EngravingTemplate, Part, PartEngravingMark, PartHistory
from ..security import hidden_mark


GENERIC_TEMPLATE = "Code caché - toutes pièces"


def template_for(part):
    """The "security" engraving template of the part model, or the one for all models : its places are suggestions."""
    return (
        EngravingTemplate.objects.filter(mark_type="security")
        .filter(Q(part_model_id=part.part_model_id) | Q(part_model__isnull=True))
        .order_by(F("part_model").asc(nulls_last=True), "name")
        .first()
    )


def spots(template):
    """The places a template allows. Several places, separated by ";", are drawn at random for each part, so a
    forger who copies a genuine part does not know where its code is."""
    return [spot.strip() for spot in template.location.split(";") if spot.strip()] or [template.location]


def pick_location(template):
    return secrets.choice(spots(template))


def location_to_show(part, marks):
    """The place already known before the engraving is checked (given by the engraving agent), or None."""
    pending = next((mark for mark in marks if mark.status == "pending"), None)
    return (pending.location or None) if pending is not None else None


def suggestions(part):
    """Places proposed in the free field (from the "security" template), the person who engraves writes the real one."""
    template = template_for(part)
    return spots(template) if template is not None else []


def _template(part):
    # the mark needs a template : without one for this model, the generic one is made rather than refusing
    return template_for(part) or EngravingTemplate.objects.get_or_create(
        name=GENERIC_TEMPLATE,
        defaults={
            "mark_type": "security",
            "location": "indiqué à la gravure",
            "lightburn_project_path": "gravure depuis le back-office",
            "variable_columns": ["value", "location"],
        },
    )[0]


def _part(part_id):
    part = Part.objects.select_for_update().filter(pk=part_id).first()
    if part is None:
        raise ValidationError("Pièce introuvable.")
    return part


def _code(part):
    try:
        return hidden_mark.code_for(part)
    except Exception as error:
        raise ValidationError(f"Clé du modèle illisible dans Vault ({error.__class__.__name__}).") from error


def _refuse_if_done(part):
    if PartEngravingMark.objects.filter(part=part, mark_type="security", status="confirmed").exists():
        raise ValidationError("Le code caché de cette pièce est déjà gravé et contrôlé : il n'est plus affiché.")


class HiddenMarkService:
    @staticmethod
    @transaction.atomic
    def code_to_engrave(part_id, user=None):
        part = _part(part_id)
        _refuse_if_done(part)
        # the mark waiting for its check is kept : the code may have been shown, or even engraved, already
        mark = (
            PartEngravingMark.objects.filter(part=part, mark_type="security", status="pending")
            .order_by("-created_at")
            .first()
        )
        if mark is None:
            # the place is written when the engraving is checked
            mark = PartEngravingMark.objects.create(
                part=part, mark_type="security", template=_template(part), location="", value="", status="pending"
            )
        code = _code(part)
        PartHistory.objects.create(
            part=part,
            event_type="fabrication",
            title="Code caché affiché pour gravure",
            description="",
            created_by=user,
            updated_by=user,
        )
        return {"code": code, "location": mark.location}

    @staticmethod
    @transaction.atomic
    def confirm_engraving(part_id, code, location="", user=None):
        part = _part(part_id)
        _refuse_if_done(part)
        mark = (
            PartEngravingMark.objects.filter(part=part, mark_type="security", status="pending")
            .order_by("-created_at")
            .first()
        )
        if mark is None:
            raise ValidationError("Affiche d'abord le code à graver, ou récupère-le avec l'agent de gravure.")
        location = " ".join((location or "").split())[:255]
        if not location:
            raise ValidationError("Indique où le code est gravé sur la pièce.")
        if not hidden_mark.normalize(code or ""):
            raise ValidationError("Saisis le code lu sur la pièce.")
        if hidden_mark.normalize(code) != hidden_mark.normalize(_code(part)):
            raise ValidationError("Le code lu ne correspond pas : relis la gravure, ou regrave-la si elle est fausse.")
        mark.status = "confirmed"
        mark.location = location
        mark.confirmed_at = timezone.now()
        mark.save(update_fields=["status", "location", "confirmed_at"])
        PartHistory.objects.create(
            part=part,
            event_type="controle",
            title="Code caché gravé et contrôlé",
            description=f"Emplacement : {mark.location}. Code relu sur la pièce et vérifié.",
            created_by=user,
            updated_by=user,
        )
        return True
