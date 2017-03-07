from __future__ import division
from __future__ import unicode_literals

import calendar
import json
import logging
import tempfile
from datetime import datetime

import inject
from builtins import range
from builtins import str
from dateutil.relativedelta import relativedelta
from django.contrib import messages
from django.contrib.auth.models import User
from django.contrib.sites.models import Site
from django.contrib.sites.shortcuts import get_current_site
from django.core.exceptions import PermissionDenied
from django.core.urlresolvers import reverse
from django.db import IntegrityError
from django.db.models import Q
from django.http import HttpResponse, HttpResponseBadRequest
from django.shortcuts import render, redirect, get_object_or_404
from django.utils.timezone import utc
from django.utils.translation import ugettext
from django.utils.translation import ugettext as _
from django.views.generic import (ListView, DetailView, UpdateView, CreateView,
        DeleteView, FormView)
from django.views.generic import (TemplateView)
from django.views.generic import View
from past.utils import old_div
from pure_pagination.paginator import Paginator, PageNotAnInteger
from pymongo.database import Database
from guardian.shortcuts import get_objects_for_organization, assign_perm, remove_perm, get_objects_for_user, \
    get_users_with_permission

from mycoracle import forms as mycoracle_forms
from mycoracle import models as mycoracle_models
from mycoracle import utils as mycoracle_utils
from mycoracle.forms import ActivityAndUsersForm, AdvancedModelMultipleChoiceField, BrandUsersForm, \
    BundledModelMultipleChoiceField
from TinCanApp.tincandb import TinCanActivityProfile
from .backends import invitation_backend, registration_backend
from .forms import (OrganizationForm, OrganizationUserForm,
                    OrganizationUserAddForm, OrganizationAddForm, SignUpForm)
from .mixins import (OrganizationMixin, OrganizationUserMixin,
                     MembershipRequiredMixin, AdminRequiredMixin, OwnerRequiredMixin, StaffRequiredMixin)
from .models import Organization, OrganizationUser
from .utils import create_organization


class BaseOrganizationList(ListView):
    # TODO change this to query on the specified model
    queryset = Organization.active.all()
    context_object_name = "organizations"

    def get_queryset(self):
        qs = super(BaseOrganizationList,
                   self).get_queryset()

        site = mycoracle_utils.get_current_user_site_profile(self.request.user).site
        qs = Organization.active.get_for_user(self.request.user)
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
                OrganizationUser.active.get(organization=o, user=self.request.user)
                o.user_is_member = True
            except OrganizationUser.DoesNotExist:
                o.user_is_member = False
            organizations.append(o)
        context["organizations"] = organizations
        return super(BaseOrganizationList, self).get_context_data(**context)


