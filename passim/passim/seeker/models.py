"""Models for the SEEKER app.

"""
from django.db import models, transaction
from django.contrib.auth.models import User, Group
from django.db.models import Q
from django.db.models.functions import Lower
from django.utils.html import mark_safe
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
from io import StringIO

# import xml.etree.ElementTree as ET
# from lxml import etree as ET
# import xmltodict
from xml.dom import minidom

STANDARD_LENGTH=100
LONG_STRING=255
MAX_TEXT_LEN = 200

VIEW_STATUS = "view.status"
LIBRARY_TYPE = "seeker.libtype"
REPORT_TYPE = "seeker.reptype"
LINK_TYPE = "seeker.linktype"
EDI_TYPE = "seeker.editype"

LINK_EQUAL = 'eqs'
LINK_PRT = ['prt', 'neq']

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

def adapt_search(val):
    if val == None: return None
    # First trim
    val = val.strip()
    val = '^' + fnmatch.translate(val) + '$'
    return val

def adapt_latin(val):
    """Change the three dots into a unicode character"""

    val = val.replace('...', u'\u2026')
    return val

def adapt_markdown(val):
    sBack = ""
    if val != None:
        val = val.replace("***", "\*\*\*")
        sBack = mark_safe(markdown(val, safe_mode='escape'))
        sBack = sBack.replace("<p>", "")
        sBack = sBack.replace("</p>", "")
    return sBack

def is_number(s_input):
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
    sText = sText.lower()
    sText = sText.replace("<", "")
    sText = sText.replace(">", "")
    sText = sText.replace("_", "")
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

def build_abbr_list(field, position=None, subcat=None, maybe_empty=False):
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

def add_gold2gold(src, dst, ltype):
    """Add a gold-to-gold relation from src to dst of type ltype"""

    # Initialisations

    # Create a list into which the items to be added are put
    lst_add = []
    added = 0

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
                                lst_prt_add.append({'src': src, 'dst': dst})
                            # Check if the reverse relation is already there
                            obj = qs_prt.filter(src=dst, dst=src).first()
                            if obj == None:
                                lst_prt_add.append({'src': dst, 'dst': src})
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

    # Main body of add_gold2gold()
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
                        lst_add.append({'src': inst_src, 'dst': inst_dst})
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
        lst_add = []
        for inst_src in grp_src:
            for inst_dst in grp_dst:
                # Make sure they are not equal
                if inst_src.id != inst_dst.id:
                    obj = SermonGoldSame.objects.filter(linktype=linktype, src=inst_src, dst=inst_dst).first()
                    if obj == None:
                        # Add the relation to the ones that should be added
                        lst_add.append({'src': inst_src, 'dst': inst_dst})
        # 4: Add those that need adding in one go
        with transaction.atomic():
            for idx, item in enumerate(lst_add):
                obj = SermonGoldSame(linktype=LINK_EQUAL, src=item['src'], dst=item['dst'])
                obj.save()
                lst_total.append("<tr><td>{}</td><td>{}</td><td>{}</td><td>{}</td><td>{}</td></tr>".format( 
                    (idx+1), item['src'].siglist, item['dst'].siglist, LINK_EQUAL, "add" ))
                added += 1
        

    # Finish the report list
    lst_total.append("</tbody></table>")

    # Return the number of added relations
    return added, lst_report


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


class Report(models.Model):
    """Report of an upload action or something like that"""

    # [1] Every report must be connected to a user and a date (when a user is deleted, the Report is deleted too)
    user = models.ForeignKey(User)
    # [1] And a date: the date of saving this report
    created = models.DateTimeField(default=datetime.now)
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
        return obj


class Profile(models.Model):
    """Information about the user"""

    # [1] Every profile is linked to a user
    user = models.ForeignKey(User)
    # [1] Every user has a stack: a list of visit objects
    stack = models.TextField("Stack", default = "[]")

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


