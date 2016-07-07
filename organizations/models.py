from __future__ import unicode_literals
from builtins import object
from django.conf import settings
from django.contrib.sites.models import Site
from django.core.exceptions import ImproperlyConfigured, PermissionDenied
from django.core.urlresolvers import reverse
from django.db import models
from django.db.models.loading import get_model
from django.utils import timezone
from django.utils.importlib import import_module
from django.utils.translation import ugettext_lazy as _
from markitup.fields import MarkupField

from .base import OrganizationBase, OrganizationUserBase, OrganizationOwnerBase
from .signals import user_added, user_removed, owner_changed

USER_MODEL = getattr(settings, 'AUTH_USER_MODEL', 'auth.User')
ORGS_SLUGFIELD = getattr(settings, 'ORGS_SLUGFIELD',
                         'django_extensions.db.fields.AutoSlugField')
ORGS_TIMESTAMPED_MODEL = getattr(settings, 'ORGS_TIMESTAMPED_MODEL',
                                 'django_extensions.db.models.TimeStampedModel')

try:
    module, klass = ORGS_SLUGFIELD.rsplit('.', 1)
    SlugField = getattr(import_module(module), klass)
except:
    raise ImproperlyConfigured("Your SlugField class, {0},"
                               " is improperly defined".format(ORGS_SLUGFIELD))

try:
    module, klass = ORGS_TIMESTAMPED_MODEL.rsplit('.', 1)
    TimeStampedModel = getattr(import_module(module), klass)
except:
    raise ImproperlyConfigured("Your TimeStampedBaseModel class, {0},"
                               " is improperly defined".format(ORGS_TIMESTAMPED_MODEL))


def get_user_model():
    """
    Returns the chosen user model as a class. This functionality won't be
    builtin until Django 1.5.
    """
    try:
        klass = get_model(USER_MODEL.split('.')[0], USER_MODEL.split('.')[1])
    except:
        raise ImproperlyConfigured("Your AUTH_USER_MODEL class '{0}'"
                                   " is improperly defined".format(USER_MODEL))
    if klass is None:
        raise ImproperlyConfigured("Your AUTH_USER_MODEL class '{0}'"
                                   " is not installed".format(USER_MODEL))
    return klass


class Organization(OrganizationBase, TimeStampedModel):
    """
    Default Organization model.
    """
    slug = SlugField(max_length=200, blank=False, editable=True,
                     populate_from='name', unique=True,
                     help_text=_(u"The name in all lowercase, suitable for URL identification"))

    description = MarkupField(blank=True, null=False, default="")
    send_signup_message = models.BooleanField(default=True)
    signup_message = models.TextField(default="You have been added to {0}.\nClick {1} for the group profile.",
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
    is_pandi_club = models.BooleanField(default=False,
                                        help_text=u"This group represents a club of P&I insurers")
    external_id = models.CharField(null=True, blank=True, max_length=255,
                                  help_text="An identifier for this group in an external system")
    is_hidden = models.BooleanField(default=False,
                                    help_text=u"Users in hidden groups are not aware that they are "
                                              u"in the group, and cannot see the group's properties "
                                              u"or members.")

    class Meta(OrganizationBase.Meta):
        verbose_name = _("organization")
        verbose_name_plural = _("organizations")

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

    def remove_user(self, user):
        """
        Deletes a user from an organization.
        """
        org_user = OrganizationUser.objects.get(user=user,
                                                organization=self)
        org_user.delete()

        # User removed signal
        user_removed.send(sender=self, user=user)

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


class OrganizationUser(OrganizationUserBase, TimeStampedModel):
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

    class Meta(OrganizationUserBase.Meta):
        verbose_name = _("organization user")
        verbose_name_plural = _("organization users")

    def __unicode__(self):
        return u"{0} ({1})".format(self.name if self.user.is_active else
                                   self.user.email, self.organization.name)

    def delete(self, using=None):
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
        super(OrganizationUserBase, self).delete(using=using)

    def get_absolute_url(self):
        return reverse('organization_user_detail', kwargs={
            'organization_pk': self.organization.pk, 'user_pk': self.user.pk})


class OrganizationOwner(OrganizationOwnerBase, TimeStampedModel):
    class Meta(object):
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
            super(OrganizationOwnerBase, self).save(*args, **kwargs)
