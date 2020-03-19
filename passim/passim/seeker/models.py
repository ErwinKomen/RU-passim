"""Models for the SEEKER app.

"""
from django.db import models, transaction
from django.contrib.auth.models import User, Group
from django.db.models import Q
from django.db.models.functions import Lower
from django.utils.html import mark_safe
from django.utils import timezone
from django.forms.models import model_to_dict
import pytz
from django.urls import reverse
from datetime import datetime
from markdown import markdown
from passim.utils import *
from passim.settings import APP_PREFIX, WRITABLE_DIR
from passim.seeker.excel import excel_to_list
import sys, os, io, re
import copy
import json
import time
import fnmatch
import csv
import math
from io import StringIO
from pyzotero import zotero

# import xml.etree.ElementTree as ET
# from lxml import etree as ET
# import xmltodict
from xml.dom import minidom

STANDARD_LENGTH=100
LONG_STRING=255
MAX_TEXT_LEN = 200
PASSIM_CODE_LENGTH = 20

VIEW_STATUS = "view.status"
LIBRARY_TYPE = "seeker.libtype"
REPORT_TYPE = "seeker.reptype"
LINK_TYPE = "seeker.linktype"
EDI_TYPE = "seeker.editype"
STATUS_TYPE = "seeker.stype"
COLLECTION_TYPE = "seeker.coltype" 

LINK_EQUAL = 'eqs'
LINK_PARTIAL = 'prt'
LINK_NEAR = 'neq'
LINK_PRT = [LINK_PARTIAL, LINK_NEAR]

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
    
    field = models.CharField(max_length=200)        # The 'path' to and including the actual field
    searchable = models.BooleanField(default=False) # Whether this field is searchable or not
    display_name = models.CharField(max_length=50)  # Name between the <a></a> tags
    help_url = models.URLField(default='')          # THe actual help url (if any)

    def __str__(self):
        return "[{}]: {}".format(
            self.field, self.display_name)

    def Text(self):
        help_text = ''
        # is anything available??
        if (self.help_url != ''):
            if self.help_url[:4] == 'http':
                help_text = "See: <a href='{}'>{}</a>".format(
                    self.help_url, self.display_name)
            else:
                help_text = "{} ({})".format(
                    self.display_name, self.help_url)
        return help_text

def get_current_datetime():
    """Get the current time"""
    return timezone.now()

def adapt_search(val, do_brackets = True):
    if val == None: return None
    # First trim
    val = val.strip()
    if do_brackets:
        arPart = val.split("[")
        for idx, part in enumerate(arPart):
            arPart[idx] = part.replace("]", "[]]")
        val = "[[]".join(arPart)
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
        help_text = entry.Text()
    except:
        help_text = "Sorry, no help available for " + field

    return help_text

def get_crpp_date(dtThis):
    """Convert datetime to string"""

    # Model: yyyy-MM-dd'T'HH:mm:ss
    sDate = dtThis.strftime("%Y-%m-%dT%H:%M:%S")
    return sDate

def get_now_time():
    """Get the current time"""
    return time.clock()

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
    user = models.ForeignKey(User)
    # [1] The item (e.g: Manuscript, SermonDescr, SermonGold)
    itemtype = models.CharField("Item type", max_length=MAX_TEXT_LEN)
    # [1] The kind of action performed (e.g: create, edit, delete)
    actiontype = models.CharField("Action type", max_length=MAX_TEXT_LEN)
    # [0-1] Room for possible action-specific details
    details = models.TextField("Detail", blank=True, null=True)
    # [1] Date and time of this action
    when = models.DateTimeField(default=get_current_datetime)

    def __str__(self):
        action = "{}|{}".format(self.user.username, self.when)
        return action

    def add(user, itemtype, actiontype, details=None):
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
        action = Action(user=oUser, itemtype=itemtype, actiontype=actiontype)
        if details != None: action.details = details
        action.save()
        return action


class Report(models.Model):
    """Report of an upload action or something like that"""

    # [1] Every report must be connected to a user and a date (when a user is deleted, the Report is deleted too)
    user = models.ForeignKey(User)
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

        # Retrieve the user
        user = User.objects.filter(username=username).first()
        obj = Report(user=user, reptype=rtype, contents=contents)
        obj.save()
        # Add a create action
        details = {'reptype': rtype, 'id': obj.id}
        Action.add(user, "Report", "create", json.dumps(details))
        # Return the object
        return obj


class Information(models.Model):
    """Specific information that needs to be kept in the database"""

    # [1] The key under which this piece of information resides
    name = models.CharField("Key name", max_length=255)
    # [0-1] The value for this piece of information
    kvalue = models.TextField("Key value", default = "", null=True, blank=True)

    def __str__(self):
        return self.name

    def get_kvalue(name):
        info = Information.objects.filter(name=name).first()
        if info == None:
            return ''
        else:
            return info.kvalue

    def save(self, force_insert = False, force_update = False, using = None, update_fields = None):
        return super(Information, self).save(force_insert, force_update, using, update_fields)


class Profile(models.Model):
    """Information about the user"""

    # [1] Every profile is linked to a user
    user = models.ForeignKey(User)
    # [1] Every user has a stack: a list of visit objects
    stack = models.TextField("Stack", default = "[]")

    # [1] Current size of the user's basket
    basketsize = models.IntegerField("Basket size", default=0)
    # Many-to-many field for the contents of a search basket per user
    basketitems = models.ManyToManyField("SermonDescr", through="Basket", related_name="basketitems_user")

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


