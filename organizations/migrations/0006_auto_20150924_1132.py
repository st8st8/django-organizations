# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('organizations', '0005_organizationuser_date_created'),
    ]

    operations = [
        migrations.AlterField(
            model_name='organizationuser',
            name='is_moderator',
            field=models.BooleanField(default=False, help_text='Moderators can access group dashboards without being able to manipulate group membership. This is not used.'),
        ),
    ]
