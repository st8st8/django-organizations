# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import datetime
from django.utils import timezone
from django.utils.timezone import utc


class Migration(migrations.Migration):

    dependencies = [
        ('organizations', '0004_set_site'),
    ]

    operations = [
        migrations.AddField(
            model_name='organizationuser',
            name='date_created',
            field=models.DateTimeField(default=timezone.now, auto_now_add=True),
            preserve_default=False,
        ),
    ]