class Visit(models.Model):
    """One visit to part of the application"""

    # [1] Every visit is made by a user
    user = models.ForeignKey(User)
    # [1] Every visit is done at a certain moment
    when = models.DateTimeField(default=datetime.now)
    # [1] Every visit is to a 'named' point
    name = models.CharField("Name", max_length=STANDARD_LENGTH)
    # [1] Every visit needs to have a URL
    path = models.URLField("URL")

    def __str__(self):
        msg = "{} ({})".format(self.name, self.path)
        return msg

    def add(username, name, path, is_menu = False, **kwargs):
        """Add a visit from user [username]"""

        oErr = ErrHandle
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
    city = models.ForeignKey(City, related_name="city_libraries")
    # [1] Name of the country this is in
    country = models.ForeignKey(Country, null=True, related_name="country_libraries")

    def __str__(self):
        return self.name

    def get_library(sId, sLibrary, bBracketed, country, city):
        iId = int(sId)
        lstQ = []
        lstQ.append(Q(idLibrEtab=iId))
        lstQ.append(Q(name=sLibrary))
        lstQ.append(Q(country=country))
        lstQ.append(Q(city=city))
        hit = Library.objects.filter(*lstQ).first()
        if hit == None:
            libtype = "br" if bBracketed else "pl"
            hit = Library(idLibrEtab=iId, name=sLibrary, libtype=libtype, country=country, city=city)
            hit.save()

        return hit

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
    # [0-1] Further details are perhaps required too
    # TODO: city/country??

    def __str__(self):
        return self.name

    def find_or_create(sName):
        """Find a location or create it."""

        qs = Origin.objects.filter(Q(name__iexact=sName))
        if qs.count() == 0:
            # Create one
            hit = Origin(name=sName)
            hit.save()
        else:
            hit = qs[0]
        # Return what we found or created
        return hit


class Provenance(models.Model):
    """The 'origin' is a location where manuscripts were originally created"""

    # [1] Name of the location
    name = models.CharField("Provenance location", max_length=LONG_STRING)
    # [0-1] Further details are perhaps required too
    note = models.TextField("Notes on this provenance", blank=True, null=True)
    # TODO: city/country??

    def __str__(self):
        return self.name

    def find_or_create(sName, note=None):
        """Find a location or create it."""

        lstQ = []
        lstQ.append(Q(name__iexact=sName))
        if note!=None: lstQ.append(Q(note__iexact=note))
        qs = Provenance.objects.filter(*lstQ)
        if qs.count() == 0:
            # Create one
            hit = Provenance(name=sName)
            if note!=None: hit.note=note
            hit.save()
        else:
            hit = qs[0]
        # Return what we found or created
        return hit


class SourceInfo(models.Model):
    """Details of the source from which we get information"""

    # [1] Obligatory time of extraction
    created = models.DateTimeField(default=datetime.now)
    # [0-1] Code used to collect information
    code = models.TextField("Code", null=True, blank=True)
    # [0-1] URL that was used
    url = models.URLField("URL", null=True, blank=True)
    # [1] The person who was in charge of extracting the information
    collector = models.CharField("Collected by", max_length=LONG_STRING)


class Manuscript(models.Model):
    """A manuscript can contain a number of sermons"""

    # [1] Name of the manuscript (that is the TITLE)
    name = models.CharField("Name", max_length=LONG_STRING)
    # [1] Date estimate: starting from this year
    yearstart = models.IntegerField("Year from", null=False)
    # [1] Date estimate: finishing with this year
    yearfinish = models.IntegerField("Year until", null=False)
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
    extent = models.CharField("Extent", max_length=LONG_STRING, null=True, blank=True)
    # [0-1] Format: the size
    format = models.CharField("Format", max_length=LONG_STRING, null=True, blank=True)

    # Where do we get our information from? And when was it added?
    # Note: deletion of a sourceinfo sets the manuscript.source to NULL
    source = models.ForeignKey(SourceInfo, null=True, blank=True, on_delete = models.SET_NULL)

    # [m] Many-to-many: all the provenances of this manuscript
    provenances = models.ManyToManyField("Provenance", through="ProvenanceMan")


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
                       filename=None, url="", support = "", extent = "", format = "", source=None):
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
                if url != "": manuscript.url = url
                if source != None: manuscript.source=source
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

                # NOTE: this would give the wrong information
                #
                ## Try to find the author within msItem
                #authors = msItem.getElementsByTagName("persName")
                #for person in authors:
                #    # Check if this is linked as author
                #    if 'role' in person.attributes and person.attributes['role'].value == "author":
                #        oMsItem['author'] = getText(person)
                #        # Don't look further: the first author is the *best*
                #        break

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
                    if 'edition' in msItem: sermon.edition = msItem['edition']
                    if 'quote' in msItem: sermon.quote = msItem['quote']
                    if 'gryson' in msItem: sermon.gryson = msItem['gryson']
                    if 'clavis' in msItem: sermon.clavis = msItem['clavis']
                    if 'feast' in msItem: sermon.feast = msItem['feast']
                    if 'keyword' in msItem: sermon.keyword = msItem['keyword']
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

                    # Now save it
                    sermon.save()
                    # Make a link using the SermonMan
                    sermonman = SermonMan(sermon=sermon, manuscript=manuscript)
                    sermonman.save()
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
                            org = item.getElementsByTagName("orgName")
                            if org.length>0:
                                orgName = getText(org[0])
                            oProv = {'name': orgName, 'note': getText(item)}
                            lProvenances.append(oProv)
                        elif sTag == "acquisition":
                            pass

            # Now [oInfo] has a full description of the contents to be added to the database
            # (1) Get the country from the city
            city = City.objects.filter(name__iexact=oInfo['city']).first()
            country = None if city == None else city.country.name

            # (2) Get the library from the info object
            library = Library.find_or_create(oInfo['city'], oInfo['library'], country)

            # (3) Get or create place of origin: This should be placed into 'provenance'
            # origin = Origin.find_or_create(oInfo['origPlace'])
            provenance_origin = Provenance.find_or_create(oInfo['origPlace'], 'origPlace')

            # (4) Get or create the Manuscript
            yearstart = oInfo['origDateFrom'] if oInfo['origDateFrom'] != "" else 1800
            yearfinish = oInfo['origDateTo'] if oInfo['origDateTo'] != "" else 2020
            support = "" if 'support' not in oInfo else oInfo['support']
            extent = "" if 'extent' not in oInfo else oInfo['extent']
            format = "" if 'format' not in oInfo else oInfo['format']
            idno = "" if 'idno' not in oInfo else oInfo['idno']
            url = oInfo['url']
            manuscript = Manuscript.find_or_create(oInfo['name'], yearstart, yearfinish, library, idno, filename, url, support, extent, format, source)

            # Add all the provenances we know of
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
                    if 'firstChild' in msItem: instance.firstchild = msItem['firstChild']['obj']
                    if 'next' in msItem: instance.next = msItem['next']['obj']
                    instance.save()

            # Make sure the requester knows how many have been added
            oBack['count'] = 1              # Only one manuscript is added here
            oBack['sermons'] = iSermCount   # The number of sermons (=msitems) added
            oBack['name'] = oInfo['name']
            oBack['filename'] = filename

        except:
            sError = errHandle.get_error_message()
            oBack['status'] = 'error'
            oBack['msg'] = sError

        # Return the object that has been created
        return oBack
    

