# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import markitup.fields


class Migration(migrations.Migration):

    dependencies = [
        ('organizations', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='organization',
            name='_description_rendered',
            field=models.TextField(editable=False, blank=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='organization',
            name='description',
            field=markitup.fields.MarkupField(default=b'', no_rendered_field=True, blank=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='organization',
            name='logo',
            field=models.ImageField(null=True, upload_to=b'group_logos', blank=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='organization',
            name='send_signup_message',
            field=models.BooleanField(default=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='organization',
            name='signup_message',
            field=models.TextField(default=b'You have been added to {0}.\nClick {1} for the group profile.', help_text=b'Message sent when user is added to group. Use {0} for the group name, and {1} for a link to the group.', null=True, blank=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='organizationuser',
            name='is_moderator',
            field=models.BooleanField(default=False),
            preserve_default=True,
        ),
    ]
