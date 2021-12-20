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
    COLLECTION_SCOPE, SPEC_TYPE, LINK_TYPE, FieldChoice, \
    Profile, EqualGold, Collection, CollectionSuper, Manuscript, SermonDescr, \
    Author, Keyword, SermonGold, EqualGoldLink
from passim.seeker.views import EqualGoldEdit

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

    # [1] And a date: the date of saving this manuscript
    created = models.DateTimeField(default=get_current_datetime)
    saved = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        """Show who proposes what kind of change"""
        sBack = "{}: [{}] on ssg {}".format(
            self.profile.user.name, self.field, self.super.id)
        return sBack

    def json_to_html(self, type):
        """Convert the proposed change from JSON into an HTML representation"""

        html = []
        oErr = ErrHandle()
        try:
            # Get the field's value
            attrvalue = getattr(self, type)
            if attrvalue != None and attrvalue != "":
                oItem = json.loads(attrvalue)
                # Find out what type this is
                field = oItem.get('field')
                if field != None:
                    if field == "author":
                        # Process author FK
                        author_id = oItem.get("id")
                        if author_id != None and author_id != "":
                            author = Author.objects.filter(id=author_id).first()
                            if author != None:
                                authorname = author.name
                                # Add to html
                                html.append(authorname)
                    elif field == "incipit":
                        # Process incipit string
                        incipit = oItem.get("incipit")
                        # Add to html
                        html.append(incipit)
                    elif field == "explicit":
                        # Process explicit string
                        explicit = oItem.get("explicit")
                        # Add to html
                        html.append(explicit)
                    elif field == "keywords":
                        # Process list of FK-to-keyword
                        kwlist = oItem.get('kwlist')
                        if kwlist != None:
                            # Process the list
                            qs = Keyword.objects.filter(id__in=kwlist).values('name')
                            lst_kw = []
                            for kw in qs:
                                # Create a display for this topic
                                lst_kw.append("<span class='keyword'>{}</span>".format(kw['name']))
                            html.append(", ".join(lst_kw))
                    elif field == "hcs":
                        # Process list of FK-to-collection
                        hclist = oItem.get('hclist')
                        if hclist != None:
                            # Process the list
                            qs = Collection.objects.filter(id__in=hclist).values('name')
                            lst_hc = []
                            for hc in qs:
                                # Create a display for this topic
                                lst_hc.append("<span class='collection'>{}</span>".format(hc['name']))
                            html.append(", ".join(lst_hc))
                    elif field == "golds":
                        # Process list of FK-to-SermonGold
                        goldlist = oItem.get('goldlist')
                        if goldlist != None:
                            # Process the list
                            html.append(EqualGoldEdit.get_goldset_html(goldlist))
                    elif field == "supers":
                        # Process list of EqualGoldLink specifications
                        linklist = oItem.get('linklist')
                        if linklist != None:
                            # TODO: Process the list
                            lst_super = []
                            number = 0
                            for superlink in linklist:
                                lst_super.append("<tr class='view-row'>")
                                sSpectype = ""
                                sAlternatives = ""
                                number += 1

                                # Get the values from [superlink]
                                linktype = superlink.get("linktype")
                                spectype = superlink.get("spectype")
                                alternatives = superlink.get("alternatives")
                                note = superlink.get("note")
                                dst_id = superlink.get("dst")
                                dst = SermonGold.objects.filter(id=dst_id).first()

                                if spectype != None and len(spectype) > 1:
                                    # Show the specification type
                                    sSpectype = "<span class='badge signature gr'>{}</span>".format(
                                        FieldChoice.get_english(SPEC_TYPE, spectype))
                                if alternatives != None and alternatives == "true":
                                    sAlternatives = "<span class='badge signature cl' title='Alternatives'>A</span>"
                                lst_super.append("<td valign='top' class='tdnowrap'><span class='badge signature ot'>{}</span>{}</td>".format(
                                    FieldChoice.get_english(LINK_TYPE, linktype), sSpectype))

                                sTitle = ""
                                sNoteShow = ""
                                sNoteDiv = ""
                                if note != None and len(note) > 1:
                                    sTitle = "title='{}'".format(note)
                                    sNoteShow = "<span class='badge signature btn-warning' title='Notes' data-toggle='collapse' data-target='#ssgnote_{}'>N</span>".format(
                                        number)
                                    sNoteDiv = "<div id='ssgnote_{}' class='collapse explanation'>{}</div>".format(
                                        number, note)
                                url = reverse('equalgold_details', kwargs={'pk': dst_id})
                                lst_super.append("<td valign='top'><a href='{}' {}>{}</a>{}{}{}</td>".format(
                                    url, sTitle, dst.get_view(), sAlternatives, sNoteShow, sNoteDiv))
                                lst_super.append("</tr>")
                            if len(lst_super) > 0:
                                sBack = "<table><tbody>{}</tbody></table>".format( "".join(lst_super))
            else:
                html.append("empty")
        except:
            msg = oErr.get_error_message()
            oErr.DoError("Proposal/json_to_html")

        # Return the HTML as a string
        sBack = "\n".join(html)
        return sBack

    def change_html(self):
        """Convert the proposed change from JSON into an HTML representation"""

        # Return the HTML as a string
        sBack = self.json_to_html("change")
        return sBack

    def current_html(self):
        """Convert the current field JSON value into an HTML representation"""

        # Return the HTML as a string
        sBack = self.json_to_html("current")
        return sBack

