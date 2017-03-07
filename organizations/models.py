# -*- coding: utf-8 -*-

# Copyright (c) 2012-2015, Ben Lopatin and contributors
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
# Redistributions of source code must retain the above copyright notice, this
# list of conditions and the following disclaimer.  Redistributions in binary
# form must reproduce the above copyright notice, this list of conditions and the
# following disclaimer in the documentation and/or other materials provided with
# the distribution
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND
# ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
# FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
# DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
# SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
# CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
# OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

from .abstract import (AbstractOrganization,
                       AbstractOrganizationUser,
                       AbstractOrganizationOwner)

from django.contrib.sites.models import Site
from django.core.exceptions import PermissionDenied
from django.core.urlresolvers import reverse
from django.db import models
from django.utils.translation import ugettext_lazy as _
from markitup.fields import MarkupField
from .fields import SlugField
from .signals import user_added, user_removed, owner_changed


class Organization(AbstractOrganization):
    """
    Default Organization model.
    """
    slug = SlugField(max_length=200, blank=False, editable=True,
                     populate_from='name', unique=True,
                     help_text=_(u"The name in all lowercase, suitable for URL identification"))

    description = MarkupField(blank=True, null=False, default="")
    send_signup_message = models.BooleanField(default=False)
    signup_message = models.TextField(default="You have been added to {{ organization.name }}.\nClick {{ link }} for the group profile.",
                                      null=True,
                                      blank=True,
                                      help_text=u"Message sent when user is added to group. "
                                                u"Use {{ organization.name }} for the group name,"
                                                u" {{ user.get_full_name }} for the user's name,"
                                                u" and {{ link }} for a link to the group.")
    logo = models.ImageField(upload_to="group_logos", blank=True, null=True)
    site = models.ForeignKey(Site, null=True, blank=True,
                             help_text=u"Tie this group explicitly to a brand so it is not visible outside "
                                       u"this brand and users outside this brand cannot join")
    is_pandi_club = models.BooleanField(default=False, db_index=True,
                                        help_text=u"This group represents a club of P&I insurers")
    external_id = models.CharField(null=True, blank=True, max_length=255,
                                  help_text="An identifier for this group in an external system")
    is_hidden = models.BooleanField(default=False,
                                    help_text=u"Users in hidden groups are not aware that they are "
                                              u"in the group, and cannot see the group's properties "
                                              u"or members.")
    parent = models.ForeignKey("self", null=True, blank=True, on_delete=models.SET_NULL,
                               help_text="If this is a subgroup, select its parent here")

    def __unicode__(self):
        return self.name

    def get_absolute_url(self):
        return reverse('organization_detail', kwargs={'organization_pk': self.pk})

    def add_user(self, user, is_admin=False):
        """
        Adds a new user and if the first user makes the user an admin and
        the owner.
        """
        users_count = self.users.all().count()
        if users_count == 0:
            is_admin = True
        # TODO get specific org user?
        if self.site:
            if not user.is_superuser:
                if self.site != user.profile.site_registered:
                    raise PermissionDenied(u"Users not registered to {0} cannot join this group"
                                           .format(self.site.domain))
        org_user = OrganizationUser.objects.create(user=user,
                organization=self, is_admin=is_admin)
        if users_count == 0:
            # TODO get specific org user?
            OrganizationOwner.objects.create(organization=self,
                    organization_user=org_user)

        # User added signal
        user_added.send(sender=self, user=user)
        return org_user

    def has_member(self, user):
        try:
            ou = OrganizationUser.active.get(
                organization=self,
                user=user
            )
            return True
        except OrganizationUser.DoesNotExist:
            return False

    @staticmethod
    def get_for_site(site, parents_only=False, subgroups_only=False):
        queryset = {
            "is_active": True,
            "is_hidden": False,
            "site": site
        }
        queryset_exclude = {}
        if parents_only:
            queryset["parent"] = None
        if subgroups_only:
            queryset_exclude["parent"] = None

        return Organization.objects.filter(**queryset).exclude(**queryset_exclude)

    def get_parents(self, include_self=False):
        parents = [self, ] if include_self else []
        parent = self.parent
        while parent:
            parents += [self.parent]
            parent = self.parent

        return parents

    def get_subgroups(self):
        subgroups = Organization.objects.filter(
            parent=self
        )
        return subgroups

    def get_members(self, include_admins=True, include_users=True, same_site_only=True, include_parents=False, include_superusers=False, *args, **kwargs):
        query = {
            "user__is_active": True
        }

        if include_admins and not include_users:
            query["is_admin"] = True
        elif not include_admins and include_users:
            query["is_admin"] = False
        elif not include_users and not include_admins:
            raise ValueError("Must include_admins or include_users")

        if same_site_only and self.site:
            query["user__profile__site_registered"] = self.site

        if include_parents:
            query["organization__in"] = self.get_parents(include_self=True),
        else:
            query["organization"] = self

        if not include_superusers:
            query["user__is_superuser"] = False

        return OrganizationUser.objects.filter(**query).select_related()

    def remove_user(self, user):
        try:
            ou = OrganizationUser.objects.filter(
                user=user,
                organization=self
            )
            ou.delete()
            # User removed signal
            user_removed.send(sender=self, user=user)

        except OrganizationUser.DoesNotExist:
            pass

        for o in self.get_subgroups():
            try:
                ou = OrganizationUser.objects.filter(
                    user=user,
                    organization=o
                )
                ou.delete()
                user_removed.send(sender=self, user=user)
            except OrganizationUser.DoesNotExist:
                pass

    def add_user_to_unique_parent_group(self, user, site, is_admin=False):
        if self.site:
            if not user.is_superuser:
                if self.site != user.profile.site_registered:
                    raise PermissionDenied(u"Users not registered to {0} cannot join this group"
                                           .format(self.site.domain))

        if self.parent:
            raise PermissionDenied(u"Cannot add user to parent with parents")

        for o in self.get_for_site(site, parents_only=True):
            o.remove_user(user)

        self.add_user(user, is_admin)

    def add_user_to_unique_subgroup(self, user, is_admin=False):
        if self.site:
            if not user.is_superuser:
                if self.site != user.profile.site_registered:
                    raise PermissionDenied(u"Users not registered to {0} cannot join this group"
                                           .format(self.site.domain))

        if not self.parent:
            raise PermissionDenied(u"Cannot add user to subgroup with no parent")

        for o in self.parent.get_subgroups():
            o.remove_user(user)

        self.add_user(user, is_admin)

    def get_or_add_user(self, user, **kwargs):
        """
        Adds a new user to the organization, and if it's the first user makes
        the user an admin and the owner. Uses the `get_or_create` method to
        create or return the existing user.

        `user` should be a user instance, e.g. `auth.User`.

        Returns the same tuple as the `get_or_create` method, the
        `OrganizationUser` and a boolean value indicating whether the
        OrganizationUser was created or not.
        """
        is_admin = kwargs.pop('is_admin', False)
        users_count = self.users.all().count()
        if users_count == 0:
            is_admin = True

        org_user, created = OrganizationUser.objects.get_or_create(
                organization=self, user=user, defaults={'is_admin': is_admin})

        if users_count == 0:
            OrganizationOwner.objects.create(organization=self,
                    organization_user=org_user)

        if created:
            # User added signal
            user_added.send(sender=self, user=user)
        return org_user, created

    def change_owner(self, new_owner):
        """
        Changes ownership of an organization.
        """
        old_owner = self.owner.organization_user
        self.owner.organization_user = new_owner
        self.owner.save()

        # Owner changed signal
        owner_changed.send(sender=self, old=old_owner, new=new_owner)

    def is_admin(self, user):
        if user.is_superuser:
            return True
        if self.organization_users.filter(user=user, is_admin=True):
            return True
        if user.profile.is_supervisor and user.profile.site_registered == self.site:
            return True
        return False

    class Meta(AbstractOrganization.Meta):
        abstract = False
        verbose_name = _("organization")
        verbose_name_plural = _("organizations")


