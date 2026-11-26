"""One serial counter per workshop, part model and year : first the part model column (see 0022)."""

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("haeron_guitar_api", "0020_order_item_link"),
    ]

    operations = [
        migrations.AlterUniqueTogether(
            name="serialcounter",
            unique_together=set(),
        ),
        migrations.AddField(
            model_name="serialcounter",
            name="part_model",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                to="haeron_guitar_api.partmodel",
            ),
        ),
    ]
