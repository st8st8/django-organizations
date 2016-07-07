from __future__ import unicode_literals
from __future__ import division
from builtins import str
from builtins import range
from django.template.loader import get_template
from past.utils import old_div
import logging
from datetime import datetime
import calendar
import tempfile

from django.contrib import messages
from django.contrib.auth.models import User
from django.contrib.sites.shortcuts import get_current_site
from django.core.exceptions import PermissionDenied
from pure_pagination import Paginator, PageNotAnInteger
from django.core.urlresolvers import reverse
from django.db import IntegrityError
from django.http import Http404, HttpResponse, HttpResponseBadRequest
from django.shortcuts import render, redirect
from django.template import RequestContext, Context, Template
from django.utils.translation import ugettext
from django.views.generic import (ListView, DetailView, UpdateView, CreateView,
                                  DeleteView, FormView, TemplateView)
import inject
from pymongo.database import Database
from django.db.models import Q
from django.utils.timezone import utc
from dateutil.relativedelta import relativedelta
from django.utils.translation import ugettext as _
from django.views.generic import (ListView, DetailView, UpdateView, CreateView,
        DeleteView, FormView)

from guardian.shortcuts import get_objects_for_organization, assign_perm, remove_perm, get_objects_for_user
from guardian.utils import get_403_or_None
from mycoracle.forms import ActivityAndUsersForm, AdvancedModelMultipleChoiceField, BrandUsersForm, \
    BundledModelMultipleChoiceField
from mycoracle.models import ActivityProfile, Site
from mycoracle.utils import DefaultFormatter
from mycoracle import utils as mycoracle_utils
from mycoracle import forms
from mycoracle.utils import get_users_with_permission
from TinCanApp.tincandb import TinCanActivityProfile
from .backends import invitation_backend, registration_backend
from .forms import (OrganizationForm, OrganizationUserForm,
                    OrganizationUserAddForm, OrganizationAddForm, SignUpForm)
from .mixins import (OrganizationMixin, OrganizationUserMixin,
                     MembershipRequiredMixin, AdminRequiredMixin, OwnerRequiredMixin, StaffRequiredMixin)
from .models import Organization, OrganizationUser
from .utils import create_organization
from django.conf import settings

class BaseOrganizationList(ListView):
    # TODO change this to query on the specified model
    queryset = Organization.active.all()
    context_object_name = "organizations"

    def get_queryset(self):
        qs = super(BaseOrganizationList,
                   self).get_queryset()

        site = mycoracle_utils.get_current_user_site_profile(self.request.user).site
        qs = Organization.objects.get_for_user(self.request.user)
        return qs

    def get_context_data(self, **kwargs):
        qs = kwargs.pop('object_list', self.object_list)
        context = {}
        context_object_name = self.get_context_object_name(qs)
        if context_object_name is not None:
            context[context_object_name] = qs
        organizations = list()
        for o in qs:
            try:
                OrganizationUser.objects.get(organization=o, user=self.request.user)
                o.user_is_member = True
            except OrganizationUser.DoesNotExist:
                o.user_is_member = False
            organizations.append(o)
        context["organizations"] = organizations
        return super(BaseOrganizationList, self).get_context_data(**context)


class BaseOrganizationDetail(OrganizationMixin, DetailView):
    def get_context_data(self, **kwargs):
        context = super(BaseOrganizationDetail, self).get_context_data(**kwargs)
        context['num_organization_users'] = len(self.organization.organization_users.all())
        context['recent_users'] = \
            self.organization.organization_users.all().order_by("-date_created", "user__first_name")[0:5]
        context['activities'] = \
            get_objects_for_organization(self.organization, "access_activity", ActivityProfile)
        context['organization'] = self.organization
        context["is_admin"] = self.organization.is_admin(self.request.user)

        # Superusers can get here without having an OrganisationUser
        context['this_organization_user'] = None
        try:
            context['this_organization_user'] = OrganizationUser.objects.get(
                organization=self.organization,
                user=self.request.user)
        except OrganizationUser.DoesNotExist:
            pass
        return context


