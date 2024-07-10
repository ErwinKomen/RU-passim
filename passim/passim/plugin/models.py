"""Models for the PLUGIN app.

This plugin has originally been created by Gleb Schmidt.
"""
from django.db import models, transaction
from django.db.models import Q
from django.urls import reverse
from django.utils import timezone
from django.utils.html import mark_safe
from markdown import markdown

import re, copy
import pytz
import os
import csv

# From own stuff
from passim.settings import APP_PREFIX, WRITABLE_DIR, TIME_ZONE, PLUGIN_DIR
from passim.utils import *
from passim.basic.models import get_current_datetime, get_crpp_date
from passim.seeker.models import build_abbr_list, Manuscript

LONG_STRING=255
STANDARD_LENGTH=100

# Any fieldchoice stuff
BOARD_DSET_STATUS = "plugin.dset_status"

# Create your models here.

class BoardDataset(models.Model):
    """A dataset points to a location on the server where pre-calculated data are kept"""

    # [1] obligatory name (to display) of the dataset
    name = models.CharField("Name", max_length=STANDARD_LENGTH)
    # [1] location where this set is kept on the server (relative path)
    location = models.CharField("Location", max_length=STANDARD_LENGTH)

    # [0-1] Optional notes for this set
    notes = models.TextField("Notes", blank=True, null=True)

    # [1] Whether this location is usable right now or not
    status = models.CharField("Board dataset status", choices=build_abbr_list(BOARD_DSET_STATUS), default="act", max_length=6)

    # [1] And a date: the date of saving this BoardDataset
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

    def scan():
        """Scan the plugin dir for possible preprocessed data and adapt the BoardDataset table"""

        bResult = True
        oErr = ErrHandle()
        bDoSermons = False
        sermon_csv = "char_codes.csv"
        bDoManuscripts = False
        manuscript_csv = "char_series.csv"
        metadata_csv = "metadata.csv"
        try:
            # Figure out whether Sermons or Manuscripts need doing
            if Psermon.objects.all().count() == 0:
                bDoSermons = True
            if Pmanuscript.objects.all().count() == 0:
                bDoManuscripts = True
            # Get to the plugin's preprocessed data location
            dir_loc = os.path.abspath(os.path.join(PLUGIN_DIR, "preprocessed_data"))
            if os.path.exists(dir_loc):
                # It exists: scan through all board dataset items
                for obj in BoardDataset.objects.all():
                    # Get the location here
                    dset_loc = os.path.abspath(os.path.join(dir_loc, obj.location))
                    bNeedSaving = False
                    if not os.path.exists(dset_loc):
                        # Make sure the status is set to inactive
                        if not obj.status == "ina":
                            obj.status = "ina"
                            bNeedSaving = True
                    else:
                        if not obj.status == "act":
                            obj.status = "act"
                            bNeedSaving = True
                    if bNeedSaving:
                        obj.save()

                    # Continue to look for Sermon data
                    serm_loc = os.path.abspath(os.path.join(dir_loc, obj.location, sermon_csv))
                    if bDoSermons and os.path.exists(serm_loc):
                        # The location is there: try to load the data
                        serm_line = []
                        with open(serm_loc, mode="r", encoding="utf-8") as f:
                            csv_file = csv.DictReader(f)
                            for line in csv_file:
                                serm_line.append(line)
                        # Walk the list and check if all data is there
                        for oLine in serm_line:
                            name = oLine.get("SermonName")
                            abbr = oLine.get("Code")
                            psermon = Psermon.objects.filter(dataset=obj, name=name).first()
                            if psermon is None:
                                psermon = Psermon.objects.create(dataset=obj, name=name, abbr=abbr)

                    # Continue to look for Manuscript data
                    manu_loc = os.path.abspath(os.path.join(dir_loc, obj.location, manuscript_csv))
                    meta_loc = os.path.abspath(os.path.join(dir_loc, obj.location, metadata_csv))
                    if bDoManuscripts and os.path.exists(manu_loc):
                        # The location is there: try to load the data
                        manu_line = []
                        with open(manu_loc, mode="r", encoding="utf-8") as f:
                            csv_file = csv.DictReader(f)
                            for line in csv_file:
                                manu_line.append(line)

                        # Also need to load the metadata
                        meta_line = []
                        if os.path.exists(meta_loc):
                            with open(meta_loc, mode="r", encoding="utf-8") as f:
                                # csv_file = csv.DictReader(f, quoting=csv.QUOTE_MINIMAL)
                                csv_file = csv.DictReader(f)
                                for line in csv_file:
                                    meta_line.append(line)

                        # Walk the list and check if all data is there
                        for idx, oLine in enumerate(manu_line):
                            name = oLine.get("SeriesName")
                            works = oLine.get("EncodedWorks")

                            skip_fields = ['Seriesname', 'EncodedWorks']

                            # optionally there is more metadata
                            oMeta = None if len(meta_line) == 0 else meta_line[idx]

                            pmanuscript = Pmanuscript.objects.filter(dataset=obj, name=name).first()
                            if pmanuscript is None:
                                pmanuscript = Pmanuscript.objects.create(dataset=obj, name=name, works=works)
                                # Do we have meta data?
                                if not oMeta is None:
                                    # Copy the meta data feature values
                                    for k, v in oMeta.items():
                                        if not k in skip_fields and hasattr(pmanuscript, k):
                                            if k == "total" and not re.match(r"^\d+$", v): # isinstance(v, int):
                                                oErr.Status("Skipping total as non-numeric: {}".format(v))
                                            else:
                                                setattr(pmanuscript, k, v)
                                    # Save the meta data
                                    pmanuscript.save()

        except:
            msg = oErr.get_error_message()
            oErr.DoError("BoardDataset/scan")
            bResult = False
        return bResult


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

    # [1] Order level: first fixed, then manuscripts
    otype = models.IntegerField("Order type", default=0)

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

    def initialize():
        """If this is empty, then initialize"""

        oErr = ErrHandle()
        lst_fixed = ['library', 'idno', 'lcity', 'lcountry', 'date', 'total', 'sermons', 'content', 'century', 'age', 'is_emblamatic']
        try:
            if Highlight.objects.count() == 0:
                # Start filling it with the fixed ones
                for sFix in lst_fixed:
                    obj = Highlight.objects.create(name=sFix, info=sFix, otype=1, notes="Automatically added from fixed list")
                # Add all manuscripts that are active
                with transaction.atomic():
                    for manu in Manuscript.objects.filter(mtype="man"):
                        sName = manu.get_full_name()
                        if not sName is None:
                            sName = sName.strip()
                            sInfo = "{}".format(manu.id)
                            obj = Highlight.objects.create(name=sName, info=sInfo, otype=2, notes="Automatically added manuscript")
        except:
            msg = oErr.get_error_message()
            oErr.DoError("Highlight/initialize")
        return None

    def get_created(self):
        """REturn the created date in a readable form"""

        sDate = get_crpp_date(self.created, True)
        return sDate

    def get_saved(self):
        """REturn the saved date in a readable form"""

        sDate = get_crpp_date(self.saved, True)
        return sDate


