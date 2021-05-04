from django.contrib import admin
from django.contrib.admin.models import LogEntry, DELETION
from django.contrib.auth.models import User
from django.contrib.auth.admin import UserAdmin
from django.core.urlresolvers import reverse

from passim.basic.models import *


class UserSearchAdmin(admin.ModelAdmin):
    """User search queries"""

    list_display = ['view', 'params']
    fields = ['view', 'params', 'history']




# Register your models here.
admin.site.register(UserSearch, UserSearchAdmin)

