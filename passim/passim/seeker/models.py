"""Models for the SEEKER app.

"""
from django.db import models, transaction
from django.contrib.auth.models import User, Group
from django.db.models import Q
from django.db.models.functions import Lower
from django.urls import reverse
from datetime import datetime
from passim.utils import *
from passim.settings import APP_PREFIX, WRITABLE_DIR
import sys, os
import copy
import json
import time
# import xml.etree.ElementTree as ET
# from lxml import etree as ET
# import xmltodict
from xml.dom import minidom

STANDARD_LENGTH=100
LONG_STRING=255
MAX_TEXT_LEN = 200

VIEW_STATUS = "view.status"
LIBRARY_TYPE = "seeker.libtype"


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


class Manuscript(models.Model):
    """A manuscript can contain a number of sermons"""

    # [1] Name of the manuscript (that is the TITLE)
    name = models.CharField("Name", max_length=LONG_STRING)
    # [1] Date estimate: starting from this year
    yearstart = models.IntegerField("Year from", null=False)
    # [1] Date estimate: finishing with this year
    yearfinish = models.IntegerField("Year until", null=False)
    # [1] One manuscript can only belong to one particular library
    library = models.ForeignKey(Library, related_name="library_manuscripts")
    # [1] Each manuscript has an identification number
    idno = models.CharField("Identifier", max_length=LONG_STRING, null=True, blank=True)
    # [0-1] If possible we need to know the original location of the manuscript
    origin = models.ForeignKey(Origin, null=True, blank=True, related_name="origin_manuscripts")
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

    # [m] Many-to-many: all the sermons of this manuscr
    sermons = models.ManyToManyField("SermonDescr", through="SermonMan")


    def __str__(self):
        return self.name

    def find_sermon(self, oDescr):
        """Find a sermon within a manuscript"""

        oErr = ErrHandle()
        sermon = None
        try:
            lstQ = []
            if 'title' in oDescr: lstQ.append(Q(title__iexact=oDescr['title']))
            if 'location' in oDescr: lstQ.append(Q(locus__iexact=oDescr['location']))
            if 'author' in oDescr: lstQ.append(Q(author__name__iexact=oDescr['author']))
            if 'incipit' in oDescr: lstQ.append(Q(incipit__iexact=oDescr['incipit']))
            if 'explicit' in oDescr: lstQ.append(Q(explicit__iexact=oDescr['explicit']))

            # Find all the SermanMan objects that point to a sermon with the same characteristics I have
            sermon = self.sermons.filter(*lstQ).first()

            # Return the sermon instance
            return sermon
        except:
            sMsg = oErr.get_error_message()
            oErr.DoError("Manuscript/find_or_create")
            return None

    def find_or_create(name,yearstart, yearfinish, library, origin, idno="", filename=None, url="", support = "", extent = "", format = ""):
        """Find an existing manuscript, or create a new one"""

        oErr = ErrHandle()
        try:
            lstQ = []
            lstQ.append(Q(name=name))
            lstQ.append(Q(yearstart=yearstart))
            lstQ.append(Q(yearfinish=yearfinish))
            lstQ.append(Q(library=library))
            qs = Manuscript.objects.filter(*lstQ)
            if qs.count() == 0:
                # Note: do *NOT* let the place of origin play a role in locating the manuscript
                manuscript = Manuscript(name=name, yearstart=yearstart, yearfinish=yearfinish, library=library )
                if idno != "": manuscript.idno = idno
                if origin != None: manuscript.origin = origin
                if filename != None: manuscript.filename = filename
                if support != "": manuscript.support = support
                if extent != "": manuscript.extent = extent
                if format != "": manuscript.format = format
                if url != "": manuscript.url = url
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
                if bNeedSave:
                    manuscript.save()
            return manuscript
        except:
            sMsg = oErr.get_error_message()
            oErr.DoError("Manuscript/find_or_create")
            return None

    def read_ecodex(username, data_file, filename, arErr, xmldoc=None, sName = None):
        """Import an XML from e-codices with manuscript data and add it to the DB
        
        This approach makes use of MINIDOM (which is part of the standard xml.dom)
        """

        # Number to order all the items we read
        order = 0

        def read_msitem(msItem, oParent, level=0):
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
                            bResult, oChild, msg = read_msitem(item, oMsItem, level)
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

        def add_msitem(msItem):
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

                    # However: double check the fields
                    bNeedSaving = False

                    if 'title' in msItem and sermon.title != msItem['title']: sermon.title = msItem['title'] ; bNeedSaving = True
                    if 'location' in msItem and sermon.locus != msItem['location']: sermon.locus = msItem['location'] ; bNeedSaving = True
                    if 'incipit' in msItem and sermon.incipit != msItem['incipit']: sermon.incipit = msItem['incipit'] ; bNeedSaving = True
                    if 'explicit' in msItem and sermon.explicit != msItem['explicit']: sermon.explicit = msItem['explicit'] ; bNeedSaving = True
                    if 'edition' in msItem and sermon.edition != msItem['edition']: sermon.edition = msItem['edition'] ; bNeedSaving = True
                    if 'quote' in msItem and sermon.quote != msItem['quote']: sermon.quote = msItem['quote'] ; bNeedSaving = True
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
                                bResult, oMsItem, msg = read_msitem(msItem, {})
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

            # Now [oInfo] has a full description of the contents to be added to the database
            # (1) Get the library from the info object
            library = Library.find_or_create(oInfo['city'], oInfo['library'], "Switzerland")

            # (2) Get or create place of origin
            origin = Origin.find_or_create(oInfo['origPlace'])

            # (3) Get or create the Manuscript
            yearstart = oInfo['origDateFrom'] if oInfo['origDateFrom'] != "" else 0
            yearfinish = oInfo['origDateTo'] if oInfo['origDateTo'] != "" else 2020
            support = "" if 'support' not in oInfo else oInfo['support']
            extent = "" if 'extent' not in oInfo else oInfo['extent']
            format = "" if 'format' not in oInfo else oInfo['format']
            idno = "" if 'idno' not in oInfo else oInfo['idno']
            url = oInfo['url']
            manuscript = Manuscript.find_or_create(oInfo['name'], yearstart, yearfinish, library, origin, idno, filename, url, support, extent, format)

            # (3) Create all the manuscript content items
            iSermCount = 0
            for msItem in oInfo['list']:

                # Check and add this [msItem] as a 'SermonDescr' with a 'SermonMan' link to the manuscript
                bResult, sermon, msg = add_msitem(msItem)


            # Make sure the requester knows how many have been added
            oBack['count'] = 1              # Only one manuscript is added here
            oBack['sermons'] = iSermCount   # The number of sermans added
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

        qs = Author.objects.filter(Q(name__iexact=sName))
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
    author = models.ForeignKey("Author", null=True, blank=True, related_name="author_nicknames")

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

    # [1]
    signature = models.CharField("Signature", null=True, blank=True, max_length=LONG_STRING)


