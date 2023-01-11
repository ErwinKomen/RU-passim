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


class SimpleAuthor(models.Model):
    """Simplified author specific for HUWA"""

    # [1] The Author's full name
    full = models.CharField("Full name", max_length = LONG_STRING)

    # [0-1] The optional components of the author's name
    name = models.CharField("Last name", max_length = LONG_STRING, blank=True, null=True)
    firstname = models.CharField("First name", max_length = LONG_STRING, blank=True, null=True)

    def __str__(self):
        sBack = self.full


class SimpleLocation(models.Model):
    """Simplified location specific for HUWA"""

    # [1] The location's city
    city = models.CharField("City", max_length = LONG_STRING)

    # [0-1] The optional components of the location
    country = models.CharField("Country", max_length = LONG_STRING, blank=True, null=True)

    def __str__(self):
        sBack = self.city


class Literatur(models.Model):
    """This hosts the gist of HUWA's [literatur] table, as combined with other tables
    
    HUWA: the specific tables that will be in here are:
        literatur
        bloomfield
        shoenberger
        stegemueller
        huwa            - this is for intra-HUWA cross-referencing
    """

    # [1] Should have the original [literatur] id field or [bloomfield] and so forth
    huwaid = models.IntegerField("Huwa ID")
    # [1] The external table name from which this literature comes: literatur, bloomfield etc
    huwatable = models.CharField("Huwa table name", max_length = LONG_STRING)

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
    slocation = models.ForeignKey(SimpleLocation, on_delete=models.SET_NULL, blank=True, null=True, related_name="locationeditions")

    # [0-1] Link to the name of an author
    sauthor = models.ForeignKey(SimpleAuthor, on_delete=models.SET_NULL, blank=True, null=True, related_name="authoreditions")

    def __str__(self):
        sName = "{}.{}".format(self.huwatable, self.huwaid)
        return sName

    def get_parts(self, pp=None, bAll=False):
        """Get the parts of this literature reference
        
        Note: possibly add one's own PP, if that is passed on
        """

        def do_append(html, field, fk = None):
            if fk is None:
                value = getattr(self, field)
                if not value is None and value != "":
                    html.append(value)
                elif bAll:
                    html.append("")
            else:
                obj = getattr(self, fk)
                if not obj is None:
                    value = getattr(obj, field)
                    if not value is None and value != "":
                        html.append(value)
                    elif bAll:
                        html.append("")
                elif bAll:
                    html.append("")
            return None

        html = []
        oErr = ErrHandle()
        try:
            do_append(html, "full", "sauthor")
            do_append(html, "year")
            do_append(html, "reihekurz")
            if pp is None:
                do_append(html, "pp")
            elif pp == "0":
                html.append("")
            else:
                html.append(pp)
            sTitel = "-"
            if not self.reihetitel is None and self.reihetitel != "":
                sTitel = self.reihetitel
            elif not self.literaturtitel is None and self.literaturtitel != "":
                sTitel = self.literaturtitel
            elif not self.title is None and self.title != "":
                sTitel = self.title
            html.append(sTitel)
            do_append(html, "band")
            do_append(html, "city", "slocation")
            do_append(html, "country", "slocation")
        except:
            msg = oErr.get_error_message()
            oErr.DoError("Literatur/get_parts")
        return html

    def get_parts_obj(self, pp=None):
        """Get the parts as an object"""

        lParts = self.get_parts(pp, bAll=True)
        oItem = dict(
            edition = None,
            author=dict(full=lParts[0]), 
            year=lParts[1], 
            reihekurz=lParts[2],
            pp=lParts[3], 
            reihetitel = None,
            literaturtitel = None,
            title=lParts[4], 
            band=lParts[5], 
            location = dict(city=lParts[6], country=lParts[7])  )
        return oItem

    def get_view(self, pp=None):
        """Get a view of this edition
        
        Note: possibly add one's own PP, if that is passed on
        """

        html = []
        sBack = ""
        oErr = ErrHandle()
        try:
            # Get the parts from [get_parts()]
            html = self.get_parts(pp)

            # Get the literature object
            sBack = ", ".join(html)
        except:
            msg = oErr.get_error_message()
            oErr.DoError("Literatur/get_view")
        return sBack

    def set_location(self, oLocation):
        """Get or create the [simple location] specified in [oLocation] and add a FK in this edition"""

        oErr = ErrHandle()
        bResult = True
        try:
            # A location may be:
            # - plain string => that should be 'city'
            # - 'city'
            # - 'country'
            if not oLocation is None:
                sCountry = None
                sCity = None
                obj = None
                if isinstance(oLocation, str):
                    # This is a simple string
                    sCity = oLocation
                else:
                    sCity = oLocation.get("city")
                    sCountry = oLocation.get("country")

                # Process city and possibly country
                if not sCity is None:
                    if sCountry is None:
                        # Try to find it
                        obj = SimpleLocation.objects.filter(city__iexact=sCity).first()
                        if obj is None:
                            # Create it
                            obj = SimpleLocation.objects.create(city=sCity)
                    else:
                        # Both city and country
                        obj = SimpleLocation.objects.filter(city__iexact=sCity, country__iexact=sCountry).first()
                        if obj is None:
                            # Create it
                            obj = SimpleLocation.objects.create(city=sCity, country=sCountry)
                elif not sCountry is None:
                    # Just the country...
                    obj = SimpleLocation.objects.filter(country__iexact=sCountry).first()
                    if obj is None:
                        # Create it
                        obj = SimpleLocation.objects.create(country=sCountry)

                # Attach to me
                if not obj is None:
                    self.slocation = obj
                    # (Saving of [self] will be done by the caller)

        except:
            msg = oErr.DoError()
            oErr.DoError("set_location")
            bResult = False

        # REturn the result
        return bResult

    def set_author(self, oAuthor):
        """Get or create the [simple author] specified in [oAuthor] and add a FK in this edition"""

        oErr = ErrHandle()
        bResult = True
        try:
            # The author must have 'full', and it may have 'name' (last name) and/or 'firstname'
            if not oAuthor is None:
                sFull = oAuthor.get("full")
                sName = oAuthor.get("name")
                sFirstname = oAuthor.get("firstname")
                # Try to find it
                lstQ = []
                lstQ.append(Q(full__iexact=sFull))
                if not sName is None:
                    lstQ.append(Q(name__iexact=sName))
                if not sFirstname is None:
                    lstQ.append(Q(firstname__iexact=sFirstname))
                obj = SimpleAuthor.objects.filter(*lstQ).first()
                if obj is None:
                    # Create it
                    obj = SimpleAuthor.objects.create(full=sFull)
                    bNeedSaving = False
                    if not sName is None:
                        obj.name = sName
                        bNeedSaving = True
                    if not sFirstname is None:
                        obj.firstname = sFirstname
                        bNeedSaving = True
                    if bNeedSaving:
                        obj.save()
                # Set the link
                if not obj is None:
                    self.sauthor = obj
                    # (Saving of [self] will be done by the caller)
        except:
            msg = oErr.DoError()
            oErr.DoError("set_author")
            bResult = False

        # REturn the result
        return bResult