class BaseOrganizationDetail(OrganizationMixin, DetailView):
    def get_context_data(self, **kwargs):
        context = super(BaseOrganizationDetail, self).get_context_data(**kwargs)
        same_site_only = self.organization.site is not None
        context['num_organization_users'] = len(
            self.organization.get_members(same_site_only=same_site_only))
        context['recent_users'] = \
            self.organization.get_members(same_site_only=same_site_only).order_by("-date_created", "user__first_name")[0:5]
        context['activities'] = \
            get_objects_for_organization(self.organization, "access_activity", mycoracle_models.ActivityProfile).filter(active=True)
        context['organization'] = self.organization
        context['subgroups'] = self.organization.get_subgroups().order_by("name")
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
        same_site_only = self.organization.site is not None
        if request.POST:
            request.session["POST"] = request.POST.copy()

        group_form = mycoracle_forms.ParticipantSortForm(request.session.get("POST"))
        if group_form.is_valid():
            if len(group_form.cleaned_data["search_text"].split()) < 2:
                kwargs["first_name"] = group_form.cleaned_data["search_text"]
                kwargs["last_name"] = group_form.cleaned_data["search_text"]
            else:
                names = group_form.cleaned_data["search_text"].split()
                kwargs["first_name"] = names[0]
                kwargs["last_name"] = names[1]

        if "first_name" in kwargs and "last_name" in kwargs:
            self.object_list = self.organization.get_members().filter(
                Q(user__first_name__icontains=kwargs["first_name"]) |
                Q(user__last_name__icontains=kwargs["last_name"]) |
                Q(user__email__icontains=group_form.cleaned_data["search_text"])
            )
        else:
            self.object_list = self.organization.get_members(same_site_only=same_site_only)

        if not (self.request.user.profile.is_brand_supervisor() or self.organization.is_admin(self.request.user)):
            self.object_list = self.object_list.filter(Q(organization__is_hidden=False) | Q(user=self.request.user))

        sortorder = ""
        sortfield = "first_name"
        if request.session.get("POST"):
            sortorder = "" if group_form.cleaned_data["sort_order"] == "+" else "-"
            sortfield = group_form.cleaned_data["sort_field"]
        self.object_list = self.object_list.order_by("{0}user__{1}".format(sortorder, sortfield))
        total_members = self.object_list.count()

        p = Paginator(self.object_list, 40).page(page)
        self.object_list = p.object_list
        context = self.get_context_data(object_list=self.object_list,
                                        organization_users=self.object_list,
                                        organization=self.organization,
                                        pager=p)

        context["can_add"] = request.user.profile.is_brand_supervisor()
        context["can_remove"] = self.organization.is_admin(self.request.user)
        group_form = mycoracle_forms.ParticipantSortForm(request.session.get("POST"))
        context["participant_form"] = group_form
        context["total_members"] = total_members
        return self.render_to_response(context)

    def post(self, request, *args, **kwargs):
        if request.POST.get("action") == "bulk-delete":
            request.session["myc_organisations_users_to_delete"] = request.POST.getlist("users")
            return redirect(reverse("organization_user_bulk_delete", args=(self.organization.pk,)))
        else:
            request.session["POST"] = request.POST.copy()
            return self.get(request, *args, **kwargs)


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
    pass


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


# I don't think this is used.
class OrganizationUserAddFromActivity(AdminRequiredMixin, OrganizationMixin, TemplateView):
    template_name = "organizations/organizationuser_add_from_activity.html"

    def get(self, request, *args, **kwargs):
        form = ActivityAndUsersForm(initial={
            "user": request.user,
            "users": None,
        })
        context = self.get_context_data()
        if request.session.get("organisation_users_current_activity"):

            try:
                page = request.GET.get('page', 1)
            except PageNotAnInteger:
                page = 1

            mycoracle_models.ActivityProfile = request.session.get("organisation_users_current_activity")
            form.fields["activities"].initial = mycoracle_models.ActivityProfile.pk
            q = get_users_with_permission(mycoracle_models.ActivityProfile, "access_activity")
            p = Paginator(q, 40, request=request).page(page)
            form.fields["users"] = AdvancedModelMultipleChoiceField(
                queryset=p.object_list)
            # for uop in form.fields["users"]:
            # if self.organization.is_member(uop.user):
            #      pass
            context = self.get_context_data()
            context["pager"] = p
            context = dict()
            context["manageform"] = form
            context["show_users"] = True
        context = dict()
        context["manageform"] = form
        return self.render_to_response(context)

    def post(self, request, *args, **kwargs):
        if request.POST.get("update_user_list"):
            form = ActivityAndUsersForm(request.POST, initial={
                "user": request.user,
                "activities": get_objects_for_user(request.user, "administer_activity", mycoracle_models.ActivityProfile)
            })
            mycoracle_models.ActivityProfile = mycoracle_models.ActivityProfile.objects.get(pk=form["activities"].value)
            request.session["organisation_users_current_activity"] = mycoracle_models.ActivityProfile
            return redirect(reverse("organization_users_add_from_activity", args=(self.organization.id,)))
        elif request.POST.get("save_group_users"):
            form = ActivityAndUsersForm(request.POST, initial={
                "user": request.user,
                "activities": get_objects_for_user(request.user, "administer_activity", mycoracle_models.ActivityProfile)
            })

            for u in form["users"].value():
                try:
                    user = User.objects.get(int(u))
                    self.organization.add_user(user)
                except User.DoesNotExist:
                    messages.error(request, _(u"This user ({0}) does not exist".format(u)))
                except IntegrityError:
                    pass
            return redirect(reverse("organization_user_list", args=(self.organization.id,)))


