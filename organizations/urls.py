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

from __future__ import unicode_literals
from django.conf.urls import url
from django.contrib.auth.decorators import login_required

from .views import (OrganizationList, OrganizationDetail,
                    OrganizationUpdate, OrganizationDelete, OrganizationCreate,
                    OrganizationUserList, OrganizationUserDetail, OrganizationUserUpdate,
                    OrganizationUserCreate, OrganizationUserRemind, OrganizationUserDelete,
                    OrganizationUserAddFromActivity, OrganizationBulkDelete, OrganizationUserAddFromBrand,
                    OrganizationActivities, OrganizationDashboard, OrganizationDashboardActivity,
                    OrganizationSubgroupsAjax)


urlpatterns = [
    # Organization URLs
    url(r'^$', view=login_required(OrganizationList.as_view()),
        name="organization_list"),
    url(r'^add/$', view=login_required(OrganizationCreate.as_view()),
        name="organization_add"),
    url(r'^(?P<organization_pk>[\d]+)/$',
        view=login_required(OrganizationDetail.as_view()),
        name="organization_detail"),
    url(r'^(?P<organization_pk>[\d]+)/edit/$',
        view=login_required(OrganizationUpdate.as_view()),
        name="organization_edit"),
    url(r'^(?P<organization_pk>[\d]+)/delete/$',
        view=login_required(OrganizationDelete.as_view()),
        name="organization_delete"),
   url(r'^(?P<organization_pk>[\d]+)/dashboard/$',
       view=login_required(OrganizationDashboard.as_view()),
       name="organization_dashboard"),
   url(r'^(?P<organization_pk>[\d]+)/dashboard/(?P<activity_url_title>.*)/activity/$',
       view=login_required(OrganizationDashboardActivity.as_view()),
       name="organization_dashboard_activity"),

    # Organization user URLs
    url(r'^(?P<organization_pk>[\d]+)/people/$',
        view=login_required(OrganizationUserList.as_view()),
        name="organization_user_list"),
    url(r'^(?P<organization_pk>[\d]+)/people/add/$',
        view=login_required(OrganizationUserCreate.as_view()),
        name="organization_user_add"),
    url(r'^(?P<organization_pk>[\d]+)/people/(?P<user_pk>[\d]+)/remind/$',
        view=login_required(OrganizationUserRemind.as_view()),
        name="organization_user_remind"),
    url(r'^(?P<organization_pk>[\d]+)/people/(?P<user_pk>[\d]+)/$',
        view=login_required(OrganizationUserDetail.as_view()),
        name="organization_user_detail"),
    url(r'^(?P<organization_pk>[\d]+)/people/(?P<user_pk>[\d]+)/edit/$',
        view=login_required(OrganizationUserUpdate.as_view()),
        name="organization_user_edit"),
    url(r'^(?P<organization_pk>[\d]+)/people/(?P<user_pk>[\d]+)/delete/$',
        view=login_required(OrganizationUserDelete.as_view()),
        name="organization_user_delete"),
   url(r'^(?P<organization_pk>[\d]+)/people/bulk-delete/$',
       view=login_required(OrganizationBulkDelete.as_view()),
       name="organization_user_bulk_delete"),
   url(r'^(?P<organization_pk>[\d]+)/people/add_from_brand/$',
       view=login_required(OrganizationUserAddFromBrand.as_view()),
       name="organization_users_add_from_brand"),
   url(r'^(?P<organization_pk>[\d]+)/people/add_from_activity/$',
       view=login_required(OrganizationUserAddFromActivity.as_view()),
       name="organization_users_add_from_activity"),
   url(r'^(?P<organization_pk>[\d]+)/activities/$',
       view=login_required(OrganizationActivities.as_view()),
       name="organization_activities"),
   url(r'^(?P<organization_pk>[\d]+)/subgroups-ajax/?$',
       view=OrganizationSubgroupsAjax.as_view(),
       name="organization_subgroups_ajax"),
]