class OperaLit(models.Model):
    """Connection between table [opera] and [literatur] in Huwa
    
    This table is used to host Stegmueller, Bloomfield, Schoenberger connections
    """

    # [1] Like the HUWA table, it should always be connected with an [opera] id
    operaid = models.IntegerField("Opera ID")
    # [1] An edition must also connect with something from the [Literatur] table
    literatur = models.ForeignKey(Literatur, on_delete=models.CASCADE, related_name="literatur_operalits")

    def __str__(self):
        sName = "{}.{}: {}".format(self.literatur.huwatable, self.literatur.huwaid, self.operaid)
        return sName


class Edition(models.Model):
    """This hosts the gist of HUWA's [editionen] table, as combined with other tables
    
    HUWA: this table links to [literatur] as well as to [opera]
    """

    # [1] Should have the original [edition] id field
    editionid = models.IntegerField("Edition ID")
    # [1] Like the HUWA table, it should always be connected with an [opera] id
    operaid = models.IntegerField("Opera ID")
    # [1] An edition must also connect with something from the [Literatur] table
    literatur = models.ForeignKey(Literatur, on_delete=models.CASCADE, related_name="literatur_editions")

    # [0-1] The HUWA 'seiten' attribute = starting page
    seiten = models.CharField("Seiten", max_length = LONG_STRING, blank=True, null=True)
    # [0-1] The HUWA 'seitenattr' attribute = what precedes the starting page
    seitenattr = models.CharField("Seiten", max_length = LONG_STRING, blank=True, null=True)
    # [0-1] The HUWA 'bis' attribute = ending page
    bis = models.CharField("Seiten", max_length = LONG_STRING, blank=True, null=True)
    # [0-1] The HUWA 'bisattr' attribute = what precedes the ending page
    bisattr = models.CharField("Seiten", max_length = LONG_STRING, blank=True, null=True)
    # [0-1] The HUWA 'titel' attribute = title of this piece of info?
    titel = models.CharField("Seiten", max_length = LONG_STRING, blank=True, null=True)

    def __str__(self):
        sName = "{}".format(self.editionid)
        return sName

    def add_locus(self, oLocus):
        """Create the [Locus] specified in [oLocus] and link it with an FK to [self]"""

        oErr = ErrHandle()
        bResult = True
        specification = ["cap", "explicit", "incipit"]
        try:
            # The locus must have page and line, but may have cap, explicit and incipit
            if not oLocus is None:
                sPage = oLocus.get("page")
                sLine = oLocus.get("line")
                # See if it is there already
                obj = Locus.objects.filter(huwaedition=self, page=sPage, line=sLine).first()
                if obj is None:
                    # Create it
                    obj = Locus.objects.create(huwaedition=self, page=sPage, line=sLine)

                    # Add other elements, if specified
                    bNeedSaving = False
                    for field in specification:
                        value = oLocus.get(field)
                        if not value is None:
                            setattr(obj, field,value)
                            bNeedSaving = True
                    if bNeedSaving:
                        obj.save()
        except:
            msg = oErr.DoError()
            oErr.DoError("add_locus")
            bResult = False

        # REturn the result
        return bResult

    def add_siglen(self, oSiglen):
        """Create the [Siglen] specified in [oSiglen] and link it with an FK to [self]"""

        oErr = ErrHandle()
        bResult = True
        try:
            # The siglen must have page and line, but may have cap, explicit and incipit
            if not oSiglen is None:
                iHandschrift = oSiglen.get("handschrift")
                sSigle = oSiglen.get("sigle")
                # See if it is there already
                obj = Siglen.objects.filter(huwaedition=self, huwahandschrift=iHandschrift, sigle=sSigle).first()
                if obj is None:
                    # Create it
                    obj = Siglen.objects.create(huwaedition=self, huwahandschrift=iHandschrift, sigle=sSigle)

                    # Add other elements, if specified
                    note = oSiglen.get("bem")
                    if not note is None and note != "":
                        obj.note = note
                        obj.save()
        except:
            msg = oErr.get_error_message()
            oErr.DoError("add_siglen")
            bResult = False

        # REturn the result
        return bResult

    def add_siglen_edd(self, oSiglenEdd):
        """Create the [SiglenEdd] specified in [oSiglen] and link it with an FK to [self]"""

        oErr = ErrHandle()
        bResult = True
        try:
            # The siglen must have page and line, but may have cap, explicit and incipit
            if not oSiglenEdd is None:
                iLiteratur = oSiglenEdd.get("literatur")
                sSigle = oSiglenEdd.get("sigle")
                # See if it is there already
                obj = SiglenEdd.objects.filter(huwaedition=self, huwaliteratur=iLiteratur, sigle=sSigle).first()
                if obj is None:
                    # Create it
                    obj = SiglenEdd.objects.create(huwaedition=self, huwaliteratur=iLiteratur, sigle=sSigle)

                    # Add other elements, if specified
                    note = oSiglenEdd.get("bem")
                    if not note is None and note != "":
                        obj.note = note
                        obj.save()
        except:
            msg = oErr.get_error_message()
            oErr.DoError("add_siglen_edd")
            bResult = False

        # REturn the result
        return bResult

    def get_edition_view(self, bParts = False):
        """Get a view of this edition, using my own defined PP"""

        pp = self.get_pp()
        oBack = self.literatur.get_parts(pp, bParts)
        if not bParts:
            oBack = ", ".join(oBack)
        return oBack

    def get_opera_literature(opera_id, handschrift_id=None):
        """Look for all literature related to [operaid]"""

        oErr = ErrHandle()
        lBack = []
        try:
            # (1) look in the table [Edition]
            qs = Edition.objects.filter(operaid=opera_id)
            for obj in qs:
                # Get the parts
                pp = obj.get_pp()
                oItem = obj.literatur.get_parts_obj(pp)
                oItem['edition'] = obj.editionid

                # Does this one have a siglen?
                sSigle = obj.get_siglen(handschrift_id)
                oItem['sigle'] = sSigle     # [ sSigle ]
                # Add it to the output list
                lBack.append(oItem)

                # Does this have any siglen_edds?
                for obj_edd in SiglenEdd.objects.filter(huwaedition=obj):
                    obj_lit = Literatur.objects.filter().first()
                    if not obj_lit is None:
                        oItem = obj_lit.get_parts_obj()
                        oItem['edition'] = obj.editionid
                        oItem['sigle'] = ", ".join(obj_edd.get_sigle())

                        # Add it to the output list
                        lBack.append(oItem)

            # (2) Look in the table [OperaLit]
            qs = OperaLit.objects.filter(operaid=opera_id)
            for obj in qs:
                # Add it to the output list
                oItem = obj.literatur.get_parts_obj()
                oItem['edition'] = ""
                oItem['sigle'] = ""
                lBack.append(oItem)
        except:
            msg = oErr.get_error_message()
            oErr.DoError("Edition/get_opera_literature")
        return lBack

    def get_pp(self):
        """Get a from until page range from table [editionen]"""

        sBack = ""
        oErr = ErrHandle()
        try:
            # Initialisations
            seiten = None
            bis = None
            von_rv = ""
            bis_rv = ""
            html = []

            # Collection of basic data
            if not self.seiten is None: seiten = self.seiten.split('.')[0]
            if not self.bis is None: bis = self.bis.split('.')[0]
            if not self.seitenattr is None: von_rv = self.seitenattr
            if not self.bisattr is None: bis_rv = self.bisattr

            # Calculate from
            lst_from = []
            if von_rv != "": lst_from.append(von_rv)
            if not seiten is None: lst_from.append(seiten)
            sFrom = "".join(lst_from)

            # Calculate until
            lst_until = []
            if bis_rv != "": lst_until.append(bis_rv)
            if not bis is None: lst_until.append(bis)
            sUntil = "".join(lst_until)

            # Combine the two
            if sFrom == sUntil:
                sBack = sFrom
            else:
                sBack = "{}-{}".format(sFrom, sUntil)

        except:
            msg = oErr.get_error_message()
            oErr.DoError("get_pp")

        return sBack

    def get_siglen(self, handschrift_id):
        """Search in [Siglen] to see if there is anything"""

        sBack = ""
        oErr = ErrHandle()
        try:
            # Take the first one that is matching
            obj = Siglen.objects.filter(huwaedition=self, huwahandschrift=handschrift_id).first()
            if not obj is None:
                # Get the sigle from it
                sBack = obj.get_sigle()
        except:
            msg = oErr.get_error_message()
            oErr.DoError("Edition/get_siglen")
        return sBack

    def get_siglen_edd(self, literatur_id):
        """Search in [SiglenEdd] to see if there is anything"""

        sBack = ""
        oErr = ErrHandle()
        try:
            # Take the first one that is matching
            obj = SiglenEdd.objects.filter(huwaedition=self, huwaliteratur=literatur_id).first()
            if not obj is None:
                # Get the sigle from it
                sBack = obj.get_sigle(handschrift_id)
        except:
            msg = oErr.get_error_message()
            oErr.DoError("Edition/get_siglen_edd")
        return sBack