class OrganizationUserAddFromBrand(StaffRequiredMixin, OrganizationMixin, TemplateView):
    template_name = "organizations/organizationuser_add_from_brand.html"

    def get_context_data(self, **kwargs):
        context = super(OrganizationUserAddFromBrand, self).get_context_data(**kwargs)
        request = self.request
        form = BrandUsersForm(initial={
            "user": request.user,
            "users": None,
        })

        try:
            page = request.GET.get('page', 1)
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

        current_users = []
        for user in OrganizationUser.objects.filter(organization=self.organization):
            current_users += [user.user.pk]
        if request.user.is_superuser:
            if "first_name" in kwargs and "last_name" in kwargs:
                q = User.objects.filter(~Q(pk__in=current_users), Q(first_name__icontains=kwargs["first_name"]) | Q(
                    last_name__icontains=kwargs["last_name"]),
                                        is_active=True, profile__site_registered=get_current_site(request))
            else:
                q = User.objects.filter(~Q(pk__in=current_users), is_active=True,
                                        profile__site_registered=get_current_site(request))
        else:
            if "first_name" in kwargs and "last_name" in kwargs:
                q = User.objects.filter(~Q(pk__in=current_users), Q(first_name__icontains=kwargs["first_name"]) | Q(
                    last_name__icontains=kwargs["last_name"]),
                                        is_active=True, profile__site_registered=request.user.profile.site_registered)
            else:
                q = User.objects.filter(~Q(pk__in=current_users), is_active=True,
                                        profile__site_registered=request.user.profile.site_registered)
        q = q.order_by("first_name")
        p = Paginator(q, 40, request=request).page(page)
        form.fields["users"] = BundledModelMultipleChoiceField(
            queryset=p.object_list)
        # for uop in form.fields["users"]:
        # if self.organization.is_member(uop.user):
        #      pass
        context["pager"] = p
        context["show_users"] = True
        context["manageform"] = form
        context["search_textbox"] = mycoracle_forms.UsersSearchForm()
        return context

    def post(self, request, *args, **kwargs):
        if request.POST.get("update_user_list"):
            form = ActivityAndUsersForm(request.POST, initial={
                "user": request.user,
                "activities": get_objects_for_user(request.user, "administer_activity", mycoracle_models.ActivityProfile)
            })
            mycoracle_models.ActivityProfile = mycoracle_models.ActivityProfile.objects.get(pk=form["activities"].value)
            request.session["organisation_users_current_activity"] = mycoracle_models.ActivityProfile
            return redirect(reverse("organization_users_add_from_brand", args=(self.organization.id,)))
        elif request.POST.get("save_group_users"):
            form = ActivityAndUsersForm(request.POST, initial={
                "user": request.user,
                "activities": get_objects_for_user(request.user, "administer_activity", mycoracle_models.ActivityProfile)
            })

            c = 0
            for u in form["users"].value():
                try:
                    user = User.objects.get(pk=int(u))
                    self.organization.add_user(user)
                    c += 1
                except IntegrityError as ie:
                    messages.warning(request, ie.message)
                except User.DoesNotExist:
                    messages.error(request, _(u"This user ({0}) does not exist".format(u)))

            messages.success(request, "{0} users added to group {1}".format(c, self.organization))
            return redirect(reverse("organization_user_list", args=(self.organization.id,)))


class OrganizationActivities(StaffRequiredMixin, OrganizationMixin, TemplateView):
    template_name = "organizations/organization_activities.html"

    def get_context_data(self, **kwargs):
        context = super(OrganizationActivities, self).get_context_data()
        context["organization"] = self.organization

        page = self.request.GET.get("page")
        page = page if page else 1
        if self.request.user.is_superuser:
            context["site_activities"] = \
                mycoracle_models.ActivityProfile.objects.filter(siteprofile__site=get_current_site(self.request))
        else:
            context["site_activities"] = mycoracle_models.ActivityProfile.objects.filter(
                siteprofile__site=self.request.user.profile.site_registered)
        context["pager"] = Paginator(context["site_activities"], 40, request=self.request).page(page)

        if self.request.method == "POST":
            for a in context["site_activities"]:
                if str(a.pk) in self.request.POST.getlist("activities"):
                    assign_perm("access_activity", self.organization, a, a.renewal_period)
                else:
                    remove_perm("access_activity", self.organization, a)
            messages.success(self.request, _("Activity permissions successfully set"))
        return context

    def get(self, request, *args, **kwargs):
        return super(OrganizationActivities, self).get(request, args, kwargs)

    def post(self, request, *args, **kwargs):
        return self.get(request)


