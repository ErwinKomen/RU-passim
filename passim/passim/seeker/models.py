"""Models for the SEEKER app.

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
from passim.utils import *
from passim.settings import APP_PREFIX, WRITABLE_DIR, TIME_ZONE
from passim.seeker.excel import excel_to_list
from passim.bible.models import Reference, Book, BKCHVS_LENGTH
import sys, os, io, re
import copy
import json
import time
import fnmatch
import csv
import math
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from difflib import SequenceMatcher
from io import StringIO
from pyzotero import zotero

# import xml.etree.ElementTree as ET
# from lxml import etree as ET
# import xmltodict
from xml.dom import minidom

STANDARD_LENGTH=100
LONG_STRING=255
MAX_TEXT_LEN = 200
ABBR_LENGTH = 5
PASSIM_CODE_LENGTH = 20
VISIT_MAX = 1400
VISIT_REDUCE = 1000

COLLECTION_SCOPE = "seeker.colscope"
COLLECTION_TYPE = "seeker.coltype" 
SET_TYPE = "seeker.settype"
EDI_TYPE = "seeker.editype"
LIBRARY_TYPE = "seeker.libtype"
LINK_TYPE = "seeker.linktype"
SPEC_TYPE = "seeker.spectype"
REPORT_TYPE = "seeker.reptype"
STATUS_TYPE = "seeker.stype"
MANIFESTATION_TYPE = "seeker.mtype"
MANUSCRIPT_TYPE = "seeker.mtype"
CERTAINTY_TYPE = "seeker.autype"
PROFILE_TYPE = "seeker.profile"     # THese are user statuses
VIEW_STATUS = "view.status"
YESNO_TYPE = "seeker.yesno"
VISIBILITY_TYPE = "seeker.visibility"

LINK_EQUAL = 'eqs'
LINK_PARTIAL = 'prt'
LINK_NEAR = 'neq'
LINK_ECHO = 'ech'
LINK_SIM = "sim"
LINK_UNSPECIFIED = "uns"
LINK_PRT = [LINK_PARTIAL, LINK_NEAR]
LINK_BIDIR = [LINK_PARTIAL, LINK_NEAR, LINK_ECHO, LINK_SIM]
LINK_SPEC_A = ['usd', 'usi', 'com', 'uns', 'udd', 'udi']
LINK_SPEC_B = ['udd', 'udi', 'com', 'uns', 'usd', 'usi']

# Author certainty levels
CERTAIN_LOWEST = 'vun'  # very uncertain
CERTAIN_LOW = 'unc'     # uncertain
CERTAIN_AVE = 'ave'     # average
CERTAIN_HIGH = 'rea'    # reasonably certain
CERTAIN_HIGHEST = 'vce' # very certain

STYPE_IMPORTED = 'imp'
STYPE_MANUAL = 'man'
STYPE_EDITED = 'edi'
STYPE_APPROVED = 'app'
traffic_red = ['-', STYPE_IMPORTED]
traffic_orange = [STYPE_MANUAL, STYPE_EDITED]
traffic_green = [STYPE_APPROVED]
traffic_light = '<span title="{}"><span class="glyphicon glyphicon-record" style="color: {};"></span>' + \
                                 '<span class="glyphicon glyphicon-record" style="color: {};"></span>' + \
                                 '<span class="glyphicon glyphicon-record" style="color: {};"></span>' + \
                '</span>'

class FieldChoice(models.Model):

    field = models.CharField(max_length=50)
    english_name = models.CharField(max_length=100)
    dutch_name = models.CharField(max_length=100)
    abbr = models.CharField(max_length=20, default='-')
    machine_value = models.IntegerField(help_text="The actual numeric value stored in the database. Created automatically.")

    def __str__(self):
        return "{}: {}, {} ({})".format(
            self.field, self.english_name, self.dutch_name, str(self.machine_value))

    class Meta:
        ordering = ['field','machine_value']
        

class HelpChoice(models.Model):
    """Define the URL to link to for the help-text"""
    
    # [1] The 'path' to and including the actual field
    field = models.CharField(max_length=200)        
    # [1] Whether this field is searchable or not
    searchable = models.BooleanField(default=False) 
    # [1] Name between the <a></a> tags
    display_name = models.CharField(max_length=50)  
    # [0-1] The actual help url (if any)
    help_url = models.URLField("Link to more help", blank=True, null=True, default='')         
    # [0-1] One-line contextual help
    help_html = models.TextField("One-line help", blank=True, null=True)

    def __str__(self):
        return "[{}]: {}".format(
            self.field, self.display_name)

    def get_text(self):
        help_text = ''
        # is anything available??
        if self.help_url != None and self.help_url != '':
            if self.help_url[:4] == 'http':
                help_text = "See: <a href='{}'>{}</a>".format(
                    self.help_url, self.display_name)
            else:
                help_text = "{} ({})".format(
                    self.display_name, self.help_url)
        elif self.help_html != None and self.help_html != "":
            help_text = self.help_html
        return help_text

    def get_help_markdown(sField):
        """Get help based on the field name """

        oErr = ErrHandle()
        sBack = ""
        try:
            obj = HelpChoice.objects.filter(field__iexact=sField).first()
            if obj != None:
                sBack = obj.get_text()
                # Convert markdown to html
                sBack = markdown(sBack)
        except:
            msg = oErr.get_error_message()
            oErr.DoError("get_help")
        return sBack


def get_reverse_spec(sSpec):
    """Given a SPECTYPE, provide the reverse one"""

    sReverse = sSpec
    for idx, spectype in enumerate(LINK_SPEC_A):
        if spectype == sSpec:
            sReverse = LINK_SPEC_B[idx]
            break
    return sReverse

def get_current_datetime():
    """Get the current time"""
    return timezone.now()

def get_default_loctype():
    """Get a default value for the loctype"""

    obj = LocationType.objects.filter(name="city").first()
    if obj == None:
        value = 0
    else:
        value = obj.id
    return value

def adapt_search(val, do_brackets = True):
    if val == None: return None
    # First trim
    val = val.strip()
    if do_brackets:
        arPart = val.split("[")
        for idx, part in enumerate(arPart):
            arPart[idx] = part.replace("]", "[]]")
        val = "[[]".join(arPart)
    if "#" in val:
        val = r'(^|(.*\b))' + val.replace('#', r'((\b.*)|$)')
    else:
        val = '^' + fnmatch.translate(val) + '$'
    return val

def adapt_brackets(val):
    """Change square brackets for better searching"""
    if val == None: return None
    # First trim
    val = val.strip()
    arPart = val.split("[")
    for part in arPart:
        part = part.replace("]", "[]]")
    val = "[[]".join(arPart)
    return val

def adapt_latin(val):
    """Change the three dots into a unicode character"""

    val = val.replace('...', u'\u2026')
    return val

def adapt_markdown(val, lowercase=True):
    sBack = ""
    if val != None:
        val = val.replace("***", "\*\*\*")
        sBack = mark_safe(markdown(val, safe_mode='escape'))
        sBack = sBack.replace("<p>", "")
        sBack = sBack.replace("</p>", "")
        if lowercase:
            sBack = sBack.lower()
    return sBack

def is_number(s_input):
    """Check if s_input is a number consisting only of digits, possibly enclosed in brackets"""
    return re.match(r'^[[]?(\d+)[]]?', s_input)

def get_linktype_abbr(sLinkType):
    """Convert a linktype into a valid abbreviation"""

    options = [{'abbr': LINK_EQUAL, 'input': 'equals' },
               {'abbr': 'prt', 'input': 'partially equals' },
               {'abbr': 'prt', 'input': 'partialy equals' },
               {'abbr': 'sim', 'input': 'similar_to' },
               {'abbr': 'sim', 'input': 'similar' },
               {'abbr': 'sim', 'input': 'similar to' },
               {'abbr': 'neq', 'input': 'nearly equals' },
               {'abbr': 'use', 'input': 'uses' },
               {'abbr': 'use', 'input': 'makes_use_of' },
               ]
    for opt in options:
        if sLinkType == opt['abbr']:
            return sLinkType
        elif sLinkType == opt['input']:
            return opt['abbr']
    # Return default
    return LINK_EQUAL

def get_help(field):
    """Create the 'help_text' for this element"""

    # find the correct instance in the database
    help_text = ""
    try:
        entry_list = HelpChoice.objects.filter(field__iexact=field)
        entry = entry_list[0]
        # Note: only take the first actual instance!!
        help_text = entry.get_text()
    except:
        help_text = "Sorry, no help available for " + field

    return help_text

def get_helptext(name):
    sBack = ""
    if name != "":
        sBack = HelpChoice.get_help_markdown(name)
    return sBack

def get_crpp_date(dtThis, readable=False):
    """Convert datetime to string"""

    if readable:
        # Convert the computer-stored timezone...
        dtThis = dtThis.astimezone(pytz.timezone(TIME_ZONE))
        # Model: yyyy-MM-dd'T'HH:mm:ss
        sDate = dtThis.strftime("%d/%B/%Y (%H:%M)")
    else:
        # Model: yyyy-MM-dd'T'HH:mm:ss
        sDate = dtThis.strftime("%Y-%m-%dT%H:%M:%S")
    return sDate

def get_now_time():
    """Get the current time"""
    return time.clock()

def get_json_list(value):
    oBack = []
    if value != None and value != "":
        if value[0] == '[' and value[-1] == ']':
            oBack = json.loads(value)
        else:
            oBack = [ value ]
    return oBack

def obj_text(d):
    stack = list(d.items())
    lBack = []
    while stack:
        k, v = stack.pop()
        if isinstance(v, dict):
            stack.extend(v.iteritems())
        else:
            # Note: the key is [k]
            lBack.append(v)
    return ", ".join(lBack)

def obj_value(d):
    def NestedDictValues(d):
        for k, v in d.items():
            # Treat attributes differently
            if k[:1] == "@":
                yield "{}={}".format(k,v)
            elif isinstance(v, dict):
                yield from NestedDictValues(v)
            else:
                yield v
    a = list(NestedDictValues(d))
    return ", ".join(a)

def getText(nodeStart):
    # Iterate all Nodes aggregate TEXT_NODE
    rc = []
    for node in nodeStart.childNodes:
        if node.nodeType == node.TEXT_NODE:
            sText = node.data.strip(' \t\n')
            if sText != "":
                rc.append(sText)
        else:
            # Recursive
            rc.append(getText(node))
    return ' '.join(rc)

def get_searchable(sText):
    sRemove = r"/\<|\>|\_|\,|\.|\:|\;|\?|\!|\(|\)|\[|\]/"

    # Validate
    if sText == None:
        sText = ""
    else:

        # Move to lower case
        sText = sText.lower()

        # Remove punctuation with nothing
        sText = re.sub(sRemove, "", sText)
        #sText = sText.replace("<", "")
        #sText = sText.replace(">", "")
        #sText = sText.replace("_", "")

        # Make sure to TRIM the text
        sText = sText.strip()
    return sText

def get_stype_light(stype, usercomment=False, count=-1):
    """HTML visualization of the different STYPE statuses"""

    sBack = ""
    if stype == "": stype = "-"
    red = "gray"
    orange = "gray"
    green = "gray"
    # Determine what the light is going to be
    
    if stype in traffic_orange:
        orange = "orange"
        htext = "This item has been edited and needs final approval"
    elif stype in traffic_green:
        green = "green"
        htext = "This item has been completely revised and approved"
    elif stype in traffic_red:
        red = "red"
        htext = "This item has been automatically received and needs editing and approval"

    # We have the color of the light: visualize it
    # sBack = "<span class=\"glyphicon glyphicon-record\" title=\"{}\" style=\"color: {};\"></span>".format(htext, light)
    sBack = traffic_light.format(htext, red, orange, green)

    if usercomment:
        # Add modal button to comment
        html = []
        count_code = ""
        if count > 0:
            # Add an indication of the number of comments
            count_code = "<span style='color: red;'> {}</span>".format(count)
        html.append(sBack)
        html.append("<span style='margin-left: 100px;'><a class='view-mode btn btn-xs jumbo-1' data-toggle='modal'")
        html.append("   data-target='#modal-comment'>")
        html.append("   <span class='glyphicon glyphicon-envelope' title='Add a user comment'></span>{}</a></span>".format(count_code))
        sBack = "\n".join(html)

    # Return what we made
    return sBack

def get_overlap(sBack, sMatch):
    # Yes, we are matching!!
    s = SequenceMatcher(lambda x: x == " ", sBack, sMatch)
    pos = 0
    html = []
    ratio = 0.0
    for block in s.get_matching_blocks():
        pos_a = block[0]
        size = block[2]
        if size > 0:
            # Add plain previous part (if it is there)
            if pos_a > pos:
                html.append(sBack[pos : pos_a - 1])
            # Add the overlapping part of the string
            html.append("<span class='overlap'>{}</span>".format(sBack[pos_a : pos_a + size]))
            # Adapt position
            pos = pos_a + size
    ratio = s.ratio()
    # THe last plain part (if any)
    if pos < len(sBack) - 1:
        html.append(sBack[pos : len(sBack) - 1 ])
    # Calculate the sBack
    sBack = "".join(html)
    return sBack, ratio

def similar(a, b):
    if a == None or a=="":
        if b == None or b == "":
            response = 1
        else:
            response = 0.00001
    else:
        response = SequenceMatcher(None, a, b).ratio()
    return response

def build_choice_list(field, position=None, subcat=None, maybe_empty=False):
    """Create a list of choice-tuples"""

    choice_list = [];
    unique_list = [];   # Check for uniqueness

    try:
        # check if there are any options at all
        if FieldChoice.objects == None:
            # Take a default list
            choice_list = [('0','-'),('1','N/A')]
            unique_list = [('0','-'),('1','N/A')]
        else:
            if maybe_empty:
                choice_list = [('0','-')]
            for choice in FieldChoice.objects.filter(field__iexact=field):
                # Default
                sEngName = ""
                # Any special position??
                if position==None:
                    sEngName = choice.english_name
                elif position=='before':
                    # We only need to take into account anything before a ":" sign
                    sEngName = choice.english_name.split(':',1)[0]
                elif position=='after':
                    if subcat!=None:
                        arName = choice.english_name.partition(':')
                        if len(arName)>1 and arName[0]==subcat:
                            sEngName = arName[2]

                # Sanity check
                if sEngName != "" and not sEngName in unique_list:
                    # Add it to the REAL list
                    choice_list.append((str(choice.machine_value),sEngName));
                    # Add it to the list that checks for uniqueness
                    unique_list.append(sEngName)

            choice_list = sorted(choice_list,key=lambda x: x[1]);
    except:
        print("Unexpected error:", sys.exc_info()[0])
        choice_list = [('0','-'),('1','N/A')];

    # Signbank returns: [('0','-'),('1','N/A')] + choice_list
    # We do not use defaults
    return choice_list;

def build_abbr_list(field, position=None, subcat=None, maybe_empty=False, exclude=None):
    """Create a list of choice-tuples"""

    choice_list = [];
    unique_list = [];   # Check for uniqueness

    try:
        if exclude ==None:
            exclude = []
        # check if there are any options at all
        if FieldChoice.objects == None:
            # Take a default list
            choice_list = [('0','-'),('1','N/A')]
            unique_list = [('0','-'),('1','N/A')]
        else:
            if maybe_empty:
                choice_list = [('0','-')]
            for choice in FieldChoice.objects.filter(field__iexact=field):
                # Default
                sEngName = ""
                # Any special position??
                if position==None:
                    sEngName = choice.english_name
                elif position=='before':
                    # We only need to take into account anything before a ":" sign
                    sEngName = choice.english_name.split(':',1)[0]
                elif position=='after':
                    if subcat!=None:
                        arName = choice.english_name.partition(':')
                        if len(arName)>1 and arName[0]==subcat:
                            sEngName = arName[2]

                # Sanity check
                if sEngName != "" and not sEngName in unique_list and not (str(choice.abbr) in exclude):
                    # Add it to the REAL list
                    choice_list.append((str(choice.abbr),sEngName));
                    # Add it to the list that checks for uniqueness
                    unique_list.append(sEngName)

            choice_list = sorted(choice_list,key=lambda x: x[1]);
    except:
        print("Unexpected error:", sys.exc_info()[0])
        choice_list = [('0','-'),('1','N/A')];

    # Signbank returns: [('0','-'),('1','N/A')] + choice_list
    # We do not use defaults
    return choice_list;

def choice_english(field, num):
    """Get the english name of the field with the indicated machine_number"""

    try:
        result_list = FieldChoice.objects.filter(field__iexact=field).filter(machine_value=num)
        if (result_list == None):
            return "(No results for "+field+" with number="+num
        return result_list[0].english_name
    except:
        return "(empty)"

def choice_value(field, term):
    """Get the numerical value of the field with the indicated English name"""

    try:
        result_list = FieldChoice.objects.filter(field__iexact=field).filter(english_name__iexact=term)
        if result_list == None or result_list.count() == 0:
            # Try looking at abbreviation
            result_list = FieldChoice.objects.filter(field__iexact=field).filter(abbr__iexact=term)
        if result_list == None:
            return -1
        else:
            return result_list[0].machine_value
    except:
        return -1

def choice_abbreviation(field, num):
    """Get the abbreviation of the field with the indicated machine_number"""

    try:
        result_list = FieldChoice.objects.filter(field__iexact=field).filter(machine_value=num)
        if (result_list == None):
            return "{}_{}".format(field, num)
        return result_list[0].abbr
    except:
        return "-"

def process_lib_entries(oStatus):
    """Read library information from a JSON file"""

    oBack = {}
    JSON_ENTRIES = "passim_entries.json"

    try:
        oStatus.set("preparing")
        fName = os.path.abspath(os.path.join(WRITABLE_DIR, JSON_ENTRIES))
        
        oResult = Library.read_json(oStatus, fName)

        # We are done!
        oStatus.set("done", oBack)

        # return positively
        oBack['result'] = True
        return oBack
    except:
        # oCsvImport['status'] = 'error'
        oStatus.set("error")
        errHandle.DoError("process_lib_entries", True)
        return oBack

def import_data_file(sContents, arErr):
    """Turn the contents of [data_file] into a json object"""

    try:
        # Validate
        if sContents == "":
            return {}
        # Adapt the contents into an object array
        lines = []
        for line in sContents:
            lines.append(line.decode("utf-8").strip())
        # Combine again
        sContents = "\n".join(lines)
        oData = json.loads(sContents)
        # This is the data
        return oData
    except:
        sMsg = errHandle.get_error_message()
        arErr.DoError("import_data_file error:")
        return {}

def add_gold2equal(src, dst_eq, eq_log = None):
    """Add a gold sermon to an equality set"""

    # Initialisations
    lst_add = []
    lst_total = []
    added = 0
    oErr = ErrHandle()

    try:

        # Main body of add_gold2gold()
        lst_total = []
        lst_total.append("<table><thead><tr><th>item</th><th>src</th><th>dst</th><th>linktype</th><th>addtype</th></tr>")
        lst_total.append("<tbody>")

        # Does this link already exist?
        if src.equal != dst_eq:
            # It's different groups, so we need to make changes
            prt_added = 0

            if eq_log != None:
                eq_log.append("gold2equal 0: add gold {} (eqg={}) to equal group {}".format(src.id, src.equal.id, dst_eq.id))

            # (1) save the source group
            grp_src = src.equal
            grp_dst = dst_eq

            # (2) Change (!) the eq-to-eq links from src to dst
            link_remove = []
            with transaction.atomic():
                qs = EqualGoldLink.objects.filter(src=grp_src)
                for link in qs:
                    # Does this changed link exist already?
                    obj = EqualGoldLink.objects.filter(src=grp_dst, dst=link.dst, linktype=link.linktype).first()
                    if obj == None:
                        # Log activity
                        if eq_log != None:
                            eq_log.append("gold2equal 1: change equalgoldlink id={} source {} into {} (dst={})".format(link.id, link.src.id, grp_dst.id, link.dst.id))
                        # Perform the change
                        link.src = grp_dst
                        link.save()
                        prt_added += 1
                    else:
                        # Add this link to those that need be removed
                        link_remove.append(link.id)
                        # Log activity
                        if eq_log != None:
                            eq_log.append("gold2equal 2: remove equalgoldlink id={}".format(link.id))
                # Reverse links
                qs_rev = EqualGoldLink.objects.filter(dst=grp_src)
                for link in qs_rev:
                    # Does this changed link exist already?
                    obj = EqualGoldLink.objects.filter(src=link.src, dst=grp_src, linktype=link.linktype).first()
                    if obj == None:
                        # Log activity
                        if eq_log != None:
                            eq_log.append("gold2equal 3: change equalgoldlink id={} dst {} into {} (src={})".format(link.id, link.dst.id, grp_src.id, link.src.id))
                        # Perform the change
                        link.dst = grp_src
                        link.save()
                        prt_added += 1
                    else:
                        # Add this link to those that need be removed
                        link_remove.append(link.id)
                        # Log activity
                        if eq_log != None:
                            eq_log.append("gold2equal 4: remove equalgoldlink id={}".format(link.id))
            # (3) remove superfluous links
            EqualGoldLink.objects.filter(id__in=link_remove).delete()

            # (4) Change the gold-sermons in the source group
            with transaction.atomic():
                for gold in grp_src.equal_goldsermons.all():
                    # Log activity
                    if eq_log != None:
                        eq_log.append("gold2equal 5: change gold {} equal group from {} into {}".format(gold.id, gold.equal.id, grp_dst.id))
                    # Perform the action
                    gold.equal = grp_dst
                    gold.save()

            # (5) Remove the source group
            if eq_log != None: eq_log.append("gold2equal 6: remove group {}".format(grp_src.id))
            grp_src.delete()
            # x = eq_log[1216]

            # (6) Bookkeeping
            added += prt_added

        # Finish the report list
        lst_total.append("</tbody></table>")
    except:
        msg = oErr.get_error_message()
        oErr.DoError("add_gold2equal")

    # Return the number of added relations
    return added, lst_total

def add_gold2gold(src, dst, ltype, eq_log = None):
    """Add a gold-to-gold relation from src to dst of type ltype"""

    # Initialisations
    lst_add = []
    lst_total = []
    added = 0
    oErr = ErrHandle()

    def spread_partial(group):
        """Make sure all members of the equality group have the same partial relations"""

        lst_back = []
        added = 0
        for linktype in LINK_PRT:
            lst_prt_add = []    # List of partially equals relations to be added
            qs_prt = SermonGoldSame.objects.filter(linktype=linktype).order_by('src__id')

            # Get a list of existing 'partially equals' destination links from the current group
            qs_grp_prt = qs_prt.filter(Q(src__in=group))
            if len(qs_grp_prt) > 0:
                # Make a list of unique destination gold objects
                lst_dst = []
                for obj in qs_grp_prt:
                    dst = obj.dst
                    if dst not in lst_dst: lst_dst.append(dst)
                # Make a list of relations that need to be added
                for src in group:
                    for dst in lst_dst:
                        # Make sure relations are not equal
                        if src.id != dst.id:
                            # Check if the relation already is there
                            obj = qs_prt.filter(src=src, dst=dst).first()
                            if obj == None:
                                oAdd = {'src': src, 'dst': dst}
                                if oAdd not in lst_prt_add:
                                    lst_prt_add.append(oAdd)
                            # Check if the reverse relation is already there
                            obj = qs_prt.filter(src=dst, dst=src).first()
                            if obj == None:
                                oAdd = {'src': dst, 'dst': src}
                                if oAdd not in lst_prt_add:
                                    lst_prt_add.append(oAdd)
            # Add all the relations in lst_prt_add
            with transaction.atomic():
                for idx, item in enumerate(lst_prt_add):
                    obj = SermonGoldSame(linktype=linktype, src=item['src'], dst=item['dst'])
                    obj.save()
                    added += 1
                    lst_back.append("<tr><td>{}</td><td>{}</td><td>{}</td><td>{}</td><td>{}</td></tr>".format( 
                        (idx+1), item['src'].siglist, item['dst'].siglist, linktype, "add" ))
        # Return the results
        return added, lst_back

    try:

        # Main body of add_gold2gold()
        lst_total = []
        lst_total.append("<table><thead><tr><th>item</th><th>src</th><th>dst</th><th>linktype</th><th>addtype</th></tr>")
        lst_total.append("<tbody>")

        # Action depends on the kind of relationship that is added
        if ltype == LINK_EQUAL:
            eq_added, eq_list = add_gold2equal(src, dst.equal, eq_log)

            for item in eq_list: lst_total.append(item)

            # (6) Bookkeeping
            added += eq_added
        elif src.equal == dst.equal:
            # Trying to add a non-equal link to two gold-sermons that are in the same equality group
            pass
        else:
            # What is added is a partially equals link - between equality groups
            prt_added = 0

            groups = ['to']
            # Implement the REVERSE for link types Partially, Similar, Nearly Equals
            if ltype in LINK_PRT:
                groups.append('back')

            for group in groups:
                # (1) save the source group
                if group == "to":
                    grp_src = src.equal
                    grp_dst = dst.equal
                else:
                    grp_src = dst.equal
                    grp_dst = src.equal

                # (2) Check existing link(s) between the groups
                obj = EqualGoldLink.objects.filter(src=grp_src, dst=grp_dst).first()
                if obj == None:
                    # (3a) there is no link yet: add it
                    obj = EqualGoldLink(src=grp_src, dst=grp_dst, linktype=ltype)
                    obj.save()
                    # Possibly log the action
                    if eq_log != None:
                        eq_log.append("Add equalgoldlink {} from eqg {} to eqg {}".format(ltype, grp_src, grp_dst))
                    # Bookkeeping
                    lst_total.append("<tr><td>{}</td><td>{}</td><td>{}</td><td>{}</td><td>{}</td></tr>".format( 
                        added+1, obj.src.equal_goldsermons.first().siglist, obj.dst.equal_goldsermons.first().siglist, ltype, "add" ))
                    prt_added += 1
                else:
                    # (3b) There is a link, but possibly of a different type
                    obj.linktype = ltype
                    obj.save()


            # (3) Bookkeeping
            added += prt_added
            x = "\n".join( eq_log[-20:])
        # Finish the report list
        lst_total.append("</tbody></table>")
    except:
        msg = oErr.get_error_message()
        oErr.DoError("add_gold2gold")

    # Return the number of added relations
    return added, lst_total

def add_ssg_equal2equal(src, dst_eq, ltype):
    """Add a EqualGold-to-EqualGold relation from src to dst of type ltype"""

    # Initialisations
    lst_add = []
    lst_total = []
    added = 0
    oErr = ErrHandle()

    try:
        # Main body of add_equal2equal()
        lst_total.append("<table><thead><tr><th>item</th><th>src</th><th>dst</th><th>linktype</th><th>addtype</th></tr>")
        lst_total.append("<tbody>")

        # Action depends on the kind of relationship that is added
        if ltype == LINK_EQUAL:
            eq_added, eq_list = add_gold2equal(src, dst_eq)

            for item in eq_list: lst_total.append(item)

            # (6) Bookkeeping
            added += eq_added
        elif src == dst_eq:
            # Trying to add an equal link to two gold-sermons that already are in the same equality group
            pass
        else:
            # What is added is a partially equals link - between equality groups
            prt_added = 0

            # (1) save the source group
            groups = []
            groups.append({'grp_src': src, 'grp_dst': dst_eq})
            groups.append({'grp_src': dst_eq, 'grp_dst': src})
            #grp_src = src.equal
            #grp_dst = dst_eq

            for group in groups:
                grp_src = group['grp_src']
                grp_dst = group['grp_dst']
                # (2) Check existing link(s) between the groups
                obj = EqualGoldLink.objects.filter(src=grp_src, dst=grp_dst).first()
                if obj == None:
                    # (3a) there is no link yet: add it
                    obj = EqualGoldLink(src=grp_src, dst=grp_dst, linktype=ltype)
                    obj.save()
                    # Bookkeeping
                    lst_total.append("<tr><td>{}</td><td>{}</td><td>{}</td><td>{}</td><td>{}</td></tr>".format( 
                        added+1, obj.src.equal_goldsermons.first().siglist, obj.dst.equal_goldsermons.first().siglist, ltype, "add" ))
                    prt_added += 1
                else:
                    # (3b) There is a link, but possibly of a different type
                    obj.linktype = ltype
                    obj.save()

            # (3) Bookkeeping
            added += prt_added

        # Finish the report list
        lst_total.append("</tbody></table>")
    except:
        msg = oErr.get_error_message()
        oErr.DoError("add_ssg_equal2equal")

    # Return the number of added relations
    return added, lst_total

def add_equal2equal(src, dst_eq, ltype):
    """Add a EqualGold-to-EqualGold relation from src to dst of type ltype"""

    # Initialisations
    lst_add = []
    lst_total = []
    added = 0
    oErr = ErrHandle()

    try:
        # Main body of add_equal2equal()
        lst_total.append("<table><thead><tr><th>item</th><th>src</th><th>dst</th><th>linktype</th><th>addtype</th></tr>")
        lst_total.append("<tbody>")

        # Action depends on the kind of relationship that is added
        if ltype == LINK_EQUAL:
            eq_added, eq_list = add_gold2equal(src, dst_eq)

            for item in eq_list: lst_total.append(item)

            # (6) Bookkeeping
            added += eq_added
        elif src.equal == dst_eq:
            # Trying to add an equal link to two gold-sermons that already are in the same equality group
            pass
        else:
            # What is added is a partially equals link - between equality groups
            prt_added = 0

            # (1) save the source group
            groups = []
            groups.append({'grp_src': src.equal, 'grp_dst': dst_eq})
            groups.append({'grp_src': dst_eq, 'grp_dst': src.equal})
            #grp_src = src.equal
            #grp_dst = dst_eq

            for group in groups:
                grp_src = group['grp_src']
                grp_dst = group['grp_dst']
                # (2) Check existing link(s) between the groups
                obj = EqualGoldLink.objects.filter(src=grp_src, dst=grp_dst).first()
                if obj == None:
                    # (3a) there is no link yet: add it
                    obj = EqualGoldLink(src=grp_src, dst=grp_dst, linktype=ltype)
                    obj.save()
                    # Bookkeeping
                    lst_total.append("<tr><td>{}</td><td>{}</td><td>{}</td><td>{}</td><td>{}</td></tr>".format( 
                        added+1, obj.src.equal_goldsermons.first().siglist, obj.dst.equal_goldsermons.first().siglist, ltype, "add" ))
                    prt_added += 1
                else:
                    # (3b) There is a link, but possibly of a different type
                    obj.linktype = ltype
                    obj.save()

            # (3) Bookkeeping
            added += prt_added

        # Finish the report list
        lst_total.append("</tbody></table>")
    except:
        msg = oErr.get_error_message()
        oErr.DoError("add_equal2equal")

    # Return the number of added relations
    return added, lst_total

def add_gold2gold_ORIGINAL(src, dst, ltype):
    """Add a gold-to-gold relation from src to dst of type ltype"""

    # Initialisations
    lst_add = []
    lst_total = []
    added = 0
    oErr = ErrHandle()

    def spread_partial(group):
        """Make sure all members of the equality group have the same partial relations"""

        lst_back = []
        added = 0
        for linktype in LINK_PRT:
            lst_prt_add = []    # List of partially equals relations to be added
            qs_prt = SermonGoldSame.objects.filter(linktype=linktype).order_by('src__id')

            # Get a list of existing 'partially equals' destination links from the current group
            qs_grp_prt = qs_prt.filter(Q(src__in=group))
            if len(qs_grp_prt) > 0:
                # Make a list of unique destination gold objects
                lst_dst = []
                for obj in qs_grp_prt:
                    dst = obj.dst
                    if dst not in lst_dst: lst_dst.append(dst)
                # Make a list of relations that need to be added
                for src in group:
                    for dst in lst_dst:
                        # Make sure relations are not equal
                        if src.id != dst.id:
                            # Check if the relation already is there
                            obj = qs_prt.filter(src=src, dst=dst).first()
                            if obj == None:
                                oAdd = {'src': src, 'dst': dst}
                                if oAdd not in lst_prt_add:
                                    lst_prt_add.append(oAdd)
                            # Check if the reverse relation is already there
                            obj = qs_prt.filter(src=dst, dst=src).first()
                            if obj == None:
                                oAdd = {'src': dst, 'dst': src}
                                if oAdd not in lst_prt_add:
                                    lst_prt_add.append(oAdd)
            # Add all the relations in lst_prt_add
            with transaction.atomic():
                for idx, item in enumerate(lst_prt_add):
                    obj = SermonGoldSame(linktype=linktype, src=item['src'], dst=item['dst'])
                    obj.save()
                    added += 1
                    lst_back.append("<tr><td>{}</td><td>{}</td><td>{}</td><td>{}</td><td>{}</td></tr>".format( 
                        (idx+1), item['src'].siglist, item['dst'].siglist, linktype, "add" ))
        # Return the results
        return added, lst_back

    try:

        # Main body of add_gold2gold()
        lst_total = []
        lst_total.append("<table><thead><tr><th>item</th><th>src</th><th>dst</th><th>linktype</th><th>addtype</th></tr>")
        lst_total.append("<tbody>")

        # Action depends on the kind of relationship that is added
        if ltype == LINK_EQUAL:
            # 1: Get the group of related gold-sermons in which the src resides
            grp_src = [x.dst for x in SermonGoldSame.objects.filter(linktype=LINK_EQUAL, src=src)]
            grp_src.append(src)
            # 2: Get the group of related gold-sermons in which the dst resides
            grp_dst = [x.dst for x in SermonGoldSame.objects.filter(linktype=LINK_EQUAL, src=dst)]
            grp_dst.append(dst)
            # 3: Double check all EQUAL relations that should be there
            lst_add = []
            for inst_src in grp_src:
                for inst_dst in grp_dst:
                    # Make sure they are not equal
                    if inst_src.id != inst_dst.id:
                        obj = SermonGoldSame.objects.filter(linktype=LINK_EQUAL, src=inst_src, dst=inst_dst).first()
                        if obj == None:
                            # Add the relation to the ones that should be added
                            oAdd = {'src': inst_src, 'dst': inst_dst}
                            if oAdd not in lst_add:
                                lst_add.append(oAdd)
                        # Also try and add the reverse relation
                        obj = SermonGoldSame.objects.filter(linktype=LINK_EQUAL, src=inst_dst, dst=inst_src).first()
                        if obj == None:
                            # Add the relation to the ones that should be added
                            oAdd = {'src': inst_dst, 'dst': inst_src}
                            if oAdd not in lst_add:
                                lst_add.append(oAdd)
            # 4: Add those that need adding in one go
            with transaction.atomic():
                for idx, item in enumerate(lst_add):
                    obj = SermonGoldSame(linktype=LINK_EQUAL, src=item['src'], dst=item['dst'])
                    obj.save()
                    lst_total.append("<tr><td>{}</td><td>{}</td><td>{}</td><td>{}</td><td>{}</td></tr>".format( 
                        (idx+1), item['src'].siglist, item['dst'].siglist, LINK_EQUAL, "add" ))
                    added += 1
            # 5: Create a new group, consisting of the two groups
            group = [x for x in grp_src]
            for item in grp_dst: group.append(item)
            # 6: Spread the partial links over the new group
            prt_added, lst_partial = spread_partial(group)
            for item in lst_partial: lst_total.append(item)
            added += prt_added
        else:
            # What is added is a partially equals link

            # 1: Get the group of related gold-sermons in which the src resides
            grp_src = [x.dst for x in SermonGoldSame.objects.filter(linktype=LINK_EQUAL, src=src)]
            grp_src.append(src)
            # 2: Get the group of related gold-sermons in which the dst resides
            grp_dst = [x.dst for x in SermonGoldSame.objects.filter(linktype=LINK_EQUAL, src=dst)]
            grp_dst.append(dst)
            # 3: make linktype-links from all in src to all in dst
            lst_prt_add = []
            for inst_src in grp_src:
                for inst_dst in grp_dst:
                    # Make sure they are not equal
                    if inst_src.id != inst_dst.id:
                        obj = SermonGoldSame.objects.filter(linktype=ltype, src=inst_src, dst=inst_dst).first()
                        if obj == None:
                            # Add the relation to the ones that should be added
                            lst_prt_add.append({'src': inst_src, 'dst': inst_dst})
                        # Check if the reverse relation is already there
                        obj = SermonGoldSame.objects.filter(linktype=ltype, src=inst_dst, dst=inst_src).first()
                        if obj == None:
                            lst_prt_add.append({'src': inst_dst, 'dst': inst_src})
            # 4: Add those that need adding in one go
            with transaction.atomic():
                for idx, item in enumerate(lst_prt_add):
                    obj = SermonGoldSame(linktype=ltype, src=item['src'], dst=item['dst'])
                    obj.save()
                    lst_total.append("<tr><td>{}</td><td>{}</td><td>{}</td><td>{}</td><td>{}</td></tr>".format( 
                        (idx+1), item['src'].siglist, item['dst'].siglist, ltype, "add" ))
                    added += 1
        

        # Finish the report list
        lst_total.append("</tbody></table>")
    except:
        msg = oErr.get_error_message()
        oErr.DoError("add_gold2gold")

    # Return the number of added relations
    return added, lst_total

def moveup(instance, tblGeneral, tblUser, ItemType):
    """Move this keyword into the general keyword-link-table"""
        
    oErr = ErrHandle()
    try:
        # Check if the kw is not in the general table yet
        general = tblGeneral.objects.filter(keyword=self.keyword).first()
        if general == None:
            # Add the keyword
            tblGeneral.objects.create(keyword=self.keyword, equal=self.equal)
        # Remove the *user* specific references to this keyword (for *all*) users
        tblUser.objects.filter(keyword=self.keyword, type=ItemType).delete()
        # Return positively
        bOkay = True
    except:
        sMsg = oErr.get_error_message()
        oErr.DoError("moveup")
        bOkay = False
    return bOkay

def send_email(subject, profile, contents, add_team=False):
    """Send an email"""

    oErr = ErrHandle()
    try:
        # Set the sender
        mail_from = Information.get_kvalue("mail_from")
        mail_to = profile.user.email
        mail_team = None
        if mail_from != "" and mail_to != "":
            # See if the second addressee needs to be added
            if add_team:
                mail_team = Information.get_kvalue("mail_team")

            # Create message container
            msgRoot = MIMEMultipart('related')
            msgRoot['Subject'] = subject
            msgRoot['From'] = mail_from
            msgRoot['To'] = mail_to
            if mail_team != None and mail_team != "":
                msgRoot['Bcc'] = mail_team
            msgHtml = MIMEText(contents, "html", "utf-8")
            # Add the HTML to the root
            msgRoot.attach(msgHtml)
            # Convert into a string
            message = msgRoot.as_string()
            # Try to send this to the indicated email address rom port 25 (SMTP)
            smtpObj = smtplib.SMTP('localhost', 25)
            smtpObj.sendmail(mail_from, mail_to, message)
            smtpObj.quit()
    except:
        msg = oErr.get_error_message()
        oErr.DoError("send_mail")
    return True


# =================== HELPER models ===================================
class Status(models.Model):
    """Intermediate loading of sync information and status of processing it"""

    # [1] Status of the process
    status = models.CharField("Status of synchronization", max_length=50)
    # [1] Counts (as stringified JSON object)
    count = models.TextField("Count details", default="{}")
    # [0-1] Synchronisation type
    type = models.CharField("Type", max_length=255, default="")
    # [0-1] User
    user = models.CharField("User", max_length=255, default="")
    # [0-1] Error message (if any)
    msg = models.TextField("Error message", blank=True, null=True)

    def __str__(self):
        # Refresh the DB connection
        self.refresh_from_db()
        # Only now provide the status
        return self.status

    def set(self, sStatus, oCount = None, msg = None):
        self.status = sStatus
        if oCount != None:
            self.count = json.dumps(oCount)
        if msg != None:
            self.msg = msg
        self.save()


class Action(models.Model):
    """Track actions made by users"""

    # [1] The user
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="user_actions")
    # [1] The item (e.g: Manuscript, SermonDescr, SermonGold = M/S/SG/SSG)
    itemtype = models.CharField("Item type", max_length=MAX_TEXT_LEN)
    # [1] The ID value of the item (M/S/SG/SSG)
    itemid = models.IntegerField("Item id", default=0)
    # [0-1] possibly FK link to M/S/SG/SSG
    linktype = models.CharField("Link type", max_length=MAX_TEXT_LEN, null=True, blank=True)
    # [0-1] The ID value of the FK to M/S/SG/SSG
    linkid = models.IntegerField("Link id", null=True, blank=True)
    # [1] The kind of action performed (e.g: create, edit, delete)
    actiontype = models.CharField("Action type", max_length=MAX_TEXT_LEN)
    # [0-1] Room for possible action-specific details
    details = models.TextField("Detail", blank=True, null=True)
    # [1] Date and time of this action
    when = models.DateTimeField(default=get_current_datetime)

    def __str__(self):
        action = "{}|{}".format(self.user.username, self.when)
        return action

    def add(user, itemtype, itemid, actiontype, details=None):
        """Add an action"""

        # Check if we are getting a string user name or not
        if isinstance(user, str):
            # Get the user object
            oUser = User.objects.filter(username=user).first()
        else:
            oUser = user
        # If there are details, make sure they are stringified
        if details != None and not isinstance(details, str):
            details = json.dumps(details)
        # Create the correct action
        action = Action(user=oUser, itemtype=itemtype, itemid=itemid, actiontype=actiontype)
        if details != None: action.details = details
        action.save()
        return action

    def get_object(self):
        """Get an object representation of this particular Action item"""

        actiontype = self.actiontype
        model = ""
        oDetails = None
        changes = {}
        if actiontype == "save" or actiontype == "add" or actiontype == "new":
            oDetails = json.loads(self.details)
            actiontype = oDetails.get('savetype', '')
            changes = oDetails.get('changes', {})
            model = oDetails.get('model', None)

        when = self.when.strftime("%d/%B/%Y %H:%M:%S")
        oBack = dict(
            actiontype = actiontype,
            itemtype = self.itemtype,
            itemid = self.itemid,
            model = model,
            username = self.user.username,
            when = when,
            changes = changes
            )
        return oBack

    def get_history(itemtype, itemid):
        """Get a list of <Action> items"""

        lHistory = []
        # Get the history for this object
        qs = Action.objects.filter(itemtype=itemtype, itemid=itemid).order_by('-when')
        for item in qs:
            bAdd = True
            oChanges = item.get_object()
            if oChanges['actiontype'] == "change":
                if 'changes' not in oChanges or len(oChanges['changes']) == 0: 
                    bAdd = False
            if bAdd: lHistory.append(item.get_object())
        return lHistory


class Report(models.Model):
    """Report of an upload action or something like that"""

    # [1] Every report must be connected to a user and a date (when a user is deleted, the Report is deleted too)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="user_reports")
    # [1] And a date: the date of saving this report
    created = models.DateTimeField(default=get_current_datetime)
    # [1] A report should have a type to know what we are reporting about
    reptype = models.CharField("Report type", choices=build_abbr_list(REPORT_TYPE), 
                            max_length=5)
    # [0-1] A report should have some contents: stringified JSON
    contents = models.TextField("Contents", default="{}")

    def __str__(self):
        sType = self.reptype
        sDate = get_crpp_date(self.created)
        return "{}: {}".format(sType, sDate)

    def make(username, rtype, contents):
        """Create a report"""

        oErr = ErrHandle()
        obj = None
        try:
            # Retrieve the user
            user = User.objects.filter(username=username).first()
            obj = Report(user=user, reptype=rtype, contents=contents)
            obj.save()
        except:
            msg = oErr.get_error_message()
            oErr.DoError("Report.make")
        # Return the object
        return obj

    def get_created(self):
        sBack = self.created.strftime("%d/%b/%Y %H:%M")
        return sBack


class Information(models.Model):
    """Specific information that needs to be kept in the database"""

    # [1] The key under which this piece of information resides
    name = models.CharField("Key name", max_length=255)
    # [0-1] The value for this piece of information
    kvalue = models.TextField("Key value", default = "", null=True, blank=True)

    class Meta:
        verbose_name_plural = "Information Items"

    def __str__(self):
        return self.name

    def get_kvalue(name):
        info = Information.objects.filter(name=name).first()
        if info == None:
            return ''
        else:
            return info.kvalue

    def set_kvalue(name, value):
        info = Information.objects.filter(name=name).first()
        if info == None:
            info = Information(name=name)
            info.save()
        info.kvalue = value
        info.save()
        return True

    def save(self, force_insert = False, force_update = False, using = None, update_fields = None):
        return super(Information, self).save(force_insert, force_update, using, update_fields)


class Profile(models.Model):
    """Information about the user"""

    # [1] Every profile is linked to a user
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="user_profiles")
    # [1] Every user has a profile-status
    ptype = models.CharField("Profile status", choices=build_abbr_list(PROFILE_TYPE), max_length=5, default="unk")
    # [1] Every user has a stack: a list of visit objects
    stack = models.TextField("Stack", default = "[]")

    # [1] Stringified JSON lists for M/S/SG/SSG search results, to facilitate basket operations
    search_manu = models.TextField("Search results Manu", default = "[]")
    search_sermo = models.TextField("Search results Sermo", default = "[]")
    search_gold = models.TextField("Search results Gold", default = "[]")
    search_super = models.TextField("Search results Super", default = "[]")

    # [0-1] Affiliation of this user with as many details as needed
    affiliation = models.TextField("Affiliation", blank=True, null=True)

    # [1] Each of the four basket types has a history
    historysermo = models.TextField("Sermon history", default="[]")
    historymanu = models.TextField("Manuscript history", default="[]")
    historygold = models.TextField("Sermon Gold history", default="[]")
    historysuper = models.TextField("Super sermon Gold history", default="[]")

    # [1] Current size of the user's basket
    basketsize = models.IntegerField("Basket size", default=0)

    # [1] Current size of the user's basket (manuscripts)
    basketsize_manu = models.IntegerField("Basket size manuscripts", default=0)

    # [1] Current size of the user's basket (sermons gold)
    basketsize_gold = models.IntegerField("Basket size sermons gold", default=0)

    # [1] Current size of the user's basket (super sermons gold)
    basketsize_super = models.IntegerField("Basket size super sermons gold", default=0)
    
    # Many-to-many field for the contents of a search basket per user (sermons)
    basketitems = models.ManyToManyField("SermonDescr", through="Basket", related_name="basketitems_user")
    
    # Many-to-many field for the contents of a search basket per user (manuscripts)
    basketitems_manu = models.ManyToManyField("Manuscript", through="BasketMan", related_name="basketitems_user_manu")

    # Many-to-many field for the contents of a search basket per user (sermons gold)
    basketitems_gold = models.ManyToManyField("SermonGold", through="BasketGold", related_name="basketitems_user_gold")

    # Many-to-many field for the contents of a search basket per user (super sermons gold)
    basketitems_super = models.ManyToManyField("EqualGold", through="BasketSuper", related_name="basketitems_user_super")
              
    def __str__(self):
        sStack = self.stack
        return sStack

    def add_visit(self, name, path, is_menu, **kwargs):
        """Process one visit in an adaptation of the stack"""

        oErr = ErrHandle()
        bNeedSaving = False
        try:
            # Check if this is a menu choice
            if is_menu:
                # Rebuild the stack
                path_home = reverse("home")
                oStack = []
                oStack.append({'name': "Home", 'url': path_home })
                if path != path_home:
                    oStack.append({'name': name, 'url': path })
                self.stack = json.dumps(oStack)
                bNeedSaving = True
            else:
                # Unpack the current stack
                lst_stack = json.loads(self.stack)
                # Check if this path is already on the stack
                bNew = True
                for idx, item in enumerate(lst_stack):
                    # Check if this item is on it already
                    if item['url'] == path:
                        # The url is on the stack, so cut off the stack from here
                        lst_stack = lst_stack[0:idx+1]
                        # But make sure to add any kwargs
                        if kwargs != None:
                            item['kwargs'] = kwargs
                        bNew = False
                        break
                    elif item['name'] == name:
                        # Replace the url
                        item['url'] = path
                        # But make sure to add any kwargs
                        if kwargs != None:
                            item['kwargs'] = kwargs
                        bNew = False
                        break
                if bNew:
                    # Add item to the stack
                    lst_stack.append({'name': name, 'url': path })
                # Add changes
                self.stack = json.dumps(lst_stack)
                bNeedSaving = True
            # All should have been done by now...
            if bNeedSaving:
                self.save()
        except:
            msg = oErr.get_error_message()
            oErr.DoError("profile/add_visit")

    def get_stack(username):
        """Get the stack as a list from the current user"""

        # Sanity check
        if username == "":
            # Rebuild the stack
            path_home = reverse("home")
            oStack = []
            oStack.append({'name': "Home", 'url': path_home })
            return oStack
        # Get the user
        user = User.objects.filter(username=username).first()
        # Get to the profile of this user
        profile = Profile.objects.filter(user=user).first()
        if profile == None:
            # Return an empty list
            return []
        else:
            # Return the stack as object (list)
            return json.loads(profile.stack)

    def get_user_profile(username):
        # Sanity check
        if username == "":
            # Rebuild the stack
            return None
        # Get the user
        user = User.objects.filter(username=username).first()
        # Get to the profile of this user
        profile = Profile.objects.filter(user=user).first()
        return profile

    def get_groups_markdown(self):
        """Get all the groups this user is member of"""

        lHtml = []
        # Visit all keywords
        for group in self.user.groups.all().order_by('name'):
            # Create a display for this topic
            lHtml.append("<span class='keyword'>{}</span>".format(group.name))

        sBack = ", ".join(lHtml)
        return sBack

    def history(self, action, type, oFields = None):
        """Perform [action] on the history of [type]"""

        oErr = ErrHandle()
        bBack = True

        def get_operation(action, oFields):
            lstOr = {}
            oOperation = {}
            try:
                for k,v in oFields.items():
                    lenOk = True
                    if isinstance(v, QuerySet):
                        lenOk = (len(v) != 0)
                    elif isinstance(v, object):
                        pass
                    else:
                        lenOk = (len(v) != 0)
                    if v!=None and v!= "" and lenOk:
                        # Possibly adapt 'v'
                        if isinstance(v, QuerySet):
                            # This is a list
                            rep_list = []
                            for rep in v:
                                # Get the id of this item
                                rep_id = rep.id
                                rep_list.append(rep_id)
                            v = json.dumps(rep_list)
                        elif isinstance(v, str) or isinstance(v,int):
                            pass
                        elif isinstance(v, object):
                            v = [ v.id ]
                        # Add v to the or-list-object
                        lstOr[k] = v
                oOperation = dict(action=action, item=lstOr)
            except:
                msg = oErr.get_error_message()
            return oOperation

        try:

            # Initializations
            h_field = "history{}".format(type)
            s_list = getattr(self, h_field)
            h_list = json.loads(s_list)
            bChanged = False
            history_actions = ["create", "remove", "add"]

            # Process the actual change
            if action == "reset":
                # Reset the history stack of this type
                setattr(self, "history{}".format(type), "[]")
                bChanged = True
            elif action in history_actions:
                if oFields != None:
                    # Process removing items to the current history
                    bChanged = True
                    oOperation = get_operation(action, oFields)
                    if action == "create": h_list = []
                    h_list.append(oOperation)

            # Only save changes if anything changed actually
            if bChanged:
                # Re-create the list
                s_list = json.dumps(h_list)
                setattr(self, h_field, s_list)
                # Save the changes
                self.save()
        except:
            msg = oErr.get_error_message()
            oErr.DoError()
            bBack = False

        return bBack


class Visit(models.Model):
    """One visit to part of the application"""

    # [1] Every visit is made by a user
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="user_visits")
    # [1] Every visit is done at a certain moment
    when = models.DateTimeField(default=get_current_datetime)
    # [1] Every visit is to a 'named' point
    name = models.CharField("Name", max_length=STANDARD_LENGTH)
    # [1] Every visit needs to have a URL
    path = models.URLField("URL")

    def __str__(self):
        msg = "{} ({})".format(self.name, self.path)
        return msg

    def add(username, name, path, is_menu = False, **kwargs):
        """Add a visit from user [username]"""

        oErr = ErrHandle()
        try:
            # Sanity check
            if username == "": return True
            # Get the user
            user = User.objects.filter(username=username).first()
            # Adapt the path if there are kwargs
            # Add an item
            obj = Visit(user=user, name=name, path=path)
            obj.save()
            # Get to the stack of this user
            profile = Profile.objects.filter(user=user).first()
            if profile == None:
                # There is no profile yet, so make it
                profile = Profile(user=user)
                profile.save()

            # Process this visit in the profile
            profile.add_visit(name, path, is_menu, **kwargs)
            # Possibly throw away an overflow of visit logs?
            user_visit_count = Visit.objects.filter(user=user).count()
            if user_visit_count > VISIT_MAX:
                # Check how many to remove
                removing = user_visit_count - VISIT_REDUCE
                # Find the ID of the first one to remove
                id_list = Visit.objects.filter(user=user).order_by('id').values('id')
                below_id = id_list[removing]['id']
                # Remove them
                Visit.objects.filter(user=user, id__lte=below_id).delete()
            # Return success
            result = True
        except:
            msg = oErr.get_error_message()
            oErr.DoError("visit/add")
            result = False
        # Return the result
        return result


class Stype(models.Model):
    """Status of M/S/SG/SSG"""

    # [1] THe abbreviation code of the status
    abbr = models.CharField("Status abbreviation", max_length=50)
    # [1] The English name
    nameeng = models.CharField("Name (ENglish)", max_length=50)
    # [1] The Dutch name
    namenld = models.CharField("Name (Dutch)", max_length=50)

    def __str__(self):
        return self.abbr


# ==================== Passim/Seeker models =============================

class LocationType(models.Model):
    """Kind of location and level on the location hierarchy"""

    # [1] obligatory name
    name = models.CharField("Name", max_length=STANDARD_LENGTH)
    # [1] obligatory level of this location on the scale
    level = models.IntegerField("Hierarchy level", default=0)

    def __str__(self):
        return self.name

    def find(sname):
        obj = LocationType.objects.filter(name__icontains=sname).first()
        return obj


class Location(models.Model):
    """One location element can be a city, village, cloister, region"""

    # [1] obligatory name in ENGLISH
    name = models.CharField("Name (eng)", max_length=STANDARD_LENGTH)
    # [1] Link to the location type of this location
    loctype = models.ForeignKey(LocationType, on_delete=models.SET_DEFAULT, default=get_default_loctype, related_name="loctypelocations")

    # [1] Every Library has a status to keep track of who edited it
    stype = models.CharField("Status", choices=build_abbr_list(STATUS_TYPE), max_length=5, default="man")
    # [0-1] Status note
    snote = models.TextField("Status note(s)", default="[]")

    # We need to know whether a location is part of a particular city or country for 'dependent_fields'
    # [0-1] City according to the 'Location' specification
    lcity = models.ForeignKey("self", null=True, related_name="lcity_locations", on_delete=models.SET_NULL)
    # [0-1] Library according to the 'Location' specification
    lcountry = models.ForeignKey("self", null=True, related_name="lcountry_locations", on_delete=models.SET_NULL)

    # Many-to-many field that identifies relations between locations
    relations = models.ManyToManyField("self", through="LocationRelation", symmetrical=False, related_name="relations_location")

    def __str__(self):
        return self.name

    def save(self, force_insert = False, force_update = False, using = None, update_fields = None):
        if self != None:
            # Check the values for [lcity] and [lcountry]
            self.lcountry = self.partof_loctype("country")
            self.lcity = self.partof_loctype("city")
        # Regular saving
        response = super(Location, self).save(force_insert, force_update, using, update_fields)
        return response

    def get_loc_name(self):
        lname = "{} ({})".format(self.name, self.loctype)
        return lname

    def get_location(city="", country=""):
        """Get the correct location object, based on the city and/or the country"""

        obj = None
        lstQ = []
        qs_country = None
        if country != "" and country != None:
            # Specify the country
            lstQ.append(Q(loctype__name="country"))
            lstQ.append(Q(name__iexact=country))
            qs_country = Location.objects.filter(*lstQ)
            if city == "" or city == None:
                obj = qs_country.first()
            else:
                lstQ = []
                lstQ.append(Q(loctype__name="city"))
                lstQ.append(Q(name__iexact=city))
                lstQ.append(relations_location__in=qs_country)
                obj = Location.objects.filter(*lstQ).first()
        elif city != "" and city != None:
            lstQ.append(Q(loctype__name="city"))
            lstQ.append(Q(name__iexact=city))
            obj = Location.objects.filter(*lstQ).first()
        return obj

    def get_idVilleEtab(self):
        """Get the identifier named [idVilleEtab]"""

        obj = self.location_identifiers.filter(idname="idVilleEtab").first()
        return "" if obj == None else obj.idvalue

    def get_partof_html(self):
        lhtml = []
        for loc in self.above():
            sItem = '<span class="badge loctype-{}" title="{}">{}</span>'.format(
                loc.loctype.name, loc.loctype.name, loc.name)
            lhtml.append(sItem)
        return "\n".join(lhtml)

    def partof(self):
        """give a list of locations (and their type) of which I am part"""

        lst_main = []
        lst_back = []

        def get_above(loc, lst_this):
            """Perform depth-first recursive procedure above"""

            above_lst = LocationRelation.objects.filter(contained=loc)
            for item in above_lst:
                # Add this item
                lst_this.append(item.container)
                # Add those above this item
                get_above(item.container, lst_this)

        # Calculate the aboves
        get_above(self, lst_main)

        # Walk the main list
        for item in lst_main:
            lst_back.append("{} ({})".format(item.name, item.loctype.name))

        # Return the list of locations
        return " | ".join(lst_back)

    def hierarchy(self, include_self=True):
        """give a list of locations (and their type) of which I am part"""

        lst_main = []
        if include_self:
            lst_main.append(self)

        def get_above(loc, lst_this):
            """Perform depth-first recursive procedure above"""

            above_lst = LocationRelation.objects.filter(contained=loc)
            for item in above_lst:
                # Add this item
                lst_this.append(item.container)
                # Add those above this item
                get_above(item.container, lst_this)

        # Calculate the aboves
        get_above(self, lst_main)

        # Return the list of locations
        return lst_main

    def above(self):
        return self.hierarchy(False)

    def partof_loctype(self, loctype):
        """See which country (if any) I am part of"""

        lcountry = None
        lst_above = self.hierarchy(False)
        for obj in lst_above:
            if obj.loctype.name == loctype:
                lcountry = obj
                break
        return lcountry

    
class LocationName(models.Model):
    """The name of a location in a particular language"""

    # [1] obligatory name in vernacular
    name = models.CharField("Name", max_length=STANDARD_LENGTH)
    # [1] the language in which this name is given - ISO 3 letter code
    language = models.CharField("Language", max_length=STANDARD_LENGTH, default="eng")
    # [1] the Location to which this (vernacular) name belongs
    location = models.ForeignKey(Location, related_name="location_names", on_delete=models.CASCADE)

    def __str__(self):
        return "{} ({})".format(self.name, self.language)


class LocationIdentifier(models.Model):
    """The name and value of a location identifier"""

    # [0-1] Optionally an identifier name
    idname = models.CharField("Identifier name", null=True, blank=True, max_length=STANDARD_LENGTH)
    # [0-1]        ... and an identifier value
    idvalue = models.IntegerField("Identifier value", null=True, blank=True)
    # [1] the Location to which this (vernacular) name belongs
    location = models.ForeignKey(Location, related_name="location_identifiers", on_delete=models.CASCADE)

    def __str__(self):
        return "{} ({})".format(self.name, self.language)


class LocationRelation(models.Model):
    """Container-contained relation between two locations"""

    # [1] Obligatory container
    container = models.ForeignKey(Location, related_name="container_locrelations", on_delete=models.CASCADE)
    # [1] Obligatory contained
    contained = models.ForeignKey(Location, related_name="contained_locrelations", on_delete=models.CASCADE)

    def save(self, force_insert = False, force_update = False, using = None, update_fields = None):
        # First do the regular saving
        response = super(LocationRelation, self).save(force_insert, force_update, using, update_fields)
        # Check the [contained] element for [lcity] and [lcountry]
        self.contained.save()
        # Return the save response
        return response


class Country(models.Model):
    """Countries in which there are library cities"""

    # [1] CNRS numerical identifier of the country
    idPaysEtab = models.IntegerField("CNRS country id", default=-1)
    # [1] Name of the country (English)
    name = models.CharField("Name (EN)", max_length=STANDARD_LENGTH)
    # [1] Name of the country (French)
    nameFR = models.CharField("Name (FR)", max_length=STANDARD_LENGTH)

    def __str__(self):
        return self.name

    def get_country(sId, sCountryEn, sCountryFr):
        iId = int(sId)
        lstQ = []
        lstQ.append(Q(idPaysEtab=iId))
        lstQ.append(Q(name=sCountryEn))
        lstQ.append(Q(nameFR=sCountryFr))
        hit = Country.objects.filter(*lstQ).first()
        if hit == None:
            hit = Country(idPaysEtab=iId, name=sCountryEn, nameFR=sCountryFr)
            hit.save()

        return hit


class City(models.Model):
    """Cities that contain libraries"""

    # [1] CNRS numerical identifier of the city
    idVilleEtab = models.IntegerField("CNRS city id", default=-1)
    # [1] Name of the city
    name = models.CharField("Name", max_length=STANDARD_LENGTH)
    # [0-1] Name of the country this is in
    #       Note: when a country is deleted, its cities are automatically deleted too
    country = models.ForeignKey(Country, null=True, blank=True, related_name="country_cities", on_delete=models.SET_NULL)

    def __str__(self):
        return self.name

    def get_city(sId, sCity, country):
        iId = int(sId)
        lstQ = []
        lstQ.append(Q(idVilleEtab=iId))
        lstQ.append(Q(name=sCity))
        lstQ.append(Q(country=country))
        hit = City.objects.filter(*lstQ).first()
        if hit == None:
            hit = City(idVilleEtab=iId, name=sCity, country=country)
            hit.save()

        return hit

    def find_or_create(sName, country):
        """Find a city or create it."""

        errHandle = ErrHandle()
        hit = None
        try:
            qs = City.objects.filter(Q(name__iexact=sName))
            if qs.count() == 0:
                # Create one
                hit = City(name=sName)
                if country != None:
                    hit.country = country
                hit.save()
            else:
                hit = qs[0]
        except:
            sError = errHandle.get_error_message()
            oBack['status'] = 'error'
            oBack['msg'] = sError
            hit = None

        # Return what we found or created
        return hit


class Library(models.Model):
    """Library in a particular city"""

    # [1] LIbrary code according to CNRS
    idLibrEtab = models.IntegerField("CNRS library id", default=-1)
    # [1] Name of the library
    name = models.CharField("Library", max_length=LONG_STRING)
    # [1] Has this library been bracketed?
    libtype = models.CharField("Library type", choices=build_abbr_list(LIBRARY_TYPE), max_length=5)

    # ============= These fields should be removed sooner or later ===================
    # [1] Name of the city this is in
    #     Note: when a city is deleted, its libraries are deleted automatically
    city = models.ForeignKey(City, null=True, related_name="city_libraries", on_delete=models.SET_NULL)
    # [1] Name of the country this is in
    country = models.ForeignKey(Country, null=True, related_name="country_libraries", on_delete=models.SET_NULL)
    # ================================================================================

    # [1] Every Library has a status to keep track of who edited it
    stype = models.CharField("Status", choices=build_abbr_list(STATUS_TYPE), max_length=5, default="man")
    # [0-1] Status note
    snote = models.TextField("Status note(s)", default="[]")

    # One field that is calculated whenever needed
    mcount = models.IntegerField("Manuscripts for this library", default=0)

    # [0-1] Location, as specific as possible, but optional in the end
    location = models.ForeignKey(Location, null=True, related_name="location_libraries", on_delete=models.SET_NULL)
    # [0-1] City according to the 'Location' specification
    lcity = models.ForeignKey(Location, null=True, related_name="lcity_libraries", on_delete=models.SET_NULL)
    # [0-1] Library according to the 'Location' specification
    lcountry = models.ForeignKey(Location, null=True, related_name="lcountry_libraries", on_delete=models.SET_NULL)

    def __str__(self):
        return self.name

    def save(self, force_insert = False, force_update = False, using = None, update_fields = None):
        # Possibly change lcity, lcountry
        obj = self.get_city(False)
        obj = self.get_country(False)
        return super(Library, self).save(force_insert, force_update, using, update_fields)

    def get_library(sId, sLibrary, bBracketed, country, city):
        iId = int(sId)
        lstQ = []
        lstQ.append(Q(idLibrEtab=iId))
        lstQ.append(Q(name=sLibrary))
        lstQ.append(Q(lcountry__name=country))
        lstQ.append(Q(lcity__name=city))
        hit = Library.objects.filter(*lstQ).first()
        if hit == None:
            libtype = "br" if bBracketed else "pl"
            hit = Library(idLibrEtab=iId, name=sLibrary, libtype=libtype, country=country, city=city)
            hit.save()

        return hit

    def get_location(self):
        """Get the location of the library to show in details view"""
        sBack = "-"
        if self.location != None:
            sBack = self.location.get_loc_name()
        return sBack

    def get_location_markdown(self):
        """Get the location of the library to show in details view"""
        sBack = "-"
        if self.location != None:
            name = self.location.get_loc_name()
            url = reverse('location_details', kwargs={'pk': self.location.id})
            sBack = "<span class='badge signature gr'><a href='{}'>{}</a></span>".format(url, name)
        return sBack

    def get_city(self, save_changes = True):
        """Given the library, get the city from the location"""

        obj = None
        if self.lcity != None:
            obj = self.lcity
        elif self.location != None:
            if self.location.loctype != None and self.location.loctype.name == "city":
                obj = self.location
            else:
                # Look at all the related locations - above and below
                qs = self.location.relations_location.all()
                for item in qs:
                    if item.loctype.name == "city":
                        obj = item
                        break
                if obj == None:
                    # Look at the first location 'above' me
                    item = self.location.contained_locrelations.first()
                    if item.container.loctype.name != "country":
                        obj = item.container
            # Store this
            self.lcity = obj
            if save_changes:
                self.save()
        return obj

    def get_city_name(self):
        obj = self.get_city()
        return "" if obj == None else obj.name

    def get_country(self, save_changes = True):
        """Given the library, get the country from the location"""

        obj = None
        if self.lcountry != None:
            obj = self.lcountry
        elif self.location != None:
            if self.location.loctype != None and self.location.loctype.name == "country":
                obj = self.location
            else:
                # Look upwards
                qs = self.location.contained_locrelations.all()
                for item in qs:
                    container = item.container
                    if container != None:
                        if container.loctype.name == "country":
                            obj = container
                            break
            # Store this
            self.lcountry = obj
            if save_changes:
                self.save()
        return obj

    def get_country_name(self):
        obj = self.get_country()
        return "" if obj == None else obj.name

    def num_manuscripts(self):
        """Get the number of manuscripts in our database that refer to this library"""

        num = Manuscript.objects.filter(library=self).count()
        return num

    def find_or_create(sCity, sLibrary, sCountry = None):
        """Find a library on the basis of the city and the library name.
        If there is no library with that combination yet, create it
        """

        errHandle = ErrHandle()
        hit = None
        country = None
        try:
            # Check if a country is mentioned
            if sCountry != None:
                country = Country.objects.filter(Q(name__iexact=sCountry)).first()
            # Try to create the city 
            if sCity != "":
                city = City.find_or_create(sCity, country)
                lstQ = []
                lstQ.append(Q(name__iexact=sLibrary))
                lstQ.append(Q(city=city))
                qs = Library.objects.filter(*lstQ)
                if qs.count() == 0:
                    # Create one
                    libtype = "-"
                    hit = Library(name=sLibrary, city=city, libtype=libtype)
                    if country != None:
                        hit.country = country
                    hit.save()
                else:
                    hit = qs[0]
        except:
            sError = errHandle.get_error_message()
            oBack['status'] = 'error'
            oBack['msg'] = sError
            hit = None

        # Return what we found or created
        return hit
            
    def read_json(oStatus, fname):
        """Read libraries from a JSON file"""

        oErr = ErrHandle()
        oResult = {}
        count = 0

        try:
            # Check
            if not os.path.exists(fname) or not os.path.isfile(fname):
                # Return negatively
                oErr.Status("Library/read_json: cannot read {}".format(fname))
                oResult['status'] = "error"
                oResult['msg'] = "Library/read_json: cannot read {}".format(fname)
                return oResult

            # Read the library list in fName
            with open(fname, "r", encoding="utf-8") as fi:
                data = fi.read()
                lEntry = json.loads(data)

            # Walk the list
            for oEntry in lEntry:
                # Process this entry
                country = Country.get_country(oEntry['country_id'], oEntry['country_en'], oEntry['country_fr'])
                city = City.get_city(oEntry['city_id'], oEntry['city'], country)
                lib = Library.get_library(oEntry['library_id'], oEntry['library'], oEntry['bracketed'], country, city)
                # Keep track of counts
                count += 1
                # Update status
                oCount = {'country': Country.objects.all().count(),
                          'city': City.objects.all().count(),
                          'library': Library.objects.all().count()}
                oStatus.set("working", oCount=oCount)

            # Now we are ready
            oResult['status'] = "ok"
            oResult['msg'] = "Read {} library definitions".format(count)
            oResult['count'] = count
        except:
            oResult['status'] = "error"
            oResult['msg'] = oErr.get_error_message()

        # Return the correct result
        return oResult


class Origin(models.Model):
    """The 'origin' is a location where manuscripts were originally created"""

    # [1] Name of the location
    name = models.CharField("Original location", max_length=LONG_STRING)

    # [0-1] Optional: LOCATION element this refers to
    location = models.ForeignKey(Location, null=True, related_name="location_origins", on_delete=models.SET_NULL)

    # [0-1] Further details are perhaps required too
    note = models.TextField("Notes on this origin", blank=True, null=True)

    def __str__(self):
        return self.name

    def find_or_create(sName, city=None, country=None, note=None):
        """Find a location or create it."""

        lstQ = []
        lstQ.append(Q(name__iexact=sName))
        obj_loc = Location.get_location(city=city, country=country)
        if obj_loc != None:
            lstQ.append(Q(location=Location))
        if note!=None: lstQ.append(Q(note__iexact=note))
        qs = Origin.objects.filter(*lstQ)
        if qs.count() == 0:
            # Create one
            hit = Origin(name=sName)
            if note!=None: hit.note=note
            if obj_loc != None: hit.location = obj_loc
            hit.save()
        else:
            hit = qs[0]
        # Return what we found or created
        return hit

    def get_location(self):
        if self.location:
            sBack = self.location.name
        else:
            sBack = "-"

        return sBack


class SourceInfo(models.Model):
    """Details of the source from which we get information"""

    # [1] Obligatory time of extraction
    created = models.DateTimeField(default=get_current_datetime)
    # [0-1] Code used to collect information
    code = models.TextField("Code", null=True, blank=True)
    # [0-1] URL that was used
    url = models.URLField("URL", null=True, blank=True)
    # [1] The person who was in charge of extracting the information
    collector = models.CharField("Collected by", max_length=LONG_STRING)
    profile = models.ForeignKey(Profile, on_delete=models.SET_NULL, blank=True, null=True, related_name="profile_sourceinfos")

    def init_profile():
        coll_set = {}
        qs = SourceInfo.objects.filter(profile__isnull=True)
        with transaction.atomic():
            for obj in qs:
                if obj.collector != "" and obj.collector not in coll_set:
                    coll_set[obj.collector] = Profile.get_user_profile(obj.collector)
                obj.profile = coll_set[obj.collector]
                obj.save()
        # Derive from profile
        qs = SourceInfo.objects.filter(collector="").exclude(profile__isnull=True)
        with transaction.atomic():
            for obj in qs:
                if obj.collector == "" or obj.collector not in coll_set:
                    obj.collector = Profile.objects.filter(id=obj.profile.id).first().user.username
                obj.save()

        result = True

    def get_created(self):
        sBack = self.created.strftime("%d/%b/%Y %H:%M")
        return sBack

    def get_code_html(self):
        sCode = "-" if self.code == None else self.code
        if len(sCode) > 80:
            button_code = "<a class='btn btn-xs jumbo-1' data-toggle='collapse' data-target='#source_code'>...</a>"
            sBack = "<pre>{}{}<span id='source_code' class='collapse'>{}</span></pre>".format(sCode[:80], button_code, sCode[80:])
        else:
            sBack = "<pre>{}</pre>".format(sCode)
        return sBack

    def get_username(self):
        sBack = "(unknown)"
        if self.profile != None:
            sBack = self.profile.user.username
        return sBack

    def get_manu_html(self):
        """Get the HTML display of the manuscript to which I am attached"""

        sBack = "Make sure to connect this source to a manuscript and save it. Otherwise it will be automatically deleted"
        manu = self.sourcemanuscripts.first()
        if manu != None:
            url = reverse('manuscript_details', kwargs={'pk': manu.id})
            sBack = "Linked to: <span class='signature ot'><a href='{}'>{}</a></span>".format(url, manu.idno)
        return sBack


class Litref(models.Model):
    """A literature reference as found in a shared Zotero database"""

    # [1] The itemId for this literature reference
    itemid = models.CharField("Item ID", max_length=LONG_STRING)
    # Optional year field
    year = models.IntegerField("Publication year", blank=True, null=True)
    # [0-1] The actual 'data' contents as a JSON string
    data = models.TextField("JSON data", blank=True, default="")
    # [0-1] The abbreviation (retrieved) for this item
    abbr = models.CharField("Abbreviation", max_length=STANDARD_LENGTH, blank=True, default="")
    # [0-1] The full reference, including possible markdown symbols
    full = models.TextField("Full reference", blank=True, default="")
    # [0-1] A short reference: including possible markdown symbols
    short = models.TextField("Short reference", blank=True, default="")

    ok_types = ['book', 'bookSection', 'conferencePaper', 'journalArticle', 'manuscript', 'thesis']

    def __str__(self):
        sBack = str(self.itemid)
        if self.short != None and self.short != "":
            sBack = self.short
        return sBack

    def sync_zotero(force=False, oStatus=None):
        """Read all stuff from Zotero"""

        libid = Information.get_kvalue("zotero_libraryid")
        libtype = "group"
        apikey = Information.get_kvalue("zotero_apikey")

        # Double check
        if libid == ""  or apikey == "":
            # Cannot proceed, but we'll return True anyway
            return True

        zot = zotero.Zotero(libid, libtype, apikey)
        group_size = 25
        oBack = dict(status="ok", msg="")
        bBack = True
        msg = ""
        changes = 0
        additions = 0
        oErr = ErrHandle()
        try:
            oBack['total'] = "Checking for literature references that have not been completely processed..."
            if oStatus != None: oStatus.set("ok", oBack)
            # Now walk all Litrefs again to see where fields are missing
            processing = 0
            for obj in Litref.objects.all():
                oData = json.loads(obj.data)
                if oData.get('itemType') in Litref.ok_types and obj.full == "" and obj.short == "":
                    # Do this one again
                    obj.read_zotero(data=oData)
                    processing += 1
                    # Update status
                    oBack['processed'] = processing
                    if oStatus != None: oStatus.set("ok", oBack)
            if processing > 0:
                oBack['processed'] = processing
                    
            # Get the total number of items
            total_count = zot.count_items()
            # Initial status
            oBack['total'] = "There are {} references in the Passim Zotero library".format(total_count)
            if oStatus != None: oStatus.set("ok", oBack)

            # Read them in groups of 25
            total_groups = math.ceil(total_count / group_size)
            for grp_num in range( total_groups):
                # Show where we are
                oErr.Status("Sync zotero {}/{}".format(grp_num, total_groups))
                # Calculate the umber to start from
                start = grp_num * group_size
                # Fetch these publications
                for item in zot.items(start=start, limit=25):
                    # Get the itemid
                    sData = json.dumps( item['data'])
                    itemid = item['key']
                    # Check if the item is in Litref
                    obj = Litref.objects.filter(itemid=itemid).first()
                    if obj == None:
                        # Add it
                        obj = Litref(itemid=itemid, data=sData)
                        obj.save()
                        additions += 1
                    # Check if it needs processing
                    if force or obj.short == "" or obj.data != sData:
                        # Do a complete check on all KV pairs
                        oDataZotero = item['data']
                        oDataLitref = json.loads(obj.data)
                        if force:
                            bNeedChanging = True
                        else:
                            bNeedChanging = False
                            for k,v in oDataZotero.items():
                                # Find the corresponding in Litref
                                if k in oDataLitref:
                                    if v != oDataLitref[k]:
                                        oErr.Status("Litref/sync_zotero: value on [{}] differs [{}] / [{}]".format(k, v, oDataLitref[k]))
                                        bNeedChanging = True
                                else:
                                    # The key is not even found
                                    oErr.Status("Litref/sync_zotero: key not found {}".format(k))
                                    bNeedChanging = True
                                    break
                        if bNeedChanging:
                            # It needs processing
                            obj.data = sData
                            obj.save()
                            obj.read_zotero(data=item['data'])
                            changes += 1
                    elif obj.data != sData:
                        obj.data = sData
                        obj.save()
                        obj.read_zotero(data=item['data'])
                        changes += 1

                # Update the status information
                oBack['group'] = "Group {}/{}".format(grp_num+1, total_groups)
                oBack['changes'] = changes
                oBack['additions'] = additions
                if oStatus != None: oStatus.set("ok", oBack)

            # Make sure to set the status to finished
            oBack['group'] = "Everything has been done"
            oBack['changes'] = changes
            oBack['additions'] = additions
            if oStatus != None: oStatus.set("finished", oBack)
        except:
            print("sync_zotero error")
            msg = oErr.get_error_message()
            oBack['msg'] = msg
            oBack['status'] = 'error'
        return oBack, ""

    def get_zotero(self):
        """Retrieve the zotero list of dicts for this item"""

        libid = Information.get_kvalue("zotero_libraryid")
        libtype = "group"
        apikey = Information.get_kvalue("zotero_apikey")
        zot = zotero.Zotero(libid, libtype, apikey)
        try:
            oZot = zot.item(self.itemid)
            if oZot == None:
                oBack = None
            elif 'data' in oZot:
                oBack = oZot['data']
            else:
                oBack = oZot
        except:
            oBack = None
        return oBack

    def read_zotero(self, data=None):
        """Process the information from zotero"""

        # Try to read the data from zotero
        if data == None:
            data = self.get_zotero()
        result = ""
        back = True
        ok_types = self.ok_types
        oErr = ErrHandle()

        try:
            # Check if this is okay
            if data != None and 'itemType' in data:
                # Action depends on the [itemType]
                itemType = data['itemType']

                if itemType in ok_types:

                    # Initialise SHORT
                    result = ""
                    bNeedShortSave = False

                    # Check presence of data
                    sData = json.dumps(data)
                    # Check and adapt the JSON string data
                    if self.data != sData:
                        self.data = sData
                        bNeedShortSave = True

                    # First step: store data 

                    # Get the first author
                    authors = Litref.get_creators(data, type="author", style= "first")
                    
                    # Get the editor(s)
                    editors = Litref.get_creators(data, type="editor")

                    # Get the year 
                    year = "?" if "date" not in data else data['date'][-4:]
                   
                    # Get the title
                    title = "(no title)" if "title" not in data else data['title']
                   
                    # Get the short title (for books and book sections)
                    short_title = "(no short title)" if "shortTitle" not in data else data['shortTitle']
                   
                    # Get the abbreviation of the journal 
                    journal_abbr = "(no abbr journal title)" if "publicationTitle" not in data else data['publicationTitle']
                   
                    # Get the volume
                    volume = "?" if "volume" not in data else data['volume']
                    
                    # Get the coding for edition ("ed") or catalogue ("cat")
                    extra = data.get('extra', "")
                    
                    # Get the name of the series
                    series = data.get('series', "")
                    
                    # Get the series number
                    series_number = "(no series number)" if "seriesNumber" not in data else data['seriesNumber']

                    # Second step: make short reference for article in journal
                    if itemType == "journalArticle":
                        # In case the journal article is marked as edition in extra ("ed")
                        if extra == "ed":
                            result = "{}, _{}_ {} ({})".format(authors, short_title, volume, year)
                        else:
                            result = "{}, _{}_ {} ({})".format(authors, journal_abbr, volume, year)
                      
                    
                    # Third step: make short reference for book section         
                    elif itemType == "bookSection":
                        result = "{} ({})".format(authors, year)
                    
                    # Fourth step: make short reference for book 
                    elif itemType == "book":

                        if extra == "": 
                            if short_title == "": 
                                # If the books is not an edition/catalogue and there is no short title
                                if authors !="":
                                    result = "{} ({})".format(authors, year)
                                # If there are only editors  
                                elif editors != "": 
                                        result = "{} ({})".format(editors, year)
                            # If there is a short title
                            elif short_title != "": 
                                # If there is a series number 
                                if series_number != "": 
                                    result = "{} {} ({})".format(short_title, series_number, year)
                                # If there is a volume number 
                                elif series_number == "" and volume != "":     
                                    result = "{} {} ({})".format(short_title, volume, year)
                                                                          
                        # Fifth step: make short reference for edition (book) 
                        # EK: only i there is a [short_title]
                        elif extra == "ed" and (short_title != "" or series_number != "" or volume != ""): 
                            if short_title == "PL":
                                if series_number != "":
                                    result = "{} {}".format(short_title, series_number)
                                # If there is no series number
                                elif series_number == "" and volume == "":
                                    result = "{}".format(short_title)
                                # If there is a volume number
                                elif volume != "":
                                    result = "{} {}".format(short_title, volume)
                            else:
                                if series_number != "":
                                    result = "{} {} ({})".format(short_title, series_number, year)
                                # If there is no series number
                                elif series_number == "" and volume == "":
                                    result = "{} ({})".format(short_title, year)
                                # If there is a volume number
                                elif volume != "":
                                    result = "{} {} ({})".format(short_title, volume, year)
                        
                        # PL exception
                        # elif extra == "ed" and short_title == "PL":
                           #  if series_number != "":
                           #      result = "{} {} ({})".format(short_title, series_number, year)
                                
                        # Sixth step: make short reference for catalogue (book)
                        elif extra == "cat":
                            # If there is no short title
                            if short_title == "": 
                                result = "{} ({})".format(authors, year)
                            # If there is a short title
                            elif short_title != "":
                                result = "{} ({})".format(short_title, year)
                        elif authors != "" and year != "":
                            # If there is no short title
                            if short_title == "": 
                                result = "{} ({})".format(authors, year)
                            else:
                                result = "{} ({})".format(short_title, year)
                        elif year != "" and short_title != "":
                            result = "{} ({})".format(short_title, year)

 
                    if result != "" and self.short != result:
                        oErr.Status("Update short [{}] to [{}]".format(self.short, result))
                        # update the short field
                        self.short = result
                        bNeedShortSave = True

                    if year != "" and year != "?":
                        try:
                            self.year = int(year)
                            bNeedShortSave = True
                        except:
                            pass

                    # Now update this item
                    if bNeedShortSave:
                        self.save()
                    
                    result = ""
                    bNeedFullSave = False
                    # Make a full reference for a book
                    authors = Litref.get_creators(data, type="author")
                    
                    # First step: store new data, combine place and publisher, series name and number
                    
                    # Get place
                    place = "(no place)" if "place" not in data else data['place']
                        
                    # Get publisher
                    publisher = "(no publisher)" if "publisher" not in data else data['publisher']

                    # Add place to publisher if both available
                    if place != "":
                        if publisher != "":
                            publisher = "{}: {}".format(place, publisher)
                        # Add place to publisher if only place available: 
                        elif publisher == "":
                            publisher = "{}".format(place)    
                    
                    # Add series number to series if both available
                    if series != "":
                        if series_number != "":
                            series = "{} {}".format(series, series_number)
                            
                    # Add series number to series if only series number available
                    if series == "":
                        if series_number != "":
                            series = "{}".format(series_number)
                   
                    # Second step: Make full reference for book
                    if itemType == "book":
                    
                        # Get the editor(s)
                        editors = Litref.get_creators(data, type="editor")
                                                
                        # For a book without authors 
                        if authors == "":
                            # And without publisher
                            if publisher == "":
                                # And without series name and or serie number
                                    if series !="":
                                        result = "_{}_ ({}) ({})".format(title, series, year)
                            # With publisher
                            elif publisher != "":
                                # With series name and or number
                                    if series !="":
                                        result = "_{}_ ({}), {} ({})".format(title, series, publisher, year)     
                                        # With only editors but NOT an edition
                                        if editors != "" and extra =="":
                                            result = "{}, _{}_ ({}), {} ({})".format(editors, title, series, publisher, year)                    
                        
                        # In other cases, with author and usual stuff
                        else: 
                            result = "{}, _{}_, {} ({})".format(authors, title, publisher, year)
                        
                        # Third step: Make a full reference for an edition (book)
                        if extra == "ed":
                            # There are no editors:
                            if editors == "":
                                # There is no series name
                                if series =="" and result == "":
                                    # There is no series number
                                    if series_number =="":
                                        result = "_{}_ {}, {} ({})".format(title, volume, publisher, year)
                            
                            # In other cases with editors
                            else:
                                result = "{}, _{}_ ({}), {}, {}".format(editors, title, series, publisher, year)
                        
                        # Fourth step: Make a full reference for a catalog (book) 
                        elif extra == "cat":
                            if series == "":
                                # There is no series_number and no series name
                                result = "{}, _{}_, {} ({})".format(authors, title, publisher, year)
                                if volume !="":
                                    result = "{}, _{}_, {} ({}), {}".format(authors, title, publisher, year, volume)        
                            else:
                                # There is a series name and or series_number
                                result = "{}, _{}_ ({}), {} ({})".format(authors, title, series, publisher, year)
                                if volume !="":
                                    result = "{}, _{}_ ({}), {} ({}), {}".format(authors, title, series, publisher, year, volume)
                           
                    # Fifth step: Make a full references for book section
                    elif itemType == "bookSection":
                        
                        # Get the editor(s)
                        editors = Litref.get_creators(data, type="editor")
                        
                        # Get the title of the book
                        booktitle = data['bookTitle']
                        
                        # Get the pages of the book section
                        pages = data['pages']
                        
                        # Reference without and with series name/number                                 
                        if series == "":
                            # There is no series_number and no series name available
                            result = "{}, '{}' in: {}, _{}_, {} ({}), {}".format(authors, title, editors, booktitle, publisher, year, pages)
                        else:
                            # There is a series name and or series_number available
                            result = "{}, '{}' in: {}, _{}_ ({}), {} ({}), {}".format(authors, title, editors, booktitle, series, publisher, year, pages)
                    
                    elif itemType == "conferencePaper":
                        combi = [authors, year, title]
                        # Name of the proceedings
                        proceedings = data['proceedingsTitle']
                        if proceedings != "": combi.append(proceedings)
                        # Get page(s)
                        pages = data['pages']
                        if pages != "": combi.append(pages)
                        # Get the location
                        place = data['place']
                        if place != "": combi.append(place)
                        # Combine
                        result = ". ".join(combi) + "."
                    elif itemType == "edited-volume":
                        # No idea how to process this
                        pass
                    
                    # Sixth step: Make a full references for a journal article
                    elif itemType == "journalArticle":
                        
                        # Name of the journal
                        journal = data['publicationTitle']
                        
                        # Volume
                        volume = data['volume']
                        
                        # Issue
                        issue = data['issue']
                        
                        if volume == "":
                            if issue == "":
                                # There is no volume or issue
                                result = "{}, '{}', _{}_, ({})".format(authors, title, journal, year)
                            else:
                                # There is no volume but there is an issue
                                result = "{}, '{}', _{}_, {} ({})".format(authors, title, journal, issue, year)
                        elif issue == "":
                            # There is a volume but there is no issue
                            result = "{}, '{}', _{}_, {} ({})".format(authors, title, journal, volume, year)
                        else:
                            # There are both volume and issue
                            result = "{}, '{}', _{}_, {} {} ({})".format(authors, title, journal, volume, issue, year)
                        
                    elif itemType == "manuscript":
                        combi = [authors, year, title]
                        # Get the location
                        place = data['place']
                        if place == "":
                            place = "Ms"
                        else:
                            place = place + ", ms"
                        if place != "": 
                            combi.append(place)
                        # Combine
                        result = ". ".join(combi) + "."
                    elif itemType == "report":
                        pass
                    elif itemType == "thesis":
                        combi = [authors, year, title]
                        # Get the location
                        place = data['place']
                        # Get the university
                        university = data['university']
                        if university != "": place = "{}: {}".format(place, university)
                        # Get the thesis type
                        thesis = data['thesisType']
                        if thesis != "":
                            place = "{} {}".format(place, thesis)
                        combi.append(place)
                        # Combine
                        result = ". ".join(combi) + "."
                    elif itemType == "webpage":
                        pass
                    if result != "" and self.full != result:
                        # update the full field
                        oErr.Status("Update full [{}] to [{}]".format(self.full, result))
                        self.full = result
                        bNeedFullSave = True

                    # Now update this item
                    if bNeedFullSave:
                        self.save()
                else:
                    # This item type is not yet supported
                    pass
            else:
                back = False
        except Exception as e:
            print("read_zotero error", str(e))
            msg = oErr.get_error_message()
            oErr.DoError("read_zotero")
            back = False
        # Return ability
        return back

    def get_creators(data, type="author", style=""):
        """Extract the authors"""

        def get_lastname(item):
            sBack = ""
            if 'lastName' in item:
                sBack = item['lastName']
            elif 'name' in item:
                sBack = item['name']
            return sBack

        def get_firstname(item):
            sBack = ""
            if 'firstName' in item:
                sBack = item['firstName']
            return sBack

        oErr = ErrHandle()
        authors = []
        extra = ['data']
        result = ""
        number = 0
        try:
            bFirst = (style == "first")
            if data != None and 'creators' in data:
                for item in data['creators']:
                    if item['creatorType'] == type:
                        number += 1
                    
                        firstname = get_firstname(item)
                        lastname = get_lastname(item)
                        # Add this author
                        if bFirst:
                            # Extremely short: only the last name of the first author TH: afvangen igv geen auteurs
                            authors.append(lastname)
                        else:
                            if number == 1 and type == "author":
                                # First author of anything must have lastname - first initial
                                authors.append("{}, {}.".format(lastname, firstname[:1]))
                                if extra == "ed": 
                                    authors.append("{} {}".format(firstname, lastname))
                            elif type == "editor":
                                # Editors should have full first name
                                authors.append("{} {}".format(firstname, lastname))
                            else:
                                # Any other author or editor is first initial-lastname
                                authors.append("{}. {}".format(firstname[:1], lastname))
                if bFirst:
                    if len(authors) == 0:
                        result = "(unknown)"
                    else:
                        result = authors[0]
                        if len(authors) > 1:
                            result = result + " e.a."
                else:
                    if number == 1:
                        result = authors[0]
                    elif number == 0:
                        if type == "author":
                            result = "(no author)"
                    else:
                        preamble = authors[:-1]
                        last = authors[-1]
                        # The first [n-1] authors should be combined with a comma, the last with an ampersand
                        result = "{} & {}".format( ", ".join(preamble), last)
                # Possibly add (ed.) or (eds.) but not in case of an edition
                # extra = data['extra']
                if type == "editor" and extra == "ed":
                    result = result
                elif type == "editor" and len(authors) > 1:
                    result = result + " (eds.)"
                elif type == "editor" and len(authors) == 1: 
                    result = result + " (ed.)"
           
            
            return result
        except:
            msg = oErr.get_error_message()
            return ""    

    def get_abbr(self):
        """Get the abbreviation, reading from Zotero if not yet done"""

        if self.abbr == "":
            self.read_zotero()
        return self.abbr

    def get_full(self):
        """Get the full text, reading from Zotero if not yet done"""

        if self.full == "":
            self.read_zotero()
        return self.full

    def get_full_markdown(self):
        """Get the full text in markdown, reading from Zotero if not yet done"""

        if self.full == "":
            self.read_zotero()
        return adapt_markdown(self.full, lowercase=False)

    def get_short(self):
        """Get the short text, reading from Zotero if not yet done"""

        if self.short == "":
            self.read_zotero()
        return self.short

    def get_short_markdown(self):
        """Get the short text in markdown, reading from Zotero if not yet done"""

        if self.short == "":
            self.read_zotero()
        return adapt_markdown(self.short, lowercase=False)


class Project(models.Model):
    """manuscripts may belong to the project 'Passim' or to something else"""

    # [1] Obligatory name for a project
    name = models.CharField("Name", max_length=LONG_STRING)

    def __str__(self):
        sName = self.name
        if sName == None or sName == "":
            sName = "(unnamed)"
        return sName

    def get_default(username):
        """Determine the default project for this user"""

        obj = Project.objects.filter(name__iexact = "passim").first()
        if obj == None:
            obj = Project.objects.all().first()
        return obj

    def save(self, force_insert = False, force_update = False, using = None, update_fields = None):
        # First do the normal saving
        response = super(Project, self).save(force_insert, force_update, using, update_fields)
        # Check if this is the first project object
        qs = Project.objects.all()
        if qs.count() == 1:
            # Set this as default project for all manuscripts
            prj = qs.first()
            with transaction.atomic():
                for obj in Manuscript.objects.all():
                    obj.project = prj
                    obj.save()

        return response


class Keyword(models.Model):
    """A keyword that can be referred to from either a SermonGold or a SermonDescr"""

    # [1] Obligatory text of a keyword
    name = models.CharField("Name", max_length=LONG_STRING)
    # [1] Every keyword has a visibility - default is 'all'
    visibility = models.CharField("Visibility", choices=build_abbr_list(VISIBILITY_TYPE), max_length=5, default="all")
    # [0-1] Further details are perhaps required too
    description = models.TextField("Description", blank=True, null=True)

    def __str__(self):
        return self.name

    def freqsermo(self):
        """Frequency in manifestation sermons"""
        freq = self.keywords_sermon.all().count()
        return freq

    def freqgold(self):
        """Frequency in Gold sermons"""
        freq = self.keywords_gold.all().count()
        return freq

    def freqmanu(self):
        """Frequency in Manuscripts"""
        freq = self.keywords_manu.all().count()
        return freq

    def freqsuper(self):
        """Frequency in Super sermons gold"""
        freq = self.keywords_super.all().count()
        return freq

    def get_scoped_queryset(username, team_group, userplus=None):
        """Get a filtered queryset, depending on type and username"""

        # Initialisations
        non_private = ['publ', 'team']
        oErr = ErrHandle()
        filter = None
        try:
            # Validate
            if username and username != "" and team_group and team_group != "":
                # First filter on owner
                owner = Profile.get_user_profile(username)
                # Now check for permissions
                is_team = (owner.user.groups.filter(name=team_group).first() != None)
                if not is_team and userplus != None and userplus != "":
                    is_team = (owner.user.groups.filter(name=userplus).first() != None)
                # Adapt the filter accordingly
                if not is_team:
                    # Non editors may only see keywords visible to all
                    filter = Q(visibility="all")
            if filter:
                # Apply the filter
                qs = Keyword.objects.filter(filter).order_by('name')
            else:
                qs = Keyword.objects.all().order_by('name')
        except:
            msg = oErr.get_error_message()
            oErr.DoError("get_scoped_queryset")
            qs = Keyword.objects.all().order_by('name')
        # REturn the result
        return qs


class Comment(models.Model):
    """User comment"""

    # [0-1] The text of the comment itself
    content = models.TextField("Comment", null=True, blank=True)
    # [1] links to a user via profile
    profile = models.ForeignKey(Profile, related_name="profilecomments", on_delete=models.CASCADE)
    # [1] The type of comment
    otype = models.CharField("Object type", max_length=STANDARD_LENGTH, default = "-")
    # [1] Date created (automatically done)
    created = models.DateTimeField(default=get_current_datetime)

    def __str__(self):
        return self.content

    def get_created(self):
        sCreated = get_crpp_date(self.created, True)
        return sCreated

    def send_by_email(self, contents):
        """Send this comment by email to two addresses"""

        oErr = ErrHandle()
        try:
            # Determine the contents
            html = []

            # Send this mail
            send_email("Passim user comment {}".format(self.id), self.profile, contents, True)
        except:
            msg = oErr.get_error_message()
            oErr.DoError("Comment/send_by_email")

        # Always return positively!!!
        return True

    def get_otype(self):
        otypes = dict(manu="Manuscript", sermo="Sermon", gold="Gold Sermon", 
                      super="Super Sermon Gold", codi="Codicological Unit")
        return otypes[self.otype]


class Manuscript(models.Model):
    """A manuscript can contain a number of sermons"""

    # [1] Name of the manuscript (that is the TITLE)
    name = models.CharField("Name", max_length=LONG_STRING, default="SUPPLY A NAME")
    # [0-1] One manuscript can only belong to one particular library
    #     Note: deleting a library sets the Manuscript.library to NULL
    library = models.ForeignKey(Library, null=True, blank=True, on_delete = models.SET_NULL, related_name="library_manuscripts")
    # [1] Each manuscript has an identification number
    idno = models.CharField("Identifier", max_length=LONG_STRING, null=True, blank=True)
    # [0-1] If possible we need to know the original location of the manuscript
    origin = models.ForeignKey(Origin, null=True, blank=True, on_delete = models.SET_NULL, related_name="origin_manuscripts")
    # [0-1] Optional filename to indicate where we got this from
    filename = models.CharField("Filename", max_length=LONG_STRING, null=True, blank=True)
    # [0-1] Optional link to a website with (more) information on this manuscript
    url = models.URLField("Web info", null=True, blank=True)
    # [0-1] Notes field, which may be empty - see issue #298
    notes = models.TextField("Notes", null=True, blank=True)

    # =============== THese are the Minimum start and the Maximum finish =========================
    # [1] Date estimate: starting from this year
    yearstart = models.IntegerField("Year from", null=False, default=100)
    # [1] Date estimate: finishing with this year
    yearfinish = models.IntegerField("Year until", null=False, default=100)
    # =============================================================================================

    # Temporary support for the LIBRARY, when that field is not completely known:
    # [0-1] City - ideally determined by field [library]
    lcity = models.ForeignKey(Location, null=True, related_name="lcity_manuscripts", on_delete=models.SET_NULL)
    # [0-1] Library - ideally determined by field [library]
    lcountry = models.ForeignKey(Location, null=True, related_name="lcountry_manuscripts", on_delete=models.SET_NULL)

    # PHYSICAL features of the manuscript (OPTIONAL)
    # [0-1] Support: the general type of manuscript
    support = models.TextField("Support", null=True, blank=True)
    # [0-1] Extent: the total number of pages
    extent = models.TextField("Extent", max_length=LONG_STRING, null=True, blank=True)
    # [0-1] Format: the size
    format = models.CharField("Format", max_length=LONG_STRING, null=True, blank=True)

    # [1] Every manuscript has a status - this is *NOT* related to model 'Status'
    stype = models.CharField("Status", choices=build_abbr_list(STATUS_TYPE), max_length=5, default="man")
    # [0-1] Status note
    snote = models.TextField("Status note(s)", default="[]")
    # [1] And a date: the date of saving this manuscript
    created = models.DateTimeField(default=get_current_datetime)
    saved = models.DateTimeField(null=True, blank=True)

    # [0-1] A manuscript may have an ID from the database from which it was read
    external = models.IntegerField("ID in external DB", null=True)

    # [1] Every manuscript may be a manifestation (default) or a template (optional)
    #     The third alternative is: a reconstruction
    #     So the options: 'man', 'tem', 'rec'
    mtype = models.CharField("Manifestation type", choices=build_abbr_list(MANIFESTATION_TYPE), max_length=5, default="man")
    # [1] Imported manuscripts need to have a codico check
    itype = models.CharField("Import codico status", max_length=MAX_TEXT_LEN, default="no")

    # [0-1] Bibliography used for the manuscript
    literature = models.TextField("Literature", null=True, blank=True)

    # Where do we get our information from? And when was it added?
    #    Note: deletion of a sourceinfo sets the manuscript.source to NULL
    source = models.ForeignKey(SourceInfo, null=True, blank=True, on_delete = models.SET_NULL, related_name="sourcemanuscripts")

    # [0-1] Each manuscript should belong to a particular project
    project = models.ForeignKey(Project, null=True, blank=True, on_delete = models.SET_NULL, related_name="project_manuscripts")

    # ============== MANYTOMANY connections
    # [m] Many-to-many: one manuscript can have a series of provenances
    provenances = models.ManyToManyField("Provenance", through="ProvenanceMan")       
    # [m] Many-to-many: one manuscript can have a series of literature references
    litrefs = models.ManyToManyField("Litref", through="LitrefMan")
     # [0-n] Many-to-many: keywords per SermonDescr
    keywords = models.ManyToManyField(Keyword, through="ManuscriptKeyword", related_name="keywords_manu")
    # [m] Many-to-many: one sermon can be a part of a series of collections 
    collections = models.ManyToManyField("Collection", through="CollectionMan", related_name="collections_manuscript")
    # [m] Many-to-many: one manuscript can have a series of user-supplied comments
    comments = models.ManyToManyField(Comment, related_name="comments_manuscript")

    # Scheme for downloading and uploading
    specification = [
        {'name': 'Status',              'type': 'field', 'path': 'stype',     'readonly': True},
        {'name': 'Country',             'type': 'fk',    'path': 'lcountry',  'fkfield': 'name', 'model': 'Location'},
        {'name': 'City',                'type': 'fk',    'path': 'lcity',     'fkfield': 'name', 'model': 'Location'},
        {'name': 'Library',             'type': 'fk',    'path': 'library',   'fkfield': 'name', 'model': 'Library'},
        {'name': 'Shelf mark',          'type': 'field', 'path': 'idno',      'readonly': True},
        {'name': 'Title',               'type': 'field', 'path': 'name'},
        {'name': 'Project',             'type': 'fk',    'path': 'project',   'fkfield': 'name', 'model': 'Project'},
        {'name': 'Keywords',            'type': 'func',  'path': 'keywords',  'readonly': True},
        {'name': 'Keywords (user)',     'type': 'func',  'path': 'keywordsU'},
        {'name': 'Personal Datasets',   'type': 'func',  'path': 'datasets'},
        {'name': 'Literature',          'type': 'func',  'path': 'literature'},
        {'name': 'Notes',               'type': 'field', 'path': 'notes'},
        {'name': 'Url',                 'type': 'field', 'path': 'url'},
        {'name': 'External id',         'type': 'field', 'path': 'external'},
        {'name': 'External links',      'type': 'func',  'path': 'external_links'},
        ]

    def __str__(self):
        return self.name

    def save(self, force_insert = False, force_update = False, using = None, update_fields = None):
        # Adapt the save date
        self.saved = get_current_datetime()
        response = super(Manuscript, self).save(force_insert, force_update, using, update_fields)

        # If this is a new manuscript there is no codi conncted yet
        # Check if the codico exists
        codi = Codico.objects.filter(manuscript=self).first()
        if codi == None:
            # Create and link a new codico
            codi = Codico.objects.create(
                name="SUPPLY A NAME", order=1, pagefirst=1, pagelast=1, manuscript=self
                )

        # Possibly adapt the number of manuscripts for the associated library
        if self.library != None:
            mcount = Manuscript.objects.filter(library=self.library).count()
            if self.library.mcount != mcount:
                self.library.mcount = mcount
                self.library.save()

        # Return the response when saving
        return response

    def adapt_hierarchy():
        bResult = True
        msg = ""
        oErr = ErrHandle()

        # ========== provisionally ================
        method = "original"
        method = "msitem"   # "sermondescr"
        # =========================================
        try:
            count = Manuscript.objects.all().count()
            with transaction.atomic():
                # Walk all manuscripts
                for idx, manu in enumerate(Manuscript.objects.all()):
                    oErr.Status("Sermon # {}/{}".format(idx, count))
                    # Walk all sermons in this manuscript, in order
                    if method == "msitem":
                        qs = manu.manuitems.all().order_by('order')
                        for sermo in qs:
                            # Reset saving
                            bNeedSaving = False
                            # Check presence of 'firstchild' and 'next'
                            firstchild = manu.manuitems.filter(parent=sermo).order_by('order').first()
                            if sermo.firstchild != firstchild:
                                sermo.firstchild = firstchild
                                bNeedSaving = True
                            # Check for the 'next' one
                            next = manu.manuitems.filter(parent=sermo.parent, order__gt=sermo.order).order_by('order').first()
                            if sermo.next != next:
                                sermo.next = next
                                bNeedSaving = True
                            # If this needs saving, so do it
                            if bNeedSaving:
                                sermo.save()
                    else:
                        qs = manu.manusermons.all().order_by('order')
                        for sermo in qs:
                            # Reset saving
                            bNeedSaving = False
                            # Check presence of 'firstchild' and 'next'
                            firstchild = manu.manusermons.filter(parent=sermo).order_by('order').first()
                            if sermo.firstchild != firstchild:
                                sermo.firstchild = firstchild
                                bNeedSaving = True
                            # Check for the 'next' one
                            next = manu.manusermons.filter(parent=sermo.parent, order__gt=sermo.order).order_by('order').first()
                            if sermo.next != next:
                                sermo.next = next
                                bNeedSaving = True
                            # If this needs saving, so do it
                            if bNeedSaving:
                                sermo.save()
        except:
            msg = oErr.get_error_message()
            bResult = False
        return bResult, msg

    def add_codico_to_manuscript(self):
        bResult, msg = add_codico_to_manuscript(self)
        return bResult, msg

    def custom_add(oManu, **kwargs):
        """Add a manuscript according to the specifications provided"""

        oErr = ErrHandle()
        manu = None
        lst_msg = []

        try:
            profile = kwargs.get("profile")
            username = kwargs.get("username")
            team_group = kwargs.get("team_group")
            # First get the shelf mark
            idno = oManu.get('shelf mark')
            if idno == None:
                oErr.DoError("Manuscript/add_one: no [shelf mark] provided")
            else:
                # Get the standard project
                project = Project.get_default(username)
                # Retrieve or create a new manuscript with default values
                obj = Manuscript.objects.filter(idno=idno, mtype="man", project=project).first()
                if obj == None:
                    # Doesn't exist: create it
                    obj = Manuscript.objects.create(idno=idno, stype="imp", mtype="man", project=project)
                        
                # Process all fields in the Specification
                for oField in Manuscript.specification:
                    field = oField.get("name").lower()
                    value = oManu.get(field)
                    readonly = oField.get('readonly', False)
                    if value != None and value != "" and not readonly:
                        path = oField.get("path")
                        type = oField.get("type")
                        if type == "field":
                            # Set the correct field's value
                            setattr(obj, path, value)
                        elif type == "fk":
                            fkfield = oField.get("fkfield")
                            model = oField.get("model")
                            if fkfield != None and model != None:
                                # Find an item with the name for the particular model
                                cls = apps.app_configs['seeker'].get_model(model)
                                instance = cls.objects.filter(**{"{}".format(fkfield): value}).first()
                                if instance != None:
                                    setattr(obj, path, instance)
                        elif type == "func":
                            # Set the KV in a special way
                            obj.custom_set(path, value, **kwargs)

                # Make sure the update the object
                obj.save()
        except:
            msg = oErr.get_error_message()
            oErr.DoError("Manuscript/add_one")
        return obj

    def custom_get(self, path, **kwargs):
        sBack = ""
        oErr = ErrHandle()
        try:
            profile = kwargs.get("profile")
            username = kwargs.get("username")
            team_group = kwargs.get("team_group")

            if path == "keywords":
                sBack = self.get_keywords_markdown(plain=True)
            elif path == "keywordsU":
                sBack =  self.get_keywords_user_markdown(profile, plain=True)
            elif path == "datasets":
                sBack = self.get_collections_markdown(username, team_group, settype="pd", plain=True)
            elif path == "literature":
                sBack = self.get_litrefs_markdown(plain=True)
            elif path == "external":
                sBack = self.get_external_markdown(plain=True)
            elif path == "brefs":
                sBack = self.get_bibleref(plain=True)
            elif path == "signaturesM":
                sBack = self.get_sermonsignatures_markdown(plain=True)
            elif path == "signaturesA":
                sBack = self.get_eqsetsignatures_markdown(plain=True)
            elif path == "ssglinks":
                sBack = self.get_eqset()
        except:
            msg = oErr.get_error_message()
            oErr.DoError("Manuscript/custom_get")
        return sBack

    def custom_getkv(self, item, **kwargs):
        """Get key and value from the manuitem entry"""

        oErr = ErrHandle()
        key = ""
        value = ""
        try:
            key = item['name']
            if self != None:
                if item['type'] == 'field':
                    value = getattr(self, item['path'])
                elif item['type'] == "fk":
                    fk_obj = getattr(self, item['path'])
                    if fk_obj != None:
                        value = getattr( fk_obj, item['fkfield'])
                elif item['type'] == 'func':
                    value = self.custom_get(item['path'], kwargs=kwargs)
                    # Adaptation for empty lists
                    if value == "[]": value = ""
        except:
            msg = oErr.get_error_message()
            oErr.DoError("Manuscript/custom_getkv")
        return key, value

    def custom_set(self, path, value, **kwargs):
        """Set related items"""

        bResult = True
        oErr = ErrHandle()
        try:
            profile = kwargs.get("profile")
            username = kwargs.get("username")
            team_group = kwargs.get("team_group")
            value_lst = []
            if isinstance(value, str) and value[0] != '[':
                value_lst = value.split(",")
                for idx, item in enumerate(value_lst):
                    value_lst[idx] = value_lst[idx].strip()
            if path == "keywordsU":
                # Get the list of keywords
                user_keywords = value_lst #  json.loads(value)
                for kw in user_keywords:
                    # Find the keyword
                    keyword = Keyword.objects.filter(name__iexact=kw).first()
                    if keyword != None:
                        # Add this keyword to the manuscript for this user
                        UserKeyword.objects.create(keyword=keyword, profile=profile, manu=self)
                # Ready
            elif path == "datasets":
                # Walk the personal datasets
                datasets = value_lst #  json.loads(value)
                for ds_name in datasets:
                    # Get the actual dataset
                    collection = Collection.objects.filter(name=ds_name, owner=profile, type="manu", settype="pd").first()
                    # Does it exist?
                    if collection == None:
                        # Create this set
                        collection = Collection.objects.create(name=ds_name, owner=profile, type="manu", settype="pd")
                    # Add manuscript to collection
                    highest = CollectionMan.objects.filter(collection=collection).order_by('-order').first()
                    if highest != None and highest.order >= 0:
                        order = highest.order + 1
                    else:
                        order = 1
                    CollectionMan.objects.create(collection=collection, manuscript=self, order=order)
                # Ready
            elif path == "literature":
                # Go through the items to be added
                litrefs_full = value_lst #  json.loads(value)
                for litref_full in litrefs_full:
                    # Divide into pages
                    arLitref = litref_full.split(", pp")
                    litref_short = arLitref[0]
                    pages = ""
                    if len(arLitref)>1: pages = arLitref[1].strip()
                    # Find the short reference
                    litref = Litref.objects.filter(short__iexact = litref_short).first()
                    if litref != None:
                        # Create an appropriate LitrefMan object
                        obj = LitrefMan.objects.create(reference=litref, manuscript=self, pages=pages)
                # Ready
            elif path == "external":
                link_names = value_lst #  json.loads(value)
                for link_name in link_names:
                    # Create this stuff
                    ManuscriptExt.objects.create(manuscript=self, url=link_name)
                # Ready
            else:
                # Figure out what to do in this case
                pass
        except:
            msg = oErr.get_error_message()
            oErr.DoError("Manuscript/custom_set")
            bResult = False
        return bResult

    def find_sermon(self, oDescr):
        """Find a sermon within a manuscript"""

        oErr = ErrHandle()
        sermon = None
        take_author = False
        method = "msitem"   # "sermondescr"
        try:
            lstQ = []
            if 'title' in oDescr: lstQ.append(Q(title__iexact=oDescr['title']))
            if 'location' in oDescr: lstQ.append(Q(locus__iexact=oDescr['location']))
            if 'incipit' in oDescr: lstQ.append(Q(incipit__iexact=oDescr['incipit']))
            if 'explicit' in oDescr: lstQ.append(Q(explicit__iexact=oDescr['explicit']))
            if 'quote' in oDescr: lstQ.append(Q(quote__iexact=oDescr['quote']))

            # Do *not* take the author into account, since he may have been initially stored
            #   in 'note', and later on replaced by someone else
            if take_author and 'author' in oDescr: 
                lstQ.append(Q(note__icontains=oDescr['author']))

            # Find all the SermanMan objects that point to a sermon with the same characteristics I have
            if method == "msitem":
                lstQ.append(Q(msitem__manu=self))
                sermon = SermonDescr.objects.filter(*lstQ).first()
            else:
                sermon = self.manusermons.filter(*lstQ).first()

            # Return the sermon instance
            return sermon
        except:
            sMsg = oErr.get_error_message()
            oErr.DoError("Manuscript/find_sermon")
            return None

    def find_or_create(name,yearstart, yearfinish, library, idno="", 
                       filename=None, url="", support = "", extent = "", format = "", source=None, stype=STYPE_IMPORTED):
        """Find an existing manuscript, or create a new one"""

        oErr = ErrHandle()
        try:
            lstQ = []
            lstQ.append(Q(name=name))
            lstQ.append(Q(yearstart=yearstart))
            lstQ.append(Q(yearfinish=yearfinish))
            lstQ.append(Q(library=library))
            # Ideally take along the idno too
            if idno != "": lstQ.append(Q(idno=idno))
            qs = Manuscript.objects.filter(*lstQ)
            if qs.count() == 0:
                # Note: do *NOT* let the place of origin play a role in locating the manuscript
                manuscript = Manuscript(name=name, yearstart=yearstart, yearfinish=yearfinish, library=library )
                if idno != "": manuscript.idno = idno
                if filename != None: manuscript.filename = filename
                if support != "": manuscript.support = support
                if extent != "": manuscript.extent = extent
                if format != "": manuscript.format = format
                # NOTE: the URL is no longer saved as part of the manuscript - it is part of ManuscriptExt
                # EXTINCT: if url != "": manuscript.url = url
                if source != None: manuscript.source=source
                manuscript.stype = stype
                manuscript.save()
            else:
                manuscript = qs[0]
                # Check if any fields need to be adapted
                bNeedSave = False
                if name != manuscript.name: 
                    manuscript.name = name ; bNeedSave = True
                if filename != manuscript.filename: 
                    manuscript.filename = filename ; bNeedSave = True
                if support != manuscript.support: 
                    manuscript.support = support ; bNeedSave = True
                if extent != manuscript.extent: 
                    manuscript.extent = extent ; bNeedSave = True
                if format != manuscript.format: 
                    manuscript.format = format ; bNeedSave = True
                if url != manuscript.url: 
                    manuscript.url = url ; bNeedSave = True
                if bNeedSave:
                    if source != None: manuscript.source=source
                    manuscript.save()
            return manuscript
        except:
            sMsg = oErr.get_error_message()
            oErr.DoError("Manuscript/find_or_create")
            return None

    def get_city(self):
        city = "-"
        oErr = ErrHandle()
        try:
            if self.lcity:
                city = self.lcity.name
                if self.library and self.library.lcity != None and self.library.lcity.id != self.lcity.id and self.library.location != None:
                    # OLD: city = self.library.lcity.name
                    city = self.library.location.get_loc_name()
            elif self.library != None and self.library.lcity != None:
                city = self.library.lcity.name
        except:
            msg = oErr.get_error_message()
            oErr.DoError("get_city")
        return city

    def get_collections_markdown(self, username, team_group, settype = None, plain=False):

        lHtml = []
        # Visit all collections that I have access to
        mycoll__id = Collection.get_scoped_queryset('manu', username, team_group, settype = settype).values('id')
        for col in self.collections.filter(id__in=mycoll__id).order_by('name'):
            if plain:
                lHtml.append(col.name)
            else:
                url = "{}?manu-collist_m={}".format(reverse('manuscript_list'), col.id)
                lHtml.append("<span class='collection'><a href='{}'>{}</a></span>".format(url, col.name))
        if plain:
            sBack = json.dumps(lHtml)
        else:
            sBack = ", ".join(lHtml)
        return sBack

    def get_country(self):
        country = "-"
        oErr = ErrHandle()
        try:
            if self.lcountry:
                country = self.lcountry.name
                if self.library != None and self.library.lcountry != None and self.library.lcountry.id != self.lcountry.id:
                    country = self.library.lcountry.name
            elif self.library != None and self.library.lcountry != None:
                country = self.library.lcountry.name
        except:
            msg = oErr.get_error_message()
            oErr.DoError("get_country")
        return country

    def get_date_markdown(self):
        """Get the date ranges as a HTML string"""

        lhtml = []
        # Get all the date ranges in the correct order
        qs = self.manuscript_dateranges.all().order_by('yearstart')
        # Walk the date range objects
        for obj in qs:
            # Determine the output for this one daterange
            ref = ""
            if obj.reference: 
                if obj.pages: 
                    ref = " <span style='font-size: x-small;'>(see {}, {})</span>".format(obj.reference.get_full_markdown(), obj.pages)
                else:
                    ref = " <span style='font-size: x-small;'>(see {})</span>".format(obj.reference.get_full_markdown())
            if obj.yearstart == obj.yearfinish:
                years = "{}".format(obj.yearstart)
            else:
                years = "{}-{}".format(obj.yearstart, obj.yearfinish)
            item = "<div><span class='badge signature ot'>{}</span>{}</div>".format(years, ref)
            lhtml.append(item)

        return "\n".join(lhtml)

    def get_external_markdown(self, plain=False):
        lHtml = []
        for obj in self.manuscriptexternals.all().order_by('url'):
            url = obj.url
            if plain:
                lHtml.append(obj.url)
            else:
                lHtml.append("<span class='collection'><a href='{}'>{}</a></span>".format(obj.url, obj.url))
        if plain:
            sBack = json.dumps(lHtml)
        else:
            sBack = ", ".join(lHtml)
        return sBack

    def get_full_name(self):
        lhtml = []
        # (1) City
        if self.lcity != None:
            lhtml.append(self.lcity.name)
        elif self.library != None:
            lhtml.append(self.library.lcity.name)
        # (2) Library
        if self.library != None:
            lhtml.append(self.library.name)
        # (3) Idno
        if self.idno != None:
            lhtml.append(self.idno)

        # What if we don't have anything?
        if len(lhtml) == 0:
            lhtml.append("Unnamed [id={}]".format(self.id))

        return ", ".join(lhtml)

    def get_keywords_markdown(self, plain=False):
        lHtml = []
        # Visit all keywords
        for keyword in self.keywords.all().order_by('name'):
            if plain:
                lHtml.append(keyword.name)
            else:
                # Determine where clicking should lead to
                url = "{}?manu-kwlist={}".format(reverse('manuscript_list'), keyword.id)
                # Create a display for this topic
                lHtml.append("<span class='keyword'><a href='{}'>{}</a></span>".format(url,keyword.name))

        if plain:
            sBack = json.dumps(lHtml)
        else:
            sBack = ", ".join(lHtml)
        return sBack

    def get_keywords_user_markdown(self, profile, plain=False):
        lHtml = []
        # Visit all keywords
        for kwlink in self.manu_userkeywords.filter(profile=profile).order_by('keyword__name'):
            keyword = kwlink.keyword
            if plain:
                lHtml.append(keyword.name)
            else:
                # Determine where clicking should lead to
                url = "{}?manu-ukwlist={}".format(reverse('manuscript_list'), keyword.id)
                # Create a display for this topic
                lHtml.append("<span class='keyword'><a href='{}'>{}</a></span>".format(url,keyword.name))

        if plain:
            sBack = json.dumps(lHtml)
        else:
            sBack = ", ".join(lHtml)
        return sBack

    def get_library(self):
        if self.library:
            lib = self.library.name
        else:
            lib = "-"
        return lib

    def get_library_markdown(self):
        sBack = "-"
        if self.library != None:
            lib = self.library.name
            url = reverse('library_details', kwargs={'pk': self.library.id})
            sBack = "<span class='badge signature ot'><a href='{}'>{}</a></span>".format(url, lib)
        return sBack

    def get_litrefs_markdown(self, plain=False):
        lHtml = []
        # Visit all literature references
        for litref in self.manuscript_litrefs.all().order_by('reference__short'):
            if plain:
                lHtml.append(litref.get_short_markdown())
            else:
                # Determine where clicking should lead to
                url = "{}#lit_{}".format(reverse('literature_list'), litref.reference.id)
                # Create a display for this item
                lHtml.append("<span class='badge signature cl'><a href='{}'>{}</a></span>".format(url,litref.get_short_markdown()))

        if plain:
            sBack = json.dumps(lHtml)
        else:
            sBack = ", ".join(lHtml)
        return sBack

    def get_origin(self):
        sBack = "-"
        if self.origin:
            # Just take the bare name of the origin
            sBack = self.origin.name
            if self.origin.location:
                # Add the actual location if it is known
                sBack = "{}: {}".format(sBack, self.origin.location.get_loc_name())
        return sBack

    def get_origin_markdown(self):
        sBack = "-"
        if self.origin:
            # Just take the bare name of the origin
            sBack = self.origin.name
            if self.origin.location:
                # Add the actual location if it is known
                sBack = "{}: {}".format(sBack, self.origin.location.get_loc_name())
            # Get the url to it
            url = reverse('origin_details', kwargs={'pk': self.origin.id})
            # Adapt what we return
            sBack = "<span class='badge signature ot'><a href='{}'>{}</a></span>".format(url, sBack)
        return sBack

    def get_project(self):
        sBack = "-" if self.project == None else self.project.name
        return sBack

    def get_project_markdown(self):
        sBack = "-"
        if self.project:
            sBack = '<span class="project">{}</span>'.format(self.project.name)
        return sBack

    def get_provenance_markdown(self, plain=False, table=True):
        lHtml = []
        # Visit all literature references
        # Issue #289: this was self.provenances.all()
        #             now back to self.provenances.all()
        order = 0
        if not plain: 
            if table: lHtml.append("<table><tbody>")
        # for prov in self.provenances.all().order_by('name'):
        for mprov in self.manuscripts_provenances.all().order_by('provenance__name'):
            order += 1
            # Get the URL
            prov = mprov.provenance
            url = reverse("provenance_details", kwargs = {'pk': prov.id})
            sNote = mprov.note
            if sNote == None: sNote = ""

            if not plain: 
                if table: lHtml.append("<tr><td valign='top'>{}</td>".format(order))

            sLocName = "" 
            if prov.location!=None:
                if plain:
                    sLocName = prov.location.name
                else:
                    sLocName = " ({})".format(prov.location.name)
            sName = "-" if prov.name == "" else prov.name
            sLoc = "{} {}".format(sName, sLocName)

            if plain:
                sMprov = dict(prov=prov.name, location=sLocName)
            else:
                sProvLink = "<span class='badge signature gr'><a href='{}'>{}</a></span>".format(url, sLoc)
                if table:
                    sMprov = "<td class='tdnowrap nostyle' valign='top'>{}</td><td valign='top'>{}</td></tr>".format(
                        sProvLink, sNote)
                else:
                    sMprov = sProvLink

            lHtml.append(sMprov)

        if not plain: 
            if table: lHtml.append("</tbody></table>")
        if plain:
            sBack = json.dumps(lHtml)
        else:
            # sBack = ", ".join(lHtml)
            sBack = "".join(lHtml)
        return sBack

    def get_sermon_count(self):
        method = "msitem"   # "sermondescr"
        if method == "msitem":
            count = SermonDescr.objects.filter(msitem__manu=self).count()
        else:
            count = self.manusermons.all().count()
        return count

    def get_sermon_list(self, username, team_group):
        """Create a list of sermons with hierarchical information"""

        oErr = ErrHandle()
        sermon_list = []
        maxdepth = 0
        msitem_dict = {}

        method = "sermondescr"  # OLD: each manuscript had a number of SermonDescr directly

        if self.mtype == "rec":
            method = "codicos"      # NEW: Take codicological units as a starting point
        else:
            method = "msitem"       # CURRENT: there is a level of [MsItem] between Manuscript and SermonDescr/SermonHead

        try:
            # Create a well sorted list of sermons
            if method == "msitem":
                qs = self.manuitems.filter(order__gte=0).order_by('order')
            elif method == "codicos":
                # Look for the Reconstruction codico's
                codico_lst = [x['codico__id'] for x in self.manuscriptreconstructions.order_by('order').values('codico__id')]
                # Create a list of MsItem objects that belong to this reconstruction manuscript
                qs = []
                for codico_id in codico_lst:
                    codico = Codico.objects.filter(id=codico_id).first()
                    for obj in MsItem.objects.filter(codico__id=codico_id, order__gte=0).order_by('order'):
                        qs.append(obj)
                        # Make sure to put this MsItem in the dictionary with the right Codico target
                        msitem_dict[obj.id] = codico
            prev_level = 0
            for idx, sermon in enumerate(qs):
                # Need this first, because it also REPAIRS possible parent errors
                level = sermon.getdepth()

                parent = sermon.parent
                firstchild = False
                if parent:
                    if method == "msitem":
                        qs_siblings = self.manuitems.filter(parent=parent).order_by('order')
                    elif method == "codicos":
                        # N.B: note that 'sermon' is not really a sermon but the MsItem
                        qs_siblings = msitem_dict[sermon.id].codicoitems.filter(parent=parent).order_by('order')
                    if sermon.id == qs_siblings.first().id:
                        firstchild = True

                # Only then continue!
                oSermon = {}
                if method == "msitem" or method == "codicos":
                    # The 'obj' always is the MsItem itself
                    oSermon['obj'] = sermon
                    # Now we need to add a reference to the actual SermonDescr object
                    oSermon['sermon'] = sermon.itemsermons.first()
                    # And we add a reference to the SermonHead object
                    oSermon['shead'] = sermon.itemheads.first()
                oSermon['nodeid'] = sermon.order + 1
                oSermon['number'] = idx + 1
                oSermon['childof'] = 1 if sermon.parent == None else sermon.parent.order + 1
                oSermon['level'] = level
                oSermon['pre'] = (level-1) * 20
                # If this is a new level, indicate it
                oSermon['group'] = firstchild   # (sermon.firstchild != None)
                # Is this one a parent of others?
                if method == "msitem" or method == "codicos":
                    if method == "msitem":
                        oSermon['isparent'] = self.manuitems.filter(parent=sermon).exists()
                    elif method == "codicos":
                        oSermon['isparent'] = msitem_dict[sermon.id].codicoitems.filter(parent=sermon).exists()
                    codi = sermon.get_codistart()
                    oSermon['codistart'] = "" if codi == None else codi.id
                    oSermon['codiorder'] = -1 if codi == None else codi.order

                # Add the user-dependent list of associated collections to this sermon descriptor
                oSermon['hclist'] = [] if oSermon['sermon'] == None else oSermon['sermon'].get_hcs_plain(username, team_group)

                sermon_list.append(oSermon)
                # Bookkeeping
                if level > maxdepth: maxdepth = level
                prev_level = level
            # Review them all and fill in the colspan
            for oSermon in sermon_list:
                oSermon['cols'] = maxdepth - oSermon['level'] + 1
                if oSermon['group']: oSermon['cols'] -= 1
        except:
            msg = oErr.get_error_message()
            oErr.DoError("Manuscript/get_sermon_list")
        
            # Return the result
        return sermon_list

    def get_stype_light(self, usercomment=False):
        count = 0
        if usercomment:
            count = self.comments.count()
        sBack = get_stype_light(self.stype, usercomment, count)
        return sBack

    def get_ssg_count(self, compare_link=False, collection = None):
        # Get a list of all SSGs related to [self]
        ssg_list_num = EqualGold.objects.filter(sermondescr_super__sermon__msitem__manu=self).order_by('id').distinct().count()
        if compare_link:
            url = "{}?manu={}".format(reverse("collhist_compare", kwargs={'pk': collection.id}), self.id)
            sBack = "<span class='clickable'><a class='nostyle' href='{}'>{}</a></span>".format(url, ssg_list_num)
        else:
            sBack = "<span>{}</span>".format(ssg_list_num)
        # Return the combined information
        return sBack

    def get_ssg_markdown(self):
        # Get a list of all SSGs related to [self]
        ssg_list = EqualGold.objects.filter(sermondescr_super__sermon__msitem__manu=self).order_by('id').distinct().order_by('code')
        html = []
        for ssg in ssg_list:
            url = reverse('equalgold_details', kwargs={'pk': ssg.id})
            code = ssg.code if ssg.code else "(ssg_{})".format(ssg.id)
            # Add a link to this SSG in the list
            html.append("<span class='passimlink'><a href='{}'>{}</a></span>".format(url, code))
        sBack = ", ".join(html)
        # Return the combined information
        return sBack

    def get_template_link(self, profile):
        sBack = ""
        # Check if I am a template
        if self.mtype == "tem":
            # add a clear TEMPLATE indicator with a link to the actual template
            template = Template.objects.filter(manu=self).first()
            # Wrong: template = Template.objects.filter(manu=self, profile=profile).first()
            # (show template even if it is not my own one)
            if template:
                url = reverse('template_details', kwargs={'pk': template.id})
                sBack = "<div class='template_notice'>THIS IS A <span class='badge'><a href='{}'>TEMPLATE</a></span></div>".format(url)
        return sBack

    def get_manutemplate_copy(self, mtype = "tem", profile=None, template=None):
        """Create a copy of myself: 
        
        - either as 'template' 
        - or as plain 'manuscript'
        """

        repair = ['parent', 'firstchild', 'next']
        # Get a link to myself and save it to create a new instance
        # See: https://docs.djangoproject.com/en/2.2/topics/db/queries/#copying-model-instances
        obj = self
        manu_id = self.id
        obj.pk = None
        obj.mtype = mtype   # Change the type
        obj.stype = "imp"   # Imported
        # Actions to perform before saving a new template
        if mtype == "tem":
            obj.notes = ""
        # Save the results
        obj.save()
        manu_src = Manuscript.objects.filter(id=manu_id).first()
        # Note: this doesn't copy relations that are not part of Manuscript proper

        # Copy all the sermons:
        # obj.load_sermons_from(manu_src, mtype="man", profile=profile)
        obj.load_sermons_from(manu_src, mtype=mtype, profile=profile)

        # Make sure the body of [obj] works out correctly
        if mtype != "tem":
            # This is only done for the creation of manuscripts from a template
            obj.import_template_adapt(template, profile)

        # Return the new object
        return obj

    def import_template_adapt(self, template, profile, notes_only=False):
        """Adapt a manuscript after importing from template"""

        manu_clear_fields = ['name', 'idno', 'filename', 'url', 'support', 'extent', 'format']
        manu_none_fields = ['library', 'lcity', 'lcountry', 'origin']
        oErr = ErrHandle()
        try:
            # Issue #314: add note "created from template" to this manuscript
            sNoteText = self.notes
            sDate = get_current_datetime().strftime("%d/%b/%Y %H:%M")
            if sNoteText == "" or sNoteText == None:
                if notes_only:
                    sNoteText = "Added sermons from template [{}] on {}".format(template.name, sDate)
                else:
                    sNoteText = "Created from template [{}] on {}".format(template.name, sDate)
            else:
                sNoteText = "{}. Added sermons from template [{}] on {}".format(sNoteText, template.name, sDate)
            self.notes = sNoteText

            if not notes_only:
                # Issue #316: clear a number of fields
                for field in manu_clear_fields:
                    setattr(self, field, "")
                for field in manu_none_fields:
                    setattr(self, field, None)

            # Make sure to save the result
            self.save()

            if not notes_only:
                # Issue #315: copy manuscript keywords
                for kw in self.keywords.all():
                    mkw = ManuscriptKeyword.objects.create(manuscript=self, keyword=kw.keyword)

        except:
            msg = oErr.get_error_message()
            oErr.DoError("Manuscript/import_template_adapt")

        return True

    def import_template(self, template, profile):
        """Import the information in [template] into the manuscript [self]"""

        oErr = ErrHandle()
        try:
            # Get the source manuscript
            manu_src = template.manu

            # Copy the sermons from [manu_src] into [self]
            # NOTE: only if there are no sermons in [self] yet!!!!
            if self.manuitems.count() == 0:
                self.load_sermons_from(manu_src, mtype="man", profile=profile)

            # Adapt the manuscript itself
            self.import_template_adapt(template, profile, notes_only = True)
        except:
            msg = oErr.get_error_message()
            oErr.DoError("Manuscript/import_template")

        # Return myself again
        return self

    def load_sermons_from(self, manu_src, mtype = "tem", profile=None):
        """Copy sermons from [manu_src] into myself"""

        # Indicate what the destination manuscript object is
        manu_dst = self
        repair = ['parent', 'firstchild', 'next']

        # copy all the sermons...
        msitems = []
        with transaction.atomic():
            # Walk over all MsItem stuff
            for msitem in manu_src.manuitems.all().order_by('order'):
                dst = msitem
                src_id = msitem.id
                dst.pk = None
                dst.manu = manu_dst     # This sets the destination's FK for the manuscript
                                        # Does this leave the original unchanged? I hope so...:)
                dst.save()
                src = MsItem.objects.filter(id=src_id).first()
                msitems.append(dict(src=src, dst=dst))

        # Repair all the relationships from sermon to sermon
        with transaction.atomic():
            for msitem in msitems:
                src = msitem['src']
                dst = msitem['dst']  
                # Repair 'parent', 'firstchild' and 'next', which are part of MsItem
                for relation in repair:
                    src_rel = getattr(src, relation)
                    if src_rel and src_rel.order:
                        # Retrieve the target MsItem from the [manu_dst] by looking for the order number!!
                        relation_target = manu_dst.manuitems.filter(order=src_rel.order).first()
                        # Correct the MsItem's [dst] field now
                        setattr(dst, relation, relation_target)
                        dst.save()
                # Copy and save a SermonDescr if needed
                sermon_src = src.itemsermons.first()
                if sermon_src != None:
                    # COpy it
                    sermon_dst = sermon_src
                    sermon_dst.pk = None
                    sermon_dst.msitem = dst
                    sermon_dst.mtype = mtype   # Change the type
                    sermon_dst.stype = "imp"   # Imported

                    # Issue #315: clear some fields after copying
                    if mtype == "man":
                        sermon_dst.locus = ""
                        sermon_dst.additional = ""

                    # Save the copy
                    sermon_dst.save()
                else:
                    head_src = src.itemheads.first()
                    if head_src != None:
                        # COpy it
                        head_dst = head_src
                        head_dst.pk = None
                        head_dst.msitem = dst
                        # NOTE: a SermonHead does *not* have an mtype or stype

                        # Save the copy
                        head_dst.save()

        # Walk the msitems again, and make sure SSG-links are copied!!
        with transaction.atomic():
            for msitem in msitems:
                src = msitem['src']
                dst = msitem['dst']  
                sermon_src = src.itemsermons.first()
                if sermon_src != None:
                    # Make sure we also have the destination
                    sermon_dst = dst.itemsermons.first()
                    # Walk the SSG links tied with sermon_src
                    for eq in sermon_src.equalgolds.all():
                        # Add it to the destination sermon
                        SermonDescrEqual.objects.create(sermon=sermon_dst, super=eq, linktype=LINK_UNSPECIFIED)

                    # Issue #315: adapt Bible reference(s) linking based on copied field
                    if mtype == "man":
                        sermon_dst.adapt_verses()

                    # Issue #315 note: 
                    #   this is *NOT* working, because templates do not contain 
                    #     keywords nor do they contain Gryson/Clavis codes
                    #   Alternative: 
                    #     Store the keywords and signatures in a special JSON field in the template
                    #     Then do the copying based on this JSON field
                    #     Look at Manuscript.custom_...() procedures to see how this goes
                    # ===============================================================================

                    ## Issue #315: copy USER keywords - only if there is a profile
                    #if profile != None:
                    #    for ukw in sermon_src.sermo_userkeywords.all():
                    #        # Copy the user-keyword to a new one attached to [sermon_dst]
                    #        keyword = UserKeyword.objects.create(
                    #            keyword=ukw.keyword, sermo=sermon_dst, type=ukw.type, profile=profile)
                    ## Copy KEYWORDS per sermon
                    #for kw in sermon_src.keywords.all():
                    #    skw = SermonDescrKeyword.objects.create(sermon=sermon_dst, keyword=kw.keyword)

                    ## Issue #315: copy manual Gryson/Clavis-codes
                    #for msig in sermon_src.sermonsignatures.all():
                    #    usig = SermonSignature.objects.create(
                    #        code=msig.code, editype=msig.editype, gsig=msig.gsig, sermon=sermon_dst)

        # Return okay
        return True

    def order_calculate(self):
        """Re-calculate the order of the MsItem stuff"""

        # Give them new order numbers
        order = 1
        with transaction.atomic():
            for msitem in self.manuitems.all().order_by('order'):
                if msitem.order != order:
                    msitem.order = order
                    msitem.save()
                order += 1
        return True

    def remove_orphans(self):
        """Remove orphan msitems"""

        lst_remove = []
        for msitem in self.manuitems.all():
            # Check if this is an orphan
            if msitem.sermonitems.count() == 0 and msitem.sermonhead.count() == 0:
                lst_remove.append(msitem.id)
        # Now remove them
        MsItem.objects.filter(id__in=lst_remove).delete()
        return True

    def read_ecodex(username, data_file, filename, arErr, xmldoc=None, sName = None, source=None):
        """Import an XML from e-codices with manuscript data and add it to the DB
        
        This approach makes use of MINIDOM (which is part of the standard xml.dom)
        """

        # Number to order all the items we read
        order = 0

        def read_msitem(msItem, oParent, lMsItem, level=0):
            """Recursively process one <msItem> and return in an object"""
        
            errHandle = ErrHandle()
            sError = ""
            nonlocal order
            
            level += 1
            order  += 1
            try:
                # Create a new item
                oMsItem = {}
                oMsItem['level'] = level
                oMsItem['order'] = order 
                oMsItem['childof'] = 0 if len(oParent) == 0 else oParent['order']

                # Already put it into the overall list
                lMsItem.append(oMsItem)

                # Check if we have a title
                if not 'title' in oMsItem:
                    # Perhaps we have a parent <msItem> that contains a title
                    parent = msItem.parentNode
                    if parent.nodeName == "msItem":
                        # Check if this one has a title
                        if 'title' in parent.childNodes:
                            oMsItem['title'] = getText(parent.childNodes['title'])

                # If there is no author, then supply the default author (if that exists)
                if not 'author' in oMsItem and 'author' in oParent:
                    oMsItem['author'] = oParent['author']

                # Process all child nodes
                lastChild = None
                lAdditional = []
                for item in msItem.childNodes:
                    if item.nodeType == minidom.Node.ELEMENT_NODE:
                        # Get the tag name of this item
                        sTag = item.tagName
                        # Action depends on the tag
                        if sTag in mapItem:
                            oMsItem[mapItem[sTag]] = getText(item)
                        elif sTag == "note":
                            if not 'note' in oMsItem:
                                oMsItem['note'] = ""
                            oMsItem['note'] = oMsItem['note'] + getText(item) + " "
                        elif sTag == "msItem":
                            # This is another <msItem>, a child of mine
                            bResult, oChild, msg = read_msitem(item, oMsItem, lMsItem, level=level)
                            if bResult:
                                if 'firstChild' in oMsItem:
                                    lastChild['next'] = oChild
                                else:
                                    oMsItem['firstChild'] = oChild
                                    lastChild = oChild
                            else:
                                sError = msg
                                break
                        else:
                            # Add the text to 'additional'
                            sAdd = getText(item).strip()
                            if sAdd != "":
                                lAdditional.append(sAdd)
                # Process the additional stuff
                if len(lAdditional) > 0:
                    oMsItem['additional'] = " | ".join(lAdditional)
                # Return what we made
                return True, oMsItem, "" 
            except:
                if sError == "":
                    sError = errHandle.get_error_message()
                return False, None, sError

        def add_msitem(msItem, type="recursive"):
            """Add one item to the list of sermons for this manuscript"""

            errHandle = ErrHandle()
            sError = ""
            nonlocal iSermCount
            try:
                # Check if we already have this *particular* sermon (as part of this manuscript)
                sermon = manuscript.find_sermon(msItem)

                if sermon == None:
                    # Create a SermonDescr
                    sermon = SermonDescr()

                    if 'title' in msItem: sermon.title = msItem['title']
                    if 'location' in msItem: sermon.locus = msItem['location']
                    if 'incipit' in msItem: sermon.incipit = msItem['incipit']
                    if 'explicit' in msItem: sermon.explicit = msItem['explicit']
                    if 'quote' in msItem: sermon.quote = msItem['quote']
                    if 'feast' in msItem: sermon.feast = msItem['feast']
                    if 'bibleref' in msItem: sermon.bibleref = msItem['bibleref']
                    if 'additional' in msItem: sermon.additional = msItem['additional']
                    if 'note' in msItem: sermon.note = msItem['note']
                    if 'order' in msItem: sermon.order = msItem['order']
                    if 'author' in msItem:
                        author = Author.find(msItem['author'])
                        if author == None:
                            # Create a nickname
                            nickname = Nickname.find_or_create(msItem['author'])
                            sermon.nickname = nickname
                        else:
                            sermon.author = author

                    # The following items are [0-n]
                    #  -- These may be replaced by separate entries in SermonSignature
                    if 'gryson' in msItem: sermon.gryson = msItem['gryson']     # SermonSignature
                    if 'clavis' in msItem: sermon.clavis = msItem['clavis']     # SermonSignature
                    if 'keyword' in msItem: sermon.keyword = msItem['keyword']  # Keyword
                    if 'edition' in msItem: sermon.edition = msItem['edition']  # Edition

                    if 'feast' in msItem: 
                        # Get object that is being referred to
                        sermon.feast = Feast.get_one(msItem['feast'])
                    if sermon.bibleref != None and sermon.biblref != "": 
                        # Calculate and set BibRange and BibVerse objects
                        sermon.do_ranges()

                    # Set the default status type
                    sermon.stype = STYPE_IMPORTED    # Imported

                    # Set my parent manuscript
                    sermon.manu = manuscript

                    # Now save it
                    sermon.save()

                    # Keep track of the number of sermons added
                    iSermCount += 1
                else:
                    # DEBUG: There already exists a sermon
                    # So there is no need to add it

                    # Sanity check: the order of the sermon we found may *NOT* be lower than that in msItem
                    if sermon.order < msItem['order']:
                        bStop = True

                    # However: double check the fields
                    bNeedSaving = False

                    if 'title' in msItem and sermon.title != msItem['title']: sermon.title = msItem['title'] ; bNeedSaving = True
                    if 'location' in msItem and sermon.locus != msItem['location']: sermon.locus = msItem['location'] ; bNeedSaving = True
                    if 'incipit' in msItem and sermon.incipit != msItem['incipit']: sermon.incipit = msItem['incipit'] ; bNeedSaving = True
                    if 'explicit' in msItem and sermon.explicit != msItem['explicit']: sermon.explicit = msItem['explicit'] ; bNeedSaving = True
                    if 'edition' in msItem and sermon.edition != msItem['edition']: sermon.edition = msItem['edition'] ; bNeedSaving = True
                    if 'quote' in msItem and sermon.quote != msItem['quote']: sermon.quote = msItem['quote'] ; bNeedSaving = True
                    if 'gryson' in msItem and sermon.gryson != msItem['gryson']: sermon.gryson = msItem['gryson'] ; bNeedSaving = True
                    if 'clavis' in msItem and sermon.clavis != msItem['clavis']: sermon.clavis = msItem['clavis'] ; bNeedSaving = True
                    if 'feast' in msItem and sermon.feast != msItem['feast']: sermon.feast = Feast.get_one(msItem['feast']) ; bNeedSaving = True
                    if 'keyword' in msItem and sermon.keyword != msItem['keyword']: sermon.keyword = msItem['keyword'] ; bNeedSaving = True
                    if 'bibleref' in msItem and sermon.bibleref != msItem['bibleref']: sermon.bibleref = msItem['bibleref'] ; bNeedSaving = True
                    if 'additional' in msItem and sermon.additional != msItem['additional']: sermon.additional = msItem['additional'] ; bNeedSaving = True
                    if 'note' in msItem and sermon.note != msItem['note']: sermon.note = msItem['note'] ; bNeedSaving = True
                    if 'order' in msItem and sermon.order != msItem['order']: sermon.order = msItem['order'] ; bNeedSaving = True
                    if 'author' in msItem and (    (sermon.author == None or sermon.author.name != msItem['author']) and
                                               (sermon.nickname == None or sermon.nickname != msItem['author'])):
                        author = Author.find(msItem['author'])
                        if author == None:
                            # Create a nickname
                            nickname = Nickname.find_or_create(msItem['author'])
                            sermon.nickname = nickname
                        else:
                            sermon.author = author
                        bNeedSaving = True

                    if sermon.bibleref != None and sermon.biblref != "": 
                        # Calculate and set BibRange and BibVerse objects
                        sermon.do_ranges()

                    if bNeedSaving:
                        # Now save it
                        sermon.save()

                # In all instances: link the sermon object to the msItem
                msItem['obj'] = sermon

                # Action depends on type
                if type=="recursive":
                    # If this [msItem] has a child, then treat it first
                    if 'firstChild' in msItem:
                        bResult, sermon_child, msg = add_msitem(msItem['firstChild'])
                        # Adapt the [sermon] to point to this child
                        sermon.firstchild = sermon_child
                        sermon.save()
                    # Do all the 'next' items
                    while 'next' in msItem:
                        bResult, sermon_next, msg = add_msitem(msItem['next'])
                        msItem = msItem['next']
                        # Adapt the [sermon] to point to this next one
                        sermon.next = sermon_next
                        sermon.save()

                # Return positively
                return True, sermon, ""
            except:
                if sError == "":
                    sError = errHandle.get_error_message()
                return False, None, sError


        oBack = {'status': 'ok', 'count': 0, 'msg': "", 'user': username}
        oInfo = {'city': '', 'library': '', 'manuscript': '', 'name': '', 'origPlace': '', 'origDateFrom': '', 'origDateTo': '', 'list': []}
        mapIdentifier = {'settlement': 'city', 'repository': 'library', 'idno': 'idno'}
        mapHead = {'title': 'name', 'origPlace': 'origPlace', 
                   'origDate': {'notBefore': "origDateFrom", 'notAfter': "origDateTo"}}
        mapPhys = {'support': 'support', 'extent': {'leavesCount': 'extent', 'pageDimensions': 'format'}}
        mapItem = {'locus': 'location', 'author': 'author', 'title': 'gryson', 'rubric': 'title', 
                   'incipit': 'incipit', 'explicit': 'explicit', 'quote': 'quote', 'bibl': 'edition'}
        ns = {'k': 'http://www.tei-c.org/ns/1.0'}
        errHandle = ErrHandle()
        iSermCount = 0

        # Overall keeping track of ms items
        lst_msitem = []

        try:
            # Make sure we have the data
            if xmldoc == None:
                # Read and parse the data into a DOM element
                xmldoc = minidom.parse(data_file)

            # Try to get an URL to this description
            url = ""
            ndTEI_list = xmldoc.getElementsByTagName("TEI")
            if ndTEI_list.length > 0:
                ndTEI = ndTEI_list[0]
                if "xml:base" in ndTEI.attributes:
                    url = ndTEI.attributes["xml:base"].value
            oInfo['url'] = url
            # Try to get a main author
            authors = xmldoc.getElementsByTagName("persName")
            mainAuthor = ""
            for person in authors:
                # Check if this is linked as author
                if 'role' in person.attributes and person.attributes['role'].value == "author":
                    mainAuthor = getText(person)
                    # Don't look further: the first author is the *main* author of it
                    break

            # Get the main title, to prevent it from remaining empty
            title_list = xmldoc.getElementsByTagName("titleStmt")
            if title_list.length > 0:
                # Get the first title
                title = title_list[0]
                oInfo['name'] = getText(title)

            # Get relevant information From the xml: the [fileDesc] element
            # /TEI/teiHeader/fileDesc/teiHeader/fileDesc/sourceDesc/msDesc
            # Alternative, but not needed: fdList = xmldoc.getElementsByTagNameNS(ns['k'], "fileDesc")
            fdList = xmldoc.getElementsByTagName("msDesc")
            if fdList.length > 0:
                msDesc = fdList[0]
                # (1) Find the 'msIdentifier' in here
                msIdents = msDesc.getElementsByTagName("msIdentifier")
                if msIdents.length > 0:
                    for item in msIdents[0].childNodes:
                        if item.nodeType == minidom.Node.ELEMENT_NODE:
                            # Get the tag name of this item
                            sTag = item.tagName
                            # Action depends on the tag
                            if sTag in mapIdentifier:
                                sInfo = mapIdentifier[sTag]
                                oInfo[sInfo] = getText(item)
                # (2) Find the 'head' in msDesc
                msHeads = msDesc.getElementsByTagName("head")
                if msHeads.length > 0:
                    # Only (!) look at the *FIRST* head if <msDesc> contains more than one
                    for item in msHeads[0].childNodes:
                        if item.nodeType == minidom.Node.ELEMENT_NODE:
                            # Get the tag name of this item
                            sTag = item.tagName
                            if sTag in mapHead:
                                # Action depends on the tag
                                oValue = mapHead[sTag]
                                if isinstance(oValue, str):
                                    oInfo[oValue] = getText(item)
                                else:
                                    # Get the attributes named in here
                                    for k, attr in oValue.items():
                                        # Get the named attribute
                                        oInfo[attr] = item.attributes[k].value
                # (3) Find the 'supportDesc' in msDesc
                msSupport = msDesc.getElementsByTagName("supportDesc")
                if msSupport.length > 0:
                    for item in msSupport[0].childNodes:
                        if item.nodeType == minidom.Node.ELEMENT_NODE:
                            # Get the tag name of this item
                            sTag = item.tagName
                            # Action depends on the tag
                            if sTag == "support":
                                oInfo['support'] = getText(item)
                            elif sTag == "extent":
                                # Look further into the <measure> children
                                for measure in item.childNodes:
                                    if measure.nodeType == minidom.Node.ELEMENT_NODE and measure.tagName == "measure":
                                        # Find out which type
                                        mType = measure.attributes['type'].value
                                        if mType == "leavesCount":
                                            oInfo['extent'] = getText(measure)
                                        elif mType == "pageDimensions":
                                            oInfo['format'] = getText(measure)

                # Set the method to process [msItem]
                itemProcessing = "recursive"
                lItems = []
                # order = 0

                # Action depends on the processing type
                if itemProcessing == "recursive":
                    # Get to the *first* (and only) [msContents] item
                    msContents = msDesc.getElementsByTagName("msContents")
                    for msOneCont in msContents:
                        for item in msOneCont.childNodes:
                            if item.nodeType == minidom.Node.ELEMENT_NODE and item.tagName == "msItem":
                                # Now we have one 'top-level' <msItem> instance
                                msItem = item
                                # Process this top-level item 
                                bResult, oMsItem, msg = read_msitem(msItem, {}, lst_msitem)
                                # Add to the list of items -- provided it is not empty
                                if len(oMsItem) > 0:
                                    lItems.append(oMsItem)

                else:
                    # (4) Walk all the ./msContents/msItem, which are the content items
                    msItems = msDesc.getElementsByTagName("msItem")

                    for msItem in msItems:
                        # Create a new item
                        oMsItem = {}
                        # Process all child nodes
                        for item in msItem.childNodes:
                            if item.nodeType == minidom.Node.ELEMENT_NODE:
                                # Get the tag name of this item
                                sTag = item.tagName
                                # Action depends on the tag
                                if sTag in mapItem:
                                    oMsItem[mapItem[sTag]] = getText(item)
                                elif sTag == "note":
                                    oMsItem['note'] = getText(item)
                        # Check if we have a title
                        if not 'title' in oMsItem:
                            # Perhaps we have a parent <msItem> that contains a title
                            parent = msItem.parentNode
                            if parent.nodeName == "msItem":
                                # Check if this one has a title
                                if 'title' in parent.childNodes:
                                    oMsItem['title'] = getText(parent.childNodes['title'])
                        # Try to find the author within msItem
                        authors = msItem.getElementsByTagName("persName")
                        for person in authors:
                            # Check if this is linked as author
                            if 'role' in person.attributes and person.attributes['role'].value == "author":
                                oMsItem['author'] = getText(person)
                                # Don't look further: the first author is the *best*
                                break
                        # If there is no author, then supply the default author (if that exists)
                        if not 'author' in oMsItem and mainAuthor != "":
                            oMsItem['author'] = mainAuthor

                        # Add to the list of items -- provided it is not empty
                        if len(msItem) > 0:
                            lItems.append(oMsItem)

                # Add to the info object
                oInfo['list'] = lItems

            lProvenances = []
            for hist in xmldoc.getElementsByTagName("history"):
                for item in hist.childNodes:
                    if item.nodeType == minidom.Node.ELEMENT_NODE:
                        # Get the tag name of this item
                        sTag = item.tagName
                        if sTag == "provenance":
                            orgName = ""
                            org = item.getElementsByTagName("orgName")
                            if org.length>0:
                                orgName = getText(org[0])
                            if orgName != "":
                                oProv = {'name': orgName, 'note': getText(item)}
                                lProvenances.append(oProv)
                        elif sTag == "origin":
                            orgText = getText(item)
                            for subitem in item.childNodes:
                                if subitem.nodeType == minidom.Node.ELEMENT_NODE:
                                    # places = item.childNodes[0].getElementsByTagName("placeName")
                                    places = subitem.getElementsByTagName("placeName")
                                    for place in places:
                                        oProv = {'name': getText(place), 'note': orgText}
                                        lProvenances.append(oProv)
                        elif sTag == "acquisition":
                            pass

            # Now [oInfo] has a full description of the contents to be added to the database
            # (1) Get the country from the city
            city = City.objects.filter(name__iexact=oInfo['city']).first()
            country = None 
            if city != None and city.country != None: country = city.country.name

            # (2) Get the library from the info object
            library = Library.find_or_create(oInfo['city'], oInfo['library'], country)

            # (3) Get or create place of origin: This should be placed into 'provenance'
            # origin = Origin.find_or_create(oInfo['origPlace'])
            if oInfo['origPlace'] == "":
                provenance_origin = None
            else:
                provenance_origin = Provenance.find_or_create(oInfo['origPlace'], note='origPlace')

            # (4) Get or create the Manuscript
            yearstart = oInfo['origDateFrom'] if oInfo['origDateFrom'] != "" else 1800
            yearfinish = oInfo['origDateTo'] if oInfo['origDateTo'] != "" else 2020
            support = "" if 'support' not in oInfo else oInfo['support']
            extent = "" if 'extent' not in oInfo else oInfo['extent']
            format = "" if 'format' not in oInfo else oInfo['format']
            idno = "" if 'idno' not in oInfo else oInfo['idno']
            url = oInfo['url']
            manuscript = Manuscript.find_or_create(oInfo['name'], yearstart, yearfinish, library, idno, filename, url, support, extent, format, source)

            # If there is an URL, then this is an external reference and it needs to be added separately
            if url != None and url != "":
                # There is an actual URL: Create a new ManuscriptExt instance
                mext = ManuscriptExt(url=url, manuscript=manuscript)
                mext.save()


            # Add all the provenances we know of
            if provenance_origin != None:
                pm = ProvenanceMan(provenance=provenance_origin, manuscript=manuscript)
                pm.save()
            for oProv in lProvenances:
                provenance = Provenance.find_or_create(oProv['name'], oProv['note'])
                pm = ProvenanceMan(provenance=provenance, manuscript=manuscript)
                pm.save()

            # (5) Create or emend all the manuscript content items
            # NOTE: doesn't work with transaction.atomic(), because need to find similar ones that include just-created-ones
            for msItem in lst_msitem:
                # emend or create the 'bare' bone of this item
                bResult, sermon, msg = add_msitem(msItem, type="bare")

            # (6) Make the relations clear
            with transaction.atomic():
                for msItem in lst_msitem:
                    # Check and emend the relations of this instance
                    instance = msItem['obj']
                    # Reset relations
                    instance.parent = None
                    instance.firstchild = None
                    instance.next = None    
                    # Add relations where appropriate
                    if 'childof' in msItem and msItem['childof']>0: 
                        instance.parent = lst_msitem[msItem['childof']-1]['obj']
                        if instance.parent.id == instance.id:
                            instance.parent = None
                    if 'firstChild' in msItem: 
                        instance.firstchild = msItem['firstChild']['obj']
                        if instance.firstchild.id == instance.id:
                            instance.firstchild = None
                    if 'next' in msItem: 
                        instance.next = msItem['next']['obj']
                        if instance.next.id == instance.id:
                            instance.next = None


                    instance.save()

            # Make sure the requester knows how many have been added
            oBack['count'] = 1              # Only one manuscript is added here
            oBack['sermons'] = iSermCount   # The number of sermons (=msitems) added
            oBack['name'] = oInfo['name']
            oBack['filename'] = filename
            oBack['obj'] = manuscript

        except:
            sError = errHandle.get_error_message()
            oBack['filename'] = filename
            oBack['status'] = 'error'
            oBack['msg'] = sError

        # Return the object that has been created
        return oBack
        

class Codico(models.Model):
    """A codicological unit is a physical part (or whole) of a Manuscript"""

    # [1] Name of the codicological unit (that is the TITLE)
    name = models.CharField("Name", max_length=LONG_STRING, default="SUPPLY A NAME")
    # [0-1] Notes field, which may be empty - see issue #298
    notes = models.TextField("Notes", null=True, blank=True)

    # PHYSICAL features of the manuscript (OPTIONAL)
    # [0-1] Support: the general type of manuscript
    support = models.TextField("Support", null=True, blank=True)
    # [0-1] Extent: the total number of pages
    extent = models.TextField("Extent", max_length=LONG_STRING, null=True, blank=True)
    # [0-1] Format: the size
    format = models.CharField("Format", max_length=LONG_STRING, null=True, blank=True)

    # [1] The order of this logical unit within the manuscript (for sorting)
    order = models.IntegerField("Order", default=0)
    # [1] The starting page of this unit
    pagefirst = models.IntegerField("First page", default=0)
    # [1] The finishing page of this unit
    pagelast = models.IntegerField("Last page", default=0)

    # =============== THese are the Minimum start and the Maximum finish =========================
    # [1] Date estimate: starting from this year
    yearstart = models.IntegerField("Year from", null=False, default=100)
    # [1] Date estimate: finishing with this year
    yearfinish = models.IntegerField("Year until", null=False, default=100)
    # =============================================================================================

    # [1] Every codicological unit has a status - this is *NOT* related to model 'Status'
    stype = models.CharField("Status", choices=build_abbr_list(STATUS_TYPE), max_length=5, default="man")
    # [0-1] Status note
    snote = models.TextField("Status note(s)", default="[]")
    # [1] And a date: the date of saving this manuscript
    created = models.DateTimeField(default=get_current_datetime)
    saved = models.DateTimeField(null=True, blank=True)

    # [0-1] If possible we need to know the original location of the codico
    origin = models.ForeignKey(Origin, null=True, blank=True, on_delete = models.SET_NULL, related_name="origin_codicos")
    # [0] One codicological unit can only belong to one particular manuscript
    manuscript = models.ForeignKey(Manuscript, on_delete = models.CASCADE, related_name="manuscriptcodicounits")

    # ============== MANYTOMANY connections
    # [m] Many-to-many: one codico can have a series of provenances
    provenances = models.ManyToManyField("Provenance", through="ProvenanceCod")
     # [m] Many-to-many: keywords per Codico
    keywords = models.ManyToManyField(Keyword, through="CodicoKeyword", related_name="keywords_codi")
    # [m] Many-to-many: one codico can have a series of user-supplied comments
    comments = models.ManyToManyField(Comment, related_name="comments_codi")

    # Scheme for downloading and uploading
    specification = [
        {'name': 'Status',              'type': 'field', 'path': 'stype',     'readonly': True},
        {'name': 'Title',               'type': 'field', 'path': 'name'},
        {'name': 'Date ranges',         'type': 'func',  'path': 'dateranges'},
        {'name': 'Support',             'type': 'field', 'path': 'support'},
        {'name': 'Extent',              'type': 'field', 'path': 'extent'},
        {'name': 'Format',              'type': 'field', 'path': 'format'},
        {'name': 'Origin',              'type': 'func',  'path': 'origin'},
        {'name': 'Provenances',         'type': 'func',  'path': 'provenances'},
        ]

    class Meta:
        verbose_name = "Codicological unit"
        verbose_name_plural = "Codicological units"

    def __str__(self):
        return self.manuscript.idno

    def save(self, force_insert = False, force_update = False, using = None, update_fields = None):
        # Adapt the save date
        self.saved = get_current_datetime()
        response = super(Codico, self).save(force_insert, force_update, using, update_fields)
        return response

    def delete(self, using = None, keep_parents = False):
        # Move the MsItem objects that are under me to the Codico that is before me
        manu = self.manuscript
        codi_first = manu.manuscriptcodicounits.all().order_by("order").first()
        if codi_first is self:
            # Can *NOT* remove the first codi
            return None
        for item in self.codicoitems.all():
            item.codico = codi_first
            item.save()

        # Note: don't touch Daterange, Keyword and Provenance -- those are lost when a codico is removed
        # (Unless the user wants this differently)

        # Perform the standard delete operation
        response = super(Codico, self).delete(using, keep_parents)
        # Return the correct response
        return response

    def custom_add(oCodico, **kwargs):
        """Add a codico according to the specifications provided"""

        oErr = ErrHandle()
        manu = None
        lst_msg = []

        try:
            profile = kwargs.get("profile")
            username = kwargs.get("username")
            team_group = kwargs.get("team_group")
            # First get the shelf mark
            manu = oCodico.get('manuscript')
            if manu == None:
                oErr.DoError("Codico/add_one: no [manuscript] provided")
            else:
                # Retrieve or create a new codico with default values
                obj = Codico.objects.filter(manuscript=manu).first()
                if obj == None:
                    # Doesn't exist: create it
                    obj = Codico.objects.create(manuscript=manu, stype="imp")
                        
                # Process all fields in the Specification
                for oField in Codico.specification:
                    field = oField.get("name").lower()
                    value = oCodico.get(field)
                    readonly = oField.get('readonly', False)
                    if value != None and value != "" and not readonly:
                        path = oField.get("path")
                        type = oField.get("type")
                        if type == "field":
                            # Set the correct field's value
                            setattr(obj, path, value)
                        elif type == "fk":
                            fkfield = oField.get("fkfield")
                            model = oField.get("model")
                            if fkfield != None and model != None:
                                # Find an item with the name for the particular model
                                cls = apps.app_configs['seeker'].get_model(model)
                                instance = cls.objects.filter(**{"{}".format(fkfield): value}).first()
                                if instance != None:
                                    setattr(obj, path, instance)
                        elif type == "func":
                            # Set the KV in a special way
                            obj.custom_set(path, value, **kwargs)

                # Make sure the update the object
                obj.save()
        except:
            msg = oErr.get_error_message()
            oErr.DoError("Codico/add_one")
        return obj

    def custom_get(self, path, **kwargs):
        sBack = ""
        oErr = ErrHandle()
        try:
            profile = kwargs.get("profile")
            username = kwargs.get("username")
            team_group = kwargs.get("team_group")
            if path == "dateranges":
                qs = self.codico_dateranges.all().order_by('yearstart')
                dates = []
                for obj in qs:
                    dates.append(obj.__str__())
                sBack = json.dumps(dates)
            elif path == "origin":
                sBack = self.get_origin()
            elif path == "provenances":
                sBack = self.get_provenance_markdown(plain=True)
        except:
            msg = oErr.get_error_message()
            oErr.DoError("Codico/custom_get")
        return sBack

    def custom_getkv(self, item, **kwargs):
        """Get key and value from the manuitem entry"""

        oErr = ErrHandle()
        key = ""
        value = ""
        try:
            key = item['name']
            if self != None:
                if item['type'] == 'field':
                    value = getattr(self, item['path'])
                elif item['type'] == "fk":
                    fk_obj = getattr(self, item['path'])
                    if fk_obj != None:
                        value = getattr( fk_obj, item['fkfield'])
                elif item['type'] == 'func':
                    value = self.custom_get(item['path'], kwargs=kwargs)
                    # Adaptation for empty lists
                    if value == "[]": value = ""
        except:
            msg = oErr.get_error_message()
            oErr.DoError("Codico/custom_getkv")
        return key, value

    def custom_set(self, path, value, **kwargs):
        """Set related items"""

        bResult = True
        oErr = ErrHandle()
        try:
            profile = kwargs.get("profile")
            username = kwargs.get("username")
            team_group = kwargs.get("team_group")
            value_lst = []
            if isinstance(value, str) and value[0] != '[':
                value_lst = value.split(",")
                for idx, item in enumerate(value_lst):
                    value_lst[idx] = value_lst[idx].strip()
            if path == "dateranges":
                # TRanslate the string into a list
                dates = value_lst # json.loads(value)
                # Possibly add each item from the list, if it doesn't yet exist
                for date_item in dates:
                    years = date_item.split("-")
                    yearstart = years[0]
                    yearfinish = yearstart
                    if len(years) > 0: yearfinish = years[1]
                    obj = Daterange.objects.filter(codico=self, yearstart=yearstart, yearfinish=yearfinish).first()
                    if obj == None:
                        # Doesn't exist, so create it
                        obj = Daterange.objects.create(codico=self, yearstart=yearstart, yearfinish=yearfinish)
                # Ready
            elif path == "origin":
                if value != "" and value != "-":
                    # THere is an origin specified
                    origin = Origin.objects.filter(name__iexact=value).first()
                    if origin == None:
                        # Try find it through location
                        origin = Origin.objects.filter(location__name__iexact=value).first()
                    if origin == None:
                        # Indicate that we didn't find it in the notes
                        intro = ""
                        if self.notes != "": intro = "{}. ".format(self.notes)
                        self.notes = "{}Please set manually origin [{}]".format(intro, value)
                        self.save()
                    else:
                        # The origin can be tied to me
                        self.origin = origin
                        self.save()
                sBack = self.get_origin()
            elif path == "provenances":
                provenance_names = value_lst #  json.loads(value)
                for pname in provenance_names:
                    pname = pname.strip()
                    # Try find this provenance
                    prov_found = Provenance.objects.filter(name__iexact=pname).first()
                    if prov_found == None:
                        prov_found = Provenance.objects.filter(location__name__iexact=pname).first()
                    if prov_found == None:
                        # Indicate that we didn't find it in the notes
                        intro = ""
                        if self.notes != "": intro = "{}. ".format(self.notes)
                        self.notes = "{}Please set manually provenance [{}]".format(intro, pname)
                        self.save()
                    else:
                        # Make a copy of prov_found
                        provenance = Provenance.objects.create(
                            name=prov_found.name, location=prov_found.location)
                        # Make link between provenance and codico
                        ProvenanceCod.objects.create(codico=self, provenance=provenance, note="Automatically added Codico/custom_getkv")
                # Ready
            else:
                # Figure out what to do in this case
                pass
        except:
            msg = oErr.get_error_message()
            oErr.DoError("Codico/custom_set")
            bResult = False
        return bResult

    def get_date_markdown(self):
        """Get the date ranges as a HTML string"""

        lhtml = []
        # Get all the date ranges in the correct order
        qs = self.codico_dateranges.all().order_by('yearstart')
        # Walk the date range objects
        for obj in qs:
            # Determine the output for this one daterange
            ref = ""
            if obj.reference: 
                if obj.pages: 
                    ref = " <span style='font-size: x-small;'>(see {}, {})</span>".format(obj.reference.get_full_markdown(), obj.pages)
                else:
                    ref = " <span style='font-size: x-small;'>(see {})</span>".format(obj.reference.get_full_markdown())
            if obj.yearstart == obj.yearfinish:
                years = "{}".format(obj.yearstart)
            else:
                years = "{}-{}".format(obj.yearstart, obj.yearfinish)
            item = "<div><span class='badge signature ot'>{}</span>{}</div>".format(years, ref)
            lhtml.append(item)

        return "\n".join(lhtml)

    def get_full_name(self):
        sBack = "-"
        manu = self.manuscript
        if manu != None:
            sBack = "{}: {}".format( manu.get_full_name(), self.order)
        return sBack

    def get_identification(self):
        """Get a unique identification of myself
        
        Target output:
             manuscriptCity+Library+Identifier ‘_’ codico volgnummer ‘_’ beginpagina-eindpagina
        """

        sBack = ""
        combi = []
        # Look for the city+library+identifier
        combi.append(self.manuscript.get_full_name())
        # Possibly add codico order number
        if self.order:
            combi.append(str(self.order))

        # do *NOT* use the name (=title) of the codico
        #if self.name:
        #    combi.append(self.name)

        # Add the page-range
        if self.pagefirst > 0:
            if self.pagelast > 0 and self.pagelast > self.pagefirst:
                combi.append("{}-{}".format(self.pagefirst, self.pagelast))
            else:
                combi.append("p{}".format(self.pagefirst))

        # Combine it all
        sBack = "_".join(combi)
        return sBack

    def get_keywords_markdown(self, plain=False):
        lHtml = []
        # Visit all keywords
        for keyword in self.keywords.all().order_by('name'):
            if plain:
                lHtml.append(keyword.name)
            else:
                # Determine where clicking should lead to
                url = "{}?codi-kwlist={}".format(reverse('codico_list'), keyword.id)
                # Create a display for this topic
                lHtml.append("<span class='keyword'><a href='{}'>{}</a></span>".format(url,keyword.name))

        if plain:
            sBack = json.dumps(lHtml)
        else:
            sBack = ", ".join(lHtml)
        return sBack

    def get_manu_markdown(self):
        """Visualize manuscript with link for details view"""
        sBack = "-"
        manu = self.manuscript
        if manu != None and manu.idno != None:
            url = reverse("manuscript_details", kwargs={'pk': manu.id})
            sBack = "<span class='badge signature cl'><a href='{}'>{}</a></span>".format(url, manu.idno)
        return sBack

    def get_origin(self):
        sBack = "-"
        if self.origin:
            # Just take the bare name of the origin
            sBack = self.origin.name
            if self.origin.location:
                # Add the actual location if it is known
                sBack = "{}: {}".format(sBack, self.origin.location.get_loc_name())
        return sBack

    def get_origin_markdown(self):
        sBack = "-"
        if self.origin:
            # Just take the bare name of the origin
            sBack = self.origin.name
            if self.origin.location:
                # Add the actual location if it is known
                sBack = "{}: {}".format(sBack, self.origin.location.get_loc_name())
            # Get the url to it
            url = reverse('origin_details', kwargs={'pk': self.origin.id})
            # Adapt what we return
            sBack = "<span class='badge signature ot'><a href='{}'>{}</a></span>".format(url, sBack)
        return sBack

    def get_project_markdown(self):
        sBack = "-"
        if self.manuscript != None and self.manuscript.project != None:
            sBack = '<span class="project">{}</span>'.format(self.manuscript.project.name)
        return sBack

    def get_provenance_markdown(self, plain=False, table=True):
        lHtml = []
        # Visit all literature references
        order = 0
        if not plain: 
            if table: lHtml.append("<table><tbody>")
        # for prov in self.provenances.all().order_by('name'):
        for cprov in self.codico_provenances.all().order_by('provenance__name'):
            order += 1
            # Get the URL
            prov = cprov.provenance
            url = reverse("provenance_details", kwargs = {'pk': prov.id})
            sNote = cprov.note
            if sNote == None: sNote = ""

            if not plain: 
                if table: lHtml.append("<tr><td valign='top'>{}</td>".format(order))

            sLocName = "" 
            if prov.location!=None:
                if plain:
                    sLocName = prov.location.name
                else:
                    sLocName = " ({})".format(prov.location.name)
            sName = "-" if prov.name == "" else prov.name
            sLoc = "{} {}".format(sName, sLocName)

            if plain:
                sCprov = dict(prov=prov.name, location=sLocName)
            else:
                sProvLink = "<span class='badge signature gr'><a href='{}'>{}</a></span>".format(url, sLoc)
                if table:
                    sCprov = "<td class='tdnowrap nostyle' valign='top'>{}</td><td valign='top'>{}</td></tr>".format(
                        sProvLink, sNote)
                else:
                    sCprov = sProvLink

            lHtml.append(sCprov)

        if not plain: 
            if table: lHtml.append("</tbody></table>")
        if plain:
            sBack = json.dumps(lHtml)
        else:
            # sBack = ", ".join(lHtml)
            sBack = "".join(lHtml)
        return sBack

    def get_sermon_count(self):
        count = SermonDescr.objects.filter(msitem__codico=self).count()
        return count

    def get_ssg_count(self, compare_link=False, collection = None):
        # Get a list of all SSGs related to [self]
        ssg_list_num = EqualGold.objects.filter(sermondescr_super__sermon__msitem__codico=self).order_by('id').distinct().count()
        if compare_link:
            url = "{}?codico={}".format(reverse("collhist_compare", kwargs={'pk': collection.id}), self.id)
            sBack = "<span class='clickable'><a class='nostyle' href='{}'>{}</a></span>".format(url, ssg_list_num)
        else:
            sBack = "<span>{}</span>".format(ssg_list_num)
        # Return the combined information
        return sBack

    def get_stype_light(self, usercomment=False):
        count = 0
        if usercomment:
            # This is from Manuscript, but we don't have Comments...
            count = self.comments.count()
            pass
        sBack = get_stype_light(self.stype, usercomment, count)
        return sBack


class Reconstruction(models.Model):
    """Combines a Codico with a reconstructed manuscript"""

    # [1] Link to the reconstruction manuscript 
    manuscript = models.ForeignKey(Manuscript, on_delete = models.CASCADE, related_name="manuscriptreconstructions")
    # [1] Link to the codico
    codico = models.ForeignKey(Codico, on_delete = models.CASCADE, related_name = "codicoreconstructions")
    # [1] The order of this link within the reconstructed manuscript
    order = models.IntegerField("Order", default=0)

    # [1] And a date: the date of saving this manuscript
    created = models.DateTimeField(default=get_current_datetime)
    saved = models.DateTimeField(null=True, blank=True)


class Daterange(models.Model):
    """Each manuscript can have a number of date ranges attached to it"""

    # [1] Date estimate: starting from this year
    yearstart = models.IntegerField("Year from", null=False, default=100)
    # [1] Date estimate: finishing with this year
    yearfinish = models.IntegerField("Year until", null=False, default=100)

    # [0-1] An optional reference for this daterange
    reference = models.ForeignKey(Litref, null=True, related_name="reference_dateranges", on_delete=models.SET_NULL)
    # [0-1] The first and last page of the reference
    pages = models.CharField("Pages", blank = True, null = True,  max_length=MAX_TEXT_LEN)

    # ========================================================================
    # [1] Every daterange belongs to exactly one manuscript
    #     Note: when a Manuscript is removed, all its associated Daterange objects are also removed
    manuscript = models.ForeignKey(Manuscript, null=False, related_name="manuscript_dateranges", on_delete=models.CASCADE)
    codico = models.ForeignKey(Codico, null=True, related_name="codico_dateranges", on_delete=models.SET_NULL)

    def __str__(self):
        sBack = "{}-{}".format(self.yearstart, self.yearfinish)
        return sBack

    def save(self, force_insert = False, force_update = False, using = None, update_fields = None):
        # Fill in manuscript, if not yet given
        if self.codico_id != None and self.codico != None and self.manuscript_id == None or self.manuscript == None:
            self.manuscript = self.codico.manuscript
        # Perform the actual saving
        response = super(Daterange, self).save(force_insert, force_update, using, update_fields)
        # Possibly adapt the dates of the related manuscript
        self.adapt_manu_dates()
        # Return the response on saving
        return response

    def delete(self, using = None, keep_parents = False):
        response = super(Daterange, self).delete(using, keep_parents)
        # Possibly adapt the dates of the related manuscript
        self.adapt_manu_dates()
        # Return the response on saving
        return response

    def adapt_manu_dates(self):
        manu_start = self.manuscript.yearstart
        manu_finish = self.manuscript.yearfinish
        current_start = 3000
        current_finish = 0
        for dr in self.manuscript.manuscript_dateranges.all():
            if dr.yearstart < current_start: current_start = dr.yearstart
            if dr.yearfinish > current_finish: current_finish = dr.yearfinish

        # Need any changes in *MANUSCRIPT*?
        bNeedSaving = False
        if manu_start != current_start:
            self.manuscript.yearstart = current_start
            bNeedSaving = True
        if manu_finish != current_finish:
            self.manuscript.yearfinish = current_finish
            bNeedSaving = True
        if bNeedSaving: self.manuscript.save()

        # Need any changes in *CODICO*?
        bNeedSaving = False
        if self.codico != None:
            codi_start = self.codico.yearstart
            codi_finish = self.codico.yearfinish
            if codi_start != current_start:
                self.codico.yearstart = current_start
                bNeedSaving = True
            if codi_finish != current_finish:
                self.codico.yearfinish = current_finish
                bNeedSaving = True
            if bNeedSaving: self.codico.save()


        return True


class Author(models.Model):
    """We have a set of authors that are the 'golden' standard"""

    # [1] Name of the author
    name = models.CharField("Name", max_length=LONG_STRING)
    # [0-1] Possibly add the Gryson abbreviation for the author
    abbr = models.CharField("Abbreviation", null=True, blank=True, max_length=LONG_STRING)
    # [0-1] Author number: automatically consecutively filled when added to EqualGold
    number = models.IntegerField("Number", null=True, blank=True)
    # [1] Can this author's name and abbreviation be edited by users?
    editable = models.BooleanField("Editable", default=True)

    def __str__(self):
        return self.name

    def find_or_create(sName):
        """Find an author or create it."""

        qs = Author.objects.filter(Q(name__iexact=sName))
        if qs.count() == 0:
            # Create one
            hit = Author(name=sName)
            hit.save()
        else:
            hit = qs[0]
        # Return what we found or created
        return hit

    def find(sName):
        """Find an author."""

        # Check for the author's full name as well as the abbreviation
        qs = Author.objects.filter(Q(name__iexact=sName) | Q(abbr__iexact=sName))
        hit = None
        if qs.count() != 0:
            hit = qs[0]
        # Return what we found or created
        return hit

    def read_csv(username, data_file, arErr, sData = None, sName = None):
        """Import a CSV list of authors and add these authors to the database"""

        oBack = {'status': 'ok', 'count': 0, 'msg': "", 'user': username}
        try:
            # Make sure we have the data
            if sData == None:
                sData = data_file

            # Go through the data
            lines = []
            bFirst = True
            for line in sData:
                # Get a good view of the line
                sLine = line.decode("utf-8").strip()
                if bFirst:
                    if "\ufeff" in sLine:
                        sLine = sLine.replace("\ufeff", "")
                    bFirst = False
                lines.append(sLine)

            iCount = 0
            added = []
            with transaction.atomic():
                for name in lines:
                    # The whole line is the author: but strip quotation marks
                    name = name.strip('"')

                    obj = Author.objects.filter(name__iexact=name).first()
                    if obj == None:
                        # Add this author
                        obj = Author(name=name)
                        obj.save()
                        added.append(name)
                        # Keep track of the authors that are ADDED
                        iCount += 1
            # Make sure the requester knows how many have been added
            oBack['count'] = iCount
            oBack['added'] = added

        except:
            sError = errHandle.get_error_message()
            oBack['status'] = 'error'
            oBack['msg'] = sError

        # Return the object that has been created
        return oBack

    def read_json(username, data_file, arErr, oData=None, sName = None):
        """Import a JSON list of authors and add them to the database"""

        oBack = {'status': 'ok', 'count': 0, 'msg': "", 'user': username}
        try:
            # Make sure we have the data
            if oData == None:
                # This treats the data as JSON already
                sData = data_file.read().decode("utf-8-sig")
                oData = json.loads(sData)

            # Go through the data
            lines = []
            bFirst = True
            for line in oData:
                sAuthor = ""
                # Each 'line' is either a string (a name) or an object with a name field
                if isinstance(line, str):
                    # This is a string, so this is the author's name
                    sAuthor = line
                else:
                    # =========================================
                    # TODO: this part has not been debugged yet
                    # =========================================
                    # this is an object, so iterate over the fields
                    for k,v in line.items:
                        if isinstance(v, str):
                            sAuthor = v
                            break
                lines.append(sAuthor)

            iCount = 0
            added = []
            with transaction.atomic():
                for name in lines:
                    # The whole line is the author: but strip quotation marks
                    name = name.strip('"')

                    obj = Author.objects.filter(name__iexact=name).first()
                    if obj == None:
                        # Add this author
                        obj = Author(name=name)
                        obj.save()
                        added.append(name)
                        # Keep track of the authors that are ADDED
                        iCount += 1
            # Make sure the requester knows how many have been added
            oBack['count'] = iCount
            oBack['added'] = added

        except:
            sError = errHandle.get_error_message()
            oBack['status'] = 'error'
            oBack['msg'] = sError

        # Return the object that has been created
        return oBack

    def list_fields(self):
        """Provide the HTML of the """
        pass

    def get_number(self):
        """Get the author number"""

        iNumber = -1
        # Validate this author
        if self.name.lower() == "undecided":
            return -1
        # Check if this author already has a number
        if not self.number:
            # Create a number for this author
            qs = Author.objects.filter(number__isnull=False).order_by('-number')
            if qs.count() == 0:
                iNumber = 1
            else:
                sName = self.name
                iNumber = qs.first().number + 1
            self.number = iNumber
            # Save changes
            self.save()
        else:
            iNumber = self.number
        return iNumber

    def get_undecided():
        author = Author.objects.filter(name__iexact="undecided").first()
        if author == None:
            author = Author(name="Undecided")
            author.save()
        return author

    def get_editable(self):
        """Get a HTML expression of this author's editability"""

        sBack = "yes" if self.editable else "no"
        return sBack


class Nickname(models.Model):
    """Authors can have 0 or more local names, which we call 'nicknames' """

    # [1] Nickname 
    name = models.CharField("Name", max_length=LONG_STRING)
    # [0-1] We should try to link this nickname to an actual author
    author = models.ForeignKey("Author", null=True, blank=True, on_delete = models.SET_NULL, related_name="author_nicknames")

    def __str__(self):
        return self.name

    def find_or_create(sName):
        """Find an author or create it."""

        qs = Nickname.objects.filter(Q(name__iexact=sName))
        if qs.count() == 0:
            # Create one
            hit = Nickname(name=sName)
            hit.save()
        else:
            hit = qs[0]
        # Return what we found or created
        return hit


class Feast(models.Model):
    """Christian feast commemmorated in one of the Latin texts or sermons"""

    # [1] Name of the feast in English
    name = models.CharField("Name (English)", max_length=LONG_STRING)
    # [0-1] Name of the feast in Latin
    latname = models.CharField("Name (Latin)", null=True, blank=True, max_length=LONG_STRING)
    # [0-1] Date of the feast
    feastdate = models.TextField("Feast date", null=True, blank=True)

    def __str__(self):
        return self.name

    def get_one(sFeastName):
        sFeastName = sFeastName.strip()
        obj = Feast.objects.filter(name__iexact=sFeastName).first()
        if obj == None:
            obj = Feast.objects.create(name=sFeastName)
        return obj

    def get_latname(self):
        sBack = ""
        if self.latname != None and self.latname != "":
            sBack = self.latname
        return sBack

    def get_date(self):
        sBack = ""
        if self.feastdate != None and self.feastdate != "":
            sBack = self.feastdate
        return sBack


class Free(models.Model):
    """Free text fields to be searched per main model"""

    # [1] Name for the user
    name = models.CharField("Name", max_length=LONG_STRING)
    # [1] Inernal field name
    field = models.CharField("Field", max_length=LONG_STRING)
    # [1] Name of the model
    main = models.CharField("Model", max_length=LONG_STRING)

    def __str__(self):
        sCombi = "{}:{}".format(self.main, self.field)
        return sCombi


class Provenance(models.Model):
    """The 'origin' is a location where manuscripts were originally created"""

    # [1] Name of the location (can be cloister or anything)
    name = models.CharField("Provenance location", max_length=LONG_STRING)
    # [0-1] Optional: LOCATION element this refers to
    location = models.ForeignKey(Location, null=True, related_name="location_provenances", on_delete=models.SET_NULL)
    ## [0-1] Further details are perhaps required too
    #note = models.TextField("Notes on this provenance", blank=True, null=True)

    ## [1] One provenance belongs to exactly one manuscript
    #manu = models.ForeignKey(Manuscript, default=0, related_name="manuprovenances")

    def __str__(self):
        return self.name

    def find_or_create(sName,  city=None, country=None, note=None):
        """Find a location or create it."""

        lstQ = []
        obj_loc = Location.get_location(city=city, country=country)
        lstQ.append(Q(name__iexact=sName))
        if obj_loc != None:
            lstQ.append(Q(location=obj_loc))
        if note!=None: lstQ.append(Q(note__iexact=note))
        qs = Provenance.objects.filter(*lstQ)
        if qs.count() == 0:
            # Create one
            hit = Provenance(name=sName)
            if note!=None: hit.note=note
            if obj_loc != None: hit.location = obj_loc
            hit.save()
        else:
            hit = qs[0]
        # Return what we found or created
        return hit

    def get_location(self):
        if self.location:
            sBack = self.location.name
        else:
            sBack = "-"

        return sBack


class EqualGold(models.Model):
    """This combines all SermonGold instance belonging to the same group"""

    # [0-1] We would very much like to know the *REAL* author
    author = models.ForeignKey(Author, null=True, blank=True, on_delete = models.SET_NULL, related_name="author_equalgolds")
    # [0-1] We would like to know the INCIPIT (first line in Latin)
    incipit = models.TextField("Incipit", null=True, blank=True)
    srchincipit = models.TextField("Incipit (searchable)", null=True, blank=True)
    # [0-1] We would like to know the EXPLICIT (last line in Latin)
    explicit = models.TextField("Explicit", null=True, blank=True)
    srchexplicit = models.TextField("Explicit (searchable)", null=True, blank=True)
    # [0-1] The 'passim-code' for a sermon - see instructions (16-01-2020 4): [PASSIM aaa.nnnn]
    code = models.CharField("Passim code", blank=True, null=True, max_length=PASSIM_CODE_LENGTH, default="ZZZ_DETERMINE")
    # [0-1] The number of this SSG (numbers are 1-based, per author)
    number = models.IntegerField("Number", blank=True, null=True)
    # [0-1] The sermon to which this one has moved
    moved = models.ForeignKey('self', on_delete=models.SET_NULL, related_name="moved_ssg", blank=True, null=True)

    # [1] Every SSG has a status - this is *NOT* related to model 'Status'
    stype = models.CharField("Status", choices=build_abbr_list(STATUS_TYPE), max_length=5, default="-")
    # [0-1] Status note
    snote = models.TextField("Status note(s)", default="[]")

    # ============= CALCULATED FIELDS =============
    # [1] We need to have the size of the equality set for sorting
    sgcount = models.IntegerField("Equality set size", default=0)
    # [1] The first signature
    firstsig = models.CharField("Code", max_length=LONG_STRING, blank=True, null=True)
    # [1] The number of associated Historical Collections
    hccount = models.IntegerField("Historical Collection count", default=0)
    # [1] The number of SermonDescr linked to me
    scount = models.IntegerField("Sermon set size", default=0)
    # [1] The number of EqualGold linked to me (i.e. relations.count)
    ssgcount = models.IntegerField("SSG set size", default=0)

    # ============= MANY_TO_MANY FIELDS ============
    # [m] Many-to-many: all the gold sermons linked to me
    relations = models.ManyToManyField("self", through="EqualGoldLink", symmetrical=False, related_name="related_to")

    # [0-n] Many-to-many: keywords per SermonGold
    keywords = models.ManyToManyField(Keyword, through="EqualGoldKeyword", related_name="keywords_super")

    # [m] Many-to-many: one sermon can be a part of a series of collections
    collections = models.ManyToManyField("Collection", through="CollectionSuper", related_name="collections_super")

    # [m] Many-to-many: one manuscript can have a series of user-supplied comments
    comments = models.ManyToManyField(Comment, related_name="comments_super")
    
    def __str__(self):
        name = "" if self.id == None else "eqg_{}".format(self.id)
        return name

    def save(self, force_insert = False, force_update = False, using = None, update_fields = None):

        oErr = ErrHandle()
        try:
            # Adapt the incipit and explicit - if necessary
            srchincipit = get_searchable(self.incipit)
            if self.srchincipit != srchincipit:
                self.srchincipit = srchincipit
            srchexplicit = get_searchable(self.explicit)
            if self.srchexplicit != srchexplicit:
                self.srchexplicit = srchexplicit

            # Double check the number and the code
            if self.author:
                # Get the author number
                auth_num = self.author.get_number()

                # Can we process this author further into a code?
                if auth_num < 0:
                    self.code = None
                else:
                    # There is an author--is this different than the author we used to have?

                    if self.number == None:
                        # This may be a mistake: see if there is a code already
                        if self.code != None and "PASSIM" in self.code:
                            # There already is a code: get the number from here
                            arPart = re.split("\s|\.", self.code)
                            if len(arPart) == 3 and arPart[0] == "PASSIM":
                                # Get the author number
                                self.number = int(arPart[2])
                        if self.number == None:
                            # Check the highest sermon number for this author
                            self.number = EqualGold.sermon_number(self.author)
                    # Now we have both an author and a number...
                    passim_code = EqualGold.passim_code(auth_num, self.number)
                    if not self.code or self.code != passim_code:
                        # Now save myself with the new code
                        self.code = passim_code

            # (Re) calculate the number of associated historical collections (for *all* users!!)
            if self.id != None:
                hccount = self.collections.filter(settype="hc", scope='publ').count()
                if hccount != self.hccount:
                    self.hccount = hccount

            # Do the saving initially
            response = super(EqualGold, self).save(force_insert, force_update, using, update_fields)
            return response
        except:
            msg = oErr.get_error_message()
            oErr.DoError("Equalgold.save")
            return None

    def author_help(self, info):
        """Provide help for this particular author"""

        html = []

        # Provide the name of the author + button for modal dialogue
        author = "(not set)" if self.author == None else self.author.name
        html.append("<div><span>{}</span>&nbsp;<a class='btn jumbo-1 btn-xs' data-toggle='modal' data-target='#author_info'>".format(author))
        html.append("<span class='glyphicon glyphicon-info-sign' style='color: darkblue;'></span></a></div>")

        # Provide the Modal contents
        html.append(info)

        return "\n".join(html)

    def create_empty():
        """Create an empty new one"""

        org = EqualGold()
        org.author = Author.get_undecided()
        org.save()
        return org

    def create_moved(self):
        """Create a copy of [self], and indicate in that copy that it moved to [self]"""

        # Get a copy of self
        org = self.create_new()
        # Now indicate where the original moved to
        org.moved = self
        # Save the result
        org.save()
        return org

    def create_new(self):
        """Create a copy of [self]"""

        fields = ['author', 'incipit', 'srchincipit', 'explicit', 'srchexplicit', 'number', 'code', 'stype', 'moved']
        org = EqualGold()
        for field in fields:
            value = getattr(self, field)
            if value != None:
                setattr(org, field, value)
        # Possibly set the author to UNDECIDED
        if org.author == None: 
            author = Author.get_undecided()
            org.author = author
        # Save the result
        org.save()
        return org

    def get_collections_markdown(self, username, team_group, settype = None):

        lHtml = []
        # Visit all collections that I have access to
        mycoll__id = Collection.get_scoped_queryset('super', username, team_group, settype = settype).values('id')
        for col in self.collections.filter(id__in=mycoll__id).order_by('name'):
            url = "{}?ssg-collist_ssg={}".format(reverse('equalgold_list'), col.id)
            lHtml.append("<span class='collection'><a href='{}'>{}</a></span>".format(url, col.name))
        sBack = ", ".join(lHtml)
        return sBack

    def get_editions_markdown(self):
        """Get all the editions associated with the SGs in this equality set"""

        lHtml = []
        # Visit all editions
        qs = EdirefSG.objects.filter(sermon_gold__equal=self).order_by('-reference__year', 'reference__short')
        for edi in qs:
            # Determine where clicking should lead to
            url = "{}#edi_{}".format(reverse('literature_list'), edi.reference.id)
            # Create a display for this item
            edi_display = "<span class='badge signature ot'><a href='{}'>{}</a></span>".format(url,edi.get_short_markdown())
            if edi_display not in lHtml:
                lHtml.append(edi_display)

        sBack = ", ".join(lHtml)
        return sBack

    def get_explicit_markdown(self, incexp_type = "actual"):
        """Get the contents of the explicit field using markdown"""

        if incexp_type == "both":
            parsed = adapt_markdown(self.explicit)
            search = self.srchexplicit
            sBack = "<div>{}</div><div class='searchincexp'>{}</div>".format(parsed, search)
        elif incexp_type == "actual":
            sBack = adapt_markdown(self.explicit)
        elif incexp_type == "search":
            sBack = adapt_markdown(self.srchexplicit)
        return sBack

    def get_hclist_markdown(self):
        html = []
        for hc in self.collections.filter(settype="hc", scope='publ').order_by('name').distinct():
            url = reverse('collhist_details', kwargs={'pk': hc.id})
            html.append("<span class='collection clickable'><a href='{}'>{}</a></span>".format(url,hc.name))
        sBack = ", ".join(html)
        return sBack

    def get_incexp_match(self, sMatch=""):
        html = []
        dots = "..." if self.incipit else ""
        sBack = "{}{}{}".format(self.srchincipit, dots, self.srchexplicit)
        ratio = 0.0
        # Are we matching with something?
        if sMatch != "":
            sBack, ratio = get_overlap(sBack, sMatch)
        return sBack, ratio

    def get_incipit_markdown(self, incexp_type = "actual"):
        """Get the contents of the incipit field using markdown"""
        # Perform
        if incexp_type == "both":
            parsed = adapt_markdown(self.incipit)
            search = self.srchincipit
            sBack = "<div>{}</div><div class='searchincexp'>{}</div>".format(parsed, search)
        elif incexp_type == "actual":
            sBack = adapt_markdown(self.incipit)
        elif incexp_type == "search":
            sBack = adapt_markdown(self.srchincipit)
        return sBack

    def get_keywords_markdown(self):
        lHtml = []
        # Visit all keywords
        for keyword in self.keywords.all().order_by('name'):
            # Determine where clicking should lead to
            url = "{}?ssg-kwlist={}".format(reverse('equalgold_list'), keyword.id)
            # Create a display for this topic
            lHtml.append("<span class='keyword'><a href='{}'>{}</a></span>".format(url,keyword.name))

        sBack = ", ".join(lHtml)
        return sBack

    def get_keywords_user_markdown(self, profile):
        lHtml = []
        # Visit all keywords
        for kwlink in self.super_userkeywords.filter(profile=profile).order_by('keyword__name'):
            keyword = kwlink.keyword
            # Determine where clicking should lead to
            url = "{}?ssg-ukwlist={}".format(reverse('equalgold_list'), keyword.id)
            # Create a display for this topic
            lHtml.append("<span class='keyword'><a href='{}'>{}</a></span>".format(url,keyword.name))

        sBack = ", ".join(lHtml)
        return sBack

    def get_label(self, do_incexpl=False):
        """Get a string view of myself to be put on a label"""

        lHtml = []

        # Treat passim code
        sLabel = self.code
        if sLabel == None: sLabel = "(Undecided {})".format(self.id)
        lHtml.append("{} ".format(sLabel))

        # Treat signatures
        equal_set = self.equal_goldsermons.all()
        siglist = [x.short() for x in Signature.objects.filter(gold__in=equal_set).order_by('-editype', 'code').distinct()]
        lHtml.append(" | ".join(siglist))

        # Treat the author
        if self.author:
            lHtml.append("(by {}) ".format(self.author.name))
        else:
            lHtml.append("(by Unknown Author) ")

        if do_incexpl:
            # Treat incipit
            if self.incipit: lHtml.append("{}".format(self.srchincipit))
            # Treat intermediate dots
            if self.incipit and self.explicit: lHtml.append("...-...")
            # Treat explicit
            if self.explicit: lHtml.append("{}".format(self.srchexplicit))

        # Return the results
        return "".join(lHtml)

    def get_litrefs_markdown(self):
        """Get all the literature references associated with the SGs in this equality set"""

        lHtml = []
        # Visit all editions
        qs = LitrefSG.objects.filter(sermon_gold__equal=self).order_by('reference__short')
        # Visit all literature references
        for litref in qs:
            # Determine where clicking should lead to
            url = "{}#lit_{}".format(reverse('literature_list'), litref.reference.id)
            # Create a display for this item
            lHtml.append("<span class='badge signature cl'><a href='{}'>{}</a></span>".format(url,litref.get_short_markdown()))

        sBack = ", ".join(lHtml)
        return sBack

    def get_moved_code(self):
        """Get the passim code of the one this is replaced by"""

        sBack = ""
        if self.moved:
            sBack = self.moved.code
            if sBack == None or sBack == "None":
                sBack = "(no Passim code)"
        return sBack

    def get_moved_url(self):
        """Get the URL of the SSG to which I have been moved"""

        url = ""
        if self.moved:
            url = reverse('equalgold_details', kwargs={'pk': self.moved.id})
        return url

    def get_previous_code(self):
        """Get information on the SSG from which I derive"""

        sBack = ""
        # Find out if I have moved from anywhere or not
        origin = EqualGold.objects.filter(moved=self).first()
        if origin != None: 
            sBack = origin.code
            if sBack == None or sBack == "None":
                sBack = "(no Passim code)"
        # REturn the information
        return sBack

    def get_previous_url(self):
        """Get information on the SSG from which I derive"""

        sBack = ""
        # Find out if I have moved from anywhere or not
        origin = EqualGold.objects.filter(moved=self).first()
        if origin != None: sBack = reverse('equalgold_details', kwargs={'pk': origin.id})
        # REturn the information
        return sBack

    def get_goldsigfirst(self):
        sBack = ""
        # Calculate the first signature
        first = Signature.objects.filter(gold__equal=self).order_by('-editype', 'code').first()
        if first != None:
            sBack = "<span class='badge signature {}'>{}</span>".format(first.editype, first.short())
        return sBack

    def get_passimcode(self):
        code = self.code if self.code and self.code != "" else "(nocode_{})".format(self.id)
        return code

    def get_passimcode_markdown(self):
        lHtml = []
        # Add the PASSIM code
        code = self.code if self.code and self.code != "" else "(nocode_{})".format(self.id)
        url = reverse('equalgold_details', kwargs={'pk': self.id})
        sBack = "<span  class='badge jumbo-1'><a href='{}'  title='Go to the Super Sermon Gold'>{}</a></span>".format(url, code)
        #lHtml.append("<span class='passimcode'>{}</span> ".format(code))
        #sBack = " ".join(lHtml)
        return sBack

    def get_short(self):
        """Get a very short textual summary"""

        lHtml = []
        # Add the PASSIM code
        lHtml.append("{}".format(self.code))
        # Treat signatures
        equal_set = self.equal_goldsermons.all()
        qs = Signature.objects.filter(gold__in=equal_set).order_by('-editype', 'code').distinct()
        if qs.count() > 0:
            lSign = []
            for item in qs:
                lSign.append(item.short())
            lHtml.append(" {} ".format(" | ".join(lSign)))
        # Treat the author
        if self.author:
            lHtml.append(" {} ".format(self.author.name))
        # Return the results
        return "".join(lHtml)

    def get_stype_light(self, usercomment=False):
        count = 0
        if usercomment:
            count = self.comments.count()
        sBack = get_stype_light(self.stype, usercomment, count)
        return sBack

    def get_superlinks_markdown(self):
        """Return all the SSG links = type + dst"""

        lHtml = []
        sBack = ""
        oErr = ErrHandle()
        try:
            for superlink in self.equalgold_src.all().order_by('dst__code', 'dst__author__name', 'dst__number'):
                lHtml.append("<tr class='view-row'>")
                sSpectype = ""
                sAlternatives = ""
                if superlink.spectype != None and len(superlink.spectype) > 1:
                    # Show the specification type
                    sSpectype = "<span class='badge signature gr'>{}</span>".format(superlink.get_spectype_display())
                if superlink.alternatives != None and superlink.alternatives == "true":
                    sAlternatives = "<span class='badge signature cl' title='Alternatives'>A</span>"
                lHtml.append("<td valign='top' class='tdnowrap'><span class='badge signature ot'>{}</span>{}</td>".format(
                    superlink.get_linktype_display(), sSpectype))
                sTitle = ""
                sNoteShow = ""
                sNoteDiv = ""
                if superlink.note != None and len(superlink.note) > 1:
                    sTitle = "title='{}'".format(superlink.note)
                    sNoteShow = "<span class='badge signature btn-warning' title='Notes' data-toggle='collapse' data-target='#ssgnote_{}'>N</span>".format(
                        superlink.id)
                    sNoteDiv = "<div id='ssgnote_{}' class='collapse explanation'>{}</div>".format(
                        superlink.id, superlink.note)
                url = reverse('equalgold_details', kwargs={'pk': superlink.dst.id})
                lHtml.append("<td valign='top'><a href='{}' {}>{}</a>{}{}{}</td>".format(
                    url, sTitle, superlink.dst.get_view(), sAlternatives, sNoteShow, sNoteDiv))
                lHtml.append("</tr>")
            if len(lHtml) > 0:
                sBack = "<table><tbody>{}</tbody></table>".format( "".join(lHtml))
        except:
            msg = oErr.get_error_message()
            oErr.DoError("get_superlinks_markdown")
        return sBack

    def get_text(self):
        """Get a short textual representation"""

        lHtml = []
        # Add the PASSIM code
        lHtml.append("{}".format(self.code))
        # Treat signatures
        equal_set = self.equal_goldsermons.all()
        qs = Signature.objects.filter(gold__in=equal_set).order_by('-editype', 'code').distinct()
        if qs.count() > 0:
            lSign = []
            for item in qs:
                lSign.append(item.short())
            lHtml.append(" {} ".format(" | ".join(lSign)))
        # Treat the author
        if self.author:
            lHtml.append(" {} ".format(self.author.name))
        # Treat incipit
        if self.incipit: lHtml.append(" {}".format(self.srchincipit))
        # Treat intermediate dots
        if self.incipit and self.explicit: lHtml.append("...-...")
        # Treat explicit
        if self.explicit: lHtml.append("{}".format(self.srchexplicit))
        # Return the results
        return "".join(lHtml)

    def get_view(self):
        """Get a HTML valid view of myself"""

        lHtml = []
        # Add the PASSIM code
        code = self.code if self.code else "(no Passim code)"
        lHtml.append("<span class='passimcode'>{}</span> ".format(code))
        # Treat signatures
        equal_set = self.equal_goldsermons.all()
        qs = Signature.objects.filter(gold__in=equal_set).order_by('-editype', 'code').distinct()
        if qs.count() > 0:
            lSign = []
            for item in qs:
                lSign.append(item.short())
            lHtml.append("<span class='signature'>{}</span>".format(" | ".join(lSign)))
        else:
            lHtml.append("[-]")
        # Treat the author
        if self.author:
            lHtml.append("(by <span class='sermon-author'>{}</span>) ".format(self.author.name))
        else:
            lHtml.append("(by <i>Unknown Author</i>) ")
        # Treat incipit
        if self.incipit: lHtml.append("{}".format(self.get_incipit_markdown()))
        # Treat intermediate dots
        if self.incipit and self.explicit: lHtml.append("...-...")
        # Treat explicit
        if self.explicit: lHtml.append("{}".format(self.get_explicit_markdown()))
        # Return the results
        return "".join(lHtml)

    def passim_code(auth_num, iNumber):
        """determine a passim code based on author number and sermon number"""

        sCode = None
        if auth_num and iNumber and iNumber > 0:
            sCode = "PASSIM {:03d}.{:04d}".format(auth_num, iNumber)
        return sCode

    def sermon_number(author):
        """Determine what the sermon number *would be* for the indicated author"""

        # Check the highest sermon number for this author
        qs_ssg = EqualGold.objects.filter(author=author).order_by("-number")
        if qs_ssg.count() == 0:
            iNumber = 1
        else:
            iNumber = qs_ssg.first().number + 1
        return iNumber

    def set_firstsig(self):
        # Calculate the first signature
        first = Signature.objects.filter(gold__equal=self).order_by('-editype', 'code').first()
        if first != None:
            firstsig = first.code
            if self.firstsig != firstsig:
                # Save changes
                self.save()
        return True

    def set_sgcount(self):
        # Calculate and set the sgcount
        sgcount = self.sgcount
        iSize = self.equal_goldsermons.all().count()
        if iSize != sgcount:
            self.sgcount = iSize
            self.save()
        return True

    def set_ssgcount(self):
        # Calculate and set the ssgcount
        ssgcount = self.ssgcount
        iSize = self.relations.count()
        if iSize != ssgcount:
            self.ssgcount = iSize
            self.save()
        return True


class SermonGold(models.Model):
    """The signature of a standard sermon"""

    # ======= OPTIONAL FIELDS describing the sermon ============
    # [0-1] We would very much like to know the *REAL* author
    author = models.ForeignKey(Author, null=True, blank=True, on_delete = models.SET_NULL, related_name="author_goldsermons")
    # [0-1] We would like to know the INCIPIT (first line in Latin)
    incipit = models.TextField("Incipit", null=True, blank=True)
    srchincipit = models.TextField("Incipit (searchable)", null=True, blank=True)
    # [0-1] We would like to know the EXPLICIT (last line in Latin)
    explicit = models.TextField("Explicit", null=True, blank=True)
    srchexplicit = models.TextField("Explicit (searchable)", null=True, blank=True)

    # [0-1] Every gold sermon must have room for a bibliography
    bibliography = models.TextField("Bibliography", null=True, blank=True)
    # [1] Every gold sermon may have 0 or more URI links to critical editions
    critlinks = models.TextField("Critical edition full text links", default="[]")

    # [1] Every gold sermon has a list of signatures that are automatically created
    siglist = models.TextField("List of signatures", default="[]")

    # [1] Every gold sermon has a status - this is *NOT* related to model 'Status'
    stype = models.CharField("Status", choices=build_abbr_list(STATUS_TYPE), max_length=5, default=STYPE_MANUAL)
    # [0-1] Status note
    snote = models.TextField("Status note(s)", default="[]")

    # [0-1] Each SermonGold should belong to exactly one equality group
    equal = models.ForeignKey(EqualGold, null=True, blank=True, on_delete=models.SET_NULL, related_name="equal_goldsermons")

    # [m] Many-to-many: all the gold sermons linked to me
    relations = models.ManyToManyField("self", through="SermonGoldSame", symmetrical=False, related_name="related_to")

    # [0-n] Many-to-many: keywords per SermonGold
    keywords = models.ManyToManyField(Keyword, through="SermonGoldKeyword", related_name="keywords_gold")

    # [0-n] Many-to-many: keywords per SermonGold
    litrefs = models.ManyToManyField(Litref, through="LitrefSG", related_name="litrefs_gold")

    # [m] Many-to-many: one sermon can be a part of a series of collections 
    collections = models.ManyToManyField("Collection", through="CollectionGold", related_name="collections_gold")

    # [m] Many-to-many: one manuscript can have a series of user-supplied comments
    comments = models.ManyToManyField(Comment, related_name="comments_gold")

    def __str__(self):
        name = self.signatures()
        if name == "":
            name = "RU_sg_{}".format(self.id)
        return name

    def add_relation(self, target, linktype):
        """Add a relation from me to [target] with the indicated type"""

        relation, created = SermonGoldSame.objects.get_or_create(
            src=self, dst=target, linktype=linktype)
        # Return the new SermonGoldSame instance that has been created
        return relation

    def collections_ordered(self):
        """Ordered sample of gold collections"""
        return self.collections_gold.all().order_by("name")

    def delete(self, using = None, keep_parents = False):
        # Remember the equal set
        equal = self.equal
        # DO the removing
        response = super(SermonGold, self).delete(using, keep_parents)
        # Adjust the SGcount
        equal.set_sgcount()
        # REturn our response
        return response

    def do_signatures(self):
        """Create or re-make a JSON list of signatures"""

        lSign = []
        for item in self.goldsignatures.all().order_by('-editype'):
            lSign.append(item.short())
        siglist = json.dumps(lSign)
        if siglist != self.siglist:
            self.siglist = siglist
            # And save myself
            self.save()

    def editions(self):
        """Combine all editions into one string: the editions are retrieved from litrefSG"""

        lEdition = []
        for item in self.sermon_gold_editions.all():
            lEdition.append(item.reference.short)
        return " | ".join(lEdition)

    def find_or_create(author, incipit, explicit, stype=STYPE_IMPORTED):
        """Find or create a SermonGold"""

        lstQ = []
        bCreated = False
        if author != None: 
            lstQ.append(Q(author=author))
        if incipit != "": 
            incipit = adapt_latin(incipit)
            lstQ.append(Q(incipit=incipit)|Q(srchincipit=incipit))
        if explicit != "": 
            explicit = adapt_latin(explicit)
            lstQ.append(Q(explicit=explicit)|Q(srchexplicit=explicit))
        obj = SermonGold.objects.filter(*lstQ).first()
        if obj == None:
            # Create a new
            obj = SermonGold(author=author, incipit=incipit, explicit=explicit)
            # Create searchable fields
            obj.srchincipit = get_searchable(incipit)
            obj.srchexplicit = get_searchable(explicit)
            obj.stype = stype       # Default status is 'imported'
            obj.save()
            bCreated = True
        # Return this object
        return bCreated, obj

    def find_first(signature, author=None, incipit=None, explicit=None):
        """Find a sermongold"""

        lstQ = []
        editype = "gr"  # Assume gryson
        if "CPPM" in signature:
            # This is a clavis number
            # EXTINCT: signature = signature.split("CPPM")[1].strip()
            editype = "cl"
        # Check if it is linked to a particular signature
        val = adapt_search(signature)
        lstQ.append(Q(goldsignatures__code__iregex=val))
        lstQ.append(Q(goldsignatures__editype=editype))
        # Optionally look for other fields
        if author != None: lstQ.append(Q(author=author))
        if incipit != None: 
            incipit = adapt_latin(incipit)
            lstQ.append(Q(incipit=incipit))
        if explicit != None: 
            explicit = adapt_latin(explicit)
            lstQ.append(Q(explicit=explicit))
        # Only look for the *FIRST* occurrance
        obj = SermonGold.objects.filter(*lstQ).first()

        if obj == None:
            istop = 1

        # Return what we found
        return obj

    def ftxtlinks(self):
        """Combine all editions into one string"""

        lFtxtlink = []
        for item in self.goldftxtlinks.all():
            lFtxtlink.append(item.short())
        return ", ".join(lFtxtlink)

    def get_author(self):
        """Get the name of the author"""

        if self.author:
            sName = self.author.name
        else:
            sName = "-"
        return sName
    
    def get_bibliography_markdown(self):
        """Get the contents of the bibliography field using markdown"""
        return adapt_markdown(self.bibliography, False)

    def get_collections_markdown(self, username, team_group, settype = None):
        lHtml = []
        # Visit all collections
        # Visit all collections that I have access to
        mycoll__id = Collection.get_scoped_queryset('gold', username, team_group, settype = settype).values('id')
        for col in self.collections.filter(id__in=mycoll__id).order_by('name'):
            # Determine where clicking should lead to
            url = "{}?gold-collist_sg={}".format(reverse('gold_list'), col.id)
            # Create a display for this topic
            lHtml.append("<span class='collection'><a href='{}'>{}</a></span>".format(url,col.name))

        sBack = ", ".join(lHtml)
        return sBack

    def get_editions(self):
        lEdition = []
        for item in self.sermon_gold_editions.all():
            lEdition.append(item.get_short())
        # Sort the items
        lEdition.sort()
        return lEdition

    def get_editions_markdown(self):
        lHtml = []
        # Visit all editions
        for edi in self.sermon_gold_editions.all().order_by('-reference__year', 'reference__short'):
            # Determine where clicking should lead to
            url = "{}#edi_{}".format(reverse('literature_list'), edi.reference.id)
            # Create a display for this item
            edi_display = "<span class='badge signature ot'><a href='{}'>{}</a></span>".format(url,edi.get_short_markdown())
            if edi_display not in lHtml:
                lHtml.append(edi_display)

        sBack = ", ".join(lHtml)
        return sBack

    def get_eqset(self):
        """Return an HTML representation of the *other* members in my equality set"""

        html = []
        # Make available the set of Gold Sermons that belongs to the same EqualGold
        if self.equal == None:
            html.append("<i>This Sermon Gold is not part of a Super Sermon Gold</i>")
        else:
            qs = SermonGold.objects.filter(equal=self.equal).exclude(id=self.id)
            for item in qs:
                sigs = json.loads(item.siglist)
                first = "id{}".format(item.id) if len(sigs) == 0 else sigs[0]
                url = reverse('gold_details', kwargs={'pk': item.id})
                html.append("<span class='badge signature eqset'><a href='{}' title='{}'>{}</a></span>".format(url, item.siglist, first))
        # Return the combination
        return " ".join(html)

    def get_explicit(self):
        """Return the *searchable* explicit, without any additional formatting"""
        return self.srchexplicit

    def get_explicit_markdown(self):
        """Get the contents of the explicit field using markdown"""
        return adapt_markdown(self.explicit)

    def get_ftxtlinks_markdown(self):
        lHtml = []
        # Visit all full text links
        for item in self.goldftxtlinks.all().order_by('url'):
            # Determine where clicking should lead to
            url = item.url
            # Create a display for this topic
            lHtml.append("<span class='badge signature gr'><a href='{}'>{}</a></span>".format(url, url))

        sBack = ", ".join(lHtml)
        return sBack

    def get_incipit(self):
        """Return the *searchable* incipit, without any additional formatting"""
        return self.srchincipit

    def get_incipit_markdown(self):
        """Get the contents of the incipit field using markdown"""
        # Perform
        return adapt_markdown(self.incipit)

    def get_keywords(self):
        """Combine all keywords into one string"""

        if self.id == None: return ""
        lKeyword = []
        for item in self.keywords.all():
            lKeyword.append(item.name)
        return " | ".join(lKeyword)

    def get_keywords_markdown(self):
        lHtml = []
        # Visit all keywords
        for keyword in self.keywords.all().order_by('name'):
            # Determine where clicking should lead to
            url = "{}?gold-kwlist={}".format(reverse('gold_list'), keyword.id)
            # Create a display for this topic
            lHtml.append("<span class='keyword'><a href='{}'>{}</a></span>".format(url,keyword.name))

        sBack = ", ".join(lHtml)
        return sBack

    def get_keywords_user_markdown(self, profile):
        lHtml = []
        # Visit all keywords
        for kwlink in self.gold_userkeywords.filter(profile=profile).order_by('keyword__name'):
            keyword = kwlink.keyword
            # Determine where clicking should lead to
            url = "{}?gold-ukwlist={}".format(reverse('gold_list'), keyword.id)
            # Create a display for this topic
            lHtml.append("<span class='keyword'><a href='{}'>{}</a></span>".format(url,keyword.name))

        sBack = ", ".join(lHtml)
        return sBack

    def get_keywords_ssg_markdown(self):
        """Get all the keywords attached to the SSG of which I am part"""

        lHtml = []
        oErr = ErrHandle()
        sBack = ""
        try:
            if self.equal != None:
                # Get all keywords attached to these SGs
                qs = Keyword.objects.filter(equal_kw__equal__id=self.equal.id).order_by("name").distinct()
                # Visit all keywords
                for keyword in qs:
                    # Determine where clicking should lead to
                    url = "{}?ssg-kwlist={}".format(reverse('equalgold_list'), keyword.id)
                    # Create a display for this topic
                    lHtml.append("<span class='keyword'><a href='{}'>{}</a></span>".format(url,keyword.name))

                sBack = ", ".join(lHtml)
        except:
            msg = oErr.get_error_message()
            oErr.DoError("get_keywords_ssg_markdown")
        return sBack

    def get_label(self, do_incexpl=False):
        """Get a string view of myself to be put on a label"""

        lHtml = []
        # do_incexpl = False

        # Treat signatures
        if self.goldsignatures.all().count() > 0:
            lHtml.append("{} ".format(self.signatures()))
        else:
            lHtml.append(" ")
        # Treat the author
        if self.author:
            lHtml.append("(by {}) ".format(self.author.name))
        else:
            lHtml.append("(by Unknwon Author) ")

        if do_incexpl:
            # Treat incipit
            if self.incipit: lHtml.append("{}".format(self.srchincipit))
            # Treat intermediate dots
            if self.incipit and self.explicit: lHtml.append("...-...")
            # Treat explicit
            if self.explicit: lHtml.append("{}".format(self.srchexplicit))

        # Return the results
        return "".join(lHtml)

    def get_litrefs_markdown(self):
        lHtml = []
        # Visit all literature references
        for litref in self.sermon_gold_litrefs.all().order_by('reference__short'):
            # Determine where clicking should lead to
            url = "{}#lit_{}".format(reverse('literature_list'), litref.reference.id)
            # Create a display for this item
            lHtml.append("<span class='badge signature cl'><a href='{}'>{}</a></span>".format(url,litref.get_short_markdown()))

        sBack = ", ".join(lHtml)
        return sBack

    def get_relations(self, linktype = None):
        """Get all SermonGoldSame instances with me as source and with the indicated linktype"""

        lstQ = []
        lstQ.append(Q(src=self))
        if linktype != None:
            lstQ.append(Q(linktype=linktype))
        qs = SermonGoldSame.objects.filter(*lstQ )
        
        # Return the whole queryset that was found
        return qs

    def get_related_to(self, linktype):
        """Get all sermongold instances that have a particular linktype relation with me"""

        qs = self.related_to.filter(sermongold_dst__linktype=linktype, sermongold_dst__dst=self)
        # Return the whole queryset that was found
        return qs

    def get_sermon_string(self):
        """Get a string summary of this one"""

        author = "" if self.author == None else self.author.name
        incipit = "" if self.incipit == None else self.incipit
        explicit = "" if self.explicit == None else self.explicit
        return "{} {} {} {}".format(author, self.signatures(), incipit, explicit)
    
    def get_signatures(self):
        lSign = []
        for item in self.goldsignatures.all().order_by('-editype'):
            lSign.append(item.short())
        return lSign

    def get_signatures_markdown(self):
        lHtml = []
        # Visit all signatures
        for sig in self.goldsignatures.all().order_by('-editype', 'code'):
            # Determine where clicking should lead to
            url = "{}?gold-siglist={}".format(reverse('gold_list'), sig.id)
            # Create a display for this topic
            lHtml.append("<span class='badge signature {}'><a href='{}'>{}</a></span>".format(sig.editype,url,sig.code))

        sBack = ", ".join(lHtml)
        return sBack

    def get_ssg_markdown(self):
        lHtml = []
        if self.equal:
            url = reverse('equalgold_details', kwargs={'pk': self.equal.id})
            code = self.equal.code if self.equal.code else "(ssg id {})".format(self.equal.id)
            lHtml.append("<span class='passimlink'><a href='{}'>{}</a></span>".format(url, code))
        else:
            # There is no EqualGold link...
            lHtml.append("<span class='passimlink'>(not linked to a super-sermon-gold)</span>")
        sBack = "".join(lHtml)
        return sBack

    def get_stype_light(self, usercomment=False):
        count = 0
        if usercomment:
            count = self.comments.count()
        sBack = get_stype_light(self.stype, usercomment, count)
        return sBack

    def get_view(self):
        """Get a HTML valid view of myself similar to [sermongold_view.html]"""

        lHtml = []
        # Treat signatures
        if self.goldsignatures.all().count() > 0:
            lHtml.append("<span class='signature'>{}</span>".format(self.signatures()))
        else:
            lHtml.append("[-]")
        # Treat the author
        if self.author:
            lHtml.append("(by <span class='sermon-author'>{}</span>) ".format(self.author.name))
        else:
            lHtml.append("(by <i>Unknwon Author</i>) ")
        # Treat incipit
        if self.incipit: lHtml.append("{}".format(self.get_incipit_markdown()))
        # Treat intermediate dots
        if self.incipit and self.explicit: lHtml.append("...-...")
        # Treat explicit
        if self.explicit: lHtml.append("{}".format(self.get_explicit_markdown()))
        # Return the results
        return "".join(lHtml)

    def has_relation(self, target, linktype):
        """Check if the indicated linktype relation exists"""

        obj = SermonGoldSame.objects.filter(src=self, dst=target, linktype=linktype).first()
        # Return existance
        return (obj != None)

    def init_latin():
        """ One time ad-hoc function"""

        with transaction.atomic():
            for obj in SermonGold.objects.all():
                obj.srchincipit = get_searchable(obj.incipit)
                obj.srchexplicit = get_searchable(obj.explicit)
                obj.save()
        return True

    def link_oview(self):
        """provide an overview of links from this gold sermon to others"""

        link_list = [
            {'abbr': 'eqs', 'class': 'eqs-link', 'count': 0, 'title': 'Is equal to' },
            {'abbr': 'prt', 'class': 'prt-link', 'count': 0, 'title': 'Is part of' },
            {'abbr': 'neq', 'class': 'neq-link', 'count': 0, 'title': 'Is nearly equal to' },
            {'abbr': 'sim', 'class': 'sim-link', 'count': 0, 'title': 'Is similar to' },
            {'abbr': 'use', 'class': 'use-link', 'count': 0, 'title': 'Makes us of' },
            ]
        lHtml = []
        for link_def in link_list:
            lt = link_def['abbr']
            links = SermonGoldSame.objects.filter(src=self, linktype=lt).count()
            link_def['count'] = links
        return link_list

    def read_gold(username, data_file, filename, arErr, objStat=None, xmldoc=None, sName = None):
        """Import an Excel file with golden sermon data and add it to the DB
        
        This approach makes use of openpyxl
        """

        def add_to_manual_list(lst, type, error, oGold):
            oManual = {}
            oManual['type'] = type
            oManual['error'] = error
            if 'row_number' in oGold:
                oManual['row_number'] = oGold['row_number']
            for k in lField:
                oManual[k] = oGold[k]
            lst.append(oManual)
            return True

        def add_to_read_list(lst, oGold):
            oRead = {}
            if 'row_number' in oGold:
                oRead['row_number'] = oGold['row_number']
            for k in lField:
                oRead[k] = oGold[k]
            lst.append(oRead)
            return True

        def do_eq_log(msg):
            """Add string msg to the equality log"""
            eq_log.append(msg)

        # Number to order all the items we read
        order = 0
        iSermCount = 0
        count_obj = 0   # Number of objects added
        count_rel = 0   # Number of relations added
        eq_log = []

        oBack = {'status': 'ok', 'count': 0, 'msg': "", 'user': username}

        # Expected column names
        lExpected = ["status", "author", "incipit", "explicit", "nr. gryson", "cppm", "edition", "link type", "linked objects", "passim code"]
        # Names of the fields in which these need to be transformed
        lField = ['status', 'author', 'incipit', 'explicit', 'gryson', 'clavis', 'edition', 'linktype', 'targetlist', 'passimcode']

        lHeader = ['type', 'error', 'row_number']
        for k in lField:
            lHeader.append(k)

        # Keep a list of lines that need to be treated manually
        lst_manual = []
        lst_read = []
        write_csv_output = True

        # Specify which status is acceptable
        status_ok = ['completed', 'splitted sermongold']

        # Prepare an output file name
        dt_str = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
        output = "{}_{}".format(dt_str, filename.replace(".xlsx", ".json"))
        output_file_name = os.path.abspath(os.path.join(WRITABLE_DIR, output))
        
        # Overall keeping track of sermongold items
        errHandle = ErrHandle()

        try:
            errHandle.Status("Reading file {}".format(filename))
            # Convert the data into a list of objects
            bResult, lst_goldsermon, msg = excel_to_list(data_file, filename, lExpected, lField)

            # Set the status
            objStat.set("reading", msg="Excel file size={}".format(lst_goldsermon.count))

            # Check the result
            if bResult == False:
                oBack['status'] = 'error'
                oBack['msg'] = msg
                return oBack

            # Iterate over the objects
            for oGold in lst_goldsermon:
                # Prepare a possible manual object
                oManual = {}

                # Reset breaking
                bBreak = False

                # Get the status of this line
                status = oGold['status'].lower()
                if status in status_ok:
                    # Show where we are
                    objStat.set("reading", msg="Pass #1, line={}".format(oGold['row_number']))

                    sAuthor = oGold['author']
                    # Check author
                    if sAuthor == "":
                        # There must be a (gold) author...
                        add_to_manual_list(lst_manual, "author", "Without author, a gold sermon cannot be added", oGold)
                        # Skip the remainder of this line
                        continue
                    # Get the author (gold)
                    author = Author.find(sAuthor)
                    if author == None:
                        # Could not find this author, so indicate to the user
                        add_to_manual_list(lst_manual, "author", "Could not find golden Author [{}]".format(oGold['author']), oGold)
                        # Skip the remainder of this line
                        continue

                    # Get or create this golden sermon (the ... symbol is treated there)
                    bCreated, gold = SermonGold.find_or_create(author, oGold['incipit'], oGold['explicit'])

                    # Make sure it belongs to an equality-set: itself
                    if gold.equal == None:
                        eqg = EqualGold()
                        eqg.save()
                        do_eq_log("Add eqg {}".format(eqg.id))
                        gold.equal = eqg
                        gold.save()
                        do_eq_log("Assign eqg {} to gold {}".format(eqg.id, gold.id))
                    else:
                        iNoNeed = 1
                    # make sure it ends up in the [obj], even though some things below may go wrong...
                    oGold['obj'] = gold

                    # Keep track of created gold
                    if bCreated: count_obj += 1

                    # Process Gryson ('+' means: link to multiple gryson codes ), Clavis and possible Other
                    signature_lst = [{'lst': 'gryson', 'editype': 'gr'}, {'lst': 'clavis', 'editype': 'cl'}, {'lst': 'other', 'editype': 'ot'}]
                    for item in signature_lst:
                        if item['lst'] in oGold:
                            code_lst = oGold[item['lst']]
                            editype = item['editype']
                            if code_lst != None and code_lst != "":
                                if '+' in code_lst:
                                    iStopHere = 1
                                    pass
                                for code in code_lst.split("+"):
                                    code = code.strip()
                                    # Insert 'CPPM' if needed
                                    if editype == "cl" and is_number(code):
                                        code = "CPPM {}".format(code)
                                    # Add this code to the signatures
                                    obj = Signature.find(code, editype)
                                    if obj == None:
                                        obj = Signature(code=code, editype=editype, gold=gold)
                                        obj.save()
                                    else:
                                        # Check if an attempt is made to attach an existing signature to a *different* gold sermon
                                        iOthers = Signature.objects.filter(code=code, editype=editype).exclude(gold=gold).count()
                                        if iOthers > 0:
                                            # There is an existing signature, but we're deailng with the *first* instance of a sermongold
                                            add_to_manual_list(lst_manual, "signature", 
                                                               "Attempt to add existing signature [{} - {}] to a different gold sermon".format(editype, code), oGold)
                                            # Skip the remainder of this line
                                            bBreak = True
                                            break
                        if bBreak:
                            # Break to a higher level
                            break
                    if bBreak:
                        # # Break from the higher gold loop
                        # continue
                        # NOTE: don't break completely. Continue with editions
                        pass

                    # Process Editions (separated by ';')
                    # NOTE: this needs to be emended to use LitrefSG
                    #edition_lst = oGold['edition'].split(";")
                    #for item in edition_lst:
                    #    item = item.strip()

                    #    # NOTE: An edition should be unique for a gold sermon; not in general!
                    #    edition = Edition.find(item, gold)
                    #    if edition == None:
                    #        edition = Edition(name=item, gold=gold)
                    #        edition.save()
                    #    elif bCreated:
                    #        # This edition already exists
                    #        add_to_manual_list(lst_manual, "edition", 
                    #                           "First instance of a gold sermon is attempted to be linked with existing edition [{}]".format(item), oGold)
                    #        # Skip the remainder of this line
                    #        bBreak = True
                    #        break

                    if bBreak:
                        # # Break from the higher gold loop
                        # continue
                        # NOTE: don't break completely. Continue with editions
                        pass

                    # Getting here means that the item is read TO SOME EXTENT
                    add_to_read_list(lst_read, oGold)

                    iSermCount += 1
                else:
                    # Show where we are
                    objStat.set("skipping", msg="Pass #1, line={} status={}".format(oGold['row_number'], status))

 
            # Iterate over the objects again, and add relations
            for oGold in lst_goldsermon:
                # Show where we are
                objStat.set("reading", msg="Pass #2, line={}".format(oGold['row_number']))

                if 'obj' in oGold:
                    obj = oGold['obj']
                    # Make sure to get the correct gold
                    gold = SermonGold.objects.filter(id=obj.id).first()

                    if obj.equal != gold.equal:
                        iStop = 1

                    # Check if any relation has been specified
                    if 'targetlist' in oGold and oGold['targetlist'] != "":
                        target_list = oGold['targetlist'].split(";")
                        for target_item in target_list:
                            # Determine the linktype
                            if 'linktype' in oGold:
                                linktype = LINK_EQUAL if oGold['linktype'] == "" else oGold['linktype']
                                # Double check valid linktype
                                linktype = get_linktype_abbr(linktype)
                            else:
                                linktype = LINK_EQUAL

                            # Get the target sermongold
                            target = SermonGold.find_first(target_item)
                            if target == None:
                                # Could not find the target sermon gold, so cannot process this
                                lMsg = []
                                lMsg.append("Cannot find a target (a gold-sermon with signature [{}]).")
                                lMsg.append("<br />Please add this separately and then perform import once more so as to lay the correct links.")
                                lMsg.append("<br />(Sermons will <i>not</i> be added twice, so no worries about that.)")
                                sMsg = "\n".join(lMsg)
                                add_to_manual_list(lst_manual, "goldlink", sMsg.format(target_item), oGold)
                                # Skip the remainder of this line
                                break
                            else:
                                # Don;t add links
                                pass

                            # Check and add relation(s), if these are not yet there
                            count_links, lst_added = add_gold2gold(gold, target, linktype, eq_log)
                            
                            count_rel += count_links

            # Make sure the requester knows how many have been added
            oBack['count'] = count_obj      # Number of gold objects created
            oBack['count_rel'] = count_rel  # Number of relations added
            oBack['sermons'] = count_obj    # The number of sermons (=msitems) reviewed
            oBack['filename'] = filename

            # Create a report and add it to what we return
            oContents = {'headers': lHeader, 'list': lst_manual, 'read': lst_read}
            oReport = Report.make(username, "ig", json.dumps(oContents))
            oBack['report_id'] = oReport.id

        except:
            sError = errHandle.get_error_message()
            oBack['status'] = 'error'
            oBack['msg'] = sError

        # Return the object that has been created
        return oBack

    def remove_relation(self, target, linktype):
        """Find and remove all links to target with the indicated type"""

        SermonGoldSame.objects.filter(src=self, dst=target, linktype=linktype).delete()
        # Return positively
        return True

    def save(self, force_insert = False, force_update = False, using = None, update_fields = None):
        # Adapt the incipit and explicit
        istop = 1
        srchincipit = get_searchable(self.incipit)
        srchexplicit = get_searchable(self.explicit)
        if self.srchincipit != srchincipit: self.srchincipit = srchincipit
        if self.srchexplicit != srchexplicit: self.srchexplicit = srchexplicit
        lSign = []
        for item in self.goldsignatures.all().order_by('-editype'):
            lSign.append(item.short())
        siglist = json.dumps(lSign)
        if siglist != self.siglist: self.siglist = siglist
        # Do the saving initially
        response = super(SermonGold, self).save(force_insert, force_update, using, update_fields)

        return response

    def signatures(self):
        """Combine all signatures into one string"""

        lSign = []
        for item in self.goldsignatures.all().order_by('-editype'):
            lSign.append(item.short())
        return " | ".join(lSign)

    def signatures_ordered(self):
        """Ordered sample of gold signatures"""
        return self.goldsignatures.all().order_by("editype", "code")


class EqualGoldLink(models.Model):
    """Link to identical sermons that have a different signature"""

    # [1] Starting from equalgold group [src]
    #     Note: when a EqualGold is deleted, then the EqualGoldLink instance that refers to it is removed too
    src = models.ForeignKey(EqualGold, related_name="equalgold_src", on_delete=models.CASCADE)
    # [1] It equals equalgoldgroup [dst]
    dst = models.ForeignKey(EqualGold, related_name="equalgold_dst", on_delete=models.CASCADE)
    # [1] Each gold-to-gold link must have a linktype, with default "equal"
    linktype = models.CharField("Link type", choices=build_abbr_list(LINK_TYPE), max_length=5, default=LINK_EQUAL)
    # [0-1] Specification of directionality and source
    spectype = models.CharField("Specification", null=True,blank=True, choices=build_abbr_list(SPEC_TYPE), max_length=5)
    # [0-1] Alternatives
    alternatives = models.CharField("Alternatives", null=True,blank=True, choices=build_abbr_list(YESNO_TYPE), max_length=5)
    # [0-1] Notes
    note = models.TextField("Notes on this link", blank=True, null=True)

    def __str__(self):
        combi = "{} is {} of {}".format(self.src.code, self.linktype, self.dst.code)
        return combi

    def save(self, force_insert = False, force_update = False, using = None, update_fields = None):
        # Check for identical links
        if self.src == self.dst:
            response = None
        else:
            # Perform the actual save() method on [self]
            response = super(EqualGoldLink, self).save(force_insert, force_update, using, update_fields)
            # Adapt the ssgcount
            self.src.set_ssgcount()
            self.dst.set_ssgcount()
        # Return the actual save() method response
        return response

    def delete(self, using = None, keep_parents = False):
        eqg_list = [self.src, self.dst]
        response = super(EqualGoldLink, self).delete(using, keep_parents)
        for obj in eqg_list:
            obj.set_ssgcount()
        return response

    def get_label(self, do_incexpl=False):
        sBack = "{}: {}".format(self.get_linktype_display(), self.dst.get_label(do_incexpl))
        return sBack


class EqualGoldKeyword(models.Model):
    """Relation between an EqualGold and a Keyword"""

    # [1] The link is between a SermonGold instance ...
    equal = models.ForeignKey(EqualGold, related_name="equal_kw", on_delete=models.CASCADE)
    # [1] ...and a keyword instance
    keyword = models.ForeignKey(Keyword, related_name="equal_kw", on_delete=models.CASCADE)
    # [1] And a date: the date of saving this relation
    created = models.DateTimeField(default=get_current_datetime)


class SermonGoldSame(models.Model):
    """Link to identical sermons that have a different signature"""

    # [1] Starting from sermon [src]
    #     Note: when a SermonGold is deleted, then the SermonGoldSame instance that refers to it is removed too
    src = models.ForeignKey(SermonGold, related_name="sermongold_src", on_delete=models.CASCADE)
    # [1] It equals sermon [dst]
    dst = models.ForeignKey(SermonGold, related_name="sermongold_dst", on_delete=models.CASCADE)
    # [1] Each gold-to-gold link must have a linktype, with default "equal"
    linktype = models.CharField("Link type", choices=build_abbr_list(LINK_TYPE), 
                            max_length=5, default=LINK_EQUAL)

    def __str__(self):
        combi = "{} is {} of {}".format(self.src.signature, self.linktype, self.dst.signature)
        return combi


class SermonGoldKeyword(models.Model):
    """Relation between a SermonGold and a Keyword"""

    # [1] The link is between a SermonGold instance ...
    gold = models.ForeignKey(SermonGold, related_name="gold_sermongold_kw", on_delete=models.CASCADE)
    # [1] ...and a keyword instance
    keyword = models.ForeignKey(Keyword, related_name="keyword_sermongold_kw", on_delete=models.CASCADE)
    # [1] And a date: the date of saving this relation
    created = models.DateTimeField(default=get_current_datetime)

    def save(self, force_insert = False, force_update = False, using = None, update_fields = None):
        response = None
        # Note: only save if there is both a gold and a keyword
        if self.gold and self.keyword_id:
            response = super(SermonGoldKeyword, self).save(force_insert, force_update, using, update_fields)
        return response


class Ftextlink(models.Model):
    """Link to the full text of a critical edition of a Gold Sermon"""

    # [1] It must have a name - that is the Gryson book or the Clavis book or something
    url = models.URLField("Full text URL", max_length=LONG_STRING)
    # [1] Every edition belongs to exactly one gold-sermon
    #     Note: when a SermonGold is removed, this FtextLink also gets removed
    gold = models.ForeignKey(SermonGold, null=False, blank=False, related_name="goldftxtlinks", on_delete=models.CASCADE)

    def __str__(self):
        return self.url

    def short(self):
        return self.url


class ManuscriptExt(models.Model):
    """External URL (link) that belongs to a particular manuscript"""

    # [1] The URL itself
    url = models.URLField("External URL", max_length=LONG_STRING)
    # [1] Every external URL belongs to exactly one Manuscript
    manuscript = models.ForeignKey(Manuscript, null=False, blank=False, related_name="manuscriptexternals", on_delete=models.CASCADE)

    def __str__(self):
        return self.url

    def short(self):
        return self.url
       

class Collection(models.Model):
    """A collection can contain one or more sermons, manuscripts, gold sermons or super super golds"""
    
    # [1] Each collection has only 1 name 
    name = models.CharField("Name", null=True, blank=True, max_length=LONG_STRING)
    # [1] Each collection has only 1 owner
    owner = models.ForeignKey(Profile, null=True, related_name="owner_collections", on_delete=models.SET_NULL)    
    # [0-1] Each collection can be marked a "read only" by Passim-team  ERUIT
    readonly = models.BooleanField(default=False)
    # [1] Each "Collection" has only 1 type    
    type = models.CharField("Type of collection", choices=build_abbr_list(COLLECTION_TYPE), 
                            max_length=5)
    # [1] Each "collection" has a settype: pd (personal dataset) versus hc (historical collection)
    settype = models.CharField("Set type", choices=build_abbr_list(SET_TYPE), max_length=5, default="pd")
    # [0-1] Each collection can have one description
    descrip = models.CharField("Description", null=True, blank=True, max_length=LONG_STRING)
    # [0-1] Link to a description or bibliography (url) 
    url = models.URLField("Web info", null=True, blank=True)
    # [1] Path to register all additions and changes to each Collection (as stringified JSON list)
    path = models.TextField("History path", default="[]")
    # [1] The scope of this collection: who can view it?
    #     E.g: private, team, global - default is 'private'
    scope = models.CharField("Scope", choices=build_abbr_list(COLLECTION_SCOPE), default="priv",
                            max_length=5)
    # [0-1] Status note
    snote = models.TextField("Status note(s)", default="[]")
    # [1] Each collection has only 1 date/timestamp that shows when the collection was created
    created = models.DateTimeField(default=get_current_datetime)
    saved = models.DateTimeField(null=True, blank=True)

    # [0-1] Number of SSG authors -- if this is a settype='hc'
    ssgauthornum = models.IntegerField("Number of SSG authors", default=0, null=True, blank=True)

    # [0-n] Many-to-many: references per collection
    litrefs = models.ManyToManyField(Litref, through="LitrefCol", related_name="litrefs_collection")

    
    def __str__(self):
        return self.name

    def save(self, force_insert = False, force_update = False, using = None, update_fields = None):
        # Double check the number of authors, if this is settype HC
        if self.settype == "hc":
            ssg_id = self.super_col.all().values('super__id')
            authornum = Author.objects.filter(Q(author_equalgolds__id__in=ssg_id)).order_by('id').distinct().count()
            self.ssgauthornum = authornum
        # Adapt the save date
        self.saved = get_current_datetime()
        respons = super(Collection, self).save(force_insert, force_update, using, update_fields)
        return respons

    def freqsermo(self):
        """Frequency in manifestation sermons"""
        freq = self.collections_sermon.all().count()
        return freq
        
    def freqmanu(self):
        """Frequency in Manuscripts"""
        freq = self.collections_manuscript.all().count()
        return freq
        
    def freqgold(self):
        """Frequency of Gold sermons"""
        freq = self.collections_gold.all().count()
        return freq
        
    def freqsuper(self):
        """Frequency in Manuscripts"""
        freq = self.collections_super.all().count()
        return freq

    def get_authors_markdown(self):
        html = []
        if self.settype == "hc":
            ssg_id = self.super_col.all().values('super__id')
            for author in Author.objects.filter(Q(author_equalgolds__id__in=ssg_id)).order_by('name').distinct():
                dots = "" if len(author.name) < 20 else "..."
                html.append("<span class='authorname' title='{}'>{}{}</span>".format(author.name, author.name[:20], dots))
        sBack = ", ".join(html)
        return sBack

    def get_created(self):
        """REturn the creation date in a readable form"""

        sDate = self.created.strftime("%d/%b/%Y %H:%M")
        return sDate

    def get_copy(self, owner=None):
        """Create a copy of myself and return it"""

        oErr = ErrHandle()
        new_copy = None
        try:
            # Create one, copying the existing one
            new_owner = self.owner if owner == None else owner
            new_copy = Collection.objects.create(
                name = self.name, owner=new_owner, readonly=self.readonly,
                type = self.type, settype = self.settype, descrip = self.descrip,
                url = self.url, path = self.path, scope=self.scope)
            # Further action depends on the type we are
            if self.type == "manu":
                # Copy manuscripts
                qs = CollectionMan.objects.filter(collection=self).order_by("order")
                for obj in qs:
                    CollectionMan.objects.create(collection=new_copy, manuscript=obj.manuscript, order=obj.order)
            elif self.type == "sermo":
                # Copy sermons
                qs = CollectionSerm.objects.filter(collection=self).order_by("order")
                for obj in qs:
                    CollectionSerm.objects.create(collection=new_copy, sermon=obj.sermon, order=obj.order)
            elif self.type == "gold":
                # Copy gold sermons
                qs = CollectionGold.objects.filter(collection=self).order_by("order")
                for obj in qs:
                    CollectionGold.objects.create(collection=new_copy, gold=obj.gold, order=obj.order)
            elif self.type == "super":
                # Copy SSGs
                qs = CollectionSuper.objects.filter(collection=self).order_by("order")
                for obj in qs:
                    CollectionSuper.objects.create(collection=new_copy, super=obj.super, order=obj.order)

            # Change the name
            new_copy.name = "{}_{}".format(new_copy.name, new_copy.id)
            # Make sure to save it once more to process any changes in the save() function
            new_copy.save()
        except:
            msg = oErr.get_error_message()
            oErr.DoError("Collection/get_copy")
        return new_copy

    def get_elevate(self):
        html = []
        url = reverse("collhist_elevate", kwargs={'pk': self.id})
        html.append("<a class='btn btn-xs jumbo-1' href='{}'>Elevate".format(url))
        html.append("<span class='glyphicon glyphicon-share-alt'></span></a>")
        html.append("<span>Turn this dataset into a historical collection</span>")
        sBack = "\n".join(html)
        return sBack

    def get_label(self):
        """Return an appropriate name or label"""

        return self.name

    def get_litrefs_markdown(self):
        lHtml = []
        # Visit all literature references
        for litref in self.collection_litrefcols.all().order_by('reference__short'):
            # Determine where clicking should lead to
            url = "{}#lit_{}".format(reverse('literature_list'), litref.reference.id)
            # Create a display for this item
            lHtml.append("<span class='badge signature cl'><a href='{}'>{}</a></span>".format(url,litref.get_short_markdown()))

        sBack = ", ".join(lHtml)
        return sBack

    def get_manuscript_link(self):
        """Return a piece of HTML with the manuscript link for the user"""

        sBack = ""
        html = []
        if self.settype == "hc":
            # Creation of a new template based on this historical collection:
            url = reverse('collhist_temp', kwargs={'pk': self.id})
            html.append("<a href='{}' title='Create a template based on this historical collection'><span class='badge signature ot'>Create a Template based on this historical collection</span></a>".format(url))
            # Creation of a new manuscript based on this historical collection:
            url = reverse('collhist_manu', kwargs={'pk': self.id})
            html.append("<a href='{}' title='Create a manuscript based on this historical collection'><span class='badge signature gr'>Create a Manuscript based on this historical collection</span></a>".format(url))
            # Combine response
            sBack = "\n".join(html)
        return sBack

    def get_readonly_display(self):
        response = "yes" if self.readonly else "no"
        return response
        
    def get_scoped_queryset(type, username, team_group, settype="pd", scope = None):
        """Get a filtered queryset, depending on type and username"""

        # Initialisations
        if scope == None or scope == "":
            non_private = ['publ', 'team']
        elif scope == "priv":
            non_private = ['team']
        if settype == None or settype == "":
            settype="pd"
        oErr = ErrHandle()
        try:
            # Validate
            if scope == "publ":
                filter = Q(scope="publ")
            elif username and team_group and username != "" and team_group != "":
                # First filter on owner
                owner = Profile.get_user_profile(username)
                filter = Q(owner=owner)
                # Now check for permissions
                is_team = (owner.user.groups.filter(name=team_group).first() != None)
                # Adapt the filter accordingly
                if is_team:
                    # User is part of the team: may not see 'private' from others
                    if type:
                        filter = ( filter & Q(type=type)) | ( Q(scope__in=non_private) & Q(type=type) )
                    else:
                        filter = ( filter ) | ( Q(scope__in=non_private)  )
                elif scope == "priv":
                    # THis is a general user: may only see the public ones
                    if type:
                        filter = ( filter & Q(type=type))
                else:
                    # THis is a general user: may only see the public ones
                    if type:
                        filter = ( filter & Q(type=type)) | ( Q(scope="publ") & Q(type=type) )
                    else:
                        filter = ( filter ) | ( Q(scope="publ")  )
            else:
                filter = Q(type=type)
            # Make sure the settype is consistent
            filter = ( filter ) & Q(settype=settype)
            # Apply the filter
            qs = Collection.objects.filter(filter)
        except:
            msg = oErr.get_error_message()
            oErr.DoError("get_scoped_queryset")
            qs = Collection.objects.all()
        # REturn the result
        return qs

    def get_size_markdown(self):
        """Count the items that belong to me, depending on my type
        
        Create a HTML output
        """

        size = 0
        lHtml = []
        if self.type == "sermo":
            size = self.freqsermo()
            # Determine where clicking should lead to
            url = "{}?sermo-collist_s={}".format(reverse('sermon_list'), self.id)
        elif self.type == "manu":
            size = self.freqmanu()
            # Determine where clicking should lead to
            url = "{}?manu-collist_m={}".format(reverse('manuscript_list'), self.id)
        elif self.type == "gold":
            size = self.freqgold()
            # Determine where clicking should lead to
            url = "{}?gold-collist_sg={}".format(reverse('gold_list'), self.id)
        elif self.type == "super":
            size = self.freqsuper()
            # Determine where clicking should lead to
            if self.settype == "hc":
                url = "{}?ssg-collist_hist={}".format(reverse('equalgold_list'), self.id)
            else:
                url = "{}?ssg-collist_ssg={}".format(reverse('equalgold_list'), self.id)
        if size > 0:
            # Create a display for this topic
            lHtml.append("<span class='badge signature gr'><a href='{}'>{}</a></span>".format(url,size))
        sBack = ", ".join(lHtml)
        return sBack

    def get_hctemplate_copy(self, username, mtype):
        """Create a manuscript + sermons based on the SSGs in this collection"""

        # Double check to see that this is a SSG collection
        if self.settype != "hc" or self.type != "super":
            # THis is not the correct starting point
            return None

        # Now we know that we're okay...
        project = Project.get_default(username)
        profile = Profile.get_user_profile(username)
        source = SourceInfo.objects.create(
            code="Copy of Historical Collection [{}] (id={})".format(self.name, self.id), 
            collector=username, 
            profile=profile)

        # Create an empty Manuscript
        manu = Manuscript.objects.create(mtype=mtype, stype="imp", source=source, project=project)
        # Figure out  what the automatically created codico is
        codico = Codico.objects.filter(manuscript=manu).first()
        
        # Create all the sermons based on the SSGs
        msitems = []
        with transaction.atomic():
            order = 1
            for ssg in self.collections_super.all():
                # Create a MsItem
                msitem = MsItem.objects.create(manu=manu, codico=codico, order=order)
                order += 1
                # Add it to the list
                msitems.append(msitem)
                # Create a S based on this SSG
                sermon = SermonDescr.objects.create(
                    manu=manu, msitem=msitem, author=ssg.author, 
                    incipit=ssg.incipit, srchincipit=ssg.srchincipit,
                    explicit=ssg.explicit, srchexplicit=ssg.srchexplicit,
                    stype="imp", mtype=mtype)
                # Create a link from the S to this SSG
                ssg_link = SermonDescrEqual.objects.create(sermon=sermon, super=ssg, linktype=LINK_UNSPECIFIED)

        # Now walk and repair the links
        with transaction.atomic():
            size = len(msitems)
            for idx, msitem in enumerate(msitems):
                # Check if this is not the last one
                if idx < size-1:
                    msitem.next = msitems[idx+1]
                    msitem.save()

        # Okay, do we need to just make a manuscript, or a template?
        if mtype == "tem":
            # Create a template based on this new manuscript
            obj = Template.objects.create(manu=manu, profile=profile, name="Template_{}_{}".format(profile.user.username, manu.id),
                                          description="Created from Historical Collection [{}] (id={})".format(self.name, self.id))
        else:
            # Just a manuscript is okay
            obj = manu

        # Return the manuscript or the template that has been created
        return obj


class MsItem(models.Model):
    """One item in a manuscript - can be sermon or heading"""

    # ========================================================================
    # [1] Every MsItem belongs to exactly one manuscript
    #     Note: when a Manuscript is removed, all its associated MsItems are also removed
    #           and when an MsItem is removed, so is its SermonDescr or SermonHead
    manu = models.ForeignKey(Manuscript, null=True, on_delete = models.CASCADE, related_name="manuitems")

    # [1] Every MsItem also belongs to exactly one Codico (which is part of a manuscript)
    codico = models.ForeignKey(Codico, null=True, on_delete = models.SET_NULL, related_name="codicoitems")

    # ============= FIELDS FOR THE HIERARCHICAL STRUCTURE ====================
    # [0-1] Parent sermon, if applicable
    parent = models.ForeignKey('self', null=True, blank=True, on_delete = models.SET_NULL, related_name="sermon_parent")
    # [0-1] Parent sermon, if applicable
    firstchild = models.ForeignKey('self', null=True, blank=True, on_delete = models.SET_NULL, related_name="sermon_child")
    # [0-1] Parent sermon, if applicable
    next = models.ForeignKey('self', null=True, blank=True, on_delete = models.SET_NULL, related_name="sermon_next")
    # [1]
    order = models.IntegerField("Order", default = -1)

    def save(self, force_insert = False, force_update = False, using = None, update_fields = None):
        # Check if a manuscript is specified but not a codico
        if self.manu != None and self.codico == None:
            # Find out what the correct codico is from the manuscript
            codi = self.manu.manuscriptcodicounits.order_by('order').last()
            if codi != None:
                # Add this msitem by default to the correct codico
                self.codico = codi
        # Perform the actual saving
        response = super(MsItem, self).save(force_insert, force_update, using, update_fields)
        # Return the saving response
        return response

    def getdepth(self):
        depth = 1
        node = self
        while node.parent:
            # Repair strategy...
            if node.id == node.parent.id:
                # This is not correct -- need to repair
                node.parent = None
                node.save()
            else:
                depth += 1
                node = node.parent
        return depth

    def delete(self, using = None, keep_parents = False):
        # Keep track of manuscript
        manu = self.manu
        # Re-arrange anything pointing to me
        # (1) My children
        for child in self.sermon_parent.all():
            child.parent = self.parent
            child.save()
        # (2) A preceding pointing to me
        for prec in self.sermon_next.all():
            prec.next = self.next
            prec.save()
        # (3) Anything above me of whom I am firstchild
        for ance in self.sermon_child.all():
            ance.firstchild = self.firstchild
            ance.save()

        # Perform deletion
        response = super(MsItem, self).delete(using, keep_parents)
        # Re-calculate order
        if manu != None:
            manu.order_calculate()
        # REturn delete response
        return response

    def get_codistart(self):
        oBack = None
        if self.codico != None:
            codi_first = self.codico.codicoitems.order_by('order').first()
            if codi_first != None:
                if self.id == self.codico.codicoitems.order_by('order').first().id:
                    oBack = self.codico
        return oBack


class SermonHead(models.Model):
    """A hierarchical element in the manuscript structure"""

    # [0-1] Optional location of this sermon on the manuscript
    locus = models.CharField("Locus", null=True, blank=True, max_length=LONG_STRING)

    # [0-1] The title of this structural element to be shown
    title = models.CharField("Title", null=True, blank=True, max_length=LONG_STRING)

    # [1] Every SermonHead belongs to exactly one MsItem
    #     Note: one [MsItem] will have only one [SermonHead], but using an FK is easier for processing (than a OneToOneField)
    #           when the MsItem is removed, its SermonHead is too
    msitem = models.ForeignKey(MsItem, null=True, on_delete = models.CASCADE, related_name="itemheads")


class SermonDescr(models.Model):
    """A sermon is part of a manuscript"""

    # [0-1] Not every sermon might have a title ...
    title = models.CharField("Title", null=True, blank=True, max_length=LONG_STRING)

    # [0-1] Some (e.g. e-codices) may have a subtitle (field <rubric>)
    subtitle = models.CharField("Sub title", null=True, blank=True, max_length=LONG_STRING)

    # [0-1] Section title 
    sectiontitle = models.CharField("Section title", null=True, blank=True, max_length=LONG_STRING)

    # ======= OPTIONAL FIELDS describing the sermon ============
    # [0-1] We would very much like to know the *REAL* author
    author = models.ForeignKey(Author, null=True, blank=True, on_delete = models.SET_NULL, related_name="author_sermons")
    # [1] Every SermonDescr has a status - this is *NOT* related to model 'Status'
    autype = models.CharField("Author certainty", choices=build_abbr_list(CERTAINTY_TYPE), max_length=5, default="ave")
    # [0-1] But most often we only start out with having just a nickname of the author
    # NOTE: THE NICKNAME IS NO LONGER IN USE (oct/2019)
    nickname = models.ForeignKey(Nickname, null=True, blank=True, on_delete = models.SET_NULL, related_name="nickname_sermons")
    # [0-1] Optional location of this sermon on the manuscript
    locus = models.CharField("Locus", null=True, blank=True, max_length=LONG_STRING)
    # [0-1] We would like to know the INCIPIT (first line in Latin)
    incipit = models.TextField("Incipit", null=True, blank=True)
    srchincipit = models.TextField("Incipit (searchable)", null=True, blank=True)
    # [0-1] We would like to know the EXPLICIT (last line in Latin)
    explicit = models.TextField("Explicit", null=True, blank=True)
    srchexplicit = models.TextField("Explicit (searchable)", null=True, blank=True)
    # [0-1] Postscriptim
    postscriptum = models.TextField("Postscriptum", null=True, blank=True)
    # [0-1] If there is a QUOTE, we would like to know the QUOTE (in Latin)
    quote = models.TextField("Quote", null=True, blank=True)
    # [0-1] Christian feast like Easter etc
    feast = models.ForeignKey(Feast, null=True, blank=True, on_delete=models.SET_NULL, related_name="feastsermons")
    # [0-1] Notes on the bibliography, literature for this sermon
    bibnotes = models.TextField("Bibliography notes", null=True, blank=True)
    # [0-1] Any notes for this sermon
    note = models.TextField("Note", null=True, blank=True)
    # [0-1] Additional information 
    additional = models.TextField("Additional", null=True, blank=True)
    # [0-1] Any number of bible references (as stringified JSON list)
    bibleref = models.TextField("Bible reference(s)", null=True, blank=True)
    verses = models.TextField("List of verses", null=True, blank=True)

    # [1] Every SermonDescr has a status - this is *NOT* related to model 'Status'
    stype = models.CharField("Status", choices=build_abbr_list(STATUS_TYPE), max_length=5, default="man")
    # [0-1] Status note
    snote = models.TextField("Status note(s)", default="[]")
    # [1] And a date: the date of saving this sermon
    created = models.DateTimeField(default=get_current_datetime)

    # [1] Every SermonDescr may be a manifestation (default) or a template (optional)
    mtype = models.CharField("Manifestation type", choices=build_abbr_list(MANIFESTATION_TYPE), max_length=5, default="man")

    ## ================ Calculated fields ===============================
    ## [1] Number of sermons 'equal' to me
    #scount = models.IntegerField("Equal sermon count", default=0)

    ## ================ MANYTOMANY relations ============================

    # [0-n] Many-to-many: keywords per SermonDescr
    keywords = models.ManyToManyField(Keyword, through="SermonDescrKeyword", related_name="keywords_sermon")

    # [0-n] Link to one or more golden standard sermons
    #       NOTE: this link is legacy. We now have the EqualGold link through 'SermonDescrEqual'
    goldsermons = models.ManyToManyField(SermonGold, through="SermonDescrGold")

    # [0-n] Link to one or more SSG (equalgold)
    equalgolds = models.ManyToManyField(EqualGold, through="SermonDescrEqual", related_name="equalgold_sermons")

    # [m] Many-to-many: one sermon can be a part of a series of collections 
    collections = models.ManyToManyField("Collection", through="CollectionSerm", related_name="collections_sermon")

    # [m] Many-to-many: signatures linked manually through SermonSignature
    signatures = models.ManyToManyField("Signature", through="SermonSignature", related_name="signatures_sermon")

    # [m] Many-to-many: one manuscript can have a series of user-supplied comments
    comments = models.ManyToManyField(Comment, related_name="comments_sermon")

    # [m] Many-to-many: distances
    distances = models.ManyToManyField(EqualGold, through="SermonEqualDist", related_name="distances_sermons")

    # ========================================================================
    # [1] Every sermondescr belongs to exactly one manuscript
    #     Note: when a Manuscript is removed, all its associated SermonDescr are also removed
    manu = models.ForeignKey(Manuscript, null=True, on_delete = models.SET_NULL, related_name="manusermons")
    # [1] Every semondescr belongs to exactly one MsItem
    #     Note: one [MsItem] will have only one [SermonDescr], but using an FK is easier for processing (than a OneToOneField)
    #           when the MsItem is removed, so are we
    msitem = models.ForeignKey(MsItem, null=True, on_delete = models.CASCADE, related_name="itemsermons")

    # Automatically created and processed fields
    # [1] Every sermondesc has a list of signatures that are automatically created
    siglist = models.TextField("List of signatures", default="[]")

    # ============= FIELDS FOR THE HIERARCHICAL STRUCTURE ====================
    # [0-1] Parent sermon, if applicable
    parent = models.ForeignKey('self', null=True, blank=True, on_delete = models.SET_NULL, related_name="sermon_parent")
    # [0-1] Parent sermon, if applicable
    firstchild = models.ForeignKey('self', null=True, blank=True, on_delete = models.SET_NULL, related_name="sermon_child")
    # [0-1] Parent sermon, if applicable
    next = models.ForeignKey('self', null=True, blank=True, on_delete = models.SET_NULL, related_name="sermon_next")
    # [1]
    order = models.IntegerField("Order", default = -1)

    # [0-1] Method
    method = models.CharField("Method", max_length=LONG_STRING, default="(OLD)")

    # SPecification for download/upload
    specification = [
        {'name': 'Order',               'type': ''},
        {'name': 'Parent',              'type': ''},
        {'name': 'FirstChild',          'type': ''},
        {'name': 'Next',                'type': ''},
        {'name': 'Type',                'type': ''},
        {'name': 'Status',              'type': 'field', 'path': 'stype'},
        {'name': 'Locus',               'type': 'field', 'path': 'locus'},
        {'name': 'Attributed author',   'type': 'fk',    'path': 'author', 'fkfield': 'name'},
        {'name': 'Section title',       'type': 'field', 'path': 'sectiontitle'},
        {'name': 'Lectio',              'type': 'field', 'path': 'quote'},
        {'name': 'Title',               'type': 'field', 'path': 'title'},
        {'name': 'Incipit',             'type': 'field', 'path': 'incipit'},
        {'name': 'Explicit',            'type': 'field', 'path': 'explicit'},
        {'name': 'Postscriptum',        'type': 'field', 'path': 'postscriptum'},
        {'name': 'Feast',               'type': 'fk',    'path': 'feast', 'fkfield': 'name'},
        {'name': 'Bible reference(s)',  'type': 'func',  'path': 'brefs'},
        {'name': 'Cod. notes',          'type': 'field', 'path': 'additional'},
        {'name': 'Note',                'type': 'field', 'path': 'note'},
        {'name': 'Keywords',            'type': 'func',  'path': 'keywords'},
        {'name': 'Keywords (user)',     'type': 'func',  'path': 'keywordsU'},
        {'name': 'Gryson/Clavis (manual)',  'type': 'func',  'path': 'signaturesM'},
        {'name': 'Gryson/Clavis (auto)','type': 'func',  'path': 'signaturesA'},
        {'name': 'Personal Datasets',   'type': 'func',  'path': 'datasets'},
        {'name': 'Literature',          'type': 'func',  'path': 'literature'},
        {'name': 'SSG links',           'type': 'func',  'path': 'ssglinks'},
        ]

    def __str__(self):
        if self.author:
            sAuthor = self.author.name
        elif self.nickname:
            sAuthor = self.nickname.name
        else:
            sAuthor = "-"
        sSignature = "{}/{}".format(sAuthor,self.locus)
        return sSignature

    def adapt_nicknames():
        """Copy all nicknames to the 'NOTE' field and remove the nickname"""

        bOkay = True
        msg = ""
        oErr = ErrHandle()
        try:
            # Get all the SermonDescr that *have* a nickname, but whose *author* field is empty
            qs = SermonDescr.objects.exclude(nickname__isnull=True).filter(author__isnull=True)
            with transaction.atomic():
                for sermon in qs:
                    # Get the nickname
                    nickname = sermon.nickname.name
                    # Add it to the NOTE field
                    nicknote = "Possible author: **{}**".format(nickname)
                    if sermon.note == None:
                        sermon.note = nicknote
                    else:
                        sermon.note = "{} -- {}".format(sermon.note, nicknote)
                    sermon.save()
            # Now remove all nicknames
            with transaction.atomic():
                for sermon in SermonDescr.objects.all():
                    if sermon.nickname != None:
                        # Set the nickname link to 'None'
                        sermon.nickname = None
                        sermon.save()
            # Now remove the whole nickname table
            Nickname.objects.all().delete()
        except:
            msg = oErr.get_error_message()
            bOkay = False
        return bOkay, msg

    def adapt_verses(self):
        """Re-calculated what should be in [verses], and adapt if needed"""

        oErr = ErrHandle()
        bStatus = True
        msg = ""
        try:
            lst_verse = []
            for obj in self.sermonbibranges.all():
                lst_verse.append("{}".format(obj.get_fullref()))
            refstring = "; ".join(lst_verse)

            # Possibly update the field [bibleref] of the sermon
            if self.bibleref != refstring:
                self.bibleref = refstring
                self.save()

            oRef = Reference(refstring)
            # Calculate the scripture verses
            bResult, msg, lst_verses = oRef.parse()
            if bResult:
                verses = "[]" if lst_verses == None else json.dumps(lst_verses)
                if self.verses != verses:
                    self.verses = verses
                    self.save()
                    # All is well, so also adapt the ranges (if needed)
                    self.do_ranges(lst_verses)
            else:
                # Unable to parse this scripture reference
                bStatus = False
        except:
            msg = oErr.get_error_message()
            bStatus = False
        return bStatus, msg

    def custom_add(oSermo, manuscript, order=None):
        """Add a manuscript according to the specifications provided"""

        oErr = ErrHandle()
        obj = None
        lst_msg = []

        try:
            # Figure out whether this sermon item already exists or not
            locus = oSermo['locus']
            if locus != None and locus != "":
                # Try retrieve an existing or 
                obj = SermonDescr.objects.filter(msitem__manu=manuscript, locus=locus, mtype="man").first()
            if obj == None:
                # Create a MsItem
                msitem = MsItem(manu=manuscript)
                # Possibly add order, parent, firstchild, next
                if order != None: msitem.order = order
                # Save the msitem
                msitem.save()

                # Create a new SermonDescr with default values, tied to the msitem
                obj = SermonDescr.objects.create(msitem=msitem, stype="imp", mtype="man")
                        
            # Process all fields in the Specification
            for oField in SermonDescr.specification:
                field = oField.get("name").lower()
                value = oSermo.get(field)
                readonly = oField.get('readonly', False)
                
                if value != None and value != "" and not readonly:
                    type = oField.get("type")
                    path = oField.get("path")
                    if type == "field":
                        # Set the correct field's value
                        setattr(obj, path, value)
                    elif type == "fk":
                        fkfield = oField.get("fkfield")
                        model = oField.get("model")
                        if fkfield != None and model != None:
                            # Find an item with the name for the particular model
                            cls = apps.app_configs['seeker'].get_model(model)
                            instance = cls.objects.filter(**{"{}".format(fkfield): value}).first()
                            if instance != None:
                                setattr(obj, path, instance)
                    elif type == "func":
                        # Set the KV in a special way
                        obj.custom_set(path, value)

            # Make sure the updae the object
            obj.save()

        except:
            msg = oErr.get_error_message()
            oErr.DoError("SermonDescr/custom_add")
        return obj

    def custom_get(self, path, **kwargs):
        sBack = ""
        oErr = ErrHandle()
        try:
            profile = kwargs.get("profile")
            username = kwargs.get("username")
            team_group = kwargs.get("team_group")
            if path == "dateranges":
                qs = self.manuscript_dateranges.all().order_by('yearstart')
                dates = []
                for obj in qs:
                    dates.append(obj.__str__())
                sBack = json.dumps(dates)
            elif path == "keywords":
                sBack = self.get_keywords_markdown(plain=True)
            elif path == "keywordsU":
                sBack =  self.get_keywords_user_markdown(profile, plain=True)
            elif path == "datasets":
                sBack = self.get_collections_markdown(username, team_group, settype="pd", plain=True)
            elif path == "literature":
                sBack = self.get_litrefs_markdown(plain=True)
            elif path == "origin":
                sBack = self.get_origin()
            elif path == "provenances":
                sBack = self.get_provenance_markdown(plain=True)
            elif path == "external":
                sBack = self.get_external_markdown(plain=True)
            elif path == "brefs":
                sBack = self.get_bibleref(plain=True)
            elif path == "signaturesM":
                sBack = self.get_sermonsignatures_markdown(plain=True)
            elif path == "signaturesA":
                sBack = self.get_eqsetsignatures_markdown(plain=True)
            elif path == "ssglinks":
                sBack = self.get_eqset(plain=True)
        except:
            msg = oErr.get_error_message()
            oErr.DoError("SermonDescr/custom_get")
        return sBack

    def custom_getkv(self, item, **kwargs):
        """Get key and value from the manuitem entry"""

        oErr = ErrHandle()
        key = ""
        value = ""
        try:
            key = item['name']
            if self != None:
                if item['type'] == 'field':
                    value = getattr(self, item['path'])
                elif item['type'] == "fk":
                    fk_obj = getattr(self, item['path'])
                    if fk_obj != None:
                        value = getattr( fk_obj, item['fkfield'])
                elif item['type'] == 'func':
                    value = self.custom_get(item['path'], kwargs=kwargs)
                    # Adaptation for empty lists
                    if value == "[]": value = ""
        except:
            msg = oErr.get_error_message()
            oErr.DoError("SermonDescr/custom_getkv")
        return key, value

    def custom_set(self, path, value, **kwargs):
        """Set related items"""

        bResult = True
        oErr = ErrHandle()
        try:
            profile = kwargs.get("profile")
            username = kwargs.get("username")
            team_group = kwargs.get("team_group")
            value_lst = []
            if isinstance(value, str):
                if value[0] == '[':
                    # Make list from JSON
                    value_lst = json.loads(value)
                else:
                    value_lst = value.split(",")
                    for idx, item in enumerate(value_lst):
                        value_lst[idx] = value_lst[idx].strip()
            # Note: we skip a number of fields that are determined automatically
            #       [ stype ]
            if path == "brefs":
                # Set the 'bibleref' field. Note: do *NOT* use value_lst here
                self.bibleref = value
                # Turn this into BibRange
                self.do_ranges()
            elif path == "keywordsU":
                # Get the list of keywords
                user_keywords = value_lst #  get_json_list(value)
                for kw in user_keywords:
                    # Find the keyword
                    keyword = Keyword.objects.filter(name__iexact=kw).first()
                    if keyword != None:
                        # Add this keyword to the sermon for this user
                        UserKeyword.objects.create(keyword=keyword, profile=profile, sermo=self)
            elif path == "datasets":
                # Walk the personal datasets
                datasets = value_lst #  get_json_list(value)
                for ds_name in datasets:
                    # Get the actual dataset
                    collection = Collection.objects.filter(name=ds_name, owner=profile, type="sermo", settype="pd").first()
                    # Does it exist?
                    if collection == None:
                        # Create this set
                        collection = Collection.objects.create(name=ds_name, owner=profile, type="sermo", settype="pd")
                    # Add manuscript to collection
                    highest = collection.collections_sermon.all().order_by('-order').first()
                    order = 1 if higest == None else highest + 1
                    CollectionSerm.objects.create(collection=collection, sermon=self, order=order)
            elif path == "ssglinks":
                ssglink_names = value_lst #  get_json_list(value)
                for ssg_code in ssglink_names:
                    # Get this SSG
                    ssg = EqualGold.objects.filter(code__iexact=ssg_code).first()

                    if ssg == None:
                        # Indicate that we didn't find it in the notes
                        intro = ""
                        if self.note != "": intro = "{}. ".format(self.note)
                        self.note = "{}Please set manually the SSG link [{}]".format(intro, ssg_code)
                        self.save()
                    else:
                        # Make link between SSG and SermonDescr
                        SermonDescrEqual.objects.create(sermon=self, super=ssg, linktype="eqs")
                # Ready
            elif path == "signaturesM":
                signatureM_names = value_lst #  get_json_list(value)
                for code in signatureM_names:
                    # Find the SIgnature
                    signature = Signature.objects.filter(code__iexact=code).first()
                    # Find the editype
                    if signature == None:
                        editype = "gr"
                        if "CPPM" in code:
                            editype = "cl"
                    else:
                        editype = signature.editype
                    # Create a manual signature
                    sig_m = SermonSignature.objects.create(code=code, gsig=signature, sermon=self, editype=editype)
                # Ready
            else:
                # Figure out what to do in this case
                pass
        except:
            msg = oErr.get_error_message()
            oErr.DoError("SermonDescr/custom_set")
            bResult = False
        return bResult

    def delete(self, using = None, keep_parents = False):
        # Keep track of the msitem, if I have one
        msitem = self.msitem
        # Regular delete operation
        response = super(SermonDescr, self).delete(using, keep_parents)
        # Now delete the msitem, if it is there
        if msitem != None:
            msitem.delete()
        return response

    def do_distance(self, bForceUpdate = False):
        """Calculate the distance from myself (sermon) to all currently available EqualGold SSGs"""

        def get_dist(inc_s, exp_s, inc_eqg, exp_eqg):
            # Get the inc and exp for the SSG
            #inc_eqg = super.srchincipit
            #exp_eqg = super.srchexplicit
            # Calculate distances
            similarity = similar(inc_s, inc_eqg) + similar(exp_s, exp_eqg)
            if similarity == 0.0:
                dist = 100000
            else:
                dist = 2 / similarity
            return dist

        oErr = ErrHandle()
        try:
            # Get my own incipit and explicit
            inc_s = "" if self.srchincipit == None else self.srchincipit
            exp_s = "" if self.srchexplicit == None else self.srchexplicit

            # Make sure we only start doing something if it is really needed
            count = self.distances.count()
            if inc_s != "" or exp_s != "" or count > 0:
                # Get a list of the current EqualGold elements in terms of id, srchinc/srchexpl
                eqg_list = EqualGold.objects.all().values('id', 'srchincipit', 'srchexplicit')

                # Walk all EqualGold objects
                with transaction.atomic():
                    # for super in EqualGold.objects.all():
                    for item in eqg_list:
                        # Get an object
                        super_id = item['id']
                        obj = SermonEqualDist.objects.filter(sermon=self, super=super_id).first()
                        if obj == None:
                            # Get the distance
                            dist = get_dist(inc_s, exp_s, item['srchincipit'], item['srchexplicit'])
                            # Create object and Set this distance
                            obj = SermonEqualDist.objects.create(sermon=self, super_id=super_id, distance=dist)
                        elif bForceUpdate:
                            # Calculate and change the distance
                            obj.distance = get_dist(inc_s, exp_s, item['srchincipit'], item['srchexplicit'])
                            obj.save()
        except:
            msg = oErr.get_error_message()
            oErr.DoError("do_distance")
        # No need to return anything
        return None

    def do_ranges(self, lst_verses = None, force = False):
        bResult = True
        if self.bibleref == None or self.bibleref == "":
            # Remove any existing bibrange objects
            self.sermonbibranges.all().delete()
        else:
            # done = Information.get_kvalue("biblerefs")
            if force or self.verses == None or self.verses == "" or self.verses == "[]" or lst_verses != None:
                # Open a Reference object
                oRef = Reference(self.bibleref)

                # Do we have verses already?
                if lst_verses == None:

                    # Calculate the scripture verses
                    bResult, msg, lst_verses = oRef.parse()
                else:
                    bResult = True
                if bResult:
                    # Add this range to the sermon (if it's not there already)
                    verses = json.dumps(lst_verses)
                    if self.verses != verses:
                        self.verses = verses
                        self.save()
                    # Check and add (if needed) the corresponding BibRange object
                    for oScrref in lst_verses:
                        intro = oScrref.get("intro", None)
                        added = oScrref.get("added", None)
                        # THis is one book and a chvslist
                        book, chvslist = oRef.get_chvslist(oScrref)

                        # Possibly create an appropriate Bibrange object (or emend it)
                        # Note: this will also add BibVerse objects
                        obj = BibRange.get_range(self, book, chvslist, intro, added)
                        
                        if obj == None:
                            # Show that something went wrong
                            print("do_ranges0 unparsable: {}".format(self.bibleref), file=sys.stderr)
                        else:
                            # Add BibVerse objects if needed
                            verses_new = oScrref.get("scr_refs", [])
                            verses_old = [x.bkchvs for x in obj.bibrangeverses.all()]
                            # Remove outdated verses
                            deletable = []
                            for item in verses_old:
                                if item not in verses_new: deletable.append(item)
                            if len(deletable) > 0:
                                obj.bibrangeverses.filter(bkchvs__in=deletable).delete()
                            # Add new verses
                            with transaction.atomic():
                                for item in verses_new:
                                    if not item in verses_old:
                                        verse = BibVerse.objects.create(bibrange=obj, bkchvs=item)
                    print("do_ranges1: {} verses={}".format(self.bibleref, self.verses), file=sys.stderr)
                else:
                    print("do_ranges2 unparsable: {}".format(self.bibleref), file=sys.stderr)
        return None
    
    def do_signatures(self):
        """Create or re-make a JSON list of signatures"""

        lSign = []
        for item in self.sermonsignatures.all():
            lSign.append(item.short())
        self.siglist = json.dumps(lSign)
        # And save myself
        self.save()

    def getdepth(self):
        depth = 1
        node = self
        while node.parent:
            # Repair strategy...
            if node.id == node.parent.id:
                # This is not correct -- need to repair
                node.parent = None
                node.save()
            else:
                depth += 1
                node = node.parent
        return depth

    def get_author(self):
        """Get the name of the author"""

        if self.author:
            sName = self.author.name
            # Also get the certainty level of the author and the corresponding flag color
            sAuType = self.get_autype()

            # Combine all of this
            sBack = "<span>{}</span>&nbsp;{}".format(sName, sAuType)
        else:
            sBack = "-"
        return sBack

    def get_autype(self):
        # Also get the certainty level of the author and the corresponding flag color
        autype = self.autype
        color = "red"
        title = ""
        if autype == CERTAIN_LOWEST: 
            color = "red"
            title = "Author: very uncertain"
        elif autype == CERTAIN_LOW: 
            color = "orange"
            title = "Author: uncertain"
        elif autype == CERTAIN_AVE: 
            color = "gray"
            title = "Author: average certainty"
        elif autype == CERTAIN_HIGH: 
            color = "lightgreen"
            title = "Author: reasonably certain"
        else: 
            color = "green"
            title = "Author: very certain"

        # Combine all of this
        sBack = "<span class='glyphicon glyphicon-flag' title='{}' style='color: {};'></span>".format(title, color)
        return sBack

    def get_bibleref(self, plain=False):
        """Interpret the BibRange objects into a proper view"""

        bAutoCorrect = False

        # First attempt: just show .bibleref
        sBack = self.bibleref
        # Or do we have BibRange objects?
        if self.sermonbibranges.count() > 0:
            html = []
            for obj in self.sermonbibranges.all().order_by('book__idno', 'chvslist'):
                # Find out the URL of this range
                url = reverse("bibrange_details", kwargs={'pk': obj.id})
                # Add this range
                intro = "" 
                if obj.intro != None and obj.intro != "":
                    intro = "{} ".format(obj.intro)
                added = ""
                if obj.added != None and obj.added != "":
                    added = " ({})".format(obj.added)
                if plain:
                    bref_display = "{}{} {}{}".format(intro, obj.book.latabbr, obj.chvslist, added)
                else:
                    bref_display = "<span class='badge signature ot' title='{}'><a href='{}'>{}{} {}{}</a></span>".format(
                        obj, url, intro, obj.book.latabbr, obj.chvslist, added)
                html.append(bref_display)
            sBack = "; ".join(html)
            # Possibly adapt the bibleref
            if bAutoCorrect and self.bibleref != sBack:
                self.bibleref = sBack
                self.save()

        # Return what we have
        return sBack

    def get_collection_link(self, settype):
        lHtml = []
        lstQ = []
        # Get all the SSG to which I link
        lstQ.append(Q(super_col__super__in=self.equalgolds.all()))
        lstQ.append(Q(settype=settype))
        # Make sure we restrict ourselves to the *public* datasets
        lstQ.append(Q(scope="publ"))
        # Get the collections in which these SSGs are
        collections = Collection.objects.filter(*lstQ).order_by('name')
        # Visit all datasets/collections linked to me via the SSGs
        for col in collections:
            # Determine where clicking should lead to
            # url = "{}?sermo-collist_s={}".format(reverse('sermon_list'), col.id)
            if settype == "hc":
                url = reverse("collhist_details", kwargs={'pk': col.id})
            else:
                url = reverse("collpubl_details", kwargs={'pk': col.id})
            # Create a display for this topic
            lHtml.append("<span class='collection'><a href='{}'>{}</a></span>".format(url,col.name))

        sBack = ", ".join(lHtml)
        return sBack
    
    def get_collections_markdown(self, username, team_group, settype = None, plain=False):
        lHtml = []
        # Visit all collections that I have access to
        mycoll__id = Collection.get_scoped_queryset('sermo', username, team_group, settype = settype).values('id')
        for col in self.collections.filter(id__in=mycoll__id).order_by('name'):
            if plain:
                lHtml.append(col.name)
            else:
                # Determine where clicking should lead to
                url = "{}?sermo-collist_s={}".format(reverse('sermon_list'), col.id)
                # Create a display for this topic
                lHtml.append("<span class='collection'><a href='{}'>{}</a></span>".format(url,col.name))

        if plain:
            sBack = json.dumps(lHtml)
        else:
            sBack = ", ".join(lHtml)
        return sBack

    def get_editions_markdown(self):

        # Initialisations
        lHtml = []
        ssg_list = []

        # Visit all linked SSG items
        #    but make sure to exclude the template sermons
        for linked in SermonDescrEqual.objects.filter(sermon=self).exclude(sermon__mtype="tem"):
            # Add this SSG
            ssg_list.append(linked.super.id)

        # Get a list of all the SG that are in these equality sets
        gold_list = SermonGold.objects.filter(equal__in=ssg_list).order_by('id').distinct().values("id")

        # Visit all the editions references of this gold sermon 
        for edi in EdirefSG.objects.filter(sermon_gold_id__in=gold_list).order_by('-reference__year', 'reference__short').distinct():
            # Determine where clicking should lead to
            url = "{}#edi_{}".format(reverse('literature_list'), edi.reference.id)
            # Create a display for this item
            edi_display = "<span class='badge signature ot'><a href='{}'>{}</a></span>".format(url,edi.get_short_markdown())
            if edi_display not in lHtml:
                lHtml.append(edi_display)
                
        sBack = ", ".join(lHtml)
        return sBack

    def get_explicit(self):
        """Return the *searchable* explicit, without any additional formatting"""
        return self.srchexplicit

    def get_explicit_markdown(self):
        """Get the contents of the explicit field using markdown"""
        return adapt_markdown(self.explicit)

    def get_eqsetcount(self):
        """Get the number of SSGs this sermon is part of"""

        # Visit all linked SSG items
        #    NOTE: do not filter out mtype=tem
        ssg_count = SermonDescrEqual.objects.filter(sermon=self).count()
        return ssg_count

    def get_eqset(self, plain=True):
        """GEt a list of SSGs linked to this SermonDescr"""

        oErr = ErrHandle()
        sBack = ""
        try:
            ssg_list = self.equalgolds.all().values('code')
            code_list = [x['code'] for x in ssg_list if x['code'] != None]
            if plain:
                sBack = json.dumps(code_list)
            else:
                sBack = ", ".join(code_list)
        except:
            msg = oErr.get_error_message()
            oErr.DoError("get_eqset")
        return sBack

    def get_eqsetsignatures_markdown(self, type="all", plain=False):
        """Get the signatures of all the sermon Gold instances in the same eqset"""

        # Initialize
        lHtml = []
        lEqual = []
        lSig = []
        ssg_list = []

        # Get all linked SSG items
        #for linked in self.sermondescr_super.all():
        #    ssg_list.append(linked.id)
        ssg_list = self.equalgolds.all().values('id')

        # Get a list of all the SG that are in these equality sets
        gold_list = SermonGold.objects.filter(equal__in=ssg_list).order_by('id').distinct().values("id")

        if type == "combi":
            # Need to have both the automatic as well as the manually linked ones
            gold_id_list = [x['id'] for x in gold_list]
            auto_list = copy.copy(gold_id_list)
            manual_list = []
            for sig in self.sermonsignatures.all().order_by('-editype', 'code'):
                if sig.gsig:
                    gold_id_list.append(sig.gsig.gold.id)
                else:
                    manual_list.append(sig.id)
            # (a) Show the gold signatures
            for sig in Signature.objects.filter(gold__id__in=gold_id_list).order_by('-editype', 'code'):
                # Determine where clicking should lead to
                url = "{}?gold-siglist={}".format(reverse('gold_list'), sig.id)
                # Check if this is an automatic code
                auto = "" if sig.gold.id in auto_list else "view-mode"
                lHtml.append("<span class='badge signature {} {}'><a href='{}'>{}</a></span>".format(sig.editype, auto, url,sig.code))
            # (b) Show the manual ones
            for sig in self.sermonsignatures.filter(id__in=manual_list).order_by('-editype', 'code'):
                # Create a display for this topic - without URL
                lHtml.append("<span class='badge signature {}'>{}</span>".format(sig.editype,sig.code))
        else:
            # Get an ordered set of signatures - automatically linked
            for sig in Signature.objects.filter(gold__in=gold_list).order_by('-editype', 'code'):
                # Create a display for this topic
                if plain:
                    lHtml.append(sig.code)
                else:
                    if type == "first":
                        # Determine where clicking should lead to
                        url = reverse('gold_details', kwargs={'pk': sig.gold.id})
                        lHtml.append("<span class='badge jumbo-1'><a href='{}' title='Go to the Sermon Gold'>{}</a></span>".format(url,sig.code))
                        break
                    else:
                        # Determine where clicking should lead to
                        url = "{}?gold-siglist={}".format(reverse('gold_list'), sig.id)
                        lHtml.append("<span class='badge signature {}'><a href='{}'>{}</a></span>".format(sig.editype,url,sig.code))

        if plain:
            sBack = json.dumps(lHtml)
        else:
            sBack = "<span class='view-mode'>,</span> ".join(lHtml)
        return sBack

    def get_feast(self):
        sBack = ""
        if self.feast != None:
            url = reverse("feast_details", kwargs={'pk': self.feast.id})
            sBack = "<span class='badge signature ot'><a href='{}'>{}</a></span>".format(url, self.feast.name)
        return sBack

    def get_goldlinks_markdown(self):
        """Return all the gold links = type + gold"""

        lHtml = []
        sBack = ""
        for goldlink in self.sermondescr_gold.all().order_by('sermon__author__name', 'sermon__siglist'):
            lHtml.append("<tr class='view-row'>")
            lHtml.append("<td valign='top'><span class='badge signature ot'>{}</span></td>".format(goldlink.get_linktype_display()))
            # for gold in self.goldsermons.all().order_by('author__name', 'siglist'):
            url = reverse('gold_details', kwargs={'pk': goldlink.gold.id})
            lHtml.append("<td valign='top'><a href='{}'>{}</a></td>".format(url, goldlink.gold.get_view()))
            lHtml.append("</tr>")
        if len(lHtml) > 0:
            sBack = "<table><tbody>{}</tbody></table>".format( "".join(lHtml))
        return sBack

    def get_hcs_plain(self, username = None, team_group=None):
        """Get all the historical collections associated with this sermon"""
        lHtml = []
        # Get all the SSG's linked to this manifestation
        qs_ssg = self.equalgolds.all().values('id')
        # qs_hc = self.collections.all()
        lstQ = []
        lstQ.append(Q(settype="hc"))
        lstQ.append(Q(collections_super__id__in=qs_ssg))
        
        if username == None or team_group == None:
            qs_hc = Collection.objects.filter(*lstQ )
        else:
            qs_hc = Collection.get_scoped_queryset("super", username, team_group, settype="hc").filter(collections_super__id__in=qs_ssg)
        # TODO: filter on (a) public only or (b) private but from the current user
        for col in qs_hc:
            # Determine where clicking should lead to
            url = reverse('collhist_details', kwargs={'pk': col.id})
            # Create a display for this topic
            lHtml.append('<span class="badge signature ot"><a href="{}" >{}</a></span>'.format(url,col.name))

        sBack = ", ".join(lHtml)
        return sBack

    def get_incexp_match(self, sMatch=""):
        html = []
        dots = "..." if self.incipit else ""
        sBack = "{}{}{}".format(self.srchincipit, dots, self.srchexplicit)
        ratio = 0.0
        # Are we matching with something?
        if sMatch != "":
            sBack, ratio = get_overlap(sBack, sMatch)
        return sBack, ratio

    def get_incipit(self):
        """Return the *searchable* incipit, without any additional formatting"""
        return self.srchincipit

    def get_incipit_markdown(self):
        """Get the contents of the incipit field using markdown"""

        # Sanity check
        if self.incipit != None and self.incipit != "":
            if self.srchincipit == None or self.srchincipit == "":
                SermonDescr.init_latin()

        return adapt_markdown(self.incipit)

    def get_keywords_plain(self):
        lHtml = []
        # Visit all keywords
        for keyword in self.keywords.all().order_by('name'):
            # Create a display for this topic
            lHtml.append("<span class='keyword'>{}</span>".format(keyword.name))

        sBack = ", ".join(lHtml)
        return sBack

    def get_keywords_markdown(self, plain=False):
        lHtml = []
        # Visit all keywords
        for keyword in self.keywords.all().order_by('name'):
            if plain:
                lHtml.append(keyword.name)
            else:
                # Determine where clicking should lead to
                url = "{}?sermo-kwlist={}".format(reverse('sermon_list'), keyword.id)
                # Create a display for this topic
                lHtml.append("<span class='keyword'><a href='{}'>{}</a></span>".format(url,keyword.name))

        if plain:
            sBack = json.dumps(lHtml)
        else:
            sBack = ", ".join(lHtml)
        return sBack

    def get_keywords_user_markdown(self, profile, plain=False):
        lHtml = []
        # Visit all keywords
        for kwlink in self.sermo_userkeywords.filter(profile=profile).order_by('keyword__name'):
            keyword = kwlink.keyword
            if plain:
                lHtml.append(keyword.name)
            else:
                # Determine where clicking should lead to
                url = "{}?sermo-ukwlist={}".format(reverse('sermon_list'), keyword.id)
                # Create a display for this topic
                lHtml.append("<span class='keyword'><a href='{}'>{}</a></span>".format(url,keyword.name))

        if plain:
            sBack = json.dumps(lHtml)
        else:
            sBack = ", ".join(lHtml)
        return sBack

    def get_keywords_ssg_markdown(self):
        """Get all the keywords attached to the SSG of which I am part"""

        lHtml = []
        # Get all the SSGs to which I link with equality
        # ssg_id = EqualGold.objects.filter(sermondescr_super__sermon=self, sermondescr_super__linktype=LINK_EQUAL).values("id")
        ssg_id = self.equalgolds.all().values("id")
        # Get all keywords attached to these SGs
        qs = Keyword.objects.filter(equal_kw__equal__id__in=ssg_id).order_by("name").distinct()
        # Visit all keywords
        for keyword in qs:
            # Determine where clicking should lead to
            url = "{}?ssg-kwlist={}".format(reverse('equalgold_list'), keyword.id)
            # Create a display for this topic
            lHtml.append("<span class='keyword'><a href='{}'>{}</a></span>".format(url,keyword.name))

        sBack = ", ".join(lHtml)
        return sBack

    def get_keywords_ssg_plain(self):
        """Get all the keywords attached to the SSG of which I am part"""

        lHtml = []
        # Get all the SSGs to which I link with equality
        # ssg_id = EqualGold.objects.filter(sermondescr_super__sermon=self, sermondescr_super__linktype=LINK_EQUAL).values("id")
        ssg_id = self.equalgolds.all().values("id")
        # Get all keywords attached to these SGs
        qs = Keyword.objects.filter(equal_kw__equal__id__in=ssg_id).order_by("name").distinct()
        # Visit all keywords
        for keyword in qs:
            # Create a display for this topic
            lHtml.append("<span class='keyword'>{}</span>".format(keyword.name))

        sBack = ", ".join(lHtml)
        return sBack

    def get_litrefs_markdown(self, plain=False):
        # Pass on all the literature from Manuscript to each of the Sermons of that Manuscript
               
        lHtml = []
        # (1) First the litrefs from the manuscript: 
        # manu = self.manu
        # lref_list = []
        for item in LitrefMan.objects.filter(manuscript=self.get_manuscript()).order_by('reference__short', 'pages'):
            if plain:
                lHtml.append(item.get_short_markdown())
            else:
                # Determine where clicking should lead to
                url = "{}#lit_{}".format(reverse('literature_list'), item.reference.id)
                # Create a display for this item
                lHtml.append("<span class='badge signature gr' title='Manuscript literature'><a href='{}'>{}</a></span>".format(
                    url,item.get_short_markdown()))
       
        # (2) The literature references available in all the SGs that are part of the SSG
        ssg_id = self.equalgolds.all().values('id')
        #     Note: the *linktype* for SSG-S doesn't matter anymore
        # ssg_id = [x.super.id for x in SermonDescrEqual.objects.filter(sermon=self)]
        gold_id = SermonGold.objects.filter(equal__id__in=ssg_id).values('id')
        # Visit all the litrefSGs
        for item in LitrefSG.objects.filter(sermon_gold__id__in = gold_id).order_by('reference__short', 'pages'):
            if plain:
                lHtml.append(item.get_short_markdown())
            else:
                # Determine where clicking should lead to
                url = "{}#lit_{}".format(reverse('literature_list'), item.reference.id)
                # Create a display for this item
                lHtml.append("<span class='badge signature cl' title='(Related) sermon gold literature'><a href='{}'>{}</a></span>".format(
                    url,item.get_short_markdown()))

        if plain:
            sBack = json.dumps(lHtml)
        else:
            sBack = ", ".join(lHtml)
        return sBack

    def get_locus(self):
        locus = "-" if self.locus == None or self.locus == "" else self.locus
        url = reverse('sermon_details', kwargs={'pk': self.id})
        sBack = "<span class='clickable'><a class='nostyle' href='{}'>{}</a></span>".format(url, locus)
        return sBack

    def get_manuscript(self):
        """Get the manuscript that links to this sermondescr"""

        manu = None
        if self.msitem and self.msitem.manu:
            manu = self.msitem.manu
        return manu

    def get_note_markdown(self):
        """Get the contents of the note field using markdown"""
        return adapt_markdown(self.note)

    def get_passimcode_markdown(self):
        """Get the Passim code (and a link to it)"""

        sBack = ""
        # Get the first equalgold
        equal = self.equalgolds.all().order_by('code', 'author__name', 'number').first()
        if equal != None and equal.code != "":
            url = reverse('equalgold_details', kwargs={'pk': equal.id})
            sBack = "<span  class='badge jumbo-1'><a href='{}'  title='Go to the Super Sermon Gold'>{}</a></span>".format(url, equal.code)
        return sBack

    def get_postscriptum_markdown(self):
        """Get the contents of the postscriptum field using markdown"""
        return adapt_markdown(self.postscriptum)

    def get_quote_markdown(self):
        """Get the contents of the quote field using markdown"""
        return adapt_markdown(self.quote)

    def get_scount(self):
        """Calculate how many sermons are associated with the same SSGs that I am associated with"""

        scount = 0
        scount_lst = self.equalgolds.values('scount')
        for item in scount_lst: scount += item['scount']
        return scount

    def get_sermonsig(self, gsig):
        """Get the sermon signature equivalent of the gold signature gsig"""

        if gsig == None: return None
        # Initialise
        sermonsig = None
        # Check if the gold signature figures in related gold sermons
        qs = self.sermonsignatures.all()
        for obj in qs:
            if obj.gsig.id == gsig.id:
                # Found it
                sermonsig = obj
                break
            elif obj.editype == gsig.editype and obj.code == gsig.code:
                # Found it
                sermonsig = obj
                # But also set the gsig feature
                obj.gsig = gsig
                obj.save()
                break
        if sermonsig == None:
            # Create a new SermonSignature based on this Gold Signature
            sermonsig = SermonSignature(sermon=self, gsig=gsig, editype=gsig.editype, code=gsig.code)
            sermonsig.save()
        # Return the sermon signature
        return sermonsig

    def get_sermonsignatures_markdown(self, plain=False):
        lHtml = []
        # Visit all signatures
        for sig in self.sermonsignatures.all().order_by('-editype', 'code'):
            if plain:
                lHtml.append(sig.code)
            else:
                # Determine where clicking should lead to
                url = ""
                if sig.gsig:
                    url = "{}?sermo-siglist={}".format(reverse('sermon_list'), sig.gsig.id)
                # Create a display for this topic
                lHtml.append("<span class='badge signature {}'><a href='{}'>{}</a></span>".format(sig.editype,url,sig.code))

        if plain:
            sBack = json.dumps(lHtml)
        else:
            sBack = ", ".join(lHtml)
        return sBack

    def get_stype_light(self, usercomment=False):
        count = 0
        if usercomment:
            count = self.comments.count()
        sBack = get_stype_light(self.stype, usercomment, count)
        return sBack

    def get_template_link(self, profile):
        sBack = ""
        # Check if I am a template
        if self.mtype == "tem":
            # add a clear TEMPLATE indicator with a link to the actual template
            template = Template.objects.filter(manu=self.msitem.manu).first()
            # Wrong template = Template.objects.filter(manu=self.msitem.manu, profile=profile).first()
            # (show template even if it isn't my own one)
            if template:
                url = reverse('template_details', kwargs={'pk': template.id})
                sBack = "<div class='template_notice'>THIS IS A <span class='badge'><a href='{}'>TEMPLATE</a></span></div>".format(url)
        return sBack

    def goldauthors(self):
        # Pass on all the linked-gold editions + get all authors from the linked-gold stuff
        lst_author = []
        # Visit all linked gold sermons
        for linked in SermonDescrGold.objects.filter(sermon=self, linktype=LINK_EQUAL):
            # Access the gold sermon
            gold = linked.gold
            # Does this one have an author?
            if gold.author != None:
                lst_author.append(gold.author)
        return lst_author

    def goldeditions_ordered(self):
        """Provide an ordered list of EdirefSG connected to me through related gold sermons"""

        lstQ = []
        lstQ.append(Q(sermon_gold__in=self.goldsermons.all()))
        edirefsg_ordered = EdirefSG.objects.filter(*lstQ).order_by("reference__short")
        return edirefsg_ordered

    def goldsignatures_ordered(self):
        """Provide an ordered list of (gold) signatures that line up with the sermonsignatures linked to me"""

        sig_ordered = []
        # Get the list of sermon signatures connected to me
        for sermosig in self.sermonsignatures.all().order_by("editype", "code"):
            # See if this sermosig has an equivalent goldsig
            gsig = sermosig.get_goldsig()
            if gsig:
                # Add the id to the list
                sig_ordered.append(gsig.id)
        
        # Return the ordered list
        return sig_ordered

    def init_latin():
        """ One time ad-hoc function"""

        with transaction.atomic():
            for obj in SermonDescr.objects.all():
                bNeedSave = False
                if obj.incipit: 
                    bNeedSave = True
                if obj.explicit: 
                    bNeedSave = True
                lSign = []
                for item in obj.sermonsignatures.all():
                    bNeedSave = True
                if bNeedSave:
                    obj.save()
        return True

    def is_codistart(self):
        sResult = ""
        if self.msitem != None:
            if self.msitem.codico != None:
                if self.msitem.codico.order == 1:
                    sResult = self.msitem.codico.id
        return sResult

    def save(self, force_insert = False, force_update = False, using = None, update_fields = None):
        # Adapt the incipit and explicit
        istop = 1
        if self.incipit: 
            srchincipit = get_searchable(self.incipit)
            if self.srchincipit != srchincipit:
                self.srchincipit = srchincipit
        if self.explicit: 
            srchexplicit = get_searchable(self.explicit)
            if self.srchexplicit != srchexplicit:
                self.srchexplicit = srchexplicit
        # Preliminary saving, before accessing m2m fields
        response = super(SermonDescr, self).save(force_insert, force_update, using, update_fields)
        # Process signatures
        lSign = []
        bCheckSave = False
        for item in self.sermonsignatures.all():
            lSign.append(item.short())
            bCheckSave = True

        # =========== DEBUGGING ================
        # self.do_ranges(force = True)
        # ======================================

        # Make sure to save the siglist too
        if bCheckSave: 
            siglist_new = json.dumps(lSign)
            if siglist_new != self.siglist:
                self.siglist = siglist_new
                # Only now do the actual saving...
                response = super(SermonDescr, self).save(force_insert, force_update, using, update_fields)
        return response

    def signature_string(self, include_auto = False, do_plain=True):
        """Combine all signatures into one string: manual ones"""

        lSign = []
        if include_auto:
            # Get the automatic signatures
            equal_set = self.equalgolds.all().values("id")
            for item in Signature.objects.filter(gold__equal__id__in=equal_set).order_by("-editype", "code"):
                short = item.short()
                editype = item.editype
                url = "{}?sermo-siglist_a={}".format(reverse("sermon_list"), item.id)
                lSign.append("<span class='badge signature {}' title='{}'><a class='nostyle' href='{}'>{}</a></span>".format(
                    editype, short, url, short[:20]))

        # Add the manual signatures
        for item in self.sermonsignatures.all().order_by("-editype", "code"):
            if do_plain:
                lSign.append(item.short())
            else:
                short = item.short()
                editype = item.editype
                url = "{}?sermo-siglist_m={}".format(reverse("sermon_list"), item.id)
                lSign.append("<span class='badge signature {}' title='{}'><a class='nostyle' href='{}'>{}</a></span>".format(
                    editype, short, url, short[:20]))


        # REturn the combination
        if do_plain:
            combi = " | ".join(lSign)
        else:
            combi = " ".join(lSign)
        if combi == "": combi = "[-]"
        return combi

    def signature_auto_string(self):
        """Combine all signatures into one string: automatic ones"""

        lSign = []

        # Get all linked SSG items
        ssg_list = self.equalgolds.all().values('id')

        # Get a list of all the SG that are in these equality sets
        gold_list = SermonGold.objects.filter(equal__in=ssg_list).order_by('id').distinct().values("id")
        # Get an ordered set of signatures
        for sig in Signature.objects.filter(gold__in=gold_list).order_by('-editype', 'code'):
            lSign.append(sig.short())

        # REturn the combination
        combi = " | ".join(lSign)
        if combi == "": combi = "[-]"
        return combi

    def signatures_ordered(self):
        # Provide an ordered list of signatures
        return self.sermonsignatures.all().order_by("editype", "code")

    def target(self):
        # Get the URL to edit this sermon
        sUrl = "" if self.id == None else reverse("sermon_edit", kwargs={'pk': self.id})
        return sUrl


class Range(models.Model):
    """A range in the bible from one place to another"""

    # [1] The start of the range is bk/ch/vs
    start = models.CharField("Start", default = "",  max_length=BKCHVS_LENGTH)
    # [1] The end of the range also in bk/ch/vs
    einde = models.CharField("Einde", default = "",  max_length=BKCHVS_LENGTH)
    # [1] Each range is linked to a Sermon
    sermon = models.ForeignKey(SermonDescr, related_name="sermonranges", on_delete=models.CASCADE)

    # [0-1] Optional introducer
    intro = models.CharField("Introducer",  null=True, blank=True, max_length=LONG_STRING)
    # [0-1] Optional addition
    added = models.CharField("Addition",  null=True, blank=True, max_length=LONG_STRING)

    def __str__(self):
        sBack = ""
        if self.start != None and self.einde != None:
            sBack = self.get_range()
        return sBack

    def get_range(self):
        sRange = ""
        # a range from a bk/ch/vs to a bk/ch/vs
        start = self.start
        einde = self.einde
        if len(start) == 9 and len(einde) == 9:
            # Derive the bk/ch/vs of start
            oStart = BkChVs(start)
            oEinde = BkChVs(einde)
            if oStart.book == oEinde.book:
                # Check if they are in the same chapter
                if oStart.ch == oEinde.ch:
                    # Same chapter
                    if oStart.vs == oEinde.vs:
                        # Just one place
                        sRange = "{} {}:{}".format(oStart.book, oStart.ch, oStart.vs)
                    else:
                        # From vs to vs
                        sRange = "{} {}:{}-{}".format(oStart.book, oStart.ch, oStart.vs, oEinde.vs)
                else:
                    # Between different chapters
                    if oStart.vs == 0 and oEinde.vs == 0:
                        # Just two different chapters
                        sRange = "{} {}-{}".format(oStart.book, oStart.ch, oEinde.ch)
                    else:
                        sRange = "{} {}:{}-{}:{}".format(oStart.book, oStart.ch, oStart.vs, oEinde.ch, oEinde.vs)
            else:
                # Between books
                sRange = "{}-{}".format(oStart.book, oEinde.book)
        # Return the total
        return sRange

    def parse(sermon, sRange):
        """Parse a string into a start/einde range
        
        Possibilities:
            BBB         - One book
            BBB-DDD     - Range of books
            BBB C       - One chapter
            BBB C-C     - Range of chapters
            BBB C:V     - One verse
            BBB C:V-V   - Range of verses in one chapter
            BBB C:V-C:V - Range of verses between chapters
        """

        SPACES = " \t\n\r"
        NUMBER = "0123456789"
        bStatus = True
        introducer = ""
        obj = None
        msg = ""
        pos = -1
        oErr = ErrHandle()
        try:
            def skip_spaces(pos):
                length = len(sRange)
                while pos < length and sRange[pos] in SPACES: pos += 1
                return pos

            def is_end(pos):
                pos_last = len(sRange)-1
                bFinish = (pos > pos_last)
                return bFinish

            def get_number(pos):
                number = -1
                pos_start = pos
                length = len(sRange)
                while pos < length and sRange[pos] in NUMBER: pos += 1
                # Get the chapter number
                number = int(sRange[pos_start: pos]) # - pos_start + 1])
                # Possibly skip following spaces
                while pos < length and sRange[pos] in SPACES: pos += 1
                return pos, number

            def syntax_error(pos):
                msg = "Cannot interpret at {}: {}".format(pos, sRange)
                bStatus = False

            # We will be assuming that references are divided by a semicolumn
            arRange = sRange.split(";")

            for sRange in arRange:
                # Initializations
                introducer = ""
                additional = ""
                obj = None
                idno = -1

                if bStatus == False: break

                # Make sure spaces are dealt with
                sRange = sRange.strip()
                pos = 0
                # Check for possible preceding text: cf. 
                if sRange[0:3] == "cf.":
                    # There is an introducer
                    introducer = "cf."
                    pos += 3
                    pos = skip_spaces(pos)
                elif sRange[0:3] == "or ":
                    # There is an introducer
                    introducer = "or"
                    pos += 3
                    pos = skip_spaces(pos)

                # Expecting to read the first book
                #sBook = sRange[pos:3]
                #pos = 3

                
                # if idno < 0:
                # Check for possible book in BOOK_NAMES
                for item in BOOK_NAMES:
                    length = len(item['name'])
                    if item['name'] == sRange[pos:length]:
                        # We have the book abbreviation
                        abbr = item['abbr']
                        idno = Book.get_idno(abbr)
                        break;
                if idno < 0:
                    sBook = sRange[pos:3]
                    idno = Book.get_idno(sBook)
                    length = len(sBook)


                if idno < 0:
                    msg = "Cannot find book {}".format(sBook)
                    bStatus = False
                else:
                    pos += length
                    # Skip spaces
                    pos = skip_spaces(pos)
                    # Check what follows now
                    sNext = sRange[pos]
                    if sNext == "-":
                        # Range of books
                        pos += 1
                        # Skip spaces
                        pos = skip_spaces(pos)
                        # Get the second book name
                        if len(sRange) - pos >=3:
                            sBook2 = sRange[pos:3]
                            # Create the two ch/bk/vs items
                            start = "{}{:0>3d}{:0>3d}".format(idno, 0, 0)
                            idno2 = Book.get_idno(sBook2)
                            if idno2 < 0:
                                msg = "Cannot identify the second book in: {}".format(sRange)
                                bStatus = False
                            else:
                                einde = "{}{:0>3d}{:0>3d}".format(idno, 0, 0)
                                # There is a start-einde, so add a Range object for this Sermon
                                obj = sermon.add_range(start, einde)
                        else:
                            msg = "Expecting book range {}".format(sRange)
                            bStatus = False
                    elif sNext in NUMBER:
                        # Chapter number
                        pos, chapter = get_number(pos)
                        # Find out what is next
                        sNext = sRange[pos]
                        if sNext == "-":
                            # Possibly skip spaces
                            pos = skip_spaces(pos)
                            # Find out what is next
                            sNext = sRange[pos]
                            if sNext in NUMBER:
                                # Range of chapters
                                pos, chnext = get_number(pos)
                                # Create the two ch/bk/vs items
                                start = "{}{:0>3d}{:0>3d}".format(idno, chapter, 0)
                                einde = "{}{:0>3d}{:0>3d}".format(idno, chnext, 0)
                                # There is a start-einde, so add a Range object for this Sermon
                                obj = sermon.add_range(start, einde)
                            else:
                                # Syntax error
                                syntax_error(pos)
                        elif sNext == ":":
                            pos += 1
                            # A verse is following
                            pos, verse = get_number(pos)
                            # At least get the start
                            start = "{:0>3d}{:0>3d}{:0>3d}".format(idno, chapter, 0)
                            # Skip spaces
                            pos = skip_spaces(pos)
                            if is_end(pos):
                                # Simple bk/ch/vs
                                einde = start
                                # Add the single verse as a Range object for this Sermon
                                obj = sermon.add_range(start, einde)
                            else:
                                # See what is following
                                sNext = sRange[pos]
                                if sNext == "-":
                                    pos += 1
                                    # Expecting a range
                                    pos = skip_spaces(pos)
                                    sNext = sRange[pos]
                                    if sNext in NUMBER:
                                        # Read the number
                                        pos, number = get_number(pos)
                                        # Skip spaces
                                        pos = skip_spaces(pos)
                                        # See what is next
                                        sNext = sRange[pos]
                                        if sNext == ":":
                                            pos += 1
                                            # Range of verses between chapters
                                            pos = skip_spaces(pos)
                                            sNext = sRange[pos]
                                            if sNext in NUMBER:
                                                pos, verse = get_number(pos)
                                                einde = "{}{:0>3d}{:0>3d}".format(idno, number, verse)
                                                # Add the BBB C:V-V
                                                obj = sermon.add_range(start, einde)
                                            else:
                                                syntax_error(pos)
                                        else:
                                            # The number is a verse
                                            einde = "{}{:0>3d}{:0>3d}".format(idno, chapter, number)
                                            # Add the BBB C:V-V
                                            obj = sermon.add_range(start, einde)
                                    else:
                                        syntax_error(pos)
                                else:
                                    # This was just one single verse
                                    einde = start
                                    # Add the single verse as a Range object for this Sermon
                                    obj = sermon.add_range(start, einde)
                        else:
                            # Syntax error
                            syntax_error(pos)
                    else:
                        # Syntax error
                        syntax_error(pos)
                bNeedSaving = False
                # Is there any remark following?
                if bStatus and not is_end(pos):
                    # Is there more stuff?
                    additional = sRange[pos:].strip()
                    if obj != None:
                        obj.added = sRemark
                        bNeedSaving = True
                if introducer != "":
                    obj.intro = introducer
                    bNeedSaving = True
                if bNeedSaving:
                    obj.save()
        except:
            msg = oErr.get_error_message()
            oErr.DoError("Range/parse")
            bStatus = False
        return bStatus, msg, obj


class BibRange(models.Model):
    """A range of chapters/verses from one particular book"""

    # [1] Each chapter belongs to a book
    book = models.ForeignKey(Book, on_delete=models.CASCADE, related_name="bookbibranges")
    # [0-1] Optional ChVs list
    chvslist = models.TextField("Chapters and verses", blank=True, null=True)
    # [1] Each range is linked to a Sermon
    sermon = models.ForeignKey(SermonDescr, on_delete=models.CASCADE, related_name="sermonbibranges")

    # [0-1] Optional introducer
    intro = models.CharField("Introducer",  null=True, blank=True, max_length=LONG_STRING)
    # [0-1] Optional addition
    added = models.CharField("Addition",  null=True, blank=True, max_length=LONG_STRING)

    def __str__(self):
        html = []
        sBack = ""
        if getattr(self,"book") == None:
            msg = "BibRange doesn't have a BOOK"
        else:
            html.append(self.book.abbr)
            if self.chvslist != None and self.chvslist != "":
                html.append(self.chvslist)
            sBack = " ".join(html)
        return sBack

    def save(self, force_insert = False, force_update = False, using = None, update_fields = None):
        # First do my own saving
        response = super(BibRange, self).save(force_insert, force_update, using, update_fields)

        # Make sure the fields in [sermon] are adapted, if needed
        bResult, msg = self.sermon.adapt_verses()


        ## Add BibVerse objects if needed
        #verses_new = oScrref.get("scr_refs", [])
        #verses_old = [x.bkchvs for x in obj.bibrangeverses.all()]
        ## Remove outdated verses
        #deletable = []
        #for item in verses_old:
        #    if item not in verses_new: deletable.append(item)
        #if len(deletable) > 0:
        #    obj.bibrangeverses.filter(bkchvs__in=deletable).delete()
        ## Add new verses
        #with transaction.atomic():
        #    for item in verses_new:
        #        if not item in verses_old:
        #            verse = BibVerse.objects.create(bibrange=obj, bkchvs=item)

        return response

    def get_abbr(self):
        """Get the official abbreviations for this book"""
        sBack = "<span class='badge signature ot' title='English'>{}</span><span class='badge signature gr' title='Latin'>{}</span>".format(
            self.book.abbr, self.book.latabbr)
        return sBack

    def get_book(self):
        """Get the book for details view"""

        sBack = "<span title='{}'>{}</span>".format(self.book.latname, self.book.name)
        return sBack

    def get_ref_latin(self):
        html = []
        sBack = ""
        if self.book != None:
            html.append(self.book.latabbr)
            if self.chvslist != None and self.chvslist != "":
                html.append(self.chvslist)
            sBack = " ".join(html)
        return sBack

    def get_fullref(self):
        html = []
        sBack = ""
        if self.book != None:
            if self.intro != None and self.intro != "":
                html.append(self.intro)
            html.append(self.book.abbr)
            if self.chvslist != None and self.chvslist != "":
                html.append(self.chvslist)
            if self.added != None and self.added != "":
                html.append(self.added)
            sBack = " ".join(html)
        return sBack

    def get_range(sermon, book, chvslist, intro=None, added=None):
        """Get the bk/ch range for this particular sermon"""

        bNeedSaving = False
        oErr = ErrHandle()
        try:
            # Sanity check
            if book is None or book == "":
                return None
            # Now we can try to search for an entry...
            obj = sermon.sermonbibranges.filter(book=book, chvslist=chvslist).first()
            if obj == None:
                obj = BibRange(sermon=sermon, book=book, chvslist=chvslist)
                bNeedSaving = True
                bNeedVerses = True
            # Double check for intro and added
            if obj.intro != intro:
                obj.intro = intro
                bNeedSaving = True
            if obj.added != added:
                obj.added = added
                bNeedSaving = True
            # Possibly save the BibRange
            if bNeedSaving:
                obj.save()
        except:
            msg = oErr.get_error_message()
            oErr.DoError("BibRange/get_range")
            obj = None
        return obj


class BibVerse(models.Model):
    """One verse that belongs to [BibRange]"""

    # [1] The Bk/Ch/Vs code (9 characters)
    bkchvs = models.CharField("Bk/Ch/Vs", max_length=BKCHVS_LENGTH)
    # [1] Each verse is part of a BibRange
    bibrange = models.ForeignKey(BibRange, on_delete=models.CASCADE, related_name="bibrangeverses")

    def __str__(self):
        return self.bkchvs


class SermonDescrKeyword(models.Model):
    """Relation between a SermonDescr and a Keyword"""

    # [1] The link is between a SermonGold instance ...
    sermon = models.ForeignKey(SermonDescr, related_name="sermondescr_kw", on_delete=models.CASCADE)
    # [1] ...and a keyword instance
    keyword = models.ForeignKey(Keyword, related_name="sermondescr_kw", on_delete=models.CASCADE)
    # [1] And a date: the date of saving this relation
    created = models.DateTimeField(default=get_current_datetime)


class ManuscriptKeyword(models.Model):
    """Relation between a Manuscript and a Keyword"""

    # [1] The link is between a Manuscript instance ...
    manuscript = models.ForeignKey(Manuscript, related_name="manuscript_kw", on_delete=models.CASCADE)
    # [1] ...and a keyword instance
    keyword = models.ForeignKey(Keyword, related_name="manuscript_kw", on_delete=models.CASCADE)
    # [1] And a date: the date of saving this relation
    created = models.DateTimeField(default=get_current_datetime)


class CodicoKeyword(models.Model):
    """Relation between a Codico and a Keyword"""

    # [1] The link is between a Manuscript instance ...
    codico = models.ForeignKey(Codico, related_name="codico_kw", on_delete=models.CASCADE)
    # [1] ...and a keyword instance
    keyword = models.ForeignKey(Keyword, related_name="codico_kw", on_delete=models.CASCADE)
    # [1] And a date: the date of saving this relation
    created = models.DateTimeField(default=get_current_datetime)


class ManuscriptCorpus(models.Model):
    """A user-SSG-specific manuscript corpus"""

    # [1] Each corpus is created with a particular SSG as starting point
    super = models.ForeignKey(EqualGold, related_name="supercorpora", on_delete=models.CASCADE)

    # Links: source.SSG - target.SSG - manu
    # [1] Link-item 1: source
    source = models.ForeignKey(EqualGold, related_name="sourcecorpora", on_delete=models.CASCADE)
    # [1] Link-item 2: target
    target = models.ForeignKey(EqualGold, related_name="targetcorpora", on_delete=models.CASCADE)
    # [1] Link-item 3: manuscript
    manu = models.ForeignKey(Manuscript, related_name="manucorpora", on_delete=models.CASCADE)

    # [1] Each corpus belongs to a person
    profile = models.ForeignKey(Profile, related_name="profilecorpora", on_delete=models.CASCADE)
    # [1] And a date: the date of saving this relation
    created = models.DateTimeField(default=get_current_datetime)


class ManuscriptCorpusLock(models.Model):
    """A user-SSG-specific manuscript corpus"""

    # [1] Each lock is created with a particular SSG as starting point
    super = models.ForeignKey(EqualGold, related_name="supercorpuslocks", on_delete=models.CASCADE)
    # [1] Each lock belongs to a person
    profile = models.ForeignKey(Profile, related_name="profilecorpuslocks", on_delete=models.CASCADE)
    # [1] And a date: the date of saving this relation
    created = models.DateTimeField(default=get_current_datetime)

    # [1] Status
    status = models.TextField("Status", default = "empty")

    
class EqualGoldCorpus(models.Model):
    """A corpus of SSG's"""

    # [1] Each lock is created with a particular SSG as starting point
    ssg = models.ForeignKey(EqualGold, related_name="ssgequalcorpora", on_delete=models.CASCADE)
    # [1] Each lock belongs to a person
    profile = models.ForeignKey(Profile, related_name="profileequalcorpora", on_delete=models.CASCADE)
    # [1] List of most frequent words
    mfw = models.TextField("Most frequent words", default = "[]")
    # [1] And a date: the date of saving this relation
    created = models.DateTimeField(default=get_current_datetime)

    # [1] Status
    status = models.TextField("Status", default = "empty")


class EqualGoldCorpusItem(models.Model):
    """One item from the EqualGoldCOrpus"""

    # [1] Link-item 1: source
    equal = models.ForeignKey(EqualGold, related_name="ssgcorpusequals", on_delete=models.CASCADE)
    # [1] WOrds in this SSG's incipit and explicit - stringified JSON
    words = models.TextField("Words", default = "{}")
    # [1] Number of sermons - the scount
    scount = models.IntegerField("Sermon count", default = 0)
    # [1] Name of the author
    authorname = models.TextField("Author's name", default = "empty")
    # [1] Link to the corpus itself
    corpus = models.ForeignKey(EqualGoldCorpus, related_name="corpusitems", on_delete=models.CASCADE)

    
class UserKeyword(models.Model):
    """Relation between a M/S/SG/SSG and a Keyword - restricted to user"""

    # [1] ...and a keyword instance
    keyword = models.ForeignKey(Keyword, related_name="kw_userkeywords", on_delete=models.CASCADE)
    # [1] It is part of a user profile
    profile = models.ForeignKey(Profile, related_name="profile_userkeywords", on_delete=models.CASCADE)
    # [1] Each "UserKeyword" has only 1 type, one of M/S/SG/SSG
    type = models.CharField("Type of user keyword", choices=build_abbr_list(COLLECTION_TYPE), max_length=5)
    # [1] And a date: the date of saving this relation
    created = models.DateTimeField(default=get_current_datetime)

    # ==== Depending on the type, only one of these will be filled
    # [0-1] The link is with a Manuscript instance ...
    manu = models.ForeignKey(Manuscript, blank=True, null=True, related_name="manu_userkeywords", on_delete=models.SET_NULL)
    # [0-1] The link is with a SermonDescr instance ...
    sermo = models.ForeignKey(SermonDescr, blank=True, null=True, related_name="sermo_userkeywords", on_delete=models.SET_NULL)
    # [0-1] The link is with a SermonGold instance ...
    gold = models.ForeignKey(SermonGold, blank=True, null=True, related_name="gold_userkeywords", on_delete=models.SET_NULL)
    # [0-1] The link is with a EqualGold instance ...
    super = models.ForeignKey(EqualGold, blank=True, null=True, related_name="super_userkeywords", on_delete=models.SET_NULL)

    def __str__(self):
        sBack = self.keyword.name
        return sBack

    def save(self, force_insert = False, force_update = False, using = None, update_fields = None):
        response = None
        # Note: only save if all obligatory elements are there
        if self.keyword_id:
            bOkay = (self.type == "manu" and self.manu != None) or \
                    (self.type == "sermo" and self.sermo != None) or \
                    (self.type == "gold" and self.gold != None) or \
                    (self.type == "super" and self.super != None)
            if bOkay:
                response = super(UserKeyword, self).save(force_insert, force_update, using, update_fields)
        return response

    def get_profile_markdown(self):
        sBack = ""
        uname = self.profile.user.username
        url = reverse("profile_details", kwargs = {'pk': self.profile.id})
        sBack = "<a href='{}'>{}</a>".format(url, uname)
        return sBack

    def moveup(self):
        """Move this keyword into the general keyword-link-table"""  
        
        oErr = ErrHandle()
        response = False
        try: 
            src = None
            dst = None
            tblGeneral = None
            if self.type == "manu":
                tblGeneral = ManuscriptKeyword
                itemfield = "manuscript"
            elif self.type == "sermo":
                tblGeneral = SermonDescrKeyword
                itemfield = "sermon"
            elif self.type == "gold":
                tblGeneral = SermonGoldKeyword
                itemfield = "gold"
            elif self.type == "super":
                tblGeneral = EqualGoldKeyword
                itemfield = "equal"
            if tblGeneral != None:
                # Check if the kw is not in the general table yet
                general = tblGeneral.objects.filter(keyword=self.keyword).first()
                if general == None:
                    # Add the keyword
                    obj = tblGeneral(keyword=self.keyword)
                    setattr(obj, itemfield, getattr(self, self.type))
                    obj.save()
                # Remove the *user* specific references to this keyword (for *all*) users
                UserKeyword.objects.filter(keyword=self.keyword, type=self.type).delete()
                # Return positively
                response = True
        except:
            msg = oErr.get_error_message()
        return response


class SermonDescrEqual(models.Model):
    """Link from sermon description (S) to super sermon gold (SSG)"""

    # [1] The sermondescr
    sermon = models.ForeignKey(SermonDescr, related_name="sermondescr_super", on_delete=models.CASCADE)
    # [0-1] The manuscript in which the sermondescr resides
    manu = models.ForeignKey(Manuscript, related_name="sermondescr_super", blank=True, null=True, on_delete=models.SET_NULL)
    # [1] The gold sermon
    super = models.ForeignKey(EqualGold, related_name="sermondescr_super", on_delete=models.CASCADE)
    # [1] Each sermon-to-gold link must have a linktype, with default "equal"
    linktype = models.CharField("Link type", choices=build_abbr_list(LINK_TYPE), max_length=5, default="uns")

    def __str__(self):
        # Temporary fix: sermon.id
        # Should be changed to something more significant in the future
        # E.G: manuscript+locus?? (assuming each sermon has a locus)
        combi = "sermon {} {} {}".format(self.sermon.id, self.get_linktype_display(), self.super.__str__())
        return combi

    def do_scount(self, super):
        # Now calculate the adapted scount for the SSG
        scount = super.equalgold_sermons.count()
        # Check if adaptation is needed
        if scount != super.scount:
            # Adapt the scount in the SSG
            super.scount = scount
            super.save()
        return None

    def delete(self, using = None, keep_parents = False):
        response = None
        oErr = ErrHandle()
        try:
            # Remember the current SSG for a moment
            obj_ssg = self.super
            # Remove the connection
            response = super(SermonDescrEqual, self).delete(using, keep_parents)
            # Perform the scount
            self.do_scount(obj_ssg)
        except:
            msg = oErr.get_error_message()
            oErr.DoError("SermonDescrEqual/delete")
        # Return the proper response
        return response

    def save(self, force_insert = False, force_update = False, using = None, update_fields = None):
        # Automatically provide the value for the manuscript through the sermon
        manu = self.sermon.msitem.manu
        if self.manu != manu:
            self.manu = manu
        # First do the saving
        response = super(SermonDescrEqual, self).save(force_insert, force_update, using, update_fields)
        # Perform the scount
        self.do_scount(self.super)
        # Return the proper response
        return response

    def get_label(self, do_incexpl=False, show_linktype=False):
        if show_linktype:
            sBack = "{}: {}".format(self.get_linktype_display(), self.super.get_label(do_incexpl))
        else:
            sBack = self.super.get_label(do_incexpl)
        return sBack

    def unique_list():
        """Get a list of links that are unique in terms of combination [ssg] [linktype]"""

        # We're not really giving unique ones
        uniques = SermonDescrEqual.objects.exclude(sermon__mtype="tem").order_by('linktype', 'sermon__author__name', 'sermon__siglist')
        return uniques


class SermonEqualDist(models.Model):
    """Keep track of the 'distance' between sermons and SSGs"""

    # [1] The sermondescr
    sermon = models.ForeignKey(SermonDescr, related_name="sermonsuperdist", on_delete=models.CASCADE)
    # [1] The equal gold sermon (=SSG)
    super = models.ForeignKey(EqualGold, related_name="sermonsuperdist", on_delete=models.CASCADE)
    # [1] Each sermon-to-equal keeps track of a distance
    distance = models.FloatField("Distance", default=100.0)

    def __str__(self):
        return "{}".format(self.distance)


class SermonDescrGold(models.Model):
    """Link from sermon description to gold standard"""

    # [1] The sermondescr
    sermon = models.ForeignKey(SermonDescr, related_name="sermondescr_gold", on_delete=models.CASCADE)
    # [1] The gold sermon
    gold = models.ForeignKey(SermonGold, related_name="sermondescr_gold", on_delete=models.CASCADE)
    # [1] Each sermon-to-gold link must have a linktype, with default "equal"
    linktype = models.CharField("Link type", choices=build_abbr_list(LINK_TYPE), 
                            max_length=5, default="eq")

    def __str__(self):
        # Temporary fix: sermon.id
        # Should be changed to something more significant in the future
        # E.G: manuscript+locus?? (assuming each sermon has a locus)
        combi = "sermon {} {} {}".format(self.sermon.id, self.get_linktype_display(), self.gold.siglist)
        return combi

    def get_label(self, do_incexpl=False):
        sBack = "{}: {}".format(self.get_linktype_display(), self.gold.get_label(do_incexpl))
        return sBack

    def unique_list(exclude=None):
        """Get a list of links that are unique in terms of combination [gold] [linktype]"""

        try_unique_list = False

        if try_unique_list:
            if exclude:
                uniques = SermonDescrGold.objects.exclude(sermon=exclude).order_by('linktype', 'sermon__author__name', 'sermon__siglist').values_list('gold', 'linktype').distinct()
            else:
                uniques = SermonDescrGold.objects.order_by('linktype', 'sermon__author__name', 'sermon__siglist').values_list('gold', 'linktype').distinct()
        else:
            # We're not really giving unique ones
            if exclude:
                uniques = SermonDescrGold.objects.exclude(sermon=exclude).order_by('linktype', 'sermon__author__name', 'sermon__siglist')
            else:
                uniques = SermonDescrGold.objects.order_by('linktype', 'sermon__author__name', 'sermon__siglist')
        return uniques


class Signature(models.Model):
    """One Gryson, Clavis or other code as taken up in an edition"""

    # [1] It must have a code = gryson code or clavis number
    code = models.CharField("Code", max_length=LONG_STRING)
    # [1] Every signature must be of a limited number of types
    editype = models.CharField("Edition type", choices=build_abbr_list(EDI_TYPE), 
                            max_length=5, default="gr")
    # [1] Every signature belongs to exactly one gold-sermon
    #     Note: when a SermonGold is removed, then its associated Signature gets removed too
    gold = models.ForeignKey(SermonGold, null=False, blank=False, related_name="goldsignatures", on_delete=models.CASCADE)

    def __str__(self):
        return "{}: {}".format(self.editype, self.code)

    def short(self):
        return self.code

    def find(code, editype):
        obj = Signature.objects.filter(code=code, editype=editype).first()
        return obj

    def save(self, force_insert = False, force_update = False, using = None, update_fields = None):
        response = None
        # Double check
        if self.code and self.editype and self.gold_id:
            # Do the saving initially
            response = super(Signature, self).save(force_insert, force_update, using, update_fields)
            # Adapt list of signatures for the related GOLD
            self.gold.do_signatures()
            # Check if manual signatures need to be linked to this gsig
            qs = SermonSignature.objects.filter(code=self.code, editype=self.editype)
            with transaction.atomic():
                for obj in qs:
                    if obj.gsig == None:
                        obj.gsig = self
                        obj.save()

        # Then return the super-response
        return response

    
class SermonSignature(models.Model):
    """One Gryson, Clavis or other code as taken up in an edition"""

    # [1] It must have a code = gryson code or clavis number
    code = models.CharField("Code", max_length=LONG_STRING)
    # [1] Every edition must be of a limited number of types
    editype = models.CharField("Edition type", choices=build_abbr_list(EDI_TYPE), 
                            max_length=5, default="gr")
    # [0-1] Optional link to the (gold) Signature from which this derives
    gsig = models.ForeignKey(Signature, blank=True, null=True, related_name="sermongoldsignatures", on_delete=models.SET_NULL)
    # [1] Every signature belongs to exactly one gold-sermon
    #     Note: when a SermonDescr gets removed, then its associated SermonSignature gets removed too
    sermon = models.ForeignKey(SermonDescr, null=False, blank=False, related_name="sermonsignatures", on_delete=models.CASCADE)

    def __str__(self):
        return "{}: {}".format(self.editype, self.code)

    def short(self):
        return self.code

    def find(code, editype):
        obj = SermonSignature.objects.filter(code=code, editype=editype).first()
        return obj

    def save(self, force_insert = False, force_update = False, using = None, update_fields = None):
        # Do the saving initially
        response = super(SermonSignature, self).save(force_insert, force_update, using, update_fields)
        # Adapt list of signatures for the related GOLD
        self.sermon.do_signatures()
        # Then return the super-response
        return response

    def get_goldsig(self, bCleanUp = False):
        """Get the equivalent gold-signature for me"""

        oErr = ErrHandle()
        oBack = None
        try:
            if bCleanUp and self.gsig:
                # There seems to be a gsig
                qs = Signature.objects.filter(Q(gold__in = self.sermon.goldsermons.all()))
                for obj in qs:
                    if obj.editype == self.editype and obj.code == self.code:
                        self.delete()
                        return None
            # See if this sermosig has an equivalent goldsig
            if self.gsig == None:
                # No gsig given, so depend on the self.editype and self.code
                qs = Signature.objects.filter(Q(gold__in = self.sermon.goldsermons.all()))
                for obj in qs:
                    if obj.editype == self.editype and obj.code == self.code:
                        # Found it
                        if bCleanUp:
                            self.delete()
                            return None
                        else:
                            self.gsig = obj
                            break
                if self.gsig == None:
                    # Get the first gold signature that exists
                    obj = Signature.objects.filter(editype=self.editype, code=self.code).first()
                    if obj:
                        self.gsig = obj
                    else:
                        # There is a signature that is not a gold signature -- this cannot be...
                        pass
                # Save the sermonsignature with the new information
                if self.gsig:
                    self.save()
            # Return what I am in the end
            oBack = self.gsig
        except:
            #y = (hasattr(self,"gsig"))
            msg = oErr.get_error_message()
            oErr.DoError("get_goldsig")
        return oBack

    def adapt_gsig():
        """Make sure all the items in SermonSignature point to a gsig, if possible"""

        qs = SermonSignature.objects.all()
        iTotal = qs.count()
        iCount = 0
        oErr = ErrHandle()
        bResult = False
        try:
            with transaction.atomic():
                for obj in qs:
                    obj.get_goldsig(bCleanUp=True)
                    iCount += 1
                    oErr.Status("adapt_gsig: id={} count={}/{}".format(obj.id, iCount, iTotal))
            bResult = True
        except:
            msg = oErr.get_error_message()
            oErr.DoError("adapt_gsig")
        return bResult


class Basket(models.Model):
    """The basket is the user's vault of search results (of sermondescr items)"""

    # [1] The sermondescr
    sermon = models.ForeignKey(SermonDescr, related_name="basket_contents", on_delete=models.CASCADE)
    # [1] The user
    profile = models.ForeignKey(Profile, related_name="basket_contents", on_delete=models.CASCADE)

    def __str__(self):
        combi = "{}_s{}".format(self.profile.user.username, self.sermon.id)
        return combi


class BasketMan(models.Model):
    """The basket is the user's vault of search results (of manuscript items)"""
    
    # [1] The manuscript
    manu = models.ForeignKey(Manuscript, related_name="basket_contents_manu", on_delete=models.CASCADE)
    # [1] The user
    profile = models.ForeignKey(Profile, related_name="basket_contents_manu", on_delete=models.CASCADE)

    def __str__(self):
        combi = "{}_s{}".format(self.profile.user.username, self.sermon.id)
        return combi


class BasketGold(models.Model):
    """The basket is the user's vault of search results (of sermon gold items)"""
    
    # [1] The sermon gold
    gold = models.ForeignKey(SermonGold, related_name="basket_contents_gold", on_delete=models.CASCADE)
    # [1] The user
    profile = models.ForeignKey(Profile, related_name="basket_contents_gold", on_delete=models.CASCADE)

    def __str__(self):
        combi = "{}_s{}".format(self.profile.user.username, self.sermon.id)
        return combi


class BasketSuper(models.Model):
    """The basket is the user's vault of search results (of super sermon gold items)"""
    
    # [1] The super sermon gold
    super = models.ForeignKey(EqualGold, related_name="basket_contents_super", on_delete=models.CASCADE)
    # [1] The user
    profile = models.ForeignKey(Profile, related_name="basket_contents_super", on_delete=models.CASCADE)

    def __str__(self):
        combi = "{}_s{}".format(self.profile.user.username, self.sermon.id)
        return combi
    

class ProvenanceMan(models.Model):
    """Link between Provenance and Codico"""

    # [1] The provenance
    provenance = models.ForeignKey(Provenance, related_name = "manuscripts_provenances", on_delete=models.CASCADE)
    # [1] The manuscript this provenance is written on 
    manuscript = models.ForeignKey(Manuscript, related_name = "manuscripts_provenances", on_delete=models.CASCADE)
    # [0-1] Further details are perhaps required too
    note = models.TextField("Manuscript-specific provenance note", blank=True, null=True)

    def get_provenance(self):
        sBack = ""
        prov = self.provenance
        sName = ""
        sLoc = ""
        url = reverse("provenance_details", kwargs={'pk': self.id})
        if prov.name != None and prov.name != "": sName = "{}: ".format(prov.name)
        if prov.location != None: sLoc = prov.location.name
        sBack = "<span class='badge signature gr'><a href='{}'>{}{}</a></span>".format(url, sName, sLoc)
        return sBack


class ProvenanceCod(models.Model):
    """Link between Provenance and Codico"""

    # [1] The provenance
    provenance = models.ForeignKey(Provenance, related_name = "codico_provenances", on_delete=models.CASCADE)
    # [1] The codico this provenance is written on 
    codico = models.ForeignKey(Codico, related_name = "codico_provenances", on_delete=models.CASCADE)
    # [0-1] Further details are perhaps required too
    note = models.TextField("Codico-specific provenance note", blank=True, null=True)

    def get_provenance(self):
        sBack = ""
        prov = self.provenance
        sName = ""
        sLoc = ""
        url = reverse("provenance_details", kwargs={'pk': self.id})
        if prov.name != None and prov.name != "": sName = "{}: ".format(prov.name)
        if prov.location != None: sLoc = prov.location.name
        sBack = "<span class='badge signature gr'><a href='{}'>{}{}</a></span>".format(url, sName, sLoc)
        return sBack


class LitrefMan(models.Model):
    """The link between a literature item and a manuscript"""

    # [1] The literature item
    reference = models.ForeignKey(Litref, related_name="reference_litrefs", on_delete=models.CASCADE)
    # [1] The manuscript to which the literature item refers
    manuscript = models.ForeignKey(Manuscript, related_name = "manuscript_litrefs", on_delete=models.CASCADE)
    # [0-1] The first and last page of the reference
    pages = models.CharField("Pages", blank = True, null = True,  max_length=MAX_TEXT_LEN)

    def get_short(self):
        short = ""
        if self.reference:
            short = self.reference.get_short()
            if self.pages and self.pages != "":
                short = "{}, pp {}".format(short, self.pages)
        return short

    def get_short_markdown(self):
        short = self.get_short()
        return adapt_markdown(short, lowercase=False)


class LitrefSG(models.Model):
    """The link between a literature item and a SermonGold"""
    
    # [1] The literature item
    reference = models.ForeignKey(Litref, related_name="reference_litrefs_2", on_delete=models.CASCADE)
    # [1] The SermonGold to which the literature item refers
    sermon_gold = models.ForeignKey(SermonGold, related_name = "sermon_gold_litrefs", on_delete=models.CASCADE)
    # [0-1] The first and last page of the reference
    pages = models.CharField("Pages", blank = True, null = True,  max_length=MAX_TEXT_LEN)

    def save(self, force_insert = False, force_update = False, using = None, update_fields = None):
        response = None
        # Double check the ESSENTIALS (pages may be empty)
        if self.sermon_gold_id and self.reference_id:
            # Do the saving initially
            response = super(LitrefSG, self).save(force_insert, force_update, using, update_fields)
        # Then return the response: should be "None"
        return response

    def get_short(self):
        short = ""
        if self.reference:
            short = self.reference.get_short()
            if self.pages and self.pages != "":
                short = "{}, pp {}".format(short, self.pages)
        return short

    def get_short_markdown(self):
        short = self.get_short()
        return adapt_markdown(short, lowercase=False)


class LitrefCol(models.Model):
    """The link between a literature item and a Collection (usually a HC)"""
    
    # [1] The literature item
    reference = models.ForeignKey(Litref, related_name="reference_litrefcols", on_delete=models.CASCADE)
    # [1] The SermonGold to which the literature item refers
    collection = models.ForeignKey(Collection, related_name = "collection_litrefcols", on_delete=models.CASCADE)
    # [0-1] The first and last page of the reference
    pages = models.CharField("Pages", blank = True, null = True,  max_length=MAX_TEXT_LEN)

    def save(self, force_insert = False, force_update = False, using = None, update_fields = None):
        response = None
        # Double check the ESSENTIALS (pages may be empty)
        if self.collection_id and self.reference_id:
            # Do the saving initially
            response = super(LitrefCol, self).save(force_insert, force_update, using, update_fields)
        # Then return the response: should be "None"
        return response

    def get_short(self):
        short = ""
        if self.reference:
            short = self.reference.get_short()
            if self.pages and self.pages != "":
                short = "{}, pp {}".format(short, self.pages)
        return short

    def get_short_markdown(self):
        short = self.get_short()
        return adapt_markdown(short, lowercase=False)


class EdirefSG(models.Model):
    """The link between an edition item and a SermonGold"""

    # [1] The edition item
    reference = models.ForeignKey(Litref, related_name = "reference_edition", on_delete=models.CASCADE)
    # [1] The SermonGold to which the literature item refers
    sermon_gold = models.ForeignKey(SermonGold, related_name = "sermon_gold_editions", on_delete=models.CASCADE)
    # [0-1] The first and last page of the reference
    pages = models.CharField("Pages", blank = True, null = True,  max_length=MAX_TEXT_LEN)

    def save(self, force_insert = False, force_update = False, using = None, update_fields = None):
        response = None
        # Double check the ESSENTIALS (pages may be empty)
        if self.sermon_gold_id and self.reference_id:
            # Do the saving initially
            response = super(EdirefSG, self).save(force_insert, force_update, using, update_fields)
        # Then return the response: should be "None"
        return response

    def get_short(self):
        short = ""
        if self.reference:
            short = self.reference.get_short()
            if self.pages and self.pages != "":
                short = "{}, pp {}".format(short, self.pages)
        return short

    def get_short_markdown(self):
        short = self.get_short()
        return adapt_markdown(short, lowercase=False)


class NewsItem(models.Model):
    """A news-item that can be displayed for a limited time"""

    # [1] title of this news-item
    title = models.CharField("Title",  max_length=MAX_TEXT_LEN)
    # [1] the date when this item was created
    created = models.DateTimeField(default=get_current_datetime)
    saved = models.DateTimeField(null=True, blank=True)
    # [0-1] optional time after which this should not be shown anymore
    until = models.DateTimeField("Remove at", null=True, blank=True)
    # [1] the message that needs to be shown (in html)
    msg = models.TextField("Message")
    # [1] the status of this message (can e.g. be 'archived')
    status = models.CharField("Status", choices=build_abbr_list(VIEW_STATUS), 
                              max_length=5, help_text=get_help(VIEW_STATUS))

    def __str__(self):
        # A news item is the tile and the created
        sDate = get_crpp_date(self.created)
        sItem = "{}-{}".format(self.title, sDate)
        return sItem

    def save(self, force_insert = False, force_update = False, using = None, update_fields = None):
      # Adapt the save date
      self.saved = get_current_datetime()
      response = super(NewsItem, self).save(force_insert, force_update, using, update_fields)
      return response

    def check_until():
        """Check all news items for the until date and emend status where needed"""

        # Get current time
        now = timezone.now()
        oErr = ErrHandle()
        try:
            with transaction.atomic():
                for obj in NewsItem.objects.all():
                    if obj.until and obj.until < now:
                        # This should be set invalid
                        obj.status = "ext"
                        obj.save()
        except:
            msg = oErr.get_error_message()
            oErr.DoError("Newsitem/check_until")
        # Return valid
        return True


class CollectionSerm(models.Model):
    """The link between a collection item and a S (sermon)"""

    # [1] The sermon to which the collection item refers
    sermon = models.ForeignKey(SermonDescr, related_name = "sermondescr_col", on_delete=models.CASCADE)
    # [1] The collection to which the context item refers to
    collection = models.ForeignKey(Collection, related_name= "sermondescr_col", on_delete=models.CASCADE)
    # [0-1] The order number for this S within the collection
    order = models.IntegerField("Order", default = -1)


class CollectionMan(models.Model):
    """The link between a collection item and a M (manuscript)"""

    # [1] The manuscript to which the collection item refers
    manuscript = models.ForeignKey(Manuscript, related_name = "manuscript_col", on_delete=models.CASCADE)
    # [1] The collection to which the context item refers to
    collection = models.ForeignKey(Collection, related_name= "manuscript_col", on_delete=models.CASCADE)
    # [0-1] The order number for this S within the collection
    order = models.IntegerField("Order", default = -1)


class CollectionGold(models.Model):
    """The link between a collection item and a SG (gold sermon)"""

    # [1] The gold sermon to which the collection item refers
    gold = models.ForeignKey(SermonGold, related_name = "gold_col", on_delete=models.CASCADE)
    # [1] The collection to which the context item refers to
    collection = models.ForeignKey(Collection, related_name= "gold_col", on_delete=models.CASCADE)
    # [0-1] The order number for this S within the collection
    order = models.IntegerField("Order", default = -1)


class CollectionSuper(models.Model):
    """The link between a collection item and a SSG (super sermon gold)"""

    # [1] The gold sermon to which the coll
    # ection item refers
    super = models.ForeignKey(EqualGold, related_name = "super_col", on_delete=models.CASCADE)
    # [1] The collection to which the context item refers to
    collection = models.ForeignKey(Collection, related_name= "super_col", on_delete=models.CASCADE)
    # [0-1] The order number for this S within the collection
    order = models.IntegerField("Order", default = -1)


class Template(models.Model):
    """A template to construct a manuscript"""

    # [1] Every template must be named
    name = models.CharField("Name", max_length=LONG_STRING)
    # [1] Every template belongs to someone
    profile = models.ForeignKey(Profile, null=True, on_delete=models.CASCADE, related_name="profiletemplates")
    # [0-1] A template may have an additional description
    description = models.TextField("Description", null=True, blank=True)
    # [0-1] Status note
    snote = models.TextField("Status note(s)", default="[]")
    # [1] Every template links to a `Manuscript` that has `mtype` set to `tem` (=template)
    manu = models.ForeignKey(Manuscript, null=True, on_delete=models.CASCADE, related_name="manutemplates")

    def __str__(self):
        return self.name

    def get_count(self):
        """Count the number of sermons under me"""

        num = 0
        if self.manu:
            num = self.manu.get_sermon_count()
        return num

    def get_username(self):
        username = ""
        if self.profile and self.profile.user:
            username = self.profile.user.username
        return username

    def get_manuscript_link(self):
        """Return a piece of HTML with the manuscript link for the user"""

        sBack = ""
        html = []
        if self.manu:
            # Navigation to a manuscript template
            url = reverse('manuscript_details', kwargs={'pk': self.manu.id})
            html.append("<a href='{}' title='Go to the manuscript template'><span class='badge signature ot'>Open the Manuscript</span></a>".format(url))
            # Creation of a new manuscript based on this template:
            url = reverse('template_apply', kwargs={'pk': self.id})
            html.append("<a href='{}' title='Create a manuscript based on this template'><span class='badge signature gr'>Create a new Manuscript based on this template</span></a>".format(url))
            # Combine response
            sBack = "\n".join(html)
        return sBack


class CollOverlap(models.Model):
    """Used to calculate the overlap between (historical) collections and manuscripts"""

    # [1] Every CollOverlap belongs to someone
    profile = models.ForeignKey(Profile, null=True, on_delete=models.CASCADE, related_name="profile_colloverlaps")
    # [1] The overlap is with one Collection
    collection = models.ForeignKey(Collection, null=True, on_delete=models.CASCADE, related_name="collection_colloverlaps")
    # [1] Every CollOverlap links to a `Manuscript`
    manuscript = models.ForeignKey(Manuscript, null=True, on_delete=models.CASCADE, related_name="manu_colloverlaps")
    # [1] The percentage overlap
    overlap = models.IntegerField("Overlap percentage", default=0)
    # [1] And a date: the date of saving this report
    created = models.DateTimeField(default=get_current_datetime)
    saved = models.DateTimeField(null=True, blank=True)

    def get_overlap(profile, collection, manuscript):
        """Calculate and set the overlap between collection and manuscript"""

        obj = CollOverlap.objects.filter(profile=profile,collection=collection, manuscript=manuscript).first()
        if obj == None:
            obj = CollOverlap.objects.create(profile=profile,collection=collection, manuscript=manuscript)
        # Get the ids of the SSGs in the collection
        coll_list = [ collection ]
        ssg_coll = EqualGold.objects.filter(collections__in=coll_list).values('id')
        if len(ssg_coll) == 0:
            ptc = 0
        else:
            # Get the id's of the SSGs in the manuscript: Manu >> MsItem >> SermonDescr >> SSG
            ssg_manu = EqualGold.objects.filter(sermondescr_super__sermon__msitem__manu=manuscript).values('id')
            # Now calculate the overlap
            count = 0
            for item in ssg_coll:
                if item in ssg_manu: count += 1
            ptc = 100 * count // len(ssg_coll)
        # Check if there is a change in percentage
        if ptc != obj.overlap:
            # Set the percentage
            obj.overlap = ptc
            obj.save()
        return ptc

    def save(self, force_insert = False, force_update = False, using = None, update_fields = None):
        # Adapt the save date
        self.saved = get_current_datetime()
        response = super(CollOverlap, self).save(force_insert, force_update, using, update_fields)
        return response