class Visit(models.Model):
    """One visit to part of the application"""

    # [1] Every visit is made by a user
    user = models.ForeignKey(User)
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
            # Return success
            result = True
        except:
            msg = oErr.get_error_message()
            oErr.DoError("visit/add")
            result = False
        # Return the result
        return result


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
    loctype = models.ForeignKey(LocationType)

    # Many-to-many field that identifies relations between locations
    relations = models.ManyToManyField("self", through="LocationRelation", symmetrical=False, related_name="relations_location")

    def __str__(self):
        return self.name

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

    
class LocationName(models.Model):
    """The name of a location in a particular language"""

    # [1] obligatory name in vernacular
    name = models.CharField("Name", max_length=STANDARD_LENGTH)
    # [1] the language in which this name is given - ISO 3 letter code
    language = models.CharField("Language", max_length=STANDARD_LENGTH, default="eng")
    # [1] the Location to which this (vernacular) name belongs
    location = models.ForeignKey(Location, related_name="location_names")

    def __str__(self):
        return "{} ({})".format(self.name, self.language)


class LocationIdentifier(models.Model):
    """The name and value of a location identifier"""

    # [0-1] Optionally an identifier name
    idname = models.CharField("Identifier name", null=True, blank=True, max_length=STANDARD_LENGTH)
    # [0-1]        ... and an identifier value
    idvalue = models.IntegerField("Identifier value", null=True, blank=True)
    # [1] the Location to which this (vernacular) name belongs
    location = models.ForeignKey(Location, related_name="location_identifiers")

    def __str__(self):
        return "{} ({})".format(self.name, self.language)


class LocationRelation(models.Model):
    """Container-contained relation between two locations"""

    # [1] Obligatory container
    container = models.ForeignKey(Location, related_name="container_locrelations")
    # [1] Obligatory contained
    contained = models.ForeignKey(Location, related_name="contained_locrelations")


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
    country = models.ForeignKey(Country, null=True, blank=True, related_name="country_cities")

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
            # Return what we found or created
            return hit
        except:
            sError = errHandle.get_error_message()
            oBack['status'] = 'error'
            oBack['msg'] = sError
            return None


class Library(models.Model):
    """Library in a particular city"""

    # [1] LIbrary code according to CNRS
    idLibrEtab = models.IntegerField("CNRS library id", default=-1)
    # [1] Name of the library
    name = models.CharField("Library", max_length=LONG_STRING)
    # [1] Has this library been bracketed?
    libtype = models.CharField("Library type", choices=build_abbr_list(LIBRARY_TYPE), 
                            max_length=5)
    # [1] Name of the city this is in
    #     Note: when a city is deleted, its libraries are deleted automatically
    city = models.ForeignKey(City, null=True, related_name="city_libraries")
    # [1] Name of the country this is in
    country = models.ForeignKey(Country, null=True, related_name="country_libraries")

    # [0-1] Location, as specific as possible, but optional in the end
    location = models.ForeignKey(Location, null=True, related_name="location_libraries")
    # [0-1] City according to the 'Location' specification
    lcity = models.ForeignKey(Location, null=True, related_name="lcity_libraries")
    # [0-1] Library according to the 'Location' specification
    lcountry = models.ForeignKey(Location, null=True, related_name="lcountry_libraries")

    def __str__(self):
        return self.name

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

    def get_city(self):
        """Given the library, get the city from the location"""

        obj = None
        if self.lcity != None:
            obj = self.lcity
        elif self.location != None:
            if self.location.loctype and self.location.loctype.name == "city":
                obj = self.location
            else:
                # Look at all the related locations - above and below
                qs = self.location.relations_location.all()
                for item in qs:
                    if item.loctype.name == "city":
                        obj = item
                        break
            # Store this
            self.lcity = obj
            self.save()
        return obj

    def get_city_name(self):
        obj = self.get_city()
        return "" if obj == None else obj.name

    def get_country(self):
        """Given the library, get the country from the location"""

        obj = None
        if self.lcountry != None:
            obj = self.lcountry
        elif self.location != None:
            if self.location.loctype and self.location.loctype.name == "country":
                obj = self.location
            else:
                # If this is a city, look upwards
                if self.location.loctype.name == "city":
                    qs = self.location.contained_locrelations.all()
                    for item in qs:
                        container = item.container
                        if container.loctype.name == "country":
                            obj = container
                            break
            # Store this
            self.lcountry = obj
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
        try:
            hit = None
            country = None
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
            # Return what we found or created
            return hit
        except:
            sError = errHandle.get_error_message()
            oBack['status'] = 'error'
            oBack['msg'] = sError
            
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
            return oResult
        except:
            oResult['status'] = "error"
            oResult['msg'] = oErr.get_error_message()
            return oResult


class Origin(models.Model):
    """The 'origin' is a location where manuscripts were originally created"""

    # [1] Name of the location
    name = models.CharField("Original location", max_length=LONG_STRING)

    # [0-1] Optional: LOCATION element this refers to
    location = models.ForeignKey(Location, null=True, related_name="location_origins")

    # ============== EXTINCT ===================================
    ## [0-1] Optional city
    #city = models.ForeignKey(City, null=True, related_name="city_origins")
    ## [0-1] Name of the country this is in
    #country = models.ForeignKey(Country, null=True, related_name="country_origins")
    # ==========================================================

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


