from django.contrib import admin
from django.contrib.admin.models import LogEntry, DELETION
from django.contrib.auth.models import User
from django.contrib.auth.admin import UserAdmin
from django.urls import reverse

from passim.plugin.models import *

# Register your models here.

class BoardDatasetAdmin(admin.ModelAdmin):
    fields = ['name', 'location', 'notes', 'status']
    list_display = ['name', 'location', 'status', 'saved']
    formfield_overrides = {
        models.TextField: {'widget': admin.widgets.AdminTextareaWidget(attrs={'rows': 1, 'class': 'mytextarea'})},
        }


class SermonsDistanceAdmin(admin.ModelAdmin):
    fields = ['name', 'codepath', 'notes']
    list_display = ['name', 'codepath', 'saved']
    formfield_overrides = {
        models.TextField: {'widget': admin.widgets.AdminTextareaWidget(attrs={'rows': 1, 'class': 'mytextarea'})},
        }


class SeriesDistanceAdmin(admin.ModelAdmin):
    fields = ['name', 'codepath', 'notes']
    list_display = ['name', 'codepath', 'saved']
    formfield_overrides = {
        models.TextField: {'widget': admin.widgets.AdminTextareaWidget(attrs={'rows': 1, 'class': 'mytextarea'})},
        }


class DimensionAdmin(admin.ModelAdmin):
    fields = ['name', 'abbr', 'notes']
    list_display = ['name', 'abbr', 'saved']
    formfield_overrides = {
        models.TextField: {'widget': admin.widgets.AdminTextareaWidget(attrs={'rows': 1, 'class': 'mytextarea'})},
        }


class ClMethodAdmin(admin.ModelAdmin):
    fields = ['name', 'abbr', 'notes']
    list_display = ['name', 'abbr', 'saved']
    formfield_overrides = {
        models.TextField: {'widget': admin.widgets.AdminTextareaWidget(attrs={'rows': 1, 'class': 'mytextarea'})},
        }


class HighlightAdmin(admin.ModelAdmin):
    fields = ['name', 'info', 'notes']
    list_display = ['name', 'info', 'saved']
    formfield_overrides = {
        models.TextField: {'widget': admin.widgets.AdminTextareaWidget(attrs={'rows': 1, 'class': 'mytextarea'})},
        }


# Main program models
admin.site.register(BoardDataset, BoardDatasetAdmin)
admin.site.register(SermonsDistance, SermonsDistanceAdmin)
admin.site.register(SeriesDistance, SeriesDistanceAdmin)
admin.site.register(Dimension, DimensionAdmin)
admin.site.register(ClMethod, ClMethodAdmin)
admin.site.register(Highlight, HighlightAdmin)
