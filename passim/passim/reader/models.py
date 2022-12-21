"""Models for the READER app.

"""
from django.apps.config import AppConfig
from django.apps import apps
from django.db import models, transaction
from django.contrib.auth.models import User, Group
from django.db.models import Q
from django.db.models.functions import Lower
from django.db.models.query import QuerySet 
from django.utils.html import mark_safe
from django.utils import timezone
from django.forms.models import model_to_dict
import pytz
from django.urls import reverse
from datetime import datetime
from markdown import markdown
import sys, os, io, re
import copy
import json
import time
import fnmatch
import csv
import math
import smtplib


# From this own application
from passim.utils import *
from passim.settings import APP_PREFIX, WRITABLE_DIR, TIME_ZONE

STANDARD_LENGTH=100
LONG_STRING=255
MAX_TEXT_LEN = 200
ABBR_LENGTH = 5

# ================================ For working with HUWA ==========================


class Author(models.Model):
    """Simplified author specific for HUWA"""

    # [1] The Author's full name
    full = models.CharField("Full name", max_length = LONG_STRING)

    # [0-1] The optional components of the author's name
    name = models.CharField("Last name", max_length = LONG_STRING, blank=True, null=True)
    firstname = models.CharField("First name", max_length = LONG_STRING, blank=True, null=True)

    def __str__(self):
        sBack = self.full


class Location(models.Model):
    """Simplified location specific for HUWA"""

    # [1] The location's city
    city = models.CharField("City", max_length = LONG_STRING)

    # [0-1] The optional components of the location
    country = models.CharField("Country", max_length = LONG_STRING, blank=True, null=True)

    def __str__(self):
        sBack = self.city


class Edition(models.Model):
    """This hosts the gist of HUWA's [editionen] table, as combined with other tables"""

    # [1] Should have the original [edition] id field
    edition = models.IntegerField("Edition ID")
    # [1] Like the HUWA table, it should always be connected with an [opera] id
    opera = models.IntegerField("Opera ID")

    # [0-1] Title 
    title = models.TextField("Title", blank=True, default="")
    # [0-1] Title of this literature
    literaturtitel = models.TextField("Literature title", blank=True, default="")
    # [0-1] The page range (optional)
    pp = models.CharField("Pages", max_length = LONG_STRING, blank=True, null=True)
    # [0-1] The year (as a string)
    year = models.CharField("Year", max_length = LONG_STRING, blank=True, null=True)
    # [0-1] The 'band' (volume) (as a string)
    band = models.CharField("Volume", max_length = LONG_STRING, blank=True, null=True)

    # [0-1] Series title full
    reihetitel = models.TextField("Series title", blank=True, default="")
    # [0-1] Series title short
    reihekurz = models.TextField("Series short", blank=True, default="")

    # [0-1] Link to a location
    location = models.ForeignKey(Location, on_delete=models.SET_NULL, blank=True, null=True, related_name="locationeditions")

    # [0-1] Link to the name of an author
    author = models.ForeignKey(Author, on_delete=models.SET_NULL, blank=True, null=True, related_name="authoreditions")

    def __str__(self):
        sName = "-"
        if not self.title is None and self.title != "":
            sName = self.title
        elif not self.literaturtitel is None and self.literaturtitel != "":
            sName = self.literaturtitel
        elif not self.reihetitel is None and self.reihetitel != "":
            sName = self.reihetitel
        elif not self.reihekurz is None and self.reihekurz != "":
            sName = self.reihekurz
        else:
            sName = "edition_{}".format(self.edition)
        return sName


class Locus(models.Model):
    """One locus is a place inside one Edition, optionally specifying an inc, exp or cap"""

    # [1] Link to the edition
    huwaedition = models.ForeignKey(Edition, on_delete=models.CASCADE, related_name="editionloci")

    # [0-1] The page and line number
    page = models.CharField("Page", max_length = LONG_STRING, blank=True, null=True)
    line = models.CharField("Line", max_length = LONG_STRING, blank=True, null=True)

    # [0-1] The optional 'cap' element
    cap = models.CharField("Cap", max_length = LONG_STRING, blank=True, null=True)

    # [0-1] The optional 'explicit' element
    explicit = models.CharField("Explicit", max_length = LONG_STRING, blank=True, null=True)
    # [0-1] The optional 'incipit' element
    incipit = models.CharField("Incipit", max_length = LONG_STRING, blank=True, null=True)

    def __str__(self):
        sBack = "-"
        html = []
        if not self.page is None and self.page != "":
            html.append("page {}".format(self.page))
        if not self.line is None and self.line != "":
            html.append("line {}".format(self.line))
        if len(html) > 0:
            sBack = " ".join(html)
        return sBack