class Provenance(models.Model):
    """The 'origin' is a location where manuscripts were originally created"""

    # [1] Name of the location (can be cloister or anything)
    name = models.CharField("Provenance location", max_length=LONG_STRING)
    # [0-1] Optional: LOCATION element this refers to
    location = models.ForeignKey(Location, null=True, related_name="location_provenances")

    # ============== EXTINCT ===================================
    ## [0-1] Optional city
    #city = models.ForeignKey(City, null=True, related_name="city_provenances")
    ## [0-1] Name of the country this is in
    #country = models.ForeignKey(Country, null=True, related_name="country_provenances")
    # ==========================================================

    # [0-1] Further details are perhaps required too
    note = models.TextField("Notes on this provenance", blank=True, null=True)

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
    profile = models.ForeignKey(Profile, on_delete=models.SET_NULL, blank=True, null=True)

    def init_profile():
        coll_set = {}
        qs = SourceInfo.objects.filter(profile__isnull=True)
        with transaction.atomic():
            for obj in qs:
                if obj.collector not in coll_set:
                    coll_set[obj.collector] = Profile.get_user_profile(obj.collector)
                obj.profile = coll_set[obj.collector]
                obj.save()
        result = True


class Litref(models.Model):
    """A literature reference as found in a shared Zotero database"""

    # [1] The itemId for this literature reference
    itemid = models.CharField("Item ID", max_length=LONG_STRING)
    # [0-1] The actual 'data' contents as a JSON string
    data = models.TextField("JSON data", blank=True, default="")
    # [0-1] The abbreviation (retrieved) for this item
    abbr = models.CharField("Abbreviation", max_length=STANDARD_LENGTH, blank=True, default="")
    # [0-1] The full reference, including possible markdown symbols
    full = models.TextField("Full reference", blank=True, default="")
    # [0-1] A short reference: including possible markdown symbols
    short = models.TextField("Short reference", blank=True, default="")

    def __str__(self):
        return self.itemid

    def sync_zotero(force=False):
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
        bBack = True
        oErr = ErrHandle()
        try:
            # Get the total number of items
            total_count = zot.count_items()
            # Read them in groups of 25
            total_groups = math.ceil(total_count / group_size)
            for grp_num in range( total_groups):
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
                    # Check if it needs processing
                    if force or obj.short == "" or obj.data != sData:
                        # It needs processing
                        obj.read_zotero(data=item['data'])
                    elif obj.data != sData:
                        obj.data = sData
                        obj.save()
                    
        except:
            print("sync_zotero error")
            msg = oErr.get_error_message()
            bBack = False
        return bBack

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
        ok_types = ['book', 'bookSection', 'conferencePaper', 'journalArticle', 'manuscript', 'thesis']
        oErr = ErrHandle()

        try:
            # Check if this is okay
            if data != None and 'itemType' in data:
                # Action depends on the [itemType]
                itemType = data['itemType']

                if itemType in ok_types:
                    # Check presence of data
                    sData = json.dumps(data)
                    # Check and adapt the JSON string data
                    if self.data != sData:
                        self.data = sData

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
                    extra = data['extra']
                    
                    # Get the name of the series
                    series = data['series']
                    
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
                                    if editors != "": 
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
                        elif extra == "ed": 
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
 
                    if result != "":
                        # update the full field
                        self.short = result

                    # Now update this item
                    self.save()
                    
                  
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
                                if series =="":
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
                    if result != "":
                        # update the full field
                        self.full = result

                    # Now update this item
                    self.save()
                else:
                    # This item type is not yet supported
                    pass
            else:
                back = False
        except Exception as e:
            print("read_zotero error", str(e))
            msg = oErr.get_error_message()
            back = False
        # Return ability
        return back

    def get_creators(data, type="author", style=""):
        """Extract the authors"""

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
                    
                        # Add this author
                        if bFirst:
                            # Extremely short: only the last name of the first author TH: afvangen igv geen auteurs
                            authors.append(item['lastName'])
                        else:
                            if number == 1 and type == "author":
                                # First author of anything must have lastname - first initial
                                authors.append("{}, {}.".format(item['lastName'], item['firstName'][:1]))
                                if extra == "ed": 
                                    authors.append("{} {}".format(item['firstName'], item['lastName']))
                            elif type == "editor":
                                # Editors should have full first name
                                authors.append("{} {}".format(item['firstName'], item['lastName']))
                            else:
                                # Any other author or editor is first initial-lastname
                                authors.append("{}. {}".format(item['firstName'][:1], item['lastName']))
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


