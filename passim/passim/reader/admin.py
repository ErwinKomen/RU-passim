from django.contrib import admin
from django.contrib.admin.models import LogEntry, DELETION
from django.contrib.auth.models import User
from django.contrib.auth.admin import UserAdmin
from django.urls import reverse
from django.utils.html import escape

from passim.reader.models import *
from passim.reader.forms import *
from passim.settings import ADMIN_SITE_URL


class SimpleLocationAdmin(admin.ModelAdmin):
    list_display = ['city', 'country']
    list_filter = ['country']


# Main program models
admin.site.register(SimpleLocation, SimpleLocationAdmin)

