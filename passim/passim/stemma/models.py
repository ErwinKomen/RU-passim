"""Models for the STEMMA app: stemmatology research

"""
from django.apps.config import AppConfig
from django.apps import apps
from django.db import models, transaction
from django.contrib.auth.models import User, Group
from django.db.models import Q
from django.db.models.functions import Lower
from django.db.models.query import QuerySet 
from django.urls import reverse


from markdown import markdown
import json, copy

# Take from my own app
from passim.utils import ErrHandle
from passim.settings import TIME_ZONE
from passim.basic.models import UserSearch
from passim.basic.views import base64_decode, base64_encode
from passim.seeker.models import get_current_datetime, get_crpp_date, build_abbr_list, COLLECTION_SCOPE, \
    EqualGold, Manuscript, Profile, CollectionSuper, Signature, SermonDescrKeyword, \
    SermonDescr, EqualGold

STANDARD_LENGTH=255
ABBR_LENGTH = 5


class StemmaSet(models.Model):
    """One stemmatology research set
    
    A research set is a user-curated collection of EqualGold objects (those that have a link to a transcription)
    It can be used as the basis for stemmatology research
    """

    # [1] obligatory name
    name = models.CharField("Name", max_length=STANDARD_LENGTH)
    # [1] a research set belongs to a particular user's profilee
    profile = models.ForeignKey(Profile, on_delete=models.CASCADE, related_name="profile_stemmasets")
    # [1] The saved items may be ordered (and they can be re-ordered by the user)
    order = models.IntegerField("Order", default=0)

    # [0-1] Optional notes for this set
    notes = models.TextField("Notes", blank=True, null=True)

    # [1] A list of all the STEMMA parameters for this research set
    contents = models.TextField("Contents", default="[]")

    # [1] The scope of this collection: who can view it?
    #     E.g: private, team, global - default is 'private'
    scope = models.CharField("Scope", choices=build_abbr_list(COLLECTION_SCOPE), default="priv", max_length=5)

    # [1] And a date: the date of saving this manuscript
    created = models.DateTimeField(default=get_current_datetime)
    saved = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        """Just return the name"""
        return self.name

    def save(self, force_insert = False, force_update = False, using = None, update_fields = None):
        # Adapt the save date
        self.saved = get_current_datetime()
        # Check if the order is specified
        if self.order is None or self.order <= 0:
            # Specify the order
            self.order = StemmaSet.objects.filter(profile=self.profile).count() + 1
        response = super(StemmaSet, self).save(force_insert, force_update, using, update_fields)

        # If there is no DCT definition yet, create a default one
        # SetDef.check_default(self, self.profile.user.username)

        # Return the response when saving
        return response

    def adapt_order(self):
        """Re-calculate the order *WITHIN* the stemmaset and adapt where needed"""

        qs = self.stemmaset_stemmaitems.all().order_by("order")
        order = 1
        with transaction.atomic():
            # Walk all the SetList objects
            for obj in qs:
                # Check if the order is as it should be
                if obj.order != order:
                    #No: adapt the order
                    obj.order = order
                    # And save it
                    obj.save()
                # Keep track of how the order should be
                order += 1
        return None

    def calculate_matches(self, ssglists):
        """Calculate the number of pm-matches for each list from ssglists"""

        oErr = ErrHandle()
        lBack = []
        try:
            # Preparation: create a list of SSG ids per list
            for oItem in ssglists:
                oItem['ssgid'] = [x['super'] for x in oItem['ssglist']]
                oItem['unique_matches'] = 0

            # Calculate the number of matches for each SSglist
            for idx_list in range(len(ssglists)):
                # Take this as the possible pivot list
                lPivot = ssglists[idx_list]['ssgid']

                # Walk all lists that are not this pivot and count matches
                lUnique = []
                oMatches = {}
                if 'matchset' in ssglists[idx_list]['title']:
                    oMatches = ssglists[idx_list]['title']['matchset']
                for idx, setlist in enumerate(ssglists):
                    if idx != idx_list:
                        # Get this ssglist
                        lSsgId = setlist['ssgid']

                        # Start calculating the number of matches this list has with the currently suggested PM
                        sKey = str(ssglists[idx]['title']['order'])
                        lMatches = []

                        # Consider all ssg id's in this list
                        for ssg_id in lSsgId:
                            # Global unique matches
                            if ssg_id in lPivot and not ssg_id in lUnique:
                                lUnique.append(ssg_id)
                            # Calculation with respect to the currently suggested PM
                            if ssg_id in lPivot: # and not ssg_id in lMatches:
                                lMatches.append(ssg_id)
                        # Keep track of the matches (for sorting)
                        oMatches[sKey] = len(lMatches)
                # Store the between-list matches
                ssglists[idx_list]['title']['matchset'] = oMatches

                # Store the number of matches for this list
                unique_matches = len(lUnique)
                ssglists[idx_list]['unique_matches'] = unique_matches

            # What we return
            lBack = ssglists
        except:
            msg = oErr.get_error_message()
            oErr.DoError("StemmaSet/calculate_matches")
            lBack = None
        # Return the status
        return lBack

    def calculate_pm(self):
        """Calculate the Pivot Manuscript/item for this research set"""

        oErr = ErrHandle()
        iBack = -1
        try:
            # Get the lists that we have made
            ssglists = self.get_ssglists()

            # Calculate the matches
            ssglists = self.calculate_matches(ssglists)

            # Figure out what the first best list is
            idx_pm = -1
            max_matches = -1
            min_order = len(ssglists) + 2
            min_year_start = 3000
            min_year_finish = 3000
            for idx, oListItem in enumerate(ssglists):
                unique_matches = oListItem['unique_matches']
                year_start = oListItem['title']['yearstart']
                year_finish = oListItem['title']['yearfinish']
                order = oListItem['title']['order']

                # Check which is the best so far
                bTakeThis = False
                bTakeThis = (unique_matches > max_matches)
                if not bTakeThis and unique_matches == max_matches:
                    bTakeThis = (year_start < min_year_start)
                    if not bTakeThis and year_start == min_year_start:
                        bTakeThis = (year_finish < min_year_finish)
                        if not bTakeThis and year_finish == min_year_finish:
                            bTakeThis = (order < min_order)

                # Adapt if this is the one
                if bTakeThis:
                    max_matches = unique_matches
                    min_year_start = year_start
                    min_year_finish = year_finish
                    min_order = order
                    idx_pm = idx

            # What we return is the 'order' value of the best matching list
            iBack = ssglists[idx_pm]['title']['order']

        except:
            msg = oErr.get_error_message()
            oErr.DoError("StemmaSet/calculate_pm")
            iBack = -1
        # Return the PM that we have found
        return iBack

    def get_analyze_markdown(self):
        """Get a button to start the analyzing process for this StemmaSet"""

        sBack = ""
        oErr = ErrHandle()
        try:
            url = reverse("stemmaset_dashboard", kwargs={'pk': self.id})
            title = "Initiate the process of analyzing the stemmatological research set"
            sBack = "<a href='{}' role='button' class='btn btn-xs jumbo-1' title='{}'><span class='glyphicon glyphicon-dashboard'></span></a>".format(
                url, title)
        except:
            msg = oErr.get_error_message()
            oErr.DoError("StemmaSet/get_analyze_markdown")
        return sBack

    def get_created(self):
        """REturn the creation date in a readable form"""

        # sDate = self.created.strftime("%d/%b/%Y %H:%M")
        sDate = get_crpp_date(self.created, True)
        return sDate

    def get_name_markdown(self):
        """Get the name of the stemmaset as well as a link to it"""

        sBack = ""
        oErr = ErrHandle()
        try:
            url = reverse("stemmaset_details", kwargs={'pk': self.id})
            sBack = "<span class='clickable'><a href='{}' class='nostyle'>{}</a><span>".format(
                url, self.name)
        except:
            msg = oErr.get_error_message()
            oErr.DoError("StemmaSet/get_name_markdown")
        return sBack

    def get_notes_html(self):
        """Convert the markdown notes"""

        sNotes = "-"
        if self.notes != None:
            sNotes = markdown(self.notes)
        return sNotes

    def get_saved(self):
        """REturn the saved date in a readable form"""

        # sDate = self.saved.strftime("%d/%b/%Y %H:%M")
        sDate = get_crpp_date(self.saved, True)
        return sDate

    def get_size_markdown(self):
        """Get a markdown representation of the size of this set"""

        size = 0
        lHtml = []
        size = self.stemmaset_stemmaitems.count()
        if size > 0:
            # Create a display for this topic
            lHtml.append("<span class='badge signature gr'>{}</span>".format(size))
        else:
            lHtml.append("0")
        sBack = ", ".join(lHtml)
        return sBack

    def get_ssglists(self, recalculate=False):
        """Get the set of lists for this particular StemmaSet"""

        oErr = ErrHandle()
        lBack = None
        try:
            if self.contents != "" and self.contents[0] == "[":
                lst_contents = json.loads(self.contents)
            else:
                lst_contents = []
            if not recalculate and len(lst_contents) > 0:
                # Should the unique_matches be re-calculated?
                if not 'unique_matches' in lst_contents[0]:
                    # Yes, re-calculate
                    lst_contents = self.calculate_matches(lst_contents)
                    # And make sure this gets saved!
                    self.contents = json.dumps(lst_contents)
                    self.save()
                lBack = lst_contents
            else:
                # Re-calculate the lists
                self.update_ssglists()
                # Get the result
                lBack = json.loads(self.contents)

        except:
            msg = oErr.get_error_message()
            oErr.DoError("StemmaSet/get_ssglists")
        return lBack

    def update_order(profile):
        """Update the order of one user's stemmaset items (within MyPassim)"""

        oErr = ErrHandle()
        bOkay = True
        try:
            # Something has happened
            qs = StemmaSet.objects.filter(profile=profile).order_by('order', 'id')
            with transaction.atomic():
                order = 1
                for obj in qs:
                    if obj.order != order:
                        obj.order = order
                        obj.save()
                    order += 1
        except:
            msg = oErr.get_error_message()
            oErr.DoError("StemmaSet/update_order")
            bOkay = False
        return bOkay