class Author(models.Model):
    """We have a set of authors that are the 'golden' standard"""

    # [1] Name of the author
    name = models.CharField("Name", max_length=LONG_STRING)
    # [0-1] Possibly add the Gryson abbreviation for the author
    abbr = models.CharField("Abbreviation", null=True, blank=True, max_length=LONG_STRING)

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


class SermonGold(models.Model):
    """The signature of a standard sermon"""

    # ======= OPTIONAL FIELDS describing the sermon ============
    # [0-1] We would very much like to know the *REAL* author
    author = models.ForeignKey(Author, null=True, blank=True, on_delete = models.SET_NULL, related_name="author_goldensermons")
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

    # [m] Many-to-many: all the gold sermons linked to me
    relations = models.ManyToManyField("self", through="SermonGoldSame", symmetrical=False, related_name="related_to")

    def __str__(self):
        name = self.signatures()
        if name == "":
            name = "RU_sg_{}".format(self.id)
        return name

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

    def find_or_create(author, incipit, explicit):
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
            signature = signature.split("CPPM")[1].strip()
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

    def do_signatures(self):
        """Create or re-make a JSON list of signatures"""

        lSign = []
        for item in self.goldsignatures.all():
            lSign.append(item.short())
        self.siglist = json.dumps(lSign)
        # And save myself
        self.save()

    def editions(self):
        """Combine all editions into one string"""

        lEdition = []
        for item in self.goldeditions.all():
            lEdition.append(item.short())
        return " | ".join(lEdition)

    def ftxtlinks(self):
        """Combine all editions into one string"""

        lFtxtlink = []
        for item in self.goldftxtlinks.all():
            lFtxtlink.append(item.short())
        return ", ".join(lFtxtlink)

    def get_bibliography_markdown(self):
        """Get the contents of the bibliography field using markdown"""
        return adapt_markdown(self.bibliography)

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

        # Number to order all the items we read
        order = 0
        iSermCount = 0
        count_obj = 0   # Number of objects added
        count_rel = 0   # Number of relations added

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
                    edition_lst = oGold['edition'].split(";")
                    for item in edition_lst:
                        item = item.strip()

                        # NOTE: An edition should be unique for a gold sermon; not in general!
                        edition = Edition.find(item, gold)
                        if edition == None:
                            edition = Edition(name=item, gold=gold)
                            edition.save()
                        elif bCreated:
                            # This edition already exists
                            add_to_manual_list(lst_manual, "edition", 
                                               "First instance of a gold sermon is attempted to be linked with existing edition [{}]".format(item), oGold)
                            # Skip the remainder of this line
                            bBreak = True
                            break

                    if bBreak:
                        # # Break from the higher gold loop
                        # continue
                        # NOTE: don't break completely. Continue with editions
                        pass

                    # Getting here means that the item is read TO SOME EXTENT
                    add_to_read_list(lst_read, oGold)

                    oGold['obj'] = gold
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
                            count_links, lst_added = add_gold2gold(obj, target, linktype)
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

    def target(self):
        # Get the URL to edit/view this sermon
        sUrl = "" if self.id == None else reverse("goldlink_view", kwargs={'pk': self.id})
        return sUrl


