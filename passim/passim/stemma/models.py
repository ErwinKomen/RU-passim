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
        response = super(StemmaSet, self).save(force_insert, force_update, using, update_fields)

        # If there is no DCT definition yet, create a default one
        # SetDef.check_default(self, self.profile.user.username)

        # Return the response when saving
        return response

    def adapt_order(self):
        """Re-calculate the order and adapt where needed"""

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

    #def add_list(self, obj, setlisttype):
    #    """Add a list of SSGs (either Manuscript or Collection) to the research set"""

    #    oErr = ErrHandle()
    #    bBack = True
    #    try:
    #        # Get the current size of the research set
    #        iCount = self.stemmaset_setlists.count()
    #        order = iCount + 1
    #        setlist = None

    #        # Action depends on the type of addition
    #        if setlisttype == "manu":   # Add a manuscript
    #            setlist = SetList.objects.filter(stemmaset=self, setlisttype=setlisttype, manuscript=obj).first()
    #            if setlist is None:
    #                setlist = SetList.objects.create(
    #                    stemmaset=self, order=order, setlisttype=setlisttype,
    #                    manuscript=obj, name="Added via add_list")
    #            pass
    #        elif setlisttype == "ssgd":   # Add a hc or pd
    #            setlist = SetList.objects.filter(stemmaset=self, setlisttype=setlisttype, collection=obj).first()
    #            if setlist is None:
    #                setlist = SetList.objects.create(
    #                    stemmaset=self, order=order, setlisttype=setlisttype,
    #                    collection=obj, name="Added via add_list")

    #        # If need be, calculate the contents
    #        if not setlist is None:
    #            self.update_ssglists()

    #    except:
    #        msg = oErr.get_error_message()
    #        oErr.DoError("StemmaSet/add_list")
    #        bBack = False
    #    # Return the status
    #    return bBack

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

    def get_created(self):
        """REturn the creation date in a readable form"""

        # sDate = self.created.strftime("%d/%b/%Y %H:%M")
        sDate = get_crpp_date(self.created, True)
        return sDate

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

    #def update_ssglists(self, force = False):
    #    """Re-calculate the set of lists for this particular StemmaSet"""

    #    oErr = ErrHandle()
    #    bResult = True
    #    lst_ssglists = []
    #    try:
    #        oPMlist = None
    #        # Get the lists of SSGs for each list in the set
    #        for idx, setlist in enumerate(self.stemmaset_setlists.all().order_by('order')):
    #            # Check for the contents
    #            if force or setlist.contents == "" or len(setlist.contents) < 3 or setlist.contents[0] == "[":
    #                setlist.calculate_contents()

    #            # Retrieve the SSG-list from the contents
    #            oSsgList = json.loads(setlist.contents)

    #            # If this is not the *first* setlist, calculate the number of matches with the first
    #            if idx == 0:
    #                oPMlist = copy.copy(oSsgList)
    #            else:
    #                # Calculate the matches
    #                oSsgList['title']['matches'] = get_list_matches(oPMlist, oSsgList)
    #            # Always pass on the default order
    #            oSsgList['title']['order'] = idx + 1

    #            # Add the list object to the list
    #            lst_ssglists.append(oSsgList)

    #        # Calculate the unique_matches for each list
    #        lst_ssglists = self.calculate_matches(lst_ssglists)

    #        # Put it in the StemmaSet and save it
    #        self.contents = json.dumps(lst_ssglists)
    #        self.save()

    #        # All related SetDef items should be warned
    #        with transaction.atomic():
    #            for obj in SetDef.objects.filter(stemmaset=self.id):
    #                contents = json.loads(obj.contents)
    #                contents['recalc'] = True
    #                obj.contents = json.dumps(contents)
    #                obj.save()

    #        # Return this list of lists
    #        bResult = True
    #    except:
    #        msg = oErr.get_error_message()
    #        oErr.DoError("StemmaSet/update_ssglists")
    #        bResult = False
    #    return bResult


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

