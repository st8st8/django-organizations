from __future__ import unicode_literals
from django.contrib import admin

from .models import Organization, OrganizationUser, OrganizationOwner


class OwnerInline(admin.StackedInline):
    model = OrganizationOwner
    raw_id_fields = ('organization_user',)


class OrganizationAdmin(admin.ModelAdmin):
    inlines = [OwnerInline]
    list_display = ['name', 'is_active', 'is_hidden']
    prepopulated_fields = {"slug": ("name",)}
    search_fields = ('name',)


class OrganizationUserAdmin(admin.ModelAdmin):
    list_display = ['user', 'organization', 'is_admin']
    raw_id_fields = ('user', 'organization')
    search_fields = ('user__username', 'user__first_name', 'user__last_name', 'organization__name')


class OrganizationOwnerAdmin(admin.ModelAdmin):
    raw_id_fields = ('organization_user', 'organization')


admin.site.register(Organization, OrganizationAdmin)
admin.site.register(OrganizationUser, OrganizationUserAdmin)
admin.site.register(OrganizationOwner, OrganizationOwnerAdmin)