class BaseOrganizationCreate(CreateView):
    model = Organization
    form_class = OrganizationAddForm
    template_name = 'organizations/organization_add_form.html'

    def post(self, request, *args, **kwargs):
        return super(BaseOrganizationCreate, self).post(request, args, kwargs)

    def get_success_url(self):
        return reverse("organization_list")

    def get_form_kwargs(self):
        kwargs = super(BaseOrganizationCreate, self).get_form_kwargs()
        kwargs.update({'request': self.request})
        return kwargs


class BaseOrganizationUpdate(OrganizationMixin, UpdateView):
    form_class = OrganizationForm

    def get_form_kwargs(self):
        kwargs = super(BaseOrganizationUpdate, self).get_form_kwargs()
        kwargs.update({'request': self.request})
        return kwargs


class BaseOrganizationDelete(OrganizationMixin, DeleteView):
    def get_success_url(self):
        return reverse("organization_list")


class BaseOrganizationUserList(OrganizationMixin, ListView):
    def get(self, request, *args, **kwargs):
        page = 1
        try:
            page = int(request.GET.get('page', 1))
        except PageNotAnInteger:
            page = 1
        if "participant_go" in request.GET:
            if len(request.GET["searchbox"].split()) < 2:
                kwargs["first_name"] = request.GET["searchbox"]
                kwargs["last_name"] = request.GET["searchbox"]
            else:
                names = request.GET["searchbox"].split()
                kwargs["first_name"] = names[0]
                kwargs["last_name"] = names[1]

        self.organization = self.get_organization()
        if "first_name" in kwargs and "last_name" in kwargs:
            self.object_list = self.organization.organization_users.filter(
                Q(user__first_name__icontains=kwargs["first_name"]) |
                Q(user__last_name__icontains=kwargs["last_name"]) |
                Q(user__email__icontains=request.GET["searchbox"])
            )
        else:
            self.object_list = self.organization.organization_users.all()

        if not (self.request.user.profile.is_brand_supervisor() or self.organization.is_admin(self.request.user)):
            self.object_list = self.object_list.filter(Q(organization__is_hidden=False) | Q(user=self.request.user))

        self.object_list = self.object_list.order_by("user__first_name")
        p = Paginator(self.object_list, 40).page(page)
        self.object_list = p.object_list
        context = self.get_context_data(object_list=self.object_list,
                                        organization_users=self.object_list,
                                        organization=self.organization,
                                        pager=p)

        context["can_add"] = request.user.profile.is_brand_supervisor()
        context["can_remove"] = self.organization.is_admin(self.request.user)

        context["search_textbox"] = forms.UsersSearchForm()
        return self.render_to_response(context)


class BaseOrganizationUserDetail(OrganizationUserMixin, DetailView):
    pass