class Psermon(models.Model):
    """A sermon according to the plugin definition"""

    # [1] The name of the sermon is the [SermonName] field from char_code.csv
    name = models.CharField("Name", max_length=STANDARD_LENGTH)
    # [1] The symbol is the japanese character code representation of this sermon
    abbr = models.CharField("Code", max_length=STANDARD_LENGTH)
    # [1] Each Plugin [Sermon] belongs to one particular dataset
    dataset = models.ForeignKey(BoardDataset, on_delete=models.CASCADE, related_name="datasetsermons")

    def __str__(self):
        sBack = "{}-{}".format(self.dataset.name, self.name)
        return sBack


class Pmanuscript(models.Model):
    """A manuscript according to the plugin definition"""

    # [1] The name of the manuscript is the [SeriesName] field from char_series.csv
    name = models.CharField("Name", max_length=STANDARD_LENGTH)
    # [1] The symbols representing the sermons - those are the [EncodedWorks] in the char_series.csv
    works = models.TextField("Works", max_length=STANDARD_LENGTH)
    # [1] Each Plugin [Sermon] belongs to one particular dataset
    dataset = models.ForeignKey(BoardDataset, on_delete=models.CASCADE, related_name="datasetmanuscripts")

    # Fields defined in the metadata.csv
    # [1] Library
    library = models.CharField("Library", max_length=LONG_STRING, default = "-")
    # [1] lcity
    lcity = models.CharField("City", max_length=LONG_STRING, default = "-")
    # [1] Shelfmark idno
    idno = models.CharField("Idno", max_length=LONG_STRING, default = "-")
    # [1] lcountry
    lcountry = models.CharField("Country", max_length=LONG_STRING, default = "-")
    # [1] Date range
    date = models.CharField("Date range", max_length=LONG_STRING, default = "-")
    # [1] total
    total = models.IntegerField("Total number", default = 0)
    # [1] List of sermons
    sermons = models.TextField("Sermons", default = "-")
    # [1] List of sermons as stringified JSON
    content = models.TextField("Content", default = "[]")
    # [1] Shelfmark
    ms_identifier = models.CharField("Shelfmark", max_length=LONG_STRING, default = "-")
    # [1] Passim Manuscript ID
    passim_ms_id = models.IntegerField("Passim MS id", default = 0)
    # [1] Century
    passim_ms_id = models.IntegerField("Century", default = 0)

    def __str__(self):
        sBack = "{}-{}".format(self.dataset.name, self.name)
        return sBack

    def get_name(self):
        """Return the name, if defined"""

        sBack = ""
        if not self.name is None:
            if self.ms_identifier != "" and self.ms_identifier != "-":
                sBack = self.ms_identifier
            else:
                sBack = self.name
        return sBack




