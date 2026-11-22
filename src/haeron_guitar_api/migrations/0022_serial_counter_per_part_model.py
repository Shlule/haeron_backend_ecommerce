"""One serial counter per workshop, part model and year (it was one per workshop and year, shared by every part).

Each new counter starts after the highest number already given to that part model that year, so a serial number
that exists is never made again. The numbers already given do not change.
"""

import re

from django.db import migrations


def start_counters_after_existing_numbers(apps, schema_editor):
    Part = apps.get_model("haeron_guitar_api", "Part")
    Factory = apps.get_model("haeron_guitar_api", "Factory")
    SerialCounter = apps.get_model("haeron_guitar_api", "SerialCounter")

    # longest code first : a code that starts like another one is matched on its own
    factories = sorted(Factory.objects.all(), key=lambda f: len(f.code or ""), reverse=True)
    highest = {}  # (factory, part model, year) -> highest number
    for part in Part.objects.select_related("part_model", "batch").exclude(batch=None).exclude(part_model=None):
        serial = part.serial_number or ""
        factory = next((f for f in factories if f.code and serial.startswith(f.code)), None)
        # <factory><type>-<model code><year>-<batch code><number>
        found = re.search(
            rf"-{re.escape(part.part_model.code)}(\d{{4}})-{re.escape(part.batch.code)}(\d+)$", serial
        )
        if factory is None or found is None:
            continue
        key = (factory.pk, part.part_model_id, int(found.group(1)))
        highest[key] = max(highest.get(key, 0), int(found.group(2)))

    for (factory_id, part_model_id, year), value in highest.items():
        SerialCounter.objects.update_or_create(
            factory_id=factory_id, part_model_id=part_model_id, year=year, defaults={"last_value": value}
        )


# in its own migration : Postgres cannot build the new unique index in the transaction that added the column
class Migration(migrations.Migration):

    dependencies = [
        ("haeron_guitar_api", "0021_serial_counter_part_model"),
    ]

    operations = [
        migrations.AlterUniqueTogether(
            name="serialcounter",
            unique_together={("factory", "part_model", "year")},
        ),
        migrations.RunPython(start_counters_after_existing_numbers, migrations.RunPython.noop),
    ]