class Locus(models.Model):
    """One locus is a place inside one Edition, optionally specifying an inc, exp or cap.
    
    HUWA: this is table [loci], which links with [editionen]
    """

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


class Siglen(models.Model):
    """One siglen is a reading sign for one edition, as it pertains to one manuscript (handschrift)

    HUWA: this is table [siglen], which links with [editionen]
    """

    # [1] Link to the edition
    huwaedition = models.ForeignKey(Edition, on_delete=models.CASCADE, related_name="editionsiglens")
    # [1] Link to the handschrift
    huwahandschrift = models.IntegerField("HUWA Handschrift")

    # [0-1] The optional 'sigle' element
    sigle = models.CharField("Sigle", max_length = LONG_STRING, blank=True, null=True)

    # [0-1] The optional 'bemerkungen' element
    note = models.CharField("Remark", max_length = LONG_STRING, blank=True, null=True)

    def __str__(self):
        sBack = "-"
        html = []
        # Should at least add the handschrift
        html.append("handschr {}".format(self.huwahandschrift))
        if not self.sigle is None and self.sigle != "":
            html.append("sigle {}".format(self.sigle))
        if len(html) > 0:
            sBack = " ".join(html)
        return sBack

    def get_sigle(self):
        sBack = self.sigle
        if not self.note is None:
            sBack = "{} ({})".format(sBack, self.note)
        return sBack


class SiglenEdd(models.Model):
    """One SiglenEdd is a reading sign for one edition, as it pertains to one literatur item

    HUWA: this is table [siglen_edd], which links with [editionen]
    """

    # [1] Link to the edition
    huwaedition = models.ForeignKey(Edition, on_delete=models.CASCADE, related_name="editionsiglenedds")
    # [1] Link to the literatur
    huwaliteratur = models.IntegerField("HUWA Literatur")

    # [0-1] The optional 'sigle' element
    sigle = models.CharField("Sigle", max_length = LONG_STRING, blank=True, null=True)

    # [0-1] The optional 'bemerkungen' element
    note = models.CharField("Remark", max_length = LONG_STRING, blank=True, null=True)

    def __str__(self):
        sBack = "-"
        html = []
        # Should at least add the handschrift
        html.append("lit {}".format(self.huwaliteratur))
        if not self.sigle is None and self.sigle != "":
            html.append("sigle {}".format(self.sigle))
        if len(html) > 0:
            sBack = " ".join(html)
        return sBack

    def get_sigle(self):
        sBack = self.sigle
        if not self.note is None:
            sBack = "{} ({})".format(sBack, self.note)
        return sBack


