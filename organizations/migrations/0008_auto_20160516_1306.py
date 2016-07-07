# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models
import django_extensions.db.fields


class Migration(migrations.Migration):

    dependencies = [
        ('organizations', '0007_template_group_signup_message'),
    ]

    operations = [
        migrations.AddField(
            model_name='organization',
            name='external_id',
            field=models.CharField(help_text='An identifier for this group in an external system', max_length=255, null=True, blank=True),
        ),
        migrations.AlterField(
            model_name='organization',
            name='created',
            field=django_extensions.db.fields.CreationDateTimeField(auto_now_add=True, verbose_name='created'),
        ),
        migrations.AlterField(
            model_name='organization',
            name='modified',
            field=django_extensions.db.fields.ModificationDateTimeField(auto_now=True, verbose_name='modified'),
        ),
        migrations.AlterField(
            model_name='organization',
            name='signup_message',
            field=models.TextField(default='You have been added to {0}.\nClick {1} for the group profile.', help_text="Message sent when user is added to group. Use {{ organization.name }} for the group name, {{ user.get_full_name }} for the user's name, and {{ link }} for a link to the group.", null=True, blank=True),
        ),
        migrations.AlterField(
            model_name='organizationowner',
            name='created',
            field=django_extensions.db.fields.CreationDateTimeField(auto_now_add=True, verbose_name='created'),
        ),
        migrations.AlterField(
            model_name='organizationowner',
            name='modified',
            field=django_extensions.db.fields.ModificationDateTimeField(auto_now=True, verbose_name='modified'),
        ),
        migrations.AlterField(
            model_name='organizationuser',
            name='created',
            field=django_extensions.db.fields.CreationDateTimeField(auto_now_add=True, verbose_name='created'),
        ),
        migrations.AlterField(
            model_name='organizationuser',
            name='modified',
            field=django_extensions.db.fields.ModificationDateTimeField(auto_now=True, verbose_name='modified'),
        ),
    ]
