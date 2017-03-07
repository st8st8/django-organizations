from __future__ import unicode_literals
from .models import Organization


def create_organization(user, name, slug=None, is_active=None, is_hidden=None, site=None,
                        org_defaults=None, org_user_defaults=None, **kwargs):
    """
    Returns a new organization, also creating an initial organization user who
    is the owner.
    The specific models can be specified if a custom organization app is used.
    The simplest way would be to use a partial.
    >>> from organizations.utils import create_organization
    >>> from myapp.models import Account
    >>> from functools import partial
    >>> create_account = partial(create_organization, model=Account)
    """
    org_model = kwargs.pop('model', None) or kwargs.pop('org_model', None) or Organization
    kwargs.pop('org_user_model', None)  # Discard deprecated argument

    org_owner_model = org_model.owner.related.related_model
    try:
        # Django 1.9
        org_user_model = org_model.organization_users.rel.related_model
    except AttributeError:
        # Django 1.8
        org_user_model = org_model.organization_users.related.related_model

    if org_defaults is None:
        org_defaults = {}
    if org_user_defaults is None:
        if 'is_admin' in org_user_model._meta.get_all_field_names():
            org_user_defaults = {'is_admin': True}
        else:
            org_user_defaults = {}

    if slug is not None:
        org_defaults.update({'slug': slug})
    if is_active is not None:
        org_defaults.update({'is_active': is_active})
    if is_hidden is not None:
        org_defaults.update({'is_hidden': is_hidden})
    if site is not None:
        org_defaults.update({'site': site})

    org_defaults.update({'name': name})
    organization = org_model.objects.create(**org_defaults)

    org_user_defaults.update({'organization': organization, 'user': user})
    new_user = org_user_model.objects.create(**org_user_defaults)

    org_owner_model.objects.create(organization=organization,
                                   organization_user=new_user)
    return organization


def model_field_attr(model, model_field, attr):
    """
    Returns the specified attribute for the specified field on the model class.
    """
    fields = dict([(field.name, field) for field in model._meta.fields])
    return getattr(fields[model_field], attr)