class BaseOrganizationUserCreate(OrganizationMixin, CreateView):
    form_class = OrganizationUserAddForm
    template_name = 'organizations/organizationuser_form.html'

    def get_success_url(self):
        return reverse('organization_user_list',
                kwargs={'organization_pk': self.object.organization.pk})

    def get_form_kwargs(self):
        kwargs = super(BaseOrganizationUserCreate, self).get_form_kwargs()
        kwargs.update({'organization': self.organization,
            'request': self.request})
        return kwargs

    def get(self, request, *args, **kwargs):
        self.organization = self.get_object()
        return super(BaseOrganizationUserCreate, self).get(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        self.organization = self.get_object()
        return super(BaseOrganizationUserCreate, self).post(request, *args, **kwargs)


class BaseOrganizationUserRemind(OrganizationUserMixin, DetailView):
    template_name = 'organizations/organizationuser_remind.html'
    # TODO move to invitations backend?

    def get_object(self, **kwargs):
        self.organization_user = super(BaseOrganizationUserRemind, self).get_object()
        if self.organization_user.user.is_active:
            raise HttpResponseBadRequest(_("User is already active"))
        return self.organization_user

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        invitation_backend().send_reminder(self.object.user,
                **{'domain': get_current_site(self.request),
                    'organization': self.organization, 'sender': request.user})
        return redirect(self.object)


class BaseOrganizationUserUpdate(OrganizationUserMixin, UpdateView):
    form_class = OrganizationUserForm


class BaseOrganizationUserDelete(OrganizationUserMixin, DeleteView):
    def get_success_url(self):
        return reverse('organization_user_list',
                kwargs={'organization_pk': self.object.organization.pk})


class OrganizationSignup(FormView):
    """
    View that allows unregistered users to create an organization account.

    It simply processes the form and then calls the specified registration
    backend.
    """
    form_class = SignUpForm
    template_name = "organizations/signup_form.html"
    # TODO get success from backend, because some backends may do something
    # else, like require verification
    backend = registration_backend()

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated():
            return redirect('organization_add')
        return super(OrganizationSignup, self).dispatch(request, *args,
                **kwargs)

    def get_success_url(self):
        if hasattr(self, 'success_url'):
            return self.success_url
        return reverse('organization_signup_success')

    def form_valid(self, form):
        """
        """
        user = self.backend.register_by_email(form.cleaned_data['email'])
        create_organization(user=user, name=form.cleaned_data['name'],
                slug=form.cleaned_data['slug'], is_active=False)
        return redirect(self.get_success_url())


def signup_success(self, request):
    return render(request, "organizations/signup_success.html", {})


class OrganizationList(BaseOrganizationList):
    pass


class OrganizationCreate(BaseOrganizationCreate):
    """
    Allows any user to create a new organization.
    """
    pass


class OrganizationDetail(MembershipRequiredMixin, BaseOrganizationDetail):
    pass


class OrganizationUpdate(AdminRequiredMixin, BaseOrganizationUpdate):
    pass


class OrganizationDelete(OwnerRequiredMixin, BaseOrganizationDelete):
    pass


class OrganizationBulkDelete(StaffRequiredMixin, OrganizationMixin, TemplateView):
    template_name = "organizations/organizationuser_confirm_bulk_delete.html"

    def get(self, request, *args, **kwargs):
        if not request.session.get("myc_organisations_users_to_delete"):
            return redirect(reverse("organization_user_list", args=(self.organization.pk,)))
        return super(OrganizationBulkDelete, self).get(request, args, kwargs)

    def post(self, request, *args, **kwargs):
        if request.POST.get("confirm_yes"):
            users_to_delete = self.request.session.get("myc_organisations_users_to_delete")
            organization_users = OrganizationUser.objects.filter(
                organization_id=self.organization.pk, user_id__in=users_to_delete)
            brand = Site.objects.get_current().domain
            for user in organization_users:
                if user.user.profile.site_registered.domain != brand:
                    messages.add_message(request, messages.ERROR,
                                         "You tried to remove user {0} but user is not registered on the site".format(
                                             user.user.username))
                    logging.getLogger().warn("{0} tried to remove {1} from {2} - {1} not part of {3}".format(
                        request.user.username, user.user.username, self.organization, brand))
                    users_to_delete.remove(str(user.user_id))

            OrganizationUser.objects.filter(organization_id=self.organization.pk, user_id__in=users_to_delete).delete()
            messages.add_message(request, messages.SUCCESS, "%d people removed from group" % len(users_to_delete))

            return redirect(reverse("organization_user_list", args=(self.organization.pk,)))
        elif request.POST.get("confirm_no"):
            return redirect(reverse("organization_user_list", args=(self.organization.pk,)))

    def get_context_data(self, **kwargs):
        context = super(OrganizationBulkDelete, self).get_context_data(**kwargs)
        context["users_to_delete"] = self.request.session.get("myc_organisations_users_to_delete")
        return context


class OrganizationUserList(MembershipRequiredMixin, BaseOrganizationUserList):
    def post(self, request, *args, **kwargs):
        request.session["myc_organisations_users_to_delete"] = request.POST.getlist("users")
        return redirect(reverse("organization_user_bulk_delete", args=(self.organization.pk,)))


class OrganizationUserDetail(AdminRequiredMixin, BaseOrganizationUserDetail):
    pass


class OrganizationUserUpdate(AdminRequiredMixin, BaseOrganizationUserUpdate):
    pass


class OrganizationUserCreate(AdminRequiredMixin, BaseOrganizationUserCreate):
    pass


class OrganizationUserRemind(AdminRequiredMixin, BaseOrganizationUserRemind):
    pass


class OrganizationUserDelete(AdminRequiredMixin, BaseOrganizationUserDelete):
    pass
