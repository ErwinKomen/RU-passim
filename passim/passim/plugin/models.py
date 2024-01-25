"""Models for the PLUGIN app.

This plugin has originally been created by Gleb Schmidt.
"""
from django.db import models
from django.db.models import Q
from django.urls import reverse
from django.utils import timezone
from django.utils.html import mark_safe
from markdown import markdown

import re, copy
import pytz

# From own stuff
from passim.settings import APP_PREFIX, WRITABLE_DIR, TIME_ZONE
from passim.utils import *
from passim.basic.models import get_current_datetime, get_crpp_date

LONG_STRING=255
STANDARD_LENGTH=100

# Create your models here.

class BoardDataset(models.Model):
    """A dataset points to a location on the server where pre-calculated data are kept"""

    # [1] obligatory name (to display) of the dataset
    name = models.CharField("Name", max_length=STANDARD_LENGTH)
    # [1] location where this set is kept on the server (relative path)
    location = models.CharField("Location", max_length=STANDARD_LENGTH)

    # [0-1] Optional notes for this set
    notes = models.TextField("Notes", blank=True, null=True)

    # [1] And a date: the date of saving this manuscript
    created = models.DateTimeField(default=get_current_datetime)
    saved = models.DateTimeField(default=get_current_datetime)

    def __str__(self):
        """Just return the name"""
        return self.name

    def save(self, force_insert = False, force_update = False, using = None, update_fields = None):
        # Adapt the save date
        self.saved = get_current_datetime()
        response = super(BoardDataset, self).save(force_insert, force_update, using, update_fields)

        # Return the response when saving
        return response

    def get_created(self):
        """REturn the created date in a readable form"""

        sDate = get_crpp_date(self.created, True)
        return sDate

    def get_saved(self):
        """REturn the saved date in a readable form"""

        sDate = get_crpp_date(self.saved, True)
        return sDate


class SermonsDistance(models.Model):
    """Which distance measure to take, in order to calculate sermons distance"""

    # [1] obligatory name (to display) of the sermons distance
    name = models.CharField("Name", max_length=STANDARD_LENGTH)
    # [1] which function to call in order to calculate it
    codepath = models.CharField("Code path", max_length=STANDARD_LENGTH)

    # [0-1] Optional notes for this distance measure
    notes = models.TextField("Notes", blank=True, null=True)

    # [1] And a date: the date of saving this item
    created = models.DateTimeField(default=get_current_datetime)
    saved = models.DateTimeField(default=get_current_datetime)

    def __str__(self):
        """Just return the name"""
        return self.name

    def save(self, force_insert = False, force_update = False, using = None, update_fields = None):
        # Adapt the save date
        self.saved = get_current_datetime()
        response = super(SermonsDistance, self).save(force_insert, force_update, using, update_fields)

        # Return the response when saving
        return response

    def get_created(self):
        """REturn the created date in a readable form"""

        sDate = get_crpp_date(self.created, True)
        return sDate

    def get_saved(self):
        """REturn the saved date in a readable form"""

        sDate = get_crpp_date(self.saved, True)
        return sDate


class SeriesDistance(models.Model):
    """Which distance measure to take, in order to calculate series distance"""

    # [1] obligatory name (to display) of the series distance
    name = models.CharField("Name", max_length=STANDARD_LENGTH)
    # [1] which function to call in order to calculate it
    codepath = models.CharField("Code path", max_length=STANDARD_LENGTH)

    # [0-1] Optional notes for this series
    notes = models.TextField("Notes", blank=True, null=True)

    # [1] And a date: the date of saving this item
    created = models.DateTimeField(default=get_current_datetime)
    saved = models.DateTimeField(default=get_current_datetime)

    def __str__(self):
        """Just return the name"""
        return self.name

    def save(self, force_insert = False, force_update = False, using = None, update_fields = None):
        # Adapt the save date
        self.saved = get_current_datetime()
        response = super(SeriesDistance, self).save(force_insert, force_update, using, update_fields)

        # Return the response when saving
        return response

    def get_created(self):
        """REturn the created date in a readable form"""

        sDate = get_crpp_date(self.created, True)
        return sDate

    def get_saved(self):
        """REturn the saved date in a readable form"""

        sDate = get_crpp_date(self.saved, True)
        return sDate