class StemmaCalc(models.Model):
    """Calculations on one stemma set"""

    # [1] Link to a particular Stemmaset
    stemmaset = models.ForeignKey(StemmaSet, on_delete=models.CASCADE, related_name="stemmaset_calcs")

    # [0-1] Place to store the Leitfehler data
    data = models.TextField("Leitfehler data", null=True, blank=True)

    # [0-1] The SVG output for visualizing this set
    svg = models.TextField("SVG", blank=True, null=True)

    # [1] Status of this stemmaset in calculations
    status = models.CharField("Status", default="none", max_length=20)

    # [0-1] Message that accompanies the status
    message = models.TextField("Message", null=True, blank=True)

    # [0-1] This is where the calculation process can be interrupted
    signal = models.CharField("Signal", default="none", max_length=20)

    # [1] And a date: the date of saving this manuscript
    created = models.DateTimeField(default=get_current_datetime)
    saved = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        sBack = "stemmacalc_{}".format(self.id)
        return sBack

    def save(self, force_insert = False, force_update = False, using = None, update_fields = None):
        # Adapt the save date
        self.saved = get_current_datetime()
        response = super(StemmaCalc, self).save(force_insert, force_update, using, update_fields)

        # Return the response when saving
        return response

    def get_lf(self):
        """Try to get the Leitfehler data"""

        lst_back = []
        lst_names = []
        oErr = ErrHandle()
        try:
            if not self.data is None and self.data != "":
                oData = json.loads(self.data)
                lst_back = oData.get("leitfehler", [])
                lst_names = oData.get("names", [])
        except:
            msg = oErr.get_error_message()
            oErr.DoError("get_lf")
        return lst_back, lst_names

    def get_lf_table(self):
        """Get the Leitfehler as a table"""

        sBack = ""
        oErr = ErrHandle()
        try:
            # Get the table and list of names
            lst_leitfehler, lst_names = self.get_lf()
            if len(lst_leitfehler) > 0 and len(lst_names) > 0:

                # Collect the data into one table
                lHtml = []
                lHtml.append("<table class='func-view'><thead><tr><th>Name</th><th>Label</th><th>numbers</th></tr>")
                lHtml.append("<tbody>")
                for idx, oLeitRow in enumerate(lst_leitfehler):
                    sName = lst_names[idx]
                    lHtml.append("<tr>")
                    lHtml.append("<td>{}</td>".format(sName))
                    lHtml.append("<td>{}</td>".format(oLeitRow[0]))
                    lHtml.append("<td>")
                    for item in oLeitRow[1:]:
                        lHtml.append("{} ".format(item))
                    lHtml.append("</td>")
                    lHtml.append("</tr>")
                lHtml.append("</tbody></table>")
                sBack = "\n".join(lHtml)

                # Also store the table in the message
                self.message = sBack
                self.save()
        except:
            msg = oErr.get_error_message()
            oErr.DoError("get_lf_table")
        return sBack

    def get_saved(self):
        """REturn the saved date in a readable form"""

        # sDate = self.saved.strftime("%d/%b/%Y %H:%M")
        sDate = get_crpp_date(self.saved, True)
        return sDate

    def get_status(self):
        sBack = self.status
        # Change behaviour when an interrupt has been pressed
        if self.signal == "interrupt":
            sBack = self.signal
        return sBack

    def get_message(self):
        return self.message

    def set_status(self, sStatus, message=None):
        sBack = ""
        oErr = ErrHandle()
        try:
            # Double check for interrupt
            if sStatus == "reset":
                self.signal = "none"
                self.status = "none"
                self.message = "..."
            elif self.signal == "interrupt":
                self.status = "error"
                self.message = "interrupted"
                # Reset the signal
                self.signal = "none"
                sBack = "interrupt"
            else:
                self.status = sStatus
                if not message is None:
                    self.message = message
                elif sStatus == "preparing":
                    self.message = ""
                sBack = self.status
            self.save()
        except:
            msg = oErr.get_error_message()
            oErr.DoError("set_status")
        return sBack

    def store_lf(self, lst_data, lst_names):
        """Store data into the stemmaset"""

        bResult = True
        oErr = ErrHandle()
        try:
            if not lst_data is None and isinstance(lst_data, list):
                oData = dict(leitfehler=lst_data, names=lst_names)
                sData = json.dumps(oData, indent=2)
                self.data = sData
                self.save()
        except:
            msg = oErr.get_error_message()
            oErr.DoError("store_lf")
            bResult = False
        return bResult

    def store_data(self, key, sData):
        """Store string data into the stemmaset"""

        bResult = True
        oErr = ErrHandle()
        try:
            if not sData is None and sData != "":
                oData = json.loads(self.data)
                oData[key] = sData
                sData = json.dumps(oData, indent=2)
                self.data = sData
                self.save()
        except:
            msg = oErr.get_error_message()
            oErr.DoError("store_data")
            bResult = False
        return bResult


class StemmaItem(models.Model):
    """A StemmaItem contains one EqualGold that is part of a StemmaSet"""

    # [1] A stemma item just belongs to a stemmaset set
    stemmaset = models.ForeignKey(StemmaSet, on_delete=models.CASCADE, related_name="stemmaset_stemmaitems")
    # [0-1] EqualGold pointer
    equal = models.ForeignKey(EqualGold, blank=True, null=True, on_delete=models.SET_NULL, related_name="equal_stemmaitems")

    # [1] The items must be ordered (and they can be re-ordered by the user)
    order = models.IntegerField("Order", default=0)

    def __str__(self):
        """Combine the name and the order"""
        sBack = "{}: {}".format(self.stemmaset.name, self.order)
        return sBack