class Manuscript(models.Model):
    """A manuscript can contain a number of sermons"""

    # [1] Name of the manuscript (that is the TITLE)
    name = models.CharField("Name", max_length=LONG_STRING, default="SUPPLY A NAME")
    # [1] Date estimate: starting from this year
    yearstart = models.IntegerField("Year from", null=False, default=100)
    # [1] Date estimate: finishing with this year
    yearfinish = models.IntegerField("Year until", null=False, default=100)
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

    # PHYSICAL features of the manuscript (OPTIONAL)
    # [0-1] Support: the general type of manuscript
    support = models.CharField("Support", max_length=LONG_STRING, null=True, blank=True)
    # [0-1] Extent: the total number of pages
    extent = models.TextField("Extent", max_length=LONG_STRING, null=True, blank=True)
    # [0-1] Format: the size
    format = models.CharField("Format", max_length=LONG_STRING, null=True, blank=True)

    # [1] Every manuscript has a status - this is *NOT* related to model 'Status'
    stype = models.CharField("Status", choices=build_abbr_list(STATUS_TYPE), 
                            max_length=5, default="man")

    # [0-1] Bibliography used for the manuscript
    literature = models.TextField("Literature", null=True, blank=True)

    # Where do we get our information from? And when was it added?
    #    Note: deletion of a sourceinfo sets the manuscript.source to NULL
    source = models.ForeignKey(SourceInfo, null=True, blank=True, on_delete = models.SET_NULL)

    # [0-1] Each manuscript should belong to a particular project
    project = models.ForeignKey(Project, null=True, blank=True, on_delete = models.SET_NULL, related_name="project_manuscripts")

    # [m] Many-to-many: one manuscript can have a series of provenances
    provenances = models.ManyToManyField("Provenance", through="ProvenanceMan")
       
    # [m] Many-to-many: one manuscript can have a series of literature references
    litrefs = models.ManyToManyField("Litref", through="LitrefMan")

     # [0-n] Many-to-many: keywords per SermonDescr
    keywords = models.ManyToManyField(Keyword, through="ManuscriptKeyword", related_name="keywords_manu")

    # [m] Many-to-many: one sermon can be a part of a series of collections 
    collections = models.ManyToManyField("Collection", through="CollectionMan", related_name="collections_manuscript")

    def __str__(self):
        return self.name

    def find_sermon(self, oDescr):
        """Find a sermon within a manuscript"""

        oErr = ErrHandle()
        sermon = None
        try:
            lstQ = []
            if 'title' in oDescr: lstQ.append(Q(title__iexact=oDescr['title']))
            if 'gryson' in oDescr: lstQ.append(Q(gryson__iexact=oDescr['gryson']))
            if 'location' in oDescr: lstQ.append(Q(locus__iexact=oDescr['location']))
            if 'author' in oDescr: lstQ.append(Q(author__name__iexact=oDescr['author']))
            if 'incipit' in oDescr: lstQ.append(Q(incipit__iexact=oDescr['incipit']))
            if 'explicit' in oDescr: lstQ.append(Q(explicit__iexact=oDescr['explicit']))
            if 'quote' in oDescr: lstQ.append(Q(quote__iexact=oDescr['quote']))

            # Find all the SermanMan objects that point to a sermon with the same characteristics I have
            sermon = self.manusermons.filter(*lstQ).first()

            # Return the sermon instance
            return sermon
        except:
            sMsg = oErr.get_error_message()
            oErr.DoError("Manuscript/find_or_create")
            return None

    def find_or_create(name,yearstart, yearfinish, library, idno="", 
                       filename=None, url="", support = "", extent = "", format = "", source=None, stype="imp"):
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
                if name != manuscript.name: manuscript.name = name ; bNeedSave = True
                if filename != manuscript.filename: manuscript.filename = filename ; bNeedSave = True
                if support != manuscript.support: manuscript.support = support ; bNeedSave = True
                if extent != manuscript.extent: manuscript.extent = extent ; bNeedSave = True
                if format != manuscript.format: manuscript.format = format ; bNeedSave = True
                if url != manuscript.url: manuscript.url = url ; bNeedSave = True
                if source != None: manuscript.source=source ; bNeedSave = True
                if bNeedSave:
                    manuscript.save()
            return manuscript
        except:
            sMsg = oErr.get_error_message()
            oErr.DoError("Manuscript/find_or_create")
            return None

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

                    # Set the default status type
                    sermon.stype = "imp"    # Imported

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
                    if 'feast' in msItem and sermon.feast != msItem['feast']: sermon.feast = msItem['feast'] ; bNeedSaving = True
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

    def __str__(self):
        sBack = "{}-{}".format(self.yearstart, self.yearfinish)
        return sBack

    def save(self, force_insert = False, force_update = False, using = None, update_fields = None):
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
        # Need any changes?
        bNeedSaving = False
        if manu_start != current_start:
            self.manuscript.yearstart = current_start
            bNeedSaving = True
        if manu_finish != current_finish:
            self.manuscript.yearfinish = current_finish
            bNeedSaving = True
        if bNeedSaving: self.manuscript.save()
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
        if self.name.lower() == "undecided" or self.name.lower() == "anonymus":
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

    # [m] Many-to-many: all the gold sermons linked to me
    relations = models.ManyToManyField("self", through="EqualGoldLink", symmetrical=False, related_name="related_to")

    # [m] Many-to-many: one sermon can be a part of a series of collections
    collections = models.ManyToManyField("Collection", through="CollectionSuper", related_name="collections_super")
    
    def __str__(self):
        name = "" if self.id == None else "eqg_{}".format(self.id)
        return name

    def save(self, force_insert = False, force_update = False, using = None, update_fields = None):

        oErr = ErrHandle()
        try:
            # Adapt the incipit and explicit
            self.srchincipit = get_searchable(self.incipit)
            self.srchexplicit = get_searchable(self.explicit)
            # Double check the number and the code
            if self.author:
                # There is an author--is this different than the author we used to have?

                if not self.number:
                    # Check the highest sermon number for this author
                    self.number = EqualGold.sermon_number(self.author)
                # Get the author number
                auth_num = self.author.get_number()
                # Now we have both an author and a number...
                passim_code = EqualGold.passim_code(auth_num, self.number)
                if not self.code or self.code != passim_code:
                    # Now save myself with the new code
                    self.code = passim_code

            # Do the saving initially
            response = super(EqualGold, self).save(force_insert, force_update, using, update_fields)
            return response
        except:
            msg = oErr.get_error_message()
            oErr.DoError("Equalgold.save")
            return None

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

        fields = ['author', 'incipit', 'srchincipit', 'explicit', 'srchexplicit', 'number', 'code']
        org = EqualGold()
        for field in fields:
            value = getattr(self, field)
            if value != None:
                setattr(org, field, value)
        # Save the result
        org.save()
        return org

    def sermon_number(author):
        """Determine what the sermon number *would be* for the indicated author"""

        # Check the highest sermon number for this author
        qs_ssg = EqualGold.objects.filter(author=author).order_by("-number")
        if qs_ssg.count() == 0:
            iNumber = 1
        else:
            iNumber = qs_ssg.first().number + 1
        return iNumber

    def get_short(self):
        """Get a very short textual summary"""

        lHtml = []
        # Add the PASSIM code
        lHtml.append("{}".format(self.code))
        # Treat signatures
        equal_set = self.equal_goldsermons.all()
        qs = Signature.objects.filter(gold__in=equal_set).order_by('editype', 'code').distinct()
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

    def get_text(self):
        """Get a short textual representation"""

        lHtml = []
        # Add the PASSIM code
        lHtml.append("{}".format(self.code))
        # Treat signatures
        equal_set = self.equal_goldsermons.all()
        qs = Signature.objects.filter(gold__in=equal_set).order_by('editype', 'code').distinct()
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
        lHtml.append("<span class='passimcode'>{}</span>".format(self.code))
        # Treat signatures
        equal_set = self.equal_goldsermons.all()
        qs = Signature.objects.filter(gold__in=equal_set).order_by('editype', 'code').distinct()
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
            lHtml.append("(by <i>Unknwon Author</i>) ")
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

    def get_moved_code(self):
        """Get the passim code of the one this is replaced by"""

        sBack = ""
        if self.moved:
            sBack = self.moved.code
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
        if origin != None: sBack = origin.code
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

    def get_incipit_markdown(self):
        """Get the contents of the incipit field using markdown"""
        # Perform
        return adapt_markdown(self.incipit)

    def get_explicit_markdown(self):
        """Get the contents of the explicit field using markdown"""
        return adapt_markdown(self.explicit)


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
    stype = models.CharField("Status", choices=build_abbr_list(STATUS_TYPE), 
                            max_length=5, default="man")

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

    def __str__(self):
        name = self.signatures()
        if name == "":
            name = "RU_sg_{}".format(self.id)
        return name

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

    def save(self, force_insert = False, force_update = False, using = None, update_fields = None):
        # Adapt the incipit and explicit
        istop = 1
        self.srchincipit = get_searchable(self.incipit)
        self.srchexplicit = get_searchable(self.explicit)
        lSign = []
        for item in self.goldsignatures.all():
            lSign.append(item.short())
        self.siglist = json.dumps(lSign)
        # Do the saving initially
        response = super(SermonGold, self).save(force_insert, force_update, using, update_fields)
        return response

    def find_or_create(author, incipit, explicit, stype="imp"):
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

    def init_latin():
        """ One time ad-hoc function"""

        with transaction.atomic():
            for obj in SermonGold.objects.all():
                obj.srchincipit = get_searchable(obj.incipit)
                obj.srchexplicit = get_searchable(obj.explicit)
                obj.save()
        return True

    def get_incipit(self):
        """Return the *searchable* incipit, without any additional formatting"""
        return self.srchincipit

    def get_explicit(self):
        """Return the *searchable* explicit, without any additional formatting"""
        return self.srchexplicit

    def signatures(self):
        """Combine all signatures into one string"""

        lSign = []
        for item in self.goldsignatures.all():
            lSign.append(item.short())
        return " | ".join(lSign)

    def get_signatures(self):
        lSign = []
        for item in self.goldsignatures.all():
            lSign.append(item.short())
        return lSign

    def signatures_ordered(self):
        return self.goldsignatures.all().order_by("editype", "code")

    def collections_ordered(self):
        return self.collections_gold.all().order_by("name")

    def get_keywords(self):
        """Combine all keywords into one string"""

        if self.id == None: return ""
        lKeyword = []
        for item in self.keywords.all():
            lKeyword.append(item.name)
        return " | ".join(lKeyword)

    def do_signatures(self):
        """Create or re-make a JSON list of signatures"""

        lSign = []
        for item in self.goldsignatures.all():
            lSign.append(item.short())
        self.siglist = json.dumps(lSign)
        # And save myself
        self.save()

    def editions(self):
        """Combine all editions into one string: the editions are retrieved from litrefSG"""

        lEdition = []
        for item in self.sermon_gold_editions.all():
            lEdition.append(item.reference.short)
        return " | ".join(lEdition)

    def get_editions(self):
        lEdition = []
        for item in self.sermon_gold_editions.all():
            lEdition.append(item.get_short())
        # Sort the items
        lEdition.sort()
        return lEdition

    def ftxtlinks(self):
        """Combine all editions into one string"""

        lFtxtlink = []
        for item in self.goldftxtlinks.all():
            lFtxtlink.append(item.short())
        return ", ".join(lFtxtlink)

    def get_bibliography_markdown(self):
        """Get the contents of the bibliography field using markdown"""
        return adapt_markdown(self.bibliography, False)

    def get_incipit_markdown(self):
        """Get the contents of the incipit field using markdown"""
        # Perform
        return adapt_markdown(self.incipit)

    def get_explicit_markdown(self):
        """Get the contents of the explicit field using markdown"""
        return adapt_markdown(self.explicit)

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

    def get_sermon_string(self):
        """Get a string summary of this one"""

        author = "" if self.author == None else self.author.name
        incipit = "" if self.incipit == None else self.incipit
        explicit = "" if self.explicit == None else self.explicit
        return "{} {} {} {}".format(author, self.signatures(), incipit, explicit)
    
    def add_relation(self, target, linktype):
        """Add a relation from me to [target] with the indicated type"""

        relation, created = SermonGoldSame.objects.get_or_create(
            src=self, dst=target, linktype=linktype)
        # Return the new SermonGoldSame instance that has been created
        return relation

    def remove_relation(self, target, linktype):
        """Find and remove all links to target with the indicated type"""

        SermonGoldSame.objects.filter(src=self, dst=target, linktype=linktype).delete()
        # Return positively
        return True

    def has_relation(self, target, linktype):
        """Check if the indicated linktype relation exists"""

        obj = SermonGoldSame.objects.filter(src=self, dst=target, linktype=linktype).first()
        # Return existance
        return (obj != None)

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


