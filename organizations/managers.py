from __future__ import unicode_literals
from django.contrib.sites.models import Site
from django.db import models
from django.db.models import Q


class OrgManager(models.Manager):

    def get_for_user(self, user, admin_only=False, parents_only=False, subgroups_only=False, site=None):
        if site is None:
            site = Site.objects.get_current()

        siteq = None
        siteq_exclude = dict()

        if user.is_superuser:
            siteq = (Q(site=None) | Q(site=site))
        elif user.profile.is_supervisor and user.profile.site_registered == site:
            siteq = Q(site=site)
        elif admin_only:
            # Makes query a bit nicer if you only want admins
            siteq = (Q(site=None) | Q(site=site)) & Q(users=user) & Q(organization_users__is_admin=True)
        else:
            # Show groups of which I'm a member, and only hidden groups if I'm admin
            siteq = (Q(site=None) | Q(site=site)) & Q(users=user) & (Q(organization_users__is_admin=True) | Q(is_hidden=False))

        if parents_only:
            siteq &= Q(parent=None)
        if subgroups_only:
            siteq_exclude["parent"] = None

        if hasattr(self, 'get_queryset'):
            return self.get_queryset().filter(siteq).exclude(**siteq_exclude)
        else:
            # Deprecated method for older versions of Django
            return self.get_query_set().filter(siteq).exclude(siteq_exclude)


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


class VisibleOrgManager(OrgManager):
    """
    A more useful extension of the default manager which returns querysets
    including only active organizations
    """

    def get_queryset(self):
        try:
            return super(VisibleOrgManager,
                         self).get_queryset().filter(is_active=True, is_hidden=False)
        except AttributeError:
            # Deprecated method for older versions of Django.
            return super(VisibleOrgManager,
                         self).get_query_set().filter(is_active=True, is_hidden=False)

    get_query_set = get_queryset


class ActiveOrgUserManager(models.Manager):
    """
    A more useful extension of the default manager which returns querysets
    including only active organizations
    """

    def get_queryset(self):
        try:
            return super(ActiveOrgUserManager,
                         self).get_queryset().filter(organization__is_active=True,
                                                     user__is_active=True,
                                                     user__is_superuser=False)
        except AttributeError:
            # Deprecated method for older versions of Django.
            return super(ActiveOrgUserManager,
                         self).get_query_set().filter(organization__is_active=True,
                                                      user__is_active=True,
                                                      user__is_superuser=False)

    get_query_set = get_queryset


class VisibleOrgUserManager(models.Manager):
    """
    A more useful extension of the default manager which returns querysets
    including only active organizations
    """

    def get_queryset(self):
        try:
            return super(VisibleOrgUserManager,
                         self).get_queryset().filter(organization__is_active=True,
                                                     organization__is_hidden=False,
                                                     user__is_active=True,
                                                     user__is_superuser=False)
        except AttributeError:
            # Deprecated method for older versions of Django.
            return super(VisibleOrgUserManager,
                         self).get_query_set().filter(organization__is_active=True,
                                                      organization__is_hidden=False,
                                                      user__is_active=True,
                                                      user__is_superuser=False)

    get_query_set = get_queryset