class Edition(models.Model):
    """Critical text edition of a Gold Sermon"""

    # [1] It must have a name - that is the Gryson book or the Clavis book or something
    name = models.CharField("Name", max_length=LONG_STRING)
    # [1] Every edition belongs to exactly one gold-sermon
    #     Note: when a SermonGold is removed, the edition that uses it is also removed
    #     This is because each Edition instance is uniquely associated with one SermonGold
    gold = models.ForeignKey(SermonGold, null=False, blank=False, related_name="goldeditions")

    def __str__(self):
        return self.name

    def short(self):
        return self.name

    def find(name, gold=None):
        lstQ = []
        lstQ.append(Q(name__iexact=name))
        if gold != None:
            lstQ.append(Q(gold=gold))
        obj = Edition.objects.filter(*lstQ).first()
        return obj

    def find_or_create(name):
        obj = self.find(name)
        if obj == None:
            obj = Edition(name=name)
            obj.save()
        return obj


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


class SermonDescr(models.Model):
    """A sermon is part of a manuscript"""

    # [0-1] Not every sermon might have a title ...
    title = models.CharField("Title", null=True, blank=True, max_length=LONG_STRING)

    # ======= OPTIONAL FIELDS describing the sermon ============
    # [0-1] We would very much like to know the *REAL* author
    author = models.ForeignKey(Author, null=True, blank=True, on_delete = models.SET_NULL, related_name="author_sermons")
    # [0-1] But most often we only start out with having just a nickname of the author
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
    # [0-1] We would like to know the Clavis number (if available)
    clavis = models.CharField("Clavis number", null=True, blank=True, max_length=LONG_STRING)
    # [0-1] We would like to know the Gryson number (if available)
    gryson = models.CharField("Gryson number", null=True, blank=True, max_length=LONG_STRING)
    # [0-1] The FEAST??
    feast = models.CharField("Feast", null=True, blank=True, max_length=LONG_STRING)
    # [0-1] Edition
    edition = models.TextField("Edition", null=True, blank=True)
    # [0-1] Any notes for this sermon
    note = models.TextField("Note", null=True, blank=True)
    # [0-1] Additional information 
    additional = models.TextField("Additional", null=True, blank=True)
    # [0-1] Any number of bible references (as stringified JSON list)
    bibleref = models.TextField("Bible reference(s)", null=True, blank=True)
    # [0-1] One keyword or more??
    keyword = models.CharField("Keyword", null=True, blank=True, max_length=LONG_STRING)

    # ========================================================================
    # [1] Every sermondescr belongs to exactly one manuscript
    #     Note: when a Manuscript is removed, all its associated SermonDescr are also removed
    manu = models.ForeignKey(Manuscript, null=True, related_name="manusermons")

    # Automatically created and processed fields
    # [1] Every gold sermon has a list of signatures that are automatically created
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

    def __str__(self):
        if self.author:
            sAuthor = self.author.name
        elif self.nickname:
            sAuthor = self.nickname.name
        else:
            sAuthor = "-"
        sSignature = "{}/{}".formate(sAuthor,self.locus)
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
            depth += 1
            node = node.parent
        return depth

    def get_manuscript(self):
        """Get the first manuscript that links to this sermondescr"""

        obj = SermonMan.objects.filter(sermon=self).first()
        if obj == None:
            return None
        else:
            return obj.manuscript

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
    # [1] Every edition must be of a limited number of types
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

    
class ProvenanceMan(models.Model):

    # [1] The provenance
    provenance = models.ForeignKey(Provenance, related_name = "manuscripts_provenances")
    # [1] The manuscript this sermon is written on 
    manuscript = models.ForeignKey(Manuscript, related_name = "manuscripts_provenances")


class NewsItem(models.Model):
    """A news-item that can be displayed for a limited time"""

    # [1] title of this news-item
    title = models.CharField("Title",  max_length=MAX_TEXT_LEN)
    # [1] the date when this item was created
    created = models.DateTimeField(default=datetime.now)
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