class OrganizationUser(AbstractOrganizationUser):
    """
    Default OrganizationUser model.
    """
    date_created = models.DateTimeField(auto_now_add=True, null=False)
    is_admin = models.BooleanField(default=False,
                                   help_text=u"This user can manage group members and change group details")
    is_moderator = models.BooleanField(default=False,
                                       help_text=u"Moderators can access group dashboards without being able "
                                                 u"to manipulate group membership. This is not used.")
    # is_approval_monitor = models.BooleanField(default=False,
    #                                           help_text=u"This user will be emailed when an unexpected user registers "
    #                                                     u"(a userwhose email domain is not in the approved list). "
    #                                                     u"This user can click a link to activate the user and "
    #                                                     u"assign them into a group.")

    class Meta(AbstractOrganizationUser.Meta):
        abstract = False
        verbose_name = _("organization user")
        verbose_name_plural = _("organization users")

    def __unicode__(self):
        return u"{0} ({1})".format(self.name if self.user.is_active else
                self.user.email, self.organization.name)

    def delete(self, using=None, keep_parents=False):
        """
        If the organization user is also the owner, this should not be deleted
        unless it's part of a cascade from the Organization.

        If there is no owner then the deletion should proceed.
        """
        from organizations.exceptions import OwnershipRequired
        try:
            if self.organization.owner.organization_user.id == self.id:
                raise OwnershipRequired(_("Cannot delete organization owner "
                    "before organization or transferring ownership."))
        # TODO This line presumes that OrgOwner model can't be modified
        except OrganizationOwner.DoesNotExist:
            pass
        super(AbstractOrganizationUser, self).delete(using=using, keep_parents=keep_parents)

    def get_absolute_url(self):
        return reverse('organization_user_detail', kwargs={
            'organization_pk': self.organization.pk, 'user_pk': self.user.pk})


class OrganizationOwner(AbstractOrganizationOwner):
    """
    Default OrganizationOwner model.
    """
    class Meta(AbstractOrganizationOwner.Meta):
        abstract = False
        verbose_name = _("organization owner")
        verbose_name_plural = _("organization owners")

    def save(self, *args, **kwargs):
        """
        Extends the default save method by verifying that the chosen
        organization user is associated with the organization.

        Method validates against the primary key of the organization because
        when validating an inherited model it may be checking an instance of
        `Organization` against an instance of `CustomOrganization`. Mutli-table
        inheritence means the database keys will be identical though.

        """
        from organizations.exceptions import OrganizationMismatch
        if self.organization_user.organization.pk != self.organization.pk:
            raise OrganizationMismatch
        else:
            super(AbstractOrganizationOwner, self).save(*args, **kwargs)