class EqualGoldLink(models.Model):
    """Link to identical sermons that have a different signature"""

    # [1] Starting from equalgold group [src]
    #     Note: when a EqualGold is deleted, then the EqualGoldLink instance that refers to it is removed too
    src = models.ForeignKey(EqualGold, related_name="equalgold_src")
    # [1] It equals equalgoldgroup [dst]
    dst = models.ForeignKey(EqualGold, related_name="equalgold_dst")
    # [1] Each gold-to-gold link must have a linktype, with default "equal"
    linktype = models.CharField("Link type", choices=build_abbr_list(LINK_TYPE), 
                            max_length=5, default=LINK_EQUAL)

    def __str__(self):
        combi = "{} is {} of {}".format(self.src.signature, self.linktype, self.dst.signature)
        return combi


class SermonGoldSame(models.Model):
    """Link to identical sermons that have a different signature"""

    # [1] Starting from sermon [src]
    #     Note: when a SermonGold is deleted, then the SermonGoldSame instance that refers to it is removed too
    src = models.ForeignKey(SermonGold, related_name="sermongold_src")
    # [1] It equals sermon [dst]
    dst = models.ForeignKey(SermonGold, related_name="sermongold_dst")
    # [1] Each gold-to-gold link must have a linktype, with default "equal"
    linktype = models.CharField("Link type", choices=build_abbr_list(LINK_TYPE), 
                            max_length=5, default=LINK_EQUAL)

    def __str__(self):
        combi = "{} is {} of {}".format(self.src.signature, self.linktype, self.dst.signature)
        return combi


