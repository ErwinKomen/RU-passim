"""Models for the DCT app: dynamic comparison tables

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

# Take from my own app
from passim.utils import ErrHandle
from passim.seeker.models import get_current_datetime, build_abbr_list, \
    Collection, Manuscript, Profile, CollectionSuper, Signature

STANDARD_LENGTH=255
ABBR_LENGTH = 5

SETLIST_TYPE = "dct.setlisttype"

def get_passimcode(super_id, super_code):
    code = super_code if super_code and super_code != "" else "(nocode_{})".format(super_id)
    return code

def get_goldsig_dct(super_id):
    """Get the best signature according to DCT rules"""

    sBack = ""
    first = None
    editype_preferences = ['gr', 'cl', 'ot']
    for editype in editype_preferences:
        siglist = Signature.objects.filter(gold__equal_id=super_id, editype=editype).order_by('code').values('code')
        if len(siglist) > 0:
            code = siglist[0]['code']
            sBack = "{}: {}".format(editype, code)
            break
    return sBack


class ResearchSet(models.Model):
    """One research set
    
    A research set is a user-curated collection of source-lists.
    It can be used as the basis for creating a DCT, a dynamic comparison table
    """

    # [1] obligatory name
    name = models.CharField("Name", max_length=STANDARD_LENGTH)
    # [1] a research set belongs to a particular user's profilee
    profile = models.ForeignKey(Profile, on_delete=models.CASCADE, related_name="profile_researchsets")

    # [0-1] Optional notes for this set
    notes = models.TextField("Notes", blank=True, null=True)

    # [1] And a date: the date of saving this manuscript
    created = models.DateTimeField(default=get_current_datetime)
    saved = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        """Just return the name"""
        return self.name

    def save(self, force_insert = False, force_update = False, using = None, update_fields = None):
        # Adapt the save date
        self.saved = get_current_datetime()
        response = super(ResearchSet, self).save(force_insert, force_update, using, update_fields)

        # If there is no DCT definition yet, create a default one
        SetDef.check_default(self, self.profile.user.username)

        # Return the response when saving
        return response

    def get_created(self):
        """REturn the creation date in a readable form"""

        sDate = self.created.strftime("%d/%b/%Y %H:%M")
        return sDate

    def get_saved(self):
        """REturn the saved date in a readable form"""

        sDate = self.saved.strftime("%d/%b/%Y %H:%M")
        return sDate

    def get_notes_html(self):
        """Convert the markdown notes"""

        sNotes = "-"
        if self.notes != None:
            sNotes = markdown(self.notes)
        return sNotes

    def get_size_markdown(self):
        """Get a markdown representation of the size of this set"""

        size = 0
        lHtml = []
        size = self.researchset_setlists.count()
        if size > 0:
            # Create a display for this topic
            lHtml.append("<span class='badge signature gr'>{}</span>".format(size))
        else:
            lHtml.append("0")
        sBack = ", ".join(lHtml)
        return sBack

    def adapt_order(self):
        """Re-calculate the order and adapt where needed"""

        qs = self.researchset_setlists.all().order_by("order")
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


class SetList(models.Model):
    """A setlist belongs to a research set"""

    # [1] A setlist just belongs to a research set
    researchset = models.ForeignKey(ResearchSet, on_delete=models.CASCADE, related_name="researchset_setlists")
    # [1] The lists must be ordered (and they can be re-ordered by the user)
    order = models.IntegerField("Order", default=0)
    # [1] Each setlist must be of a particular type
    setlisttype = models.CharField("Setlist type", choices=build_abbr_list(SETLIST_TYPE), max_length=5)

    # [1] For convenience and faster operation: keep a JSON list of the SSGs in this setlist
    contents = models.TextField("Contents", default="[]")

    # Depending on the type of setlist, there is a pointer to the actual list of SSGs
    # [0-1] Manuscript pointer
    manuscript = models.ForeignKey(Manuscript, blank=True, null=True, on_delete=models.SET_NULL, related_name="manuscript_setlists")
    # [0-1] Collection pointer (that can be HC, public or personal collection
    collection = models.ForeignKey(Collection, blank=True, null=True, on_delete=models.SET_NULL, related_name="collection_setlists")

    def __str__(self):
        """Combine the name and the order"""
        sBack = "{}: {}".format(self.researchset.name, self.order)
        return sBack

    def get_ssg_list(self):
        """Create a list of SSGs,depending on the type I am"""

        oErr = ErrHandle()
        lBack = None
        collection_types = ['hist', 'ssgd']
        try:
            if self.setlisttype == "manu":
                # Create a list of SSG's from the manuscript
                lBack = self.ssgs_manuscript(self.manuscript)
            elif self.setlisttype in collection_types:
                lBack = self.ssgs_collection(self.collection)
        except:
            msg = oErr.get_error_message()
            oErr.DoError("SetList/get_ssg_list")
        return lBack

    def get_title_object(self):
        """Depending on the setlisttype, this provides the title of the setlist
        
        The title is stored in an object, to facilitate template rendering
        """

        oBack = {"main": "", "size": 0}
        if self.setlisttype == "manu":
            # This is a manuscript
            oBack = self.manuscript.get_full_name_html(field1="top", field2="middle", field3="main")
            oBack['size'] = self.manuscript.get_sermon_count()
        elif self.setlisttype == "hist":
            # Historical collection
            oBack['top'] = "hc"
            oBack['main'] = self.collection.name
            oBack['size'] = self.collection.freqsuper()
        elif self.setlisttype == "ssgd":
            # Personal collection
            oBack['top'] = "pd"
            oBack['main'] = self.collection.name
            oBack['size'] = self.collection.freqsuper()
        else:
            # No idea what this is
            oBack['top'] = "UNKNOWN"
            oBack['main'] = self.setlisttype
        # Return the result
        return oBack

    def ssgs_collection(self, bDebug = False):
        """Get the ordered list of SSGs in the [super] type collection"""

        oErr = ErrHandle()
        lBack = None
        try:
            coll = self.collection
            # Get the list of SSGs inside this collection
            qs = CollectionSuper.objects.filter(collection=coll).order_by('order').values(
                'order', 'super', 'super__code')
            lBack = []
            with transaction.atomic():
                for obj in qs:
                    # Get the order number
                    order = obj['order']
                    # Get the SSG
                    super = obj['super']
                    code = obj['super__code']
                    # Treat signatures for this SSG
                    sigbest = get_goldsig_dct(super)
                    if sigbest == "":
                        sigbest = "ssg_{}".format(super)
                    # Put into object
                    oItem = dict(super=super, sig=sigbest, order=order, code=code)
                    # Add to list
                    lBack.append(oItem)

            # Debugging: print the list
            if bDebug:
                print("Collection id={}".format(coll.id))
                for oItem in lBack:
                    order = oItem.get("order")
                    super = oItem.get("super")
                    sig = oItem.get("sig")
                    code = get_passimcode(super, code)
                    print("sermon {}: ssg={} sig=[{}]".format(order, code, sig))

        except:
            msg = oErr.get_error_message()
            oErr.DoError("ssgs_collection")
        return lBack

    def ssgs_manuscript(self, bDebug = False):
        """Get the ordered list of SSGs related to a manuscript"""

        oErr = ErrHandle()
        lBack = None
        try:
            manu = self.manuscript
            # Get a list of SSGs to which the sermons in this manuscript point
            qs = manu.sermondescr_super.all().order_by('sermon__msitem__order').values(
                'sermon__msitem__order', 'super', 'super__code')
            lBack = []
            with transaction.atomic():
                for obj in qs:
                    # Get the order number
                    order = obj['sermon__msitem__order']
                    # Get the SSG
                    super = obj['super']
                    code = obj['super__code']
                    # Treat signatures for this SSG
                    sigbest = get_goldsig_dct(super)
                    if sigbest == "":
                        sigbest = "ssg_{}".format(super)
                    # Put into object
                    oItem = dict(super=super, sig=sigbest, order=order, code=code)
                    # Add to list
                    lBack.append(oItem)

            # Debugging: print the list
            if bDebug:
                print("Manuscript id={}".format(manu.id))
                for oItem in lBack:
                    order = oItem.get("order")
                    super = oItem.get("super")
                    sig = oItem.get("sig")
                    code = get_passimcode(super, code)
                    print("sermon {}: ssg={} sig=[{}]".format(order, code, sig))

        except:
            msg = oErr.get_error_message()
            oErr.DoError("ssgs_manuscript")
        return lBack
    

class SetDef(models.Model):
    """THe definition of a DCT"""

    # [1] obligatory name
    name = models.CharField("Name", max_length=STANDARD_LENGTH)
    # [1] A setlist just belongs to a research set
    researchset = models.ForeignKey(ResearchSet, on_delete=models.CASCADE, related_name="researchset_setdefs")
    # [1] order number of this DCT (assigned automatically)
    order = models.IntegerField("Order", default = 0)

    # [0-1] Optional notes for this definition
    notes = models.TextField("Notes", blank=True, null=True)

    # [1] A list of all the DCT parameters for this DCT
    contents = models.TextField("Contents", default="[]")

    # [1] And a date: the date of saving this manuscript
    created = models.DateTimeField(default=get_current_datetime)
    saved = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        """Just return the name"""
        return self.name

    def save(self, force_insert = False, force_update = False, using = None, update_fields = None):
        # Adapt the save date
        self.saved = get_current_datetime()
        # Calculate the proper order
        last = SetDef.objects.filter(researchset=self.researchset).order_by("-order").first()
        if last == None:
            order = 1
        else:
            order = last.order + 1
        # Automatically assign a name
        default_name = "{}_DCT_{:06}".format(self.researchset.profile.user.username, order)
        self.name = default_name
        self.notes = "Automatically created"
        # Initial saving
        response = super(SetDef, self).save(force_insert, force_update, using, update_fields)

        # Return the response when saving
        return response

    def check_default(rset, username):
        """Create a default SetDef for this research set"""

        # Are there any setdefs?
        if SetDef.objects.filter(researchset=rset).count() == 0:
            # Make sure to create at least one (with overall default values)
            obj = SetDef.objects.create(researchset=rset)
        return True

    def get_created(self):
        """REturn the creation date in a readable form"""

        sDate = self.created.strftime("%d/%b/%Y %H:%M")
        return sDate

    def get_notes_html(self):
        """Convert the markdown notes"""

        sNotes = "-"
        if self.notes != None:
            sNotes = markdown(self.notes)
        return sNotes

    def get_saved(self):
        """REturn the saved date in a readable form"""

        sDate = self.saved.strftime("%d/%b/%Y %H:%M")
        return sDate

    def get_setlist(self, pivot_id=None):
        """Get the set of lists for this particular DCT"""

        oErr = ErrHandle()
        oBack = None
        try:
            # Get to the research set
            id_list = [x['id'] for x in self.researchset.researchset_setlists.all().order_by('order').values("id")]
            lst_rset = []
            if pivot_id != None and pivot_id in id_list:
                lst_rset.append(pivot_id)
            # Add the remaining ID's
            for id in id_list:
                if not id in lst_rset: lst_rset.append(id)

            # Check the number of lists in the research set
            if lst_rset == None or len(lst_rset) < 2:
                oErr.Status("Not enough SSG-lists to compare")
                return None

            # We have enough lists: Get the lists of SSGs for each 
            lst_ssglists = []
            for setlist_id in lst_rset:
                # Get the actual setlist
                setlist = SetList.objects.filter(id=setlist_id).first()
                if setlist != None:
                    # Create an empty SSG-list
                    oSsgList = {}
                    # Add the object itself
                    oSsgList['obj'] = setlist
                    # Add the name object for this list
                    oSsgList['title'] = setlist.get_title_object()
                    # Get the list of SSGs for this list
                    oSsgList['ssglist'] = setlist.get_ssg_list()
                    # Add the list object to the list
                    lst_ssglists.append(oSsgList)
            
            # Return this list of lists
            oBack = dict(ssglists=lst_ssglists)
            # Prepare and create an appropriate table = list of rows
            rows = []
            # Create header row
            oRow = []
            oRow.append('Gr/Cl/Ot')
            for oSsgList in lst_ssglists:
                # Add the title *object*
                oRow.append(oSsgList['title'])
            rows.append(oRow)

            # Start out with the pivot: the *first* one in 'ssglist'
            lst_pivot = lst_ssglists[0]
            for oPivot in lst_pivot['ssglist']:
                # Create a row based on this pivot
                oRow = []
                # (1) row header
                oRow.append(oPivot['sig'])
                # (2) pivot SSG number
                oRow.append(oPivot['order'])
                # (3) SSG number in all other manuscripts
                ssg_id = oPivot['super']
                for lst_this in lst_ssglists[1:]:
                    bFound = False
                    order = ""
                    for oItem in lst_this['ssglist']:
                        if ssg_id == oItem['super']:
                            # Found it!
                            order = oItem['order']
                            bFound = True
                            break
                    oRow.append(order)
                # (4) add the row to the list
                rows.append(oRow)
            # Make sure we return the right information
            oBack['setlist'] = rows
        except:
            msg = oErr.get_error_message()
            oErr.DoError("SetDef/get_setlist")
        return oBack

    def get_ssglists(self, pivot_id=None):
        """Get the set of lists for this particular DCT"""

        oErr = ErrHandle()
        lBack = None
        try:
            # Get to the research set
            id_list = [x['id'] for x in self.researchset.researchset_setlists.all().order_by('order').values("id")]
            lst_rset = []
            if pivot_id != None and pivot_id in id_list:
                lst_rset.append(pivot_id)
            # Add the remaining ID's
            for id in id_list:
                if not id in lst_rset: lst_rset.append(id)

            # Check the number of lists in the research set
            if lst_rset == None or len(lst_rset) < 2:
                oErr.Status("Not enough SSG-lists to compare")
                return None

            # We have enough lists: Get the lists of SSGs for each 
            lst_ssglists = []
            for setlist_id in lst_rset:
                # Get the actual setlist
                setlist = SetList.objects.filter(id=setlist_id).first()
                if setlist != None:
                    # Create an empty SSG-list
                    oSsgList = {}

                    # Add the name object for this list
                    oSsgList['title'] = setlist.get_title_object()
                    # Get the list of SSGs for this list
                    oSsgList['ssglist'] = setlist.get_ssg_list()
                    # Add the list object to the list
                    lst_ssglists.append(oSsgList)
            
            # Return this list of lists
            lBack = lst_ssglists

        except:
            msg = oErr.get_error_message()
            oErr.DoError("SetDef/get_ssglists")
        return lBack