class SermonGoldSame(models.Model):
    """Link to identical sermons that have a different signature"""

    # [1] Starting from sermon [src]
    src = models.ForeignKey(SermonGold, related_name="sermongold_src")
    # [1] It equals sermon [dst]
    dst = models.ForeignKey(SermonGold, related_name="sermongold_dst")

    def __str__(self):
        combi = "{}: {}".format(self.src.signature, self.dst.signature)
        return combi


class SermonDescr(models.Model):
    """A sermon is part of a manuscript"""

    # [0-1] Not every sermon might have a title ...
    title = models.CharField("Title", null=True, blank=True, max_length=LONG_STRING)

    # ======= OPTIONAL FIELDS describing the sermon ============
    # [0-1] We would very much like to know the *REAL* author
    author = models.ForeignKey(Author, null=True, blank=True, related_name="author_sermons")
    # [0-1] But most often we only start out with having just a nickname of the author
    nickname = models.ForeignKey(Nickname, null=True, blank=True, related_name="nickname_sermons")
    # [0-1] Optional location of this sermon on the manuscript
    locus = models.CharField("Locus", null=True, blank=True, max_length=LONG_STRING)
    # [0-1] We would like to know the INCIPIT (first line in Latin)
    incipit = models.CharField("Incipit", null=True, blank=True, max_length=LONG_STRING)
    # [0-1] We would like to know the EXPLICIT (last line in Latin)
    explicit = models.CharField("Explicit", null=True, blank=True, max_length=LONG_STRING)
    # [0-1] If there is a QUOTE, we would like to know the QUOTE (in Latin)
    quote = models.CharField("Quote", null=True, blank=True, max_length=LONG_STRING)
    # [0-1] We would like to know the Clavis number (if available)
    clavis = models.CharField("Clavis number", null=True, blank=True, max_length=LONG_STRING)
    # [0-1] We would like to know the Gryson number (if available)
    gryson = models.CharField("Gryson number", null=True, blank=True, max_length=LONG_STRING)
    # [0-1] The FEAST??
    feast = models.CharField("Feast", null=True, blank=True, max_length=LONG_STRING)
    # [0-1] Edition
    edition = models.CharField("Edition", null=True, blank=True, max_length=LONG_STRING)
    # [0-1] Any notes for this sermon
    note = models.TextField("Note", null=True, blank=True)
    # [0-1] Additional information 
    additional = models.TextField("Additional", null=True, blank=True)
    # [0-1] Any number of bible references (as stringified JSON list)
    bibleref = models.TextField("Bible reference(s)", null=True, blank=True)
    # [0-1] One keyword or more??
    keyword = models.CharField("Keyword", null=True, blank=True, max_length=LONG_STRING)

    # ============= FIELDS FOR THE HIERARCHICAL STRUCTURE ====================
    # [0-1] Parent sermon, if applicable
    parent = models.ForeignKey('self', null=True, blank=True, related_name="sermon_parent")
    # [0-1] Parent sermon, if applicable
    firstchild = models.ForeignKey('self', null=True, blank=True, related_name="sermon_child")
    # [0-1] Parent sermon, if applicable
    next = models.ForeignKey('self', null=True, blank=True, related_name="sermon_next")
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

    def target(self):
        # Get the URL to edit/view this sermon
        sUrl = "" if self.id == None else reverse("sermon_view", kwargs={'pk': self.id})
        return sUrl


class SermonDescrGold(models.Model):
    """Link from sermon description to gold standard"""

    # [1] The sermondescr
    sermon = models.ForeignKey(SermonDescr, related_name="sermondescr_gold")
    # [1] The gold sermon
    gold = models.ForeignKey(SermonGold, related_name="sermondescr_gold")

    def __str__(self):
        # Temporary fix: sermon.id
        # Should be changed to something more significant in the future
        # E.G: manuscript+locus?? (assuming each sermon has a locus)
        combi = "{}: {}".format(self.sermon.id, self.gold.signature)
        return combi


class SermonMan(models.Model):
    """A particular sermon is located in a particular manuscript"""

    # [1] The sermon we are talking about
    sermon = models.ForeignKey(SermonDescr, related_name="manuscripts_sermons")
    # [1] The manuscript this sermon is written on 
    manuscript = models.ForeignKey(Manuscript, related_name = "manuscripts_sermons")

    def __str__(self):
        combi = "{}: {}".format(self.manuscript.name, self.sermon.title)


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