class SermonGoldKeyword(models.Model):
    """Relation between a SermonGold and a Keyword"""

    # [1] The link is between a SermonGold instance ...
    gold = models.ForeignKey(SermonGold, related_name="sermongold_kw")
    # [1] ...and a keyword instance
    keyword = models.ForeignKey(Keyword, related_name="sermongold_kw")
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
    gold = models.ForeignKey(SermonGold, null=False, blank=False, related_name="goldftxtlinks")

    def __str__(self):
        return self.url

    def short(self):
        return self.url


class ManuscriptExt(models.Model):
    """External URL (link) that belongs to a particular manuscript"""

    # [1] The URL itself
    url = models.URLField("External URL", max_length=LONG_STRING)
    # [1] Every external URL belongs to exactly one Manuscript
    manuscript = models.ForeignKey(Manuscript, null=False, blank=False, related_name="manuscriptexternals")

    def __str__(self):
        return self.url

    def short(self):
        return self.url
       

class Collection(models.Model):
    """A collection can contain one or more sermons, manuscripts, gold sermons or super super golds"""
    
    # [1] Each collection has only 1 name 
    name = models.CharField("Name", null=True, blank=True, max_length=LONG_STRING)

    # [1] Each collecttion has only 1 owner
    owner = models.ForeignKey(Profile, null=True)
    
    # [0-1] Each collection can be marked a "read only" by Passim-team  ERUIT
    readonly = models.BooleanField(default=False)

    # [1] Each collection has only 1 type    
    type = models.CharField("Type of collection", choices=build_abbr_list(COLLECTION_TYPE), 
                            max_length=5)

    # [0-1] Each collection can have one description
    descrip = models.CharField("Description", null=True, blank=True, max_length=LONG_STRING)

    # [0-1] Link to a description or bibliography (url) 
    url = models.URLField("Web info", null=True, blank=True)

    # Path to register all additions and changes to each Collection (as stringified JSON list)
    path = models.TextField("History of collection", null=True, blank=True)

    # [1] Each collection has only 1 date/timestamp that shows when the collection was created
   # date = models.DateTimeField(default=get_current_datetime)
   
    # [0-1] Each collection can be marked as "private" by each user 
    
    #private = models.BooleanField(default=True)
    
    # [0-1] Each collection can be marked as "team" by editors (only when private == False) 
    #team = models.BooleanField(default=True)
    
    
    def __str__(self):
        return self.name

    def get_readonly_display(self):
        response = "yes" if self.readonly else "no"
        return response
        
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

    def get_label(self):
        """Return an appropriate name or label"""

        return self.name


