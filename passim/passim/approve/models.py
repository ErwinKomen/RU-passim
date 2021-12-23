"""Models for the APPROVE app: approval by editors of a SSG modification or creation

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
from passim.seeker.models import get_current_datetime, get_crpp_date, build_abbr_list, \
    APPROVAL_TYPE, \
    EqualGold, Profile

STANDARD_LENGTH=255
LONG_STRING=255
ABBR_LENGTH = 5

class EqualChange(models.Model):
    """A proposal to change the value of one field within one SSG"""

    # [1] obligatory link to the SSG
    super = models.ForeignKey(EqualGold, on_delete=models.CASCADE, related_name="superproposals")
    # [1] a proposal belongs to a particular user's profilee
    profile = models.ForeignKey(Profile, on_delete=models.CASCADE, related_name="profileproposals")
    # [1] The name of the field for which a change is being suggested
    field = models.CharField("Field name", max_length=LONG_STRING)
    # [0-1] The current field's value (which may be none, if a new SSG is suggested)
    current = models.TextField("Current value", null=True, blank=True)
    # [0-1] The proposed value for the field as a stringified JSON
    change = models.TextField("Proposed value", default="{}")

    # [1] The approval status of this proposed change
    atype = models.CharField("Approval", choices=build_abbr_list(APPROVAL_TYPE), max_length=5, default="def")

    # [1] And a date: the date of saving this manuscript
    created = models.DateTimeField(default=get_current_datetime)
    saved = models.DateTimeField(null=True, blank=True)

    # Fields for which changes need to be monitored
    approve_fields = [
        {'field': 'author',             'tofld': 'author',   'type': 'fk'},
        {'field': 'incipit',            'tofld': 'incipit',  'type': 'string'},
        {'field': 'explicit',           'tofld': 'explicit', 'type': 'string'},
        {'field': 'keywords',           'tofld': 'keywords', 'type': 'm2m-inline',  'listfield': 'kwlist'},
        #{'field': 'projects',           'tofld': 'projects', 'type': 'm2m-inline',  'listfield': 'projlist'},
        {'field': 'collections',        'tofld': 'hcs',      'type': 'm2m-inline',  'listfield': 'collist_hist',
         'lstQ': [Q(settype="hc") & (Q(scope='publ') | Q(scope='team'))] },
        {'field': 'equal_goldsermons',  'tofld': 'golds',    'type': 'm2o',         'listfield': 'goldlist'},
        {'field': 'equalgold_src',      'tofld': 'supers',   'type': 'm2m-addable', 'listfield': 'superlist',
         'prefix': 'ssglink', 'formfields': [
             {'field': 'linktype',      'type': 'string'},
             {'field': 'spectype',      'type': 'string'},
             {'field': 'note',          'type': 'string'},
             {'field': 'alternatives',  'type': 'string'},
             {'field': 'dst',           'type': 'fk'},
             ]},
        ]

    def __str__(self):
        """Show who proposes what kind of change"""
        sBack = "{}: [{}] on ssg {}".format(
            self.profile.user.name, self.field, self.super.id)
        return sBack

    def add_item(super, profile, field, oChange, oCurrent=None):
        """Add one item"""

        oErr = ErrHandle()
        obj = None
        try:
            # Make sure to stringify, sorting the keys
            change = json.dumps(oChange, sort_keys=True)
            if oCurrent is None:
                current = None
            else:
                current = json.dumps(oCurrent, sort_keys=True)

            obj = EqualChange.objects.filter(super=super, profile=profile, field=field, current=current, change=change).first()
            if obj == None:
                obj = EqualChange.objects.create(super=super, profile=profile, field=field, current=current, change=change)
        except:
            msg = oErr.get_error_message()
            oErr.DoError("EqualChange/add_item")
        return obj





