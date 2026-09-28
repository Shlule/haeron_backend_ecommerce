"""
Logique métier de la gravure, dans le même style que PartService.
Appelé depuis provisionning_agent/views.py comme PartService l'est déjà
pour le NFC.
"""
from collections import defaultdict

from django.db import transaction
from django.utils import timezone

from haeron_guitar_api.models import EngravingTemplate, Part, PartEngravingMark


class EngravingService:

    @staticmethod
    def compute_mark_value(part: Part, template: EngravingTemplate) -> str:
        """
        PLACEHOLDER pour mark_type="security" : à remplacer par le vrai calcul
        (payload signé, format spécifique, etc.) avant mise en prod.
        """
        if template.mark_type == "serial_number":
            return part.serial_number

        if template.mark_type == "security":
            return f"SEC-{part.uuid.hex[:12].upper()}"

        raise ValueError(f"Pas de règle de calcul pour mark_type={template.mark_type!r}")

    @staticmethod
    def find_parts_missing_mark(template: EngravingTemplate):
        parts_qs = Part.objects.all()

        if template.part_model_id:
            parts_qs = parts_qs.filter(part_model_id=template.part_model_id)

        parts_qs = parts_qs.exclude(
            security_marks__mark_type=template.mark_type,
            security_marks__location=template.location,
            security_marks__status__in=["pending", "confirmed"],
        )

        return parts_qs

    @classmethod
    @transaction.atomic
    def reserve_pending_marks(cls, mark_type: str = None, part_model_uuid=None, limit: int = None):
        """
        Réserve les pièces à graver et retourne le tout groupé par template
        (un groupe = un CSV LightBurn côté agent).

        Requêtes SQL : 1 (templates) + 1 (toutes les marques déjà pending, tous
        templates confondus) + 1 par template pour trouver les pièces manquantes
        (inévitable : le critère d'exclusion — mark_type/location/part_model —
        diffère par template) + 1 bulk_create global pour toutes les nouvelles
        marques, tous templates confondus.
        Soit 3 + N_templates requêtes, contre 1 + 3×N_templates avant.
        """
        templates_qs = EngravingTemplate.objects.all()
        if mark_type:
            templates_qs = templates_qs.filter(mark_type=mark_type)
        templates = list(templates_qs)  # 1 requête

        if not templates:
            return {}

        # 1 seule requête pour récupérer les marques pending de TOUS les templates
        existing_pending_qs = PartEngravingMark.objects.filter(
            template__in=templates, status="pending",
        ).select_related("part", "template")
        if part_model_uuid:
            existing_pending_qs = existing_pending_qs.filter(part__part_model_id=part_model_uuid)

        existing_by_template_pk = defaultdict(list)
        for mark in existing_pending_qs:  # évalue la requête ici, une seule fois
            existing_by_template_pk[mark.template_id].append(mark)

        grouped = defaultdict(list)
        all_new_marks = []

        for template in templates:
            existing = existing_by_template_pk.get(template.pk, [])
            grouped[template].extend(existing)

            already_reserved_part_ids = {m.part_id for m in existing}
            parts_qs = cls.find_parts_missing_mark(template)
            if part_model_uuid:
                parts_qs = parts_qs.filter(part_model_id=part_model_uuid)
            parts_qs = parts_qs.exclude(uuid__in=already_reserved_part_ids)

            if limit:
                remaining = limit - len(existing)
                if remaining <= 0:
                    continue
                parts_qs = parts_qs[:remaining]

            for part in parts_qs:  # 1 requête par template, critère d'exclusion propre au template
                value = cls.compute_mark_value(part, template)
                mark = PartEngravingMark(
                    part=part,
                    mark_type=template.mark_type,
                    template=template,
                    value=value,
                    location=template.location,
                    status="pending",
                )
                all_new_marks.append(mark)
                grouped[template].append(mark)

        if all_new_marks:
            # 1 seule requête d'insertion pour toutes les nouvelles marques,
            # tous templates confondus (au lieu d'un bulk_create par template)
            PartEngravingMark.objects.bulk_create(all_new_marks)

        return grouped

    @staticmethod
    @transaction.atomic
    def confirm_marks(results: list[dict]) -> list[dict]:
        """
        results: [{"mark_uuid": ..., "status": "confirmed"|"failed", "description": "..."}]
        Idempotent : rejouer un mark_uuid déjà traité ne renvoie pas d'erreur.

        Vrai batch SQL : une seule requête de lecture, un seul bulk_update en écriture,
        peu importe le nombre d'entrées dans `results`.
        """
        requested_uuids = [item["mark_uuid"] for item in results]

        # une seule requête pour tout récupérer, verrouillé pour la durée de la transaction
        marks_by_uuid = {
            str(mark.uuid): mark
            for mark in PartEngravingMark.objects.select_for_update().filter(uuid__in=requested_uuids)
        }

        outcomes = []
        to_update = []
        now = timezone.now()

        for item in results:
            mark_uuid = item["mark_uuid"]
            new_status = item["status"]
            description = item.get("description", "")

            mark = marks_by_uuid.get(str(mark_uuid))
            if mark is None:
                outcomes.append({"mark_uuid": mark_uuid, "ok": False, "error": "mark introuvable"})
                continue

            if mark.status != "pending":
                # déjà traité (rejeu du sync) -> idempotent, pas une erreur, pas réécrit
                outcomes.append({"mark_uuid": mark_uuid, "ok": True, "error": None})
                continue

            mark.status = new_status
            mark.description = description
            if new_status == "confirmed":
                mark.confirmed_at = now

            to_update.append(mark)
            outcomes.append({"mark_uuid": mark_uuid, "ok": True, "error": None})

        if to_update:
            PartEngravingMark.objects.bulk_update(to_update, ["status", "description", "confirmed_at"])

        return outcomes