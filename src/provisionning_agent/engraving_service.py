"""
Logique métier de la gravure, dans le même style que PartService.
Appelé depuis provisionning_agent/views.py comme PartService l'est déjà
pour le NFC.
"""
from collections import defaultdict

from django.db import transaction
from django.db.models import Exists, F, OuterRef
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

        # Exists plutôt que exclude(security_marks__a=..., security_marks__b=...) :
        # sur une relation multi-valuée, les conditions d'un même exclude() ne
        # portent pas forcément sur la MÊME marque, ce qui exclut à tort une pièce
        # ayant par ex. une marque "failed" ici et une "confirmed" ailleurs.
        active_mark = PartEngravingMark.objects.filter(
            part=OuterRef("pk"),
            mark_type=template.mark_type,
            location=template.location,
            status__in=["pending", "confirmed"],
        )
        return parts_qs.exclude(Exists(active_mark)).order_by("serial_number")

    @classmethod
    @transaction.atomic
    def reserve_pending_marks(cls, mark_type: str = None, part_model_uuid=None, limit: int = None):
        """
        Réserve les pièces à graver et retourne le tout groupé par template
        (un groupe = un CSV LightBurn côté agent).

        `limit` est un plafond GLOBAL (tous templates confondus) sur le nombre
        de marques renvoyées, marques déjà pending comprises.

        Requêtes SQL : 1 (templates) + 1 (toutes les marques déjà pending, tous
        templates confondus) + 1 par template pour trouver les pièces manquantes
        (inévitable : le critère d'exclusion — mark_type/location/part_model —
        diffère par template) + 1 bulk_create global pour toutes les nouvelles
        marques, tous templates confondus.
        """
        # templates spécifiques à un modèle de pièce d'abord : si un template
        # "tous modèles" vise le même emplacement, c'est le spécifique qui gagne
        templates_qs = EngravingTemplate.objects.order_by(F("part_model").asc(nulls_last=True), "name")
        if mark_type:
            templates_qs = templates_qs.filter(mark_type=mark_type)
        # verrou sur les templates : deux fetch simultanés (deux postes) sont
        # sérialisés au lieu de se disputer les mêmes pièces
        templates = list(templates_qs.select_for_update())  # 1 requête

        if not templates:
            return {}

        # 1 seule requête pour récupérer les marques pending de TOUS les templates
        existing_pending_qs = PartEngravingMark.objects.filter(
            template__in=templates, status="pending",
        ).select_related("part", "template").order_by("part__serial_number")
        if part_model_uuid:
            existing_pending_qs = existing_pending_qs.filter(part__part_model_id=part_model_uuid)

        existing_by_template_pk = defaultdict(list)
        # (part, mark_type, location) déjà occupés : miroir en mémoire de la
        # contrainte uniq_active_mark_per_part_location, pour que deux templates
        # qui se recouvrent (ex. "tous modèles" + un modèle précis, même
        # emplacement) ne créent pas deux marques pour la même pièce dans ce
        # fetch -> sinon IntegrityError au bulk_create et fetch en 500.
        taken = set()
        for mark in existing_pending_qs:  # évalue la requête ici, une seule fois
            existing_by_template_pk[mark.template_id].append(mark)
            taken.add((mark.part_id, mark.mark_type, mark.location))

        grouped = defaultdict(list)
        all_new_marks = []
        remaining = limit - len(taken) if limit else None

        for template in templates:
            grouped[template].extend(existing_by_template_pk.get(template.pk, []))

            if remaining is not None and remaining <= 0:
                continue

            parts_qs = cls.find_parts_missing_mark(template)
            if part_model_uuid:
                parts_qs = parts_qs.filter(part_model_id=part_model_uuid)

            for part in parts_qs.iterator():  # 1 requête par template, critère d'exclusion propre au template
                key = (part.pk, template.mark_type, template.location)
                if key in taken:
                    continue
                if remaining is not None and remaining <= 0:
                    break

                value = cls.compute_mark_value(part, template)
                mark = PartEngravingMark(
                    part=part,
                    mark_type=template.mark_type,
                    template=template,
                    value=value,
                    location=template.location,
                    status="pending",
                )
                taken.add(key)
                all_new_marks.append(mark)
                grouped[template].append(mark)
                if remaining is not None:
                    remaining -= 1

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