class OrganizationSubgroupsAjax(OrganizationMixin, View):

    def get(self, request, *args, **kwargs):
        self.organization = get_object_or_404(Organization, pk=kwargs["organization_pk"])
        response = HttpResponse()
        response["Content-Type"] = "application/json"

        ret = list(Organization.objects.filter(
            is_active=True,
            is_hidden=False,
            parent=self.organization
        ))

        ret = json.dumps([{"id": x.pk, "text": x.name} for x in ret])
        response.write(ret)
        return response


class OrganizationDashboard(StaffRequiredMixin, OrganizationMixin, TemplateView):
    template_name = "organizations/organization_dashboard.html"
    context = dict()

    def post(self, request, *args, **kwargs):
        month = request.POST.get("month")
        year = request.POST.get("year")

        monthly = False
        if month or year:
            monthly = True

        if not month:
            month = datetime.utcnow().replace(tzinfo=utc).month
        if not year:
            year = datetime.utcnow().replace(tzinfo=utc).year

        period_start = datetime(int(year), int(month), 1, tzinfo=utc)
        period_end = period_start + relativedelta(months=1)

        self.context["period_start"] = None
        if monthly:
            self.context["period_start"] = period_start.strftime("%b %Y")
        self.context["monthly"] = monthly
        self.context["start"] = period_start
        self.context["end"] = period_end

        return self.get(request, *args, **kwargs)

    @inject.param("ap_repo", TinCanActivityProfile)
    def get(self, request, *args, **kwargs):
        self.context["organization"] = self.organization

        # moddables = list(
        #     get_objects_for_organization(
        #         kwargs["organization_pk"], "access_activity", mycoracle_models.ActivityProfile).order_by("name")
        # )
        siteprofile = mycoracle_utils.get_current_user_site_profile(self.request.user)
        try:
            orgnization_activities = mycoracle_models.OrganizationActivity.objects.get(
                site=siteprofile.site,
                organization=self.organization,
                active=True
            )
            moddables = list()
            for ag in orgnization_activities.activity_groups.all():
                moddables += [a for a in ag.activities.all()]
            moddables += [a for a in orgnization_activities.activities.all()]
        except mycoracle_models.OrganizationActivity.DoesNotExist:
            moddables = list(mycoracle_models.ActivityProfile.objects.filter(siteprofile__site=Site.objects.get_current()))
        if len(moddables) == 0:
            messages.warning(request, _("There are no activities to moderate"))
            return redirect(reverse("organization_detail", args=(self.organization.pk,)))

        self.context["acts"] = list()
        organization_users = self.organization.get_members()
        users_in_group = []
        for user in organization_users:
            users_in_group += [str(user.user_id)]

        self.context["statistic_date"] = mycoracle_forms.StatisticsDateForm(request.POST)
        for a in moddables:
            if not a.active:
                continue
            tcprofile = kwargs["ap_repo"].GetSingleActivityProfile({
                "profileId": "outline",
                "activityId": a.url
            })

            if not tcprofile:
                continue

            brand = Site.objects.get_current()
            if self.context.get("monthly"):
                a = mycoracle_utils.GetStatistics(
                    tcProfile=tcprofile, activity=a, organisation=self.organization,
                    brand=brand, monthly=True, start=self.context["start"], end=self.context["end"])
            else:
                a = mycoracle_utils.GetStatistics(tcProfile=tcprofile, activity=a, organisation=self.organization, brand=brand)
            a.total_users = len(users_in_group)
            self.context["acts"].append(a)
        return self.render_to_response(self.context)