class SermonDescr(models.Model):
    """A sermon is part of a manuscript"""

    # [0-1] Not every sermon might have a title ...
    title = models.CharField("Title", null=True, blank=True, max_length=LONG_STRING)

    # [0-1] Some (e.g. e-codices) may have a subtitle (field <rubric>)
    subtitle = models.CharField("Sub title", null=True, blank=True, max_length=LONG_STRING)

    # ======= OPTIONAL FIELDS describing the sermon ============
    # [0-1] We would very much like to know the *REAL* author
    author = models.ForeignKey(Author, null=True, blank=True, on_delete = models.SET_NULL, related_name="author_sermons")
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
    # [0-1] If there is a QUOTE, we would like to know the QUOTE (in Latin)
    quote = models.TextField("Quote", null=True, blank=True)
    # [0-1] The FEAST??
    feast = models.CharField("Feast", null=True, blank=True, max_length=LONG_STRING)
    # [0-1] Notes on the bibliography, literature for this sermon
    bibnotes = models.TextField("Bibliography notes", null=True, blank=True)
    # [0-1] Any notes for this sermon
    note = models.TextField("Note", null=True, blank=True)
    # [0-1] Additional information 
    additional = models.TextField("Additional", null=True, blank=True)
    # [0-1] Any number of bible references (as stringified JSON list)
    bibleref = models.TextField("Bible reference(s)", null=True, blank=True)

    # [1] Every SermonDescr has a status - this is *NOT* related to model 'Status'
    stype = models.CharField("Status", choices=build_abbr_list(STATUS_TYPE), 
                            max_length=5, default="man")

    # [0-n] Many-to-many: keywords per SermonDescr
    keywords = models.ManyToManyField(Keyword, through="SermonDescrKeyword", related_name="keywords_sermon")

    # ========================================================================
    # [1] Every sermondescr belongs to exactly one manuscript
    #     Note: when a Manuscript is removed, all its associated SermonDescr are also removed
    manu = models.ForeignKey(Manuscript, null=True, related_name="manusermons")

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

    # [0-n] Link to one or more golden standard sermons
    goldsermons = models.ManyToManyField(SermonGold, through="SermonDescrGold")

    # [0-1] Method
    method = models.CharField("Method", max_length=LONG_STRING, default="(OLD)")

    # [m] Many-to-many: one sermon can be a part of a series of collections 
    collections = models.ManyToManyField("Collection", through="CollectionSerm", related_name="collections_sermon")

    def __str__(self):
        if self.author:
            sAuthor = self.author.name
        elif self.nickname:
            sAuthor = self.nickname.name
        else:
            sAuthor = "-"
        sSignature = "{}/{}".format(sAuthor,self.locus)
        return sSignature

    def save(self, force_insert = False, force_update = False, using = None, update_fields = None):
        # Adapt the incipit and explicit
        istop = 1
        if self.incipit: self.srchincipit = get_searchable(self.incipit)
        if self.explicit: self.srchexplicit = get_searchable(self.explicit)
        lSign = []
        bNeedSave = False
        for item in self.sermonsignatures.all():
            lSign.append(item.short())
            bNeedSave = True
        if bNeedSave: self.siglist = json.dumps(lSign)
        # Do the saving initially
        response = super(SermonDescr, self).save(force_insert, force_update, using, update_fields)
        return response

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

    def target(self):
        # Get the URL to edit this sermon
        sUrl = "" if self.id == None else reverse("sermon_edit", kwargs={'pk': self.id})
        return sUrl

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

    def get_manuscript(self):
        """Get the manuscript that links to this sermondescr"""

        return obj.manu

    def signatures(self):
        """Combine all signatures into one string"""

        lSign = []
        for item in self.sermonsignatures.all():
            lSign.append(item.short())
        return " | ".join(lSign)

    def do_signatures(self):
        """Create or re-make a JSON list of signatures"""

        lSign = []
        for item in self.sermonsignatures.all():
            lSign.append(item.short())
        self.siglist = json.dumps(lSign)
        # And save myself
        self.save()

    def signatures_ordered(self):
        # Provide an ordered list of signatures
        return self.sermonsignatures.all().order_by("editype", "code")

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

    def goldeditions_ordered(self):
        """Provide an ordered list of EdirefSG connected to me through related gold sermons"""

        lstQ = []
        lstQ.append(Q(sermon_gold__in=self.goldsermons.all()))
        edirefsg_ordered = EdirefSG.objects.filter(*lstQ).order_by("reference__short")
        return edirefsg_ordered

    def get_incipit(self):
        """Return the *searchable* incipit, without any additional formatting"""
        return self.srchincipit

    def get_explicit(self):
        """Return the *searchable* explicit, without any additional formatting"""
        return self.srchexplicit

    def get_incipit_markdown(self):
        """Get the contents of the incipit field using markdown"""

        # Sanity check
        if self.incipit != None and self.incipit != "":
            if self.srchincipit == None or self.srchincipit == "":
                SermonDescr.init_latin()

        return adapt_markdown(self.incipit)

    def get_explicit_markdown(self):
        """Get the contents of the explicit field using markdown"""
        return adapt_markdown(self.explicit)


class SermonDescrKeyword(models.Model):
    """Relation between a SermonDescr and a Keyword"""

    # [1] The link is between a SermonGold instance ...
    sermon = models.ForeignKey(SermonDescr, related_name="sermondescr_kw")
    # [1] ...and a keyword instance
    keyword = models.ForeignKey(Keyword, related_name="sermondescr_kw")
    # [1] And a date: the date of saving this relation
    created = models.DateTimeField(default=get_current_datetime)


class ManuscriptKeyword(models.Model):
    """Relation between a Manuscript and a Keyword"""

    # [1] The link is between a Manuscript instance ...
    manuscript = models.ForeignKey(Manuscript, related_name="manuscript_kw")
    # [1] ...and a keyword instance
    keyword = models.ForeignKey(Keyword, related_name="manuscript_kw")
    # [1] And a date: the date of saving this relation
    created = models.DateTimeField(default=get_current_datetime)


