# -*- coding: utf-8 -*-
from __future__ import unicode_literals
from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('organizations', '0002_auto_20150814_1147'),
    ]
    operations = [
        migrations.AddField(
            model_name='organization',
            name='site',
            field=models.ForeignKey(blank=True, to='sites.Site', help_text='Tie this group explicitly to a brand so it is not visible outside this brand and users outside this brand cannot join', null=True),
            preserve_default=True,
        ),
    ]