class Dimension(models.Model):
    """Usually just 2d or 3d dimension"""

    # [1] obligatory name (to display) of the series distance
    name = models.CharField("Name", max_length=STANDARD_LENGTH)
    # [1] abbreviation for this dimension
    abbr = models.CharField("Abbreviation", max_length=STANDARD_LENGTH)

    # [0-1] Optional notes for this dimension
    notes = models.TextField("Notes", blank=True, null=True)

    # [1] And a date: the date of saving this item
    created = models.DateTimeField(default=get_current_datetime)
    saved = models.DateTimeField(default=get_current_datetime)

    def __str__(self):
        """Just return the name"""
        return self.name

    def save(self, force_insert = False, force_update = False, using = None, update_fields = None):
        # Adapt the save date
        self.saved = get_current_datetime()
        response = super(Dimension, self).save(force_insert, force_update, using, update_fields)

        # Return the response when saving
        return response

    def get_created(self):
        """REturn the created date in a readable form"""

        sDate = get_crpp_date(self.created, True)
        return sDate

    def get_saved(self):
        """REturn the saved date in a readable form"""

        sDate = get_crpp_date(self.saved, True)
        return sDate


class ClMethod(models.Model):
    """Clustering method"""

    # [1] obligatory name (to display) of the Clustering method
    name = models.CharField("Name", max_length=STANDARD_LENGTH)
    # [1] abbreviation for this Clustering method
    abbr = models.CharField("Abbreviation", max_length=STANDARD_LENGTH)

    # [0-1] Optional notes for this Clustering method
    notes = models.TextField("Notes", blank=True, null=True)

    # [1] And a date: the date of saving this item
    created = models.DateTimeField(default=get_current_datetime)
    saved = models.DateTimeField(default=get_current_datetime)

    def __str__(self):
        """Just return the name"""
        return self.name

    def save(self, force_insert = False, force_update = False, using = None, update_fields = None):
        # Adapt the save date
        self.saved = get_current_datetime()
        response = super(ClMethod, self).save(force_insert, force_update, using, update_fields)

        # Return the response when saving
        return response

    def get_created(self):
        """REturn the created date in a readable form"""

        sDate = get_crpp_date(self.created, True)
        return sDate

    def get_saved(self):
        """REturn the saved date in a readable form"""

        sDate = get_crpp_date(self.saved, True)
        return sDate


class Highlight(models.Model):
    """UMAP highlight"""

    # [1] obligatory name (to display) of the UMAP highlight
    name = models.CharField("Name", max_length=STANDARD_LENGTH)
    # [1] additional information for this UMAP highlight
    info = models.TextField("Information", null=True, blank=True)

    # [0-1] Optional notes for this UMAP highlight
    notes = models.TextField("Notes", blank=True, null=True)

    # [1] And a date: the date of saving this item
    created = models.DateTimeField(default=get_current_datetime)
    saved = models.DateTimeField(default=get_current_datetime)

    def __str__(self):
        """Just return the name"""
        return self.name

    def save(self, force_insert = False, force_update = False, using = None, update_fields = None):
        # Adapt the save date
        self.saved = get_current_datetime()
        response = super(Highlight, self).save(force_insert, force_update, using, update_fields)

        # Return the response when saving
        return response

    def get_created(self):
        """REturn the created date in a readable form"""

        sDate = get_crpp_date(self.created, True)
        return sDate

    def get_saved(self):
        """REturn the saved date in a readable form"""

        sDate = get_crpp_date(self.saved, True)
        return sDate


