# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import datetime
from django.utils import timezone
from django.utils.timezone import utc
from organizations import models as organization_models


def formatstr_to_template(apps, schema_editor):
    for x in organization_models.Organization.objects.all():
        x.signup_message = x.signup_message.replace("{0}", "{{ organization.name }}").replace("{1}", "{{ link }}")
        x.save()


class Migration(migrations.Migration):

    dependencies = [
        ('organizations', '0006_auto_20150924_1132'),
    ]

    operations = [
        migrations.RunPython(
            formatstr_to_template
        ),
    ]