class SermonDescrGold(models.Model):
    """Link from sermon description to gold standard"""

    # [1] The sermondescr
    sermon = models.ForeignKey(SermonDescr, related_name="sermondescr_gold")
    # [1] The gold sermon
    gold = models.ForeignKey(SermonGold, related_name="sermondescr_gold")
    # [1] Each sermon-to-gold link must have a linktype, with default "equal"
    linktype = models.CharField("Link type", choices=build_abbr_list(LINK_TYPE), 
                            max_length=5, default="eq")

    def __str__(self):
        # Temporary fix: sermon.id
        # Should be changed to something more significant in the future
        # E.G: manuscript+locus?? (assuming each sermon has a locus)
        combi = "{} is {} of {}".format(self.sermon.id, self.linktype, self.gold.signature)
        return combi


class Signature(models.Model):
    """One Gryson, Clavis or other code as taken up in an edition"""

    # [1] It must have a code = gryson code or clavis number
    code = models.CharField("Code", max_length=LONG_STRING)
    # [1] Every signature must be of a limited number of types
    editype = models.CharField("Edition type", choices=build_abbr_list(EDI_TYPE), 
                            max_length=5, default="gr")
    # [1] Every signature belongs to exactly one gold-sermon
    #     Note: when a SermonGold is removed, then its associated Signature gets removed too
    gold = models.ForeignKey(SermonGold, null=False, blank=False, related_name="goldsignatures")

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
    gsig = models.ForeignKey(Signature, blank=True, null=True, related_name="sermongoldsignatures")
    # [1] Every signature belongs to exactly one gold-sermon
    #     Note: when a SermonDescr gets removed, then its associated SermonSignature gets removed too
    sermon = models.ForeignKey(SermonDescr, null=False, blank=False, related_name="sermonsignatures")

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

    def get_goldsig(self):
        """Get the equivalent gold-signature for me"""

        # See if this sermosig has an equivalent goldsig
        if self.gsig == None:
            # No gsig given, so depend on the self.editype and self.code
            qs = Signature.objects.filter(Q(gold__in = self.sermon.goldsermons.all()))
            for obj in qs:
                if obj.editype == self.editype and obj.code == self.code:
                    # Found it
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
        return self.gsig

    
class Basket(models.Model):
    """The basket is the user's vault of search results (sermondescr items)"""

    # [1] The sermondescr
    sermon = models.ForeignKey(SermonDescr, related_name="basket_contents")
    # [1] The user
    profile = models.ForeignKey(Profile, related_name="basket_contents")

    def __str__(self):
        combi = "{}_s{}".format(self.profile.user.username, self.sermon.id)
        return combi


class ProvenanceMan(models.Model):

    # [1] The provenance
    provenance = models.ForeignKey(Provenance, related_name = "manuscripts_provenances")
    # [1] The manuscript this sermon is written on 
    manuscript = models.ForeignKey(Manuscript, related_name = "manuscripts_provenances")


class LitrefMan(models.Model):
    """The link between a literature item and a manuscript"""

    # [1] The literature item
    reference = models.ForeignKey(Litref, related_name="reference_litrefs")
    # [1] The manuscript to which the literature item refers
    manuscript = models.ForeignKey(Manuscript, related_name = "manuscript_litrefs")
    # [0-1] The first and last page of the reference
    pages = models.CharField("Pages", blank = True, null = True,  max_length=MAX_TEXT_LEN)


class LitrefSG(models.Model):
    """The link between a literature item and a SermonGold"""
    
    # [1] The literature item
    reference = models.ForeignKey(Litref, related_name="reference_litrefs_2")
    # [1] The SermonGold to which the literature item refers
    sermon_gold = models.ForeignKey(SermonGold, related_name = "sermon_gold_litrefs")
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


class EdirefSG(models.Model):
    """The link between an edition item and a SermonGold"""

    # [1] The edition item
    reference = models.ForeignKey(Litref, related_name = "reference_edition")
    # [1] The SermonGold to which the literature item refers
    sermon_gold = models.ForeignKey(SermonGold, related_name = "sermon_gold_editions")
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
      self.saved = datetime.now()
      response = super(NewsItem, self).save(force_insert, force_update, using, update_fields)
      return response

    def check_until():
        """Check all news items for the until date and emend status where needed"""

        # Get current time
        now = timezone.now()
        for obj in NewsItem.objects.all():
            if obj.until and obj.until < now:
                # This should be set invalid
                obj.status = "ext"
                obj.save()
        # Return valid
        return True


class CollectionSerm(models.Model):
    """The link between a collection item and a sermon"""
    # [1] The sermon to which the collection item refers
    sermon = models.ForeignKey(SermonDescr, related_name = "sermondescr_col")
    # [1] The collection to which the context item refers to
    collection = models.ForeignKey(Collection, related_name= "sermondescr_col")


class CollectionMan(models.Model):
    """The link between a collection item and a manuscript"""
    # [1] The manuscript to which the collection item refers
    manuscript = models.ForeignKey(Manuscript, related_name = "manuscript_col")
    # [1] The collection to which the context item refers to
    collection = models.ForeignKey(Collection, related_name= "manuscript_col")


class CollectionGold(models.Model):
    """The link between a collection item and a gold sermon"""
    # [1] The gold sermon to which the collection item refers
    gold = models.ForeignKey(SermonGold, related_name = "gold_col")
    # [1] The collection to which the context item refers to
    collection = models.ForeignKey(Collection, related_name= "gold_col")


class CollectionSuper(models.Model):
    """The link between a collection item and a gold sermon"""
    # [1] The gold sermon to which the coll
    # ection item refers
    super = models.ForeignKey(EqualGold, related_name = "super_col")
    # [1] The collection to which the context item refers to
    collection = models.ForeignKey(Collection, related_name= "super_col")

