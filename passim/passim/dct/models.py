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
from passim.seeker.models import get_current_datetime, build_abbr_list, \
    Collection, Manuscript, Profile

STANDARD_LENGTH=255
ABBR_LENGTH = 5

SETLIST_TYPE = "dct.setlisttype"


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

    def get_title_object(self):
        """Depending on the setlisttype, this provides the title of the setlist
        
        The title is stored in an object, to facilitate template rendering
        """

        oBack = {"main": ""}
        if self.setlisttype == "manu":
            # This is a manuscript
            oBack = self.manuscript.get_full_name_html(field1="top", field2="middle", field3="main")
        elif self.setlisttype == "hist":
            # Historical collection
            pass
        elif self.setlisttype == "pers":
            # Personal collection
            pass
        elif self.setlisttype == "publ":
            # Public collection
            pass
        else:
            # No idea what this is
            oBack['main'] = self.setlisttype
        # Return the result
        return oBack


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

    # [1] A list of all the DCT parameter-objects defined for this research set
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
            #default_name = "{}_DCT_000".format(
            #    username)
            obj = SetDef.objects.create(researchset=rset)
            # Save once more
            obj.save()
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




