from __future__ import unicode_literals
from django.contrib.sites.models import Site
from django.db import models
from django.db.models import Q


class OrgManager(models.Manager):
    def get_for_user(self, user, supervisor_is_member=False):
        site = Site.objects.get_current()
        all_site_groups = False
        siteq = None
        if not supervisor_is_member:
            if user.is_superuser:
                siteq = (Q(site=None) | Q(site=site))
            elif user.profile.is_supervisor and user.profile.site_registered == site:
                siteq = Q(site=site)

        if not siteq:
            siteq = (Q(site=None) | Q(site=site)) & Q(users=user, is_hidden=False)

        if hasattr(self, 'get_queryset'):
            return self.get_queryset().filter(siteq)
        else:
            # Deprecated method for older versions of Django
            return self.get_query_set().filter(siteq)


class ActiveOrgManager(OrgManager):
    """
    A more useful extension of the default manager which returns querysets
    including only active organizations
    """

    def get_queryset(self):
        try:
            return super(ActiveOrgManager,
                         self).get_queryset().filter(is_active=True)
        except AttributeError:
            # Deprecated method for older versions of Django.
            return super(ActiveOrgManager,
                         self).get_query_set().filter(is_active=True)

    get_query_set = get_queryset