class OrganizationDashboardActivity(TemplateView):
    template_name = "organizations/organization_dashboard_activity.html"

    def post(self, request, *args, **kwargs):
        svg = request.POST.getlist("svg[]")
        svgtext = request.POST.getlist("svgtitle[]")
        text = request.POST.getlist("text[]")
        title = request.POST.get("title")
        response = HttpResponse()
        if request.POST.get("type") == "png":
            tf = tempfile.NamedTemporaryFile(delete=False, suffix='.png')
            tf.write(mycoracle_utils.GenerateStatisticPng(svg[0]))
            response.write(file.name)
            tf.close()
            return response
        tf = tempfile.NamedTemporaryFile(delete=False, suffix='.pdf')
        tf.write(mycoracle_utils.GenerateStatisticPdf(svg, svgtext, text, title))
        response.write(tf.name)
        tf.close()
        return response

    @inject.param("ap_repo", TinCanActivityProfile)
    @inject.param("db", Database)
    def get(self, request, *args, **kwargs):
        try:
            activityprofile = mycoracle_models.ActivityProfile.objects.get(url_title=kwargs["activity_url_title"])
        except mycoracle_models.ActivityProfile.DoesNotExist:
            return redirect(reverse("url_home"))

        organization = get_object_or_404(Organization, pk=kwargs["organization_pk"])
        cansee = False
        organization_user = None
        try:
            organization_user = OrganizationUser.objects.get(organization=kwargs["organization_pk"], user=request.user)
            cansee = True
        except OrganizationUser.DoesNotExist:
            pass
        if (request.user.is_superuser
            or request.user.profile.is_brand_supervisor()
            or request.user.has_perm("administer_activity", activityprofile)
            or organization_user.is_moderator):
            cansee = True
        if not cansee:
            raise PermissionDenied
        users_in_group = [
            str(user["user_id"]) for user in
            organization.get_members().values("user_id")]

        xdata = ["0-25%", "25-50%", "50-75%", "75-100%"]
        tcprofile = kwargs["ap_repo"].GetSingleActivityProfile({
            "profileId": "outline",
            "activityId": activityprofile.url
        })
        stmts = 0
        testees = []
        test_bucket_hash = {}
        test_bucket_info = {}
        ctx = dict()
        if tcprofile:
            for x in tcprofile["objects"]:
                stmts += 1
                for v in x.get("verbs"):
                    if v.get("has_score"):
                        testees.append(x["id"])
                        test_bucket_hash[x["id"]] = [0, 0, 0, 0]
                        test_bucket_info[x["id"]] = {
                            "name": x["name"]
                        }

            res = kwargs["db"].activitystates.find({
                "stateId": "progress-by-id",
                "activityId": activityprofile.url,
                "agent.account.name": {"$in": users_in_group}
            })
            buckets = [0, 0, 0, 0]
            test_buckets = [0, 0, 0, 0]
            if stmts > 0:
                for x in res:
                    if not x.get("state"):
                        continue

                    s = len(x["state"])
                    if old_div(float(s), stmts) < 0.25:
                        buckets[0] += 1
                    elif old_div(float(s), stmts) < 0.5:
                        buckets[1] += 1
                    elif old_div(float(s), stmts) < 0.75:
                        buckets[2] += 1
                    else:
                        buckets[3] += 1
                    if test_buckets:
                        pass

                    for s in x["state"]:
                        if s["id"] in testees:
                            for v in s["verbs"]:
                                if v.get("result"):
                                    score = v["result"]["score"]["scaled"]
                                    if score < 0.25:
                                        test_bucket_hash[s["id"]][0] += 1
                                    elif score < 0.5:
                                        test_bucket_hash[s["id"]][1] += 1
                                    elif score < 0.75:
                                        test_bucket_hash[s["id"]][2] += 1
                                    else:
                                        test_bucket_hash[s["id"]][3] += 1

            chartdata1 = {'x': xdata, 'name1': 'Participants', 'y1': buckets}
            chartdata2 = {'x': xdata}
            for x in range(0, len(list(test_bucket_hash.keys()))):
                chartdata2.update({
                    "name{0}".format(x + 1): test_bucket_info[list(test_bucket_hash.keys())[x]]["name"],
                    "y{0}".format(x + 1): test_bucket_hash[list(test_bucket_hash.keys())[x]]
                })

            charttype1 = "discreteBarChart"
            charttype2 = "multiBarChart"

            ctx = {
                "charttype1": charttype1,
                "chartdata1": chartdata1,
                "chartcontainer1": "discretebarchart_container",
                'extra1': {
                    'x_is_date': False,
                    'x_axis_format': '',
                },
                "charttype2": charttype2,
                "chartdata2": chartdata2,
                "chartcontainer2": "multibarchart_container",
                "extra2": {
                    'x_is_date': False,
                    'x_axis_format': '',
                }
            }

            end = datetime(datetime.now().year, datetime.now().month, 1)
            start = end - relativedelta(months=12)
            year = list(mycoracle_utils.daterange(start, end))
            xdata = [1000 * int(calendar.timegm(y.timetuple())) for y in year]
            tcp = kwargs["ap_repo"].GetSingleActivityProfile({
                "profileId": "outline",
                "activityId": activityprofile.url
            })

            brand = Site.objects.get_current()
            stats = [mycoracle_utils.GetStatistics(
                tcProfile=tcp, activity=activityprofile, organisation=organization,
                brand=brand, monthly=True, start=month) for month in year]

            ydata = [[stat.num_started for stat in stats], [stat.average_statements for stat in stats],
                     [stat.average_visit_time for stat in stats], [stat.test_passed_percent for stat in stats]]

            data = \
                {
                    'charttype3': "stackedAreaChart",
                    'chartdata3': {
                        'x': xdata,
                        'name1': ugettext("Active users"),
                    },
                    "chartcontainer3": "stackedareachart_container3",
                    'extra3': {
                        'x_is_date': True,
                        'x_axis_format': "%b",
                        'show_controls': False,
                        'show_legend': False,
                        'chart_attr': {
                            # 'color': ['#afd000']
                        }
                    },
                    'charttype4': "stackedAreaChart",
                    'chartdata4': {
                        'x': xdata,
                        'name1': ugettext("Avg. statements/user"),
                    },
                    "chartcontainer4": "stackedareachart_container4",
                    'extra4': {
                        'x_is_date': True,
                        'x_axis_format': "%b",
                        'show_controls': False,
                        'show_legend': False,
                        'chart_attr': {
                            # 'color': ['#d44f57']
                        }
                    },
                    'charttype5': "stackedAreaChart",
                    'chartdata5': {
                        'x': xdata,
                        'name1': ugettext("Avg. page visit"),
                    },
                    "chartcontainer5": "stackedareachart_container5",
                    'extra5': {
                        'x_is_date': True,
                        'x_axis_format': "%b",
                        'show_controls': False,
                        'show_legend': False,
                        'chart_attr': {
                            # 'color': ['#18d4fe']
                        }
                    },
                    'charttype6': "stackedAreaChart",
                    'chartdata6': {
                        'x': xdata,
                        'name1': ugettext("Tests passed"),
                    },
                    "chartcontainer6": "stackedareachart_container6",
                    'extra6': {
                        'x_is_date': True,
                        'x_axis_format': "%b",
                        'show_controls': False,
                        'show_legend': False,
                        'chart_attr': {
                            # 'color': ['#ffc213']
                        }
                    },
                    "charttype7": "discreteBarChart",
                    "chartdata7": {
                        "name1": ugettext("Page activity"),
                    },
                    "chartcontainer7": "discretebarchart_container2",
                    'extra7': {
                        'x_is_date': False,
                        'x_axis_format': '',
                        'margin_bottom': 200,
                        'xAxis_rotateLabel': -80,
                    },
                }
            if any(ydata[0]):
                data["chartdata3"]["y1"] = ydata[0]
            if any(ydata[1]):
                data["chartdata4"]["y1"] = ydata[1]
            if any(ydata[2]):
                data["chartdata5"]["y1"] = ydata[2]
            if any(ydata[3]):
                data["chartdata6"]["y1"] = ydata[3]

            pagestats = mycoracle_utils.get_number_stmts_activity_page(activityprofile, organisation=organization,
                                                                       brand=brand)
            data["chartdata7"]["x"] = [stat[0]["name"] for stat in pagestats]
            data["chartdata7"]["y1"] = [stat[1] for stat in pagestats]
            ctx.update(data)

        ctx["activity"] = activityprofile
        return self.render_to_response(ctx)
