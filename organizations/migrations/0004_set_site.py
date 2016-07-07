# -*- coding: utf-8 -*-
from __future__ import unicode_literals
from django.db import models, migrations


def set_sites_for_groups(apps, schema_editor):
    Organization = apps.get_model("organizations", "Organization")
    Site = apps.get_model("sites", "Site")
    for o in Organization.objects.all():
        if o.is_pandi_club:
            o.site = Site.objects.get(domain="pandiq.mycoracle.com")
        if o.name.startswith("ISG"):
            o.site = Site.objects.get(domain="isg.mycoracle.com")
        if o.name.startswith("PANDIQ"):
            o.site = Site.objects.get(domain="pandiq.mycoracle.com")
        if o.name.startswith("Guru"):
            o.site = Site.objects.get(domain="pandiq.mycoracle.com")
        if o.name.startswith("RMT"):
            o.site = Site.objects.get(domain="rmt.mycoracle.com")
        if o.name.startswith("Marsoc"):
            o.site = Site.objects.get(domain="marsoc.mycoracle.com")
        if o.name.startswith("Maersk"):
            o.site = Site.objects.get(domain="marsoc.mycoracle.com")
        if o.name.startswith("Maths"):
            o.site = Site.objects.get(domain="marsoc.mycoracle.com")
        if o.name.startswith("Sea Cadets"):
            o.site = Site.objects.get(domain="marsoc.mycoracle.com")
        if o.name.startswith("Chiltern"):
            o.site = Site.objects.get(domain="marsoc.mycoracle.com")
        if o.name.startswith("DFDS"):
            o.site = Site.objects.get(domain="marsoc.mycoracle.com")
        if o.name.startswith("Helicon"):
            o.site = Site.objects.get(domain="heliconhealth.mycoracle.com")
        if o.name.startswith("SSY"):
            o.site = Site.objects.get(domain="ssy.mycoracle.com")
        o.save()

class Migration(migrations.Migration):

    dependencies = [
        ('organizations', '0003_add_site'),
    ]
    operations = [
        migrations.RunPython(
            set_sites_for_groups
        )
    ]
