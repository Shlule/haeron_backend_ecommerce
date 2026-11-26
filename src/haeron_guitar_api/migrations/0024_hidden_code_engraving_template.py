"""Adds the engraving template of the hidden code (mark_type "security"), for all part models, when there is none
yet : without it the back-office cannot show the code to engrave. Several places separated by ";" are drawn at random
for each part. Nothing is changed when a "security" template already exists ; the places can be edited in
Données > Modèles de gravure, or a template made for one part model, which then takes precedence."""

from django.db import migrations

NAME = "Code caché - toutes pièces"
PLACES = (
    "face de contact avec la pièce voisine, côté gauche ; "
    "face de contact avec la pièce voisine, côté droit ; "
    "face de contact avec la pièce voisine, au centre"
)


def add_template(apps, schema_editor):
    EngravingTemplate = apps.get_model("haeron_guitar_api", "EngravingTemplate")
    if EngravingTemplate.objects.filter(mark_type="security").exists() or EngravingTemplate.objects.filter(name=NAME).exists():
        return
    EngravingTemplate.objects.create(
        name=NAME,
        mark_type="security",
        part_model=None,
        location=PLACES,
        lightburn_project_path="gravure depuis le back-office",
        variable_columns=["value", "location"],
    )


def remove_template(apps, schema_editor):
    EngravingTemplate = apps.get_model("haeron_guitar_api", "EngravingTemplate")
    PartEngravingMark = apps.get_model("haeron_guitar_api", "PartEngravingMark")
    template = EngravingTemplate.objects.filter(name=NAME).first()
    if template is not None and not PartEngravingMark.objects.filter(template=template).exists():
        template.delete()


class Migration(migrations.Migration):

    dependencies = [
        ("haeron_guitar_api", "0023_order_terms_accepted"),
    ]

    operations = [
        migrations.RunPython(add_template, remove_template),
    ]
