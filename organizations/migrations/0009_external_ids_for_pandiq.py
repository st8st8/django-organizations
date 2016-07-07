# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import datetime
from django.utils import timezone
from django.utils.timezone import utc
from organizations import models as organization_models


def get_clubmaps():
    return {
        "American Club": "American",
        "Britannia": "Britannia",
        "Gard": "Gard",
        "Japan Club": "Japan",
        "London Club": "London",
        "North of England Club": "North",
        "Shipowners Club": "Shipowners",
        "Standard": "Standard",
        "Steamship Mutual": "Steamship",
        "Swedish Club": "Swedish",
        "UK P&I Club": "UK Mutual",
        "West of England": "West",
        "Skuld": "SKULD",
        "IGPI": "IGP",
        "Guru": "Guru"
    }


def external_ids_for_pandiq(apps, schema_editor):
    maps = get_clubmaps()
    Organization = apps.get_model("organizations", "Organization")
    for x in Organization.objects.filter(is_pandi_club=True):
        x.external_id = maps[x.name]
        x.save()

def nothing(apps, schema_editor):
    return


class Migration(migrations.Migration):

    dependencies = [
        ('organizations', '0008_auto_20160516_1306'),
    ]

    operations = [
        migrations.RunPython(
            external_ids_for_pandiq,
            nothing
        ),
    ]
