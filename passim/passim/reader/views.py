"""
Definition of views for the READER app.
"""

from django.apps import apps
from django.contrib import admin
from django.contrib.auth import login, authenticate
from django.contrib.auth.models import Group, User
from django.urls import reverse
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.db import transaction
from django.db.models import Q, Prefetch, Count, F
from django.db.models.functions import Lower
from django.db.models.query import QuerySet 
from django.forms import formset_factory, modelformset_factory, inlineformset_factory, ValidationError
from django.forms.models import model_to_dict
from django.http import HttpRequest, HttpResponse, HttpResponseRedirect, JsonResponse, FileResponse
from django.shortcuts import get_object_or_404, render, redirect
from django.template.loader import render_to_string
from django.template import Context
from django.views.generic.detail import DetailView
from django.views.generic.base import RedirectView
from django.views.generic import ListView, View
from django.views.decorators.csrf import csrf_exempt

# General imports
from datetime import datetime
import operator 
from operator import itemgetter
from functools import reduce
from time import sleep 
import fnmatch
import sys, os
import base64
import json
import csv, re
import requests
import demjson
import openpyxl
import sqlite3
from openpyxl.utils.cell import get_column_letter
from io import StringIO
from itertools import chain

# Imports needed for working with XML and other file formats
from xml.dom import minidom
# See: http://effbot.org/zone/celementtree.htm
import xml.etree.ElementTree as ElementTree
 
# ======= imports from my own application ======
from passim.settings import APP_PREFIX, MEDIA_DIR, WRITABLE_DIR
from passim.utils import ErrHandle
from passim.reader.forms import UploadFileForm, UploadFilesForm
from passim.seeker.models import Manuscript, SermonDescr, Status, SourceInfo, ManuscriptExt, Provenance, ProvenanceMan, \
    EqualGold, \
    Library, Location, SermonSignature, Author, Feast, Daterange, Comment, Profile, MsItem, SermonHead, Origin, \
    Report, Keyword, ManuscriptKeyword, ManuscriptProject, STYPE_IMPORTED, get_current_datetime

# ======= from RU-Basic ========================
from passim.basic.views import BasicList, BasicDetails, BasicPart

# =================== This is imported by seeker/views.py ===============
# OLD METHODS
#reader_uploads = [
#    {"title": "ecodex",  "label": "e-codices",     "url": "import_ecodex",  "type": "multiple", "msg": "Upload e-codices XML files"},
#    {"title": "ead",     "label": "EAD",           "url": "import_ead",     "type": "multiple","msg": "Upload 'archives et manuscripts' XML files"}
#    ]
# NEW METHODS
reader_uploads = [
    {"title": "ecodex", "label": "e-codices", "url": "import_ecodex", "type": "multiple",
     "msg": "Upload e-codices XML files (n), using default project assignment defined in MyPassim"},
    {"title": "ead",    "label": "EAD",       "url": "import_ead",    "type": "multiple",
     "msg": "Upload 'Archives et Manuscripts' XML files, using default project assignment defined in MyPassim"}
    ]
# Global debugging 
bDebug = False


# =============== Helper functions ======================================

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

def download_file(url):
    """Download a file from the indicated URL"""

    bResult = True
    sResult = ""
    errHandle = ErrHandle()
    # Get the filename from the url
    name = url.split("/")[-1]
    # Set the output directory
    outdir = os.path.abspath(os.path.join(MEDIA_DIR, "e-codices"))
    if not os.path.exists(outdir):
        os.mkdir(outdir)
    # Create a filename where we can store it
    filename = os.path.abspath(os.path.join(outdir, name))
    try:
        r = requests.get(url)
    except:
        sMsg = errHandle.get_error_message()
        errHandle.DoError("Request problem")
        return False, sMsg
    if r.status_code == 200:
        # Read the response
        sText = r.text
        # Write away
        with open(filename, "w", encoding="utf-8") as f:
            f.write(sText)
        sResult = filename
    else:
        bResult = False
        sResult = "download_file received status {} for {}".format(r.status_code, url)
    # Return the result
    return bResult, sResult

def user_is_ingroup(request, sGroup):
    # Is this user part of the indicated group?
    username = request.user.username
    user = User.objects.filter(username=username).first()
    # glist = user.groups.values_list('name', flat=True)

    # Only look at group if the user is known
    if user == None:
        glist = []
    else:
        glist = [x.name for x in user.groups.all()]

        # Only needed for debugging
        if bDebug:
            ErrHandle().Status("User [{}] is in groups: {}".format(user, glist))
    # Evaluate the list
    bIsInGroup = (sGroup in glist)
    return bIsInGroup

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
                if 'additional' in msItem: sermon.additional = msItem['additional']
                if 'note' in msItem: sermon.note = msItem['note']
                if 'bibleref' in msItem: sermon.bibleref = msItem['bibleref']
                if 'order' in msItem: sermon.order = msItem['order']
                if 'author' in msItem:
                    author = Author.find(msItem['author'])
                    if author == None:
                        # Add to the NOTE
                        space = "" if sermon.note == "" else " "
                        sermon.note = "{}{}AUTHOR: {}".format(sermon.note, space, msItem['author']) ; bNeedSaving = True
                    else:
                        sermon.author = author
                    bNeedSaving = True
                # Added information into .note:
                if 'edition' in msItem and msItem['edition'] != "Elektronische Version nach TEI P5.1": 
                    space = "" if sermon.note == "" else " "
                    sermon.note = "{}{}EDITION: {}".format(sermon.note, space, msItem['edition']) ; bNeedSaving = True
                    
                # Set the default status type
                sermon.stype = STYPE_IMPORTED    # Imported

                # Set my parent manuscript
                # TODO: this needs correction of [sermon] actually is a [SermonDescr]: sermon.msitem.manu
                #       and where is sermon.msitem established??
                sermon.manu = manuscript

                # Now save it
                sermon.save()

                # The following items are [0-n]
                # Connected to 'SermonDescr' with one-to-many
                if 'gryson' in msItem : 
                    code = msItem['gryson']
                    sig = SermonSignature.objects.create(sermon=sermon, editype="gr", code=code)
                if 'clavis' in msItem : 
                    code = msItem['clavis']
                    sig = SermonSignature.objects.create(sermon=sermon, editype="cl", code=code)
                if 'feast' in msItem: 
                    # Get object that is being referred to
                    sermon.feast = Feast.get_one(msItem['feast'])
                if sermon.bibleref != None and sermon.biblref != "": 
                    # Calculate and set BibRange and BibVerse objects
                    sermon.do_ranges()

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

                # Main attributes of 'SermonDescr'
                if 'title' in msItem and sermon.title != msItem['title']: sermon.title = msItem['title'] ; bNeedSaving = True
                if 'location' in msItem and sermon.locus != msItem['location']: sermon.locus = msItem['location'] ; bNeedSaving = True
                if 'incipit' in msItem and sermon.incipit != msItem['incipit']: sermon.incipit = msItem['incipit'] ; bNeedSaving = True
                if 'explicit' in msItem and sermon.explicit != msItem['explicit']: sermon.explicit = msItem['explicit'] ; bNeedSaving = True
                if 'quote' in msItem and sermon.quote != msItem['quote']: sermon.quote = msItem['quote'] ; bNeedSaving = True
                if 'feast' in msItem and sermon.feast != msItem['feast']: sermon.feast = Feast.get_one(msItem['feast']) ; bNeedSaving = True
                # OLD (doesn't exist in e-codices)if 'keyword' in msItem and sermon.keyword != msItem['keyword']: sermon.keyword = msItem['keyword'] ; bNeedSaving = True
                if 'bibleref' in msItem and sermon.bibleref != msItem['bibleref']: sermon.bibleref = msItem['bibleref'] ; bNeedSaving = True
                if 'additional' in msItem and sermon.additional != msItem['additional']: sermon.additional = msItem['additional'] ; bNeedSaving = True
                if 'note' in msItem and sermon.note != msItem['note']: sermon.note = msItem['note'] ; bNeedSaving = True
                if 'order' in msItem and sermon.order != msItem['order']: sermon.order = msItem['order'] ; bNeedSaving = True

                if sermon.bibleref != None and sermon.biblref != "": 
                    # Calculate and set BibRange and BibVerse objects
                    sermon.do_ranges()

                if 'author' in msItem and (sermon.author == None or sermon.author.name != msItem['author'] ):
                    author = Author.find(msItem['author'])
                    if author == None:
                        # Add to the NOTE
                        space = "" if sermon.note == "" else " "
                        sermon.note = "{}{}AUTHOR: {}".format(sermon.note, space, msItem['author']) ; bNeedSaving = True
                    else:
                        sermon.author = author
                    bNeedSaving = True

                # Added information into .note:
                if 'edition' in msItem and msItem['edition'] != "Elektronische Version nach TEI P5.1": 
                    space = "" if sermon.note == "" else " "
                    sermon.note = "{}{}EDITION: {}".format(sermon.note, space, msItem['edition']) ; bNeedSaving = True

                # Connected to 'SermonDescr' with one-to-many
                if 'gryson' in msItem : 
                    code = msItem['gryson']
                    sig = SermonSignature.objects.filter(sermon=sermon, editype="gr", code=code).first()
                    if sig == None:
                        sig = SermonSignature.objects.create(sermon=sermon, editype="gr", code=code)
                if 'clavis' in msItem : 
                    code = msItem['clavis']
                    sig = SermonSignature.objects.filter(sermon=sermon, editype="cl", code=code).first()
                    if sig == None:
                        sig = SermonSignature.objects.create(sermon=sermon, editype="cl", code=code)

                # Connected to 'SermonDescr' with many-to-many

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
        # (1a) Get the city
        # OLD: city = City.objects.filter(name__iexact=oInfo['city']).first()
        city = Location.objects.filter(name__iexact=oInfo['city'], loctype__name="city").first()
        # (1b) Get the country from the city
        country = None 
        # OLD: if city != None and city.country != None: country = city.country.name
        if city != None:
            # Get all the locations inside which I am contained
            lst_above = city.above()
            for loc in lst_above:
                if loc.loctype.name == "country":
                    # Get the name of the country
                    country = loc.name
                    break

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
            mext = ManuscriptExt.objects.filter(url=url, manuscript=manuscript).first()
            if mext == None:
                mext = ManuscriptExt.objects.create(url=url, manuscript=manuscript)


        # Add all the provenances we know of -- only if they don't exist yet!!!
        if provenance_origin != None:
            pm = ProvenanceMan.objects.filter(provenance=provenance_origin, manuscript=manuscript).first()
            if pm == None:
                pm = ProvenanceMan.objects.create(provenance=provenance_origin, manuscript=manuscript)
        for oProv in lProvenances:
            provenance = Provenance.find_or_create(oProv['name'], oProv['note'])
            pm = ProvenanceMan.objects.filter(provenance=provenance, manuscript=manuscript).first()
            if pm == None:
                pm = ProvenanceMan.objects.create(provenance=provenance, manuscript=manuscript)

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

def read_ead(username, data_file, filename, arErr, xmldoc=None, sName = None, source=None):
    """Import an XML from EAD with manuscript data and add it to the DB
         
    This approach makes use of MINIDOM (which is part of the standard xml.dom)    
    """

    mapIdentifier = {'settlement': 'city', 'repository': 'library', 'idno': 'idno'}
    oInfo = {'city': '', 'library': '', 'manuscript': '', 'name': '', 'origPlace': '', 'origDateFrom': '', 'origDateTo': '', 'url':'', 'list': []}
    oBack = {'status': 'ok', 'count': 0, 'msg': "", 'user': username, 'lst_obj': []}
    errHandle = ErrHandle()
    iSermCount = 0

    # Number to order all the items we read        
    order = 0   
    # Overal keeping track of manuscripts
    lst_manus = []
    # Overall keeping track of ms items  
    lst_msitem = []
    
    try:
        # Make sure we have the data
        if xmldoc == None:
            # Read and parse the data into a DOM element
            xmldoc = ElementTree.parse(data_file)  
            
        # Find out who I am: Get profile      
        profile = Profile.get_user_profile(username) 
             
            
        # First the manuscript data will be extracted from the XML, then the general parts of the XML.
        # The last part is extracting the data on the sermons.
     
        # (1) Find all the MANUSCRIPTS in this XML document
        
        # The list manu_list stores ALL manuscripts (both the ones on the highest level and 
        # the ones on the lower level, that are part of combined manuscripts)                       
        manu_list = xmldoc.findall("//c[did]")

        # Here the information on the XML is extracted
        manu_info = xmldoc.find("//eadheader")
        manuidno_end = "0"
        
        # Import wishlist_final_total.csv that holds the shelfmarks of the selected A+M manuscripts 
        filename = os.path.abspath(os.path.join(MEDIA_DIR, 'wishlist_final_total.csv'))
        with open(filename) as f:            

            reader = csv.reader(f, dialect='excel', delimiter=';')
            
            # Transpose the result     
            shelfmark, digitization = zip(*reader)       
            
            # Make lists of the tuples
            shelfmark_list = list(shelfmark)
            digitized_list = list(digitization)  
            
            # Delete the first rows of both lists (with fieldname "Shelfmark" / "Digitization")
            shelfmark_list.pop(0)
            digitized_list.pop(0)
            
            # Make set of the list, sm_shelfmark is to be used to compare 
            # each shelfmark of each manuscript in all available A+M XML's
            shelfmark_set = set(shelfmark_list)
            errHandle.Status(shelfmark_set)
            
            # Make a dictionary that can be used to find out if a shelfmark has
            # been digitized or not
            shelf_digit = dict(zip(shelfmark_list, digitized_list))
                     
        # Iterate through the list of ALL manuscripts (manu_list)      
        for manu in manu_list:          

            # Get the SHELFMARK of the manuscript

            # Get the shelfmark of this manuscript (assuming this level represents a complete manuscript)
            unitid = manu.find("./did/unitid[@type='cote']")
            if unitid is None:
                continue
                        
            # This is the shelfmark
            manuidno = unitid.text

            # Get the NUMBER of the SHELFMARK of the manuscript

            # Store only the NUMBER of the shelfmark to aid in the adding of the 
            # higher level title (if this is the case) 

            if "-" not in manuidno:
                manuidno_list_2 = manuidno.split()         
                manuidno_number = manuidno_list_2[1]              
            
            # First store data of COMBINED manuscripts

            # Get TITLE of a COMBINED manuscript
        
            # Here the title of a combined manuscript (consisting of multiple manuscripts) is extracted. 
            # This title will later on be placed in front of the titles of manuscripts that are 
            # part of this combined manuscript      
            
            # Create a new string to add all parts of the title, later on in the process
            title_high_temp = ""
            
            # Seek out the combined manuscripts (but steer away from manuscripts like "Latin 646B (1-2)"
            # And from Latin "774A-C" (works) 
            if "-" in manuidno and not "(" in manuidno and not "A" in manuidno and not "B" in manuidno and not "C" in manuidno:

                # Store start and end shelfmarks to help in the check when the title of the 
                # combined manuscript must be added to the titles lower level manuscripts. 
                manudino_1 = manuidno.replace('-', ' ')
                manudino_list = manudino_1.split()         
                manudidno_start = manudino_list[-2] # Probably not necessary
                manuidno_end = manudino_list[-1]

                # Find the <did> element in which <unittitle> is placed
                unit_did = manu.find("./did")

                # List all <unittitle> elements and iterate over them
                for unittitle_high in unit_did.findall("./unittitle"): 
                    # First: grab ALL text from within the <unittitle> tage
                    unittitle_high_1 = ''.join(unittitle_high.itertext())                    
                    # Second: clean the string
                    unittitle_high_2 = re.sub("[\n\s]+"," ", unittitle_high_1)                      
                    # Third: strip string of spaces 
                    unittitle_high_3 = unittitle_high_2.strip()                      
                    # Add all available cleaned up text from the list of the 
                    # unittitles parts to a string and add an underscore 
                    # for usage later on
                    title_high_temp += unittitle_high_3 + "_"

                # When all <unittitle> elements in the list are handled and placed in one string
                # split them up using the underscores added above and use a comma to separate
                # the multiple title parts
                title_high_temp_comma = ', '.join(title_high_temp.split("_"))
                    
                # The last part is getting rid of the last comma at the end of the string
                # The title is used in case there are underlying manuscripts and then
                # the title is placed before the <unittitle> in those manuscripts (for instance "I")
                unittitle_high_combined = title_high_temp_comma.rstrip(", ")
                
                # Get SUPPORT and BINDING of the manuscript (HIGH)

                # Get the support and binding of the manuscript - if it is exists 
                # Support and binding are combined (<physfacet type="support"> / <physfacet type="reliure">)                
                unitsupport_high = manu.find("./did/physdesc/physfacet[@type='support']")
                if unitsupport_high != None and unitsupport_high != "":
                    manusupport_high = unitsupport_high.text                
                else:
                    manusupport_high = ""
                    
                # Get the part in between the two parts of the reliure - if it exists  
                # <emph render="super">e</emph>
                unitreliure_emph_high = manu.find("./did/physdesc/physfacet/emph")
                if unitreliure_emph_high != None and unitreliure_emph_high != "":
                    manureliure_emph_high = unitreliure_emph_high.text
                else: 
                    manureliure_emph_high = ""
                
                # Get the binding - if it exists
                # <physfacet type="reliure">) = binding
                unitreliure_high = manu.find("./did/physdesc/physfacet[@type='reliure']")
                if unitreliure_high != None and unitreliure_high != "" and manureliure_emph_high == "":
                    manureliure_high = unitreliure_high.text
                elif unitreliure_high != None and unitreliure_high != "" and manureliure_emph_high != "":
                    unitreliure_join_high = ''.join(unitreliure_high.itertext()) 
                    manureliure_high = re.sub("[\n\s]+"," ", unitreliure_join_high) 
                else:
                    manureliure_high = ""
                
                # This is the complete support, combinining support and binding       
                unitsupport_high_combined = manusupport_high + " " + manureliure_high
                                
                # Get FORMAT of the manuscript (HIGH)

                # Look for the format of the manuscript - if it is exists 
                # (<dimensions>) 
                unitdimensions_high = manu.find("./did/physdesc/dimensions")
                if unitdimensions_high != None and unitdimensions_high != "":
                    unitdimensions_high_combined = unitdimensions_high.text
                
                # If there is no element here then the one from the former 
                # processed CM (combined manuscript) should be deleted
                else:
                    unitdimensions_high_combined = ""
                
                # Get EXTENT of the manuscript (HIGH)

                # Look for the extent of the manuscrpt - if it is exists 
                unitextent_high = manu.find("./did/physdesc/extent")
                if unitextent_high != None and unitextent_high != "":
                    unitextent_high_combined = unitextent_high.text

                # If there is no element here then the one from the former 
                # processed CM (combined manuscript) should be deleted
                else:
                    unitextent_high_combined = ""
                
                # Get the ORIGIN of the manuscript (HIGH)                          
                
                # Look for the origin of the manuscript - if it exists                    
                unitorigin_high = manu.find("./did/physdesc/geogname")
                if unitorigin_high != None and unitorigin_high != "":
                    unitorigin_high_combined = unitorigin_high.text

                # If there is no element here then the one from the former 
                # processed CM (combined manuscript) should be deleted
                else:
                    unitorigin_high_combined = ""                    
                
                # Get the DATE of the manuscript (HIGH) 
                
                # Look for the date of the manuscript - if it exists 
                unitdate_high = manu.find("./did/unitdate")
                    
                # In case of no unitdate on manuscript level, add "9999" as year
                if unitdate_high is None:
                    unit_yearstart_high = "9999"
                    unit_yearfinish_high = "9999"
                    pass
                
                # In case of 'normal' in attributes:
                elif unitdate_high != None and unitdate_high != "" and 'normal' in unitdate_high.attrib:
                    unitdate_normal_high = unitdate_high.attrib.get('normal')
                    ardate_high = unitdate_normal_high.split("/")
                    if len(ardate_high) == 1:
                        unit_yearstart_high = int(unitdate_normal_high)
                        unit_yearfinish_high = int(unitdate_normal_high)
                    else:
                        unit_yearstart_high = int(ardate_high[0])
                        unit_yearfinish_high = int(ardate_high[1])
                
                # In case 'normal' not in attributes:
                elif unitdate_high != None and unitdate_high != "" and 'normal' not in unitdate_high.attrib:
                    unitdate_complete_high = unitdate.text
                    if "-" in unitdate_complete_high:
                        # use regex to split up string, will result in list with 4 items. 
                        ardate_high = re.split('[\-\(\)]', unitdate_complete_high)
                    
                        # use positions 3 and to to grab the first and last year
                        unit_yearstart_high = int(ardate_high[-3]) 
                        unit_yearfinish_high = int(ardate_high[-2])

                    # use the century indication in Roman numerals to create "virtual" 
                    # start and finish years                     
                    elif "-" not in unitdate_complete_high:
                        ardate_high = unitdate_complete_high.split('e ')
                        if len(ardate_high) < 3:  
                            unit_century_high = ardate_high[0]
                            if unit_century_high == "IX":
                                unit_yearstart_high = "800"
                                unit_yearfinish_high = "900"
                            elif unit_century_high == "X":
                                 unit_yearstart_high = "900"
                                 unit_yearfinish_high = "1000"
                            elif unit_century_high == "XI":
                                 unit_yearstart_high = "1000"
                                 unit_yearfinish_high = "1100"
                            elif unit_century_high == "XII":
                                 unit_yearstart_high = "1100"
                                 unit_yearfinish_high = "1200"
                            elif unit_century_high == "XIII":
                                 unit_yearstart_high = "1200"
                                 unit_yearfinish_high = "1300"
                                                                              
                # Get the ANCIENNE COTES of the manuscript (HIGH)               
                
                # The old shelfmarks of the manuscript need to be stored in the notes section
                # of the manuscript

                # Create a new string for the storage of ancienne cotes
                old_sm_temp_high = ""
                
                # Find all old shelfmarks and store them in a string
                for unit_anccote_high in manu.findall("./did/unitid[@type='ancienne cote']"): 
                    old_sm_high = unit_anccote_high.text
                    old_sm_temp_high += old_sm_high + "_"
                                       
                # When all ancienne cotes in the list are handled and placed in one string,
                # the underscores are replaced by a comma
                old_sm_temp_comma_high = ', '.join(old_sm_temp_high.split("_"))
                   
                # The last part is getting rid of the last comma at the end of the string
                unit_anccote_final_high = old_sm_temp_comma_high.rstrip(", ")      

                # Get the PROVENANCE of the manuscript (HIGH)

                # For now only <custodhist>, if needed: add also <origination>(HIGH)
                                
                # Provenance in CUSTODHIST (HIGH)

                # Examples Latin 813-814

                # Look for the <custodhist> elements of the combined manuscript - if they exists
                # and place them all in one string 
                custodhist_high = ""
                for unit_custodhist_high in manu.findall("./custodhist/p"):
                    if unit_custodhist_high != None and unit_custodhist_high != "":
                        
                        # First get all the text from <custodhist>
                        unit_custh_1_high = ''.join(unit_custodhist_high.itertext())
                        
                        # Second clean the string
                        unit_custh_2_high = re.sub("[\n\s]+"," ", unit_custh_1_high)                        

                        # Third strip string of spaces 
                        unit_custh_3_high = unit_custh_2_high.strip()                        
                        
                        # Add to the custodhist_high string
                        custodhist_high += unit_custh_3_high
                    else:
                        custodhist_high = ""
                                
                # Location(s) (role=4010) in custodhist
                # Store in list, later to be used in the lower manuscripts

                prov_custh_high_list=[]
                for prov_custh_high in manu.findall("./custodhist/p/corpname[@role='4010']"):
                        provtemp_custh_high = prov_custh_high.text 
                        prov_custh_high_list.append(provtemp_custh_high)
                
                # Get the URL of the manuscript (HIGH) 
                #                             
                # Look for URL of the manuscript - if it exists      
                # The URL needs to be added to the manuscript
                uniturl_high = manu.find("./dao")
                if uniturl_high != None and uniturl_high != "":
                    url_high = uniturl_high.attrib.get('href')
                else:
                    url_high = ""
                         
            # HERE we return the manuscript iteration process
                                                          
            # Check if the shelfmark that is listed in "shelfmark_set"
            if manuidno in shelfmark_set:
            # Create a new Manuscript if this is the case
                manu_obj = Manuscript.objects.filter(idno=manuidno).first()
                if manu_obj == None:
                    # Now we can create a completely fresh manuscript with the correct manuscript IDNO and source
                    manu_obj = Manuscript.objects.create(idno=manuidno, source=source) 
                else:
                    # Remove *ALL* existing Manuscript-Comment links and delete Comments (for this manuscript)                     
                    # Retrieve the id's of the Comments linked to the manuscript
                    deletables = [x['id'] for x in manu_obj.comments.values('id')]                    
                    # Remove the Manuscript-Comment link
                    manu_obj.comments.clear()                     
                    # Delete the linked Comments                    
                    Comment.objects.filter(id__in=deletables).delete() 
               
                    # Remove *ALL* existing Manuscript-External records (for this manuscript)
                    ManuscriptExt.objects.filter(manuscript=manu_obj).delete()

                    # Remove *ALL* existing Manuscript-DateRange records (for this manuscript)
                    Daterange.objects.filter(manuscript=manu_obj).delete()
                    
                    # Remove *ALL* existing Manuscript-Sermon records (for this manuscript)
                    MsItem.objects.filter(manu=manu_obj).delete()  
                
                # Print the shelfmark to keep track of process during import
                print(manuidno)  

                # Add the manuscript to the list of read objects
                oBack['lst_obj'].append(manu_obj)
                
                # Check if the shelfmark is registered as "not digitized"
                if shelf_digit[manuidno] == "not_digitized":
                    name = "Not digitized"
                    description = "This manuscript has been marked as 'not digitized."                                        
                    # Try to find if the keyword already exists:
                    keywordfound = Keyword.objects.filter(name__iexact=name).first()
                    if keywordfound == None:
                        # If the keyword does not already exist, it needs to be added to the database
                        keyword = Keyword.objects.create(name = name, description = description)
                        # And a link should be made between this new keyword and the manuscript
                        ManuscriptKeyword.objects.create(keyword = keyword, manuscript = manu_obj)
                    else:
                        manukeylink = ManuscriptKeyword.objects.filter(keyword = keywordfound, manuscript = manu_obj).first()
                        if manukeylink == None:
                            # If the keyword already exists, but not the link, than only a link should be 
                            # made between manuscript and keyword
                            ManuscriptKeyword.objects.create(keyword = keywordfound, manuscript = manu_obj) 
                
                # Add Keyword to each manuscript in order to filter out the A+M manuscripts after import
                name = "Archives et Manuscrit import"
                description = "This manuscript belongs to the Archives et Manuscrit collection."  
                
                # Try to find if the keyword already exists:
                keywordfound = Keyword.objects.filter(name__iexact=name).first()
                if keywordfound == None:
                    # If the keyword does not already exist, it needs to be added to the database
                    keyword = Keyword.objects.create(name = name, description = description)
                    # And a link should be made between this new keyword and the manuscript
                    ManuscriptKeyword.objects.create(keyword = keyword, manuscript = manu_obj)
                else:
                    manukeylink = ManuscriptKeyword.objects.filter(keyword = keywordfound, manuscript = manu_obj).first()
                    if manukeylink == None:
                        # If the keyword already exists, but not the link, than only a link should be 
                        # made between the manuscript and keyword
                        ManuscriptKeyword.objects.create(keyword = keywordfound, manuscript = manu_obj)
                
                # Set the default status type
                manu_obj.stype = STYPE_IMPORTED
                errHandle.Status(manu_obj.stype)

                # Add shelfmark to list of processed manuscripts                
                lst_manus.append(manuidno)
                
                # Get the TITLE(S) of the manuscript

                # Get the name of the manuscript - if it exists
                
                # Create a new string to add all parts of the title to later on, 
                # since there can be multiple <unittitle> elements
                title_temp = ""
                             
                # Find the <did> element in which the <unittitle> element is nested
                unit_did = manu.find("./did")                
      
                if unit_did is None:
                    continue
                
                else:
                # Make a list of all <unittitle> tags from within the <did> element and iterate over the list
                    for element_unittitle in unit_did.findall("./unittitle"): 
                        # First: grab ALL text from within the <unittitle> tage
                        unittitle_1 = ''.join(element_unittitle.itertext())                    
                        # Second: clean the string
                        unittitle_2 = re.sub("[\n\s]+"," ", unittitle_1)                      
                        # Third: strip string of spaces 
                        unittitle_3 = unittitle_2.strip()                      
                    
                        # Add all available cleaned up text from the list of the unittitles parts to a string
                        # and add an underscore for usage later on
                        title_temp += unittitle_3 + "_"

                    # When all <unittitle> tags in the list are handled and placed in one string
                    # the underscores are replaced by a comma
                    title_temp_comma = ', '.join(title_temp.split("_"))
                    
                    # The last part is getting rid of the last comma at the end of the string
                    unittitle_stripped = title_temp_comma.rstrip(", ")

                    # Check if there is a HIGHER level title available, in case of a COMBINED manuscript.

                    # The number part of the shelfmark of each individual manuscript is used to check if
                    # it belongs to a combined manuscript. If not: only the title(s) of the manuscript itself
                    # will be stored. 

                    # manuidno_end will be "empty" if there is no combined manuscript that is associated 
                    # with a specific manuscript

                    # Check if a manuscript is part of a combined manuscript                   
                    if manuidno_number <= manuidno_end:
                        # Combine the HIGH manuscript titles with the regular titles
                        unittitle_final = unittitle_high_combined + ", " + unittitle_stripped                    
                    
                    # If this is not the case, use only the regular title
                    else:
                        unittitle_final = unittitle_stripped
                        
                    # Now the title of the manuscript can be stored in the database
                    manu_obj.name = unittitle_final                        
                    
                    # Get the ANCIENNE COTES of the manuscript              
                  
                    # The old shelfmarks of the manuscript need to be stored in the notes section
                    # of the manuscript

                    # Create two new string for the storage of ancienne cotes
                    old_sm_temp = ""
                    unit_anccote_final_low = ""

                    # Find all old shelfmarks and store them in a string
                    for unit_anccote in manu.findall("./did/unitid[@type='ancienne cote']"): 
                        old_sm = unit_anccote.text
                        old_sm_temp += old_sm + "_"
                                       
                    # When all ancienne cotes in the list are handled and placed in one string
                    # the underscores are replaced by a comma
                    old_sm_temp_comma = ', '.join(old_sm_temp.split("_"))
                    
                    # The last part is getting rid of the last comma at the end of the string
                    unit_anccote_final_low = old_sm_temp_comma.rstrip(", ")       
                    
                    # Check if there is a combined manuscript, if so use the cotes from the CM 
                    # otherwise use the one from the manuscript itself
                    if manuidno_number <= manuidno_end:                     
                        if unit_anccote_final_low == "":
                            unit_anccote_final = unit_anccote_final_high
                        elif unit_anccote_final_low != "":
                            unit_anccote_final = unit_anccote_final_low
                    else:
                        unit_anccote_final = unit_anccote_final_low

                    # The combined old shelfmarks can now be stored in the database
                    # For many manuscripts there will be <scopecontent> elements that will also be stored in the 
                    # notes field, in these cases the contents in the notes field are overwritten by the combined
                    # ancient shelfmarks and scopececontent, later on.                      
                    manu_obj.notes = unit_anccote_final
                                                                                
                    # Get the SUPPORT and BINDING of the manuscript

                    # Get the support and binding of the manuscript - if it is exists 
                    # Support and binding are combined 
                    # (<physfacet type="support">  # <physfacet type="reliure">)                
                    unitsupport = manu.find("./did/physdesc/physfacet[@type='support']")
                    if unitsupport != None and unitsupport != "":
                        manusupport = unitsupport.text
                    else:
                        manusupport = ""

                    # Get the part in between the two parts of the reliure - if it exists  
                    # <emph render="super">e</emph>
                    unitreliure_emph = manu.find("./did/physdesc/physfacet/emph")
                    if unitreliure_emph != None and unitreliure_emph != "":
                        manureliure_emph = unitreliure_emph.text
                    else: 
                        manureliure_emph = ""
                
                    # Get the binding - if it exists
                    # <physfacet type="reliure">) = binding
                    unitreliure = manu.find("./did/physdesc/physfacet[@type='reliure']")
                    if unitreliure != None and unitreliure != "" and manureliure_emph == "":
                        manureliure = unitreliure.text
                    elif unitreliure != None and unitreliure != "" and manureliure_emph != "":
                        unitreliure_join = ''.join(unitreliure.itertext()) 
                        manureliure = re.sub("[\n\s]+"," ", unitreliure_join) 
                    else:
                        manureliure = ""
                        
                    # This is the complete support, combinining support and binding       
                    unitsupport_low = manusupport + " " + manureliure 
                    
                    # Check if there is a higher level extent available, in case of combined manuscripts.              
                    if manuidno_number <= manuidno_end:                     
                        unitsupport_final = unitsupport_high_combined + unitsupport_low                    
                    else:
                        unitsupport_final = unitsupport_low  
                    
                    # Now the extent of the manuscript can be stored in the database
                    manu_obj.support = unitsupport_final

                    # Get the FORMAT of the manuscript

                    # Look for the format of the manuscript - if it is exists 
                    # (<dimensions>) 
                    unitdimensions = manu.find("./did/physdesc/dimensions")
                    if unitdimensions != None and unitdimensions != "":
                        unitdimensions_low = unitdimensions.text
                    else:
                        unitdimensions_low = ""
                    
                    # Check if there is a higher level format available, in case of combined manuscripts.                    
                    if manuidno_number <= manuidno_end:                     
                        unitdimensions_final = unitdimensions_high_combined + unitdimensions_low                 
                    else:
                        unitdimensions_final = unitdimensions_low  
                    
                    # Now the dimenssions of the manuscript can be stored in the database
                    manu_obj.format = unitdimensions_final

                    # Get the EXTENT of the manuscript

                    # Look for the extent of the manuscript - if it is exists 
                    unitextent = manu.find("./did/physdesc/extent")
                    if unitextent != None and unitextent != "":
                        unitextent_low = unitextent.text
                    else:
                        unitextent_low = ""

                    # Check if there is a higher level extent available, in case of combined manuscripts.              
                    if manuidno_number <= manuidno_end:                     
                        unitextent_final = unitextent_high_combined + unitextent_low                    
                    else:
                        unitextent_final = unitextent_low  
                    
                    # Now the extent of the manuscript can be stored in the database
                    manu_obj.extent = unitextent_final
                                       
                    
                    # Get the ORIGIN of the manuscript (LOW) 

                    # Look for the origin of the manuscript - if it exists, 
                    # in two places: directly under <physdesc> and under <physdesc/physfacet>
                    unitorigin_1 = manu.find("./did/physdesc/geogname")
                    unitorigin_2 = manu.find("./did/physdesc/physfacet/geogname")

                    if unitorigin_1 != None and unitorigin_1 != "":
                       unitorigin_low = unitorigin_1.text
                    elif unitorigin_1 == None:
                        if unitorigin_2 != None and unitorigin_2 != "":
                            unitorigin_low = unitorigin_2.text
                        else:
                            unitorigin_low = ""
                    
                    # Check if there is a higher level origin available, in case of combined manuscripts.              
                    if manuidno_number <= manuidno_end:                     
                        unitorigin_final = unitorigin_high_combined + unitorigin_low
                        orname = unitorigin_final
                    else:
                        unitorigin_final = unitorigin_low  
                        orname = unitorigin_final
                    # Check if orname is not empty
                    if orname != None and orname != "":                        
                        # Try find the origin that is found
                        origfound = Origin.objects.filter(name__iexact=orname).first()
                        # If there is no origin name match, check if there is a name 
                        # that matches in the location table 
                        if origfound == None:                                                            
                            intro = ""
                            if manu_obj.notes != "": 
                                intro = "{}. ".format(manu_obj.notes) 
                                manu_obj.notes = "{}// Please set origin manually [{}] ".format(intro, orname)
                                manu_obj.save()                            
                        else: 
                            # The originfound can be tied to the manuscript 
                            manu_obj.origin = origfound
                                               
                            
                    # Get the PROVENANCE of the manuscript

                    # Look for the provenance of the manuscript in 
                    # <custodhist> and <origination> elements 

                    # Provenance in CUSTODHIST 

                    # Look for the <custodhist> elements of the manuscript - if they exist
                    # and place them in one string 
                    custodhist_low = ""
                    for unit_custodhist in manu.findall("./custodhist/p"):
                        if unit_custodhist != None and unit_custodhist != "":
                            # First get all the text from <custodhist>
                            unit_custh_1 = ''.join(unit_custodhist.itertext())
                        
                            # Second clean the string
                            unit_custh_2 = re.sub("[\n\s]+"," ", unit_custh_1)
                        
                            # Third strip string of spaces 
                            unit_custh_3 = unit_custh_2.strip()
                            
                            # Add to the custodhist_low string
                            custodhist_low += unit_custh_3 + " "
                            errHandle.Status(custodhist_low) 
                        else: 
                            custodhist_low = ""                                 
                    
                    prov_custh_low_list=[]
                    
                    # Location(s) (role=4010) in custodhist                                                                              
                    for prov_custh_low in manu.findall("./custodhist/p/corpname[@role='4010']"):
                        provtemp_custh_low = prov_custh_low.text                       
                        prov_custh_low_list.append(provtemp_custh_low)
                       
                    # Take care of the provenances and notes from <custodhist> element from the combined manuscripts 
                    # if available unit_custh_3_high, prov_custh_high_list HIGH       
                    # see if there are provenances from the CM if there is one
                    if manuidno_number <= manuidno_end:
                        
                        # Combine the HIGH prov custh list and the LOW prov custh list
                        prov_custh_list = prov_custh_high_list + prov_custh_low_list

                        # Combine the HIGH custodhist notes with the LOW custodhist notes
                        custodhist_notes = custodhist_high + " " + custodhist_low
                    
                    # If this is not the case, use only the regular prov_custh_low_list and 
                    # custodhist_low need to be used
                    else:                          
                        prov_custh_list = prov_custh_low_list                        
                        custodhist_notes = custodhist_low

                    # Now the complete text of all custodhist elements of the manuscript can be added to the notes field
                    # of the Manuscripts table
                    if custodhist_notes != "":
                        intro = ""
                        if manu_obj.notes != "": 
                            intro = "{}. ".format(manu_obj.notes) 
                            manu_obj.notes = "{}// Please view information from <custodhist> elements [{}]".format(intro, custodhist_notes)
                            manu_obj.save()
                   
                    # Then we need to iterate over the prov_custh_list in order to seek out if the provenances are already 
                    # in the Provenance table or in Location, otherwise the found provenances should be added manually.                  
                    if prov_custh_list:
                        for pcname in prov_custh_list:
                            # Try find the provenance that is found
                            provfound = Provenance.objects.filter(name__iexact=pcname).first()
                            
                            # If there is no provenance name match, check if there is a name 
                            # that matches in the location table
                            if provfound == None:                           
                                provfound = Provenance.objects.filter(location__name__iexact=pcname).first() 
                            
                                # If there is also no existing provenance found via the location id,  
                                # the provenance should be added to the manuscript manually. The message to do so, 
                                # and the complete contents of <custodhist> are added to manu_obj.notes    
                                if provfound == None:                                                            
                                    intro = ""
                                    if manu_obj.notes != "": 
                                        intro = "{}. ".format(manu_obj.notes) 
                                        manu_obj.notes = "{}// Please set provenance manually [{}]".format(intro, pcname)
                                        manu_obj.save()   
                            else: 
                                # In case there is a provfound, check for a link, if so, nothing should happen, 
                                # than there is already a link between a manuscript and a provenance
                                manuprovlink = ProvenanceMan.objects.filter(manuscript = manu_obj, provenance = provfound).first()
                                # If the provenance already exists than only a link should be 
                                # made between manuscript and provfound, and notes should be added.
                                if manuprovlink == None:
                                    ProvenanceMan.objects.create(manuscript=manu_obj, provenance=provfound, note=custodhist_notes) 

                    # Provenance in ORIGINATION 

                    # Look for the <origination> element of the manuscript - if it exists
                    unit_origination = manu.find("./did/origination")
                    if unit_origination != None and unit_origination != "":
                        # First get all the text from <origination>
                        unit_orig_1 = ''.join(unit_origination.itertext())
     
                        # Second clean the string
                        unit_orig_2 = re.sub("[\n\s]+"," ", unit_orig_1)
                  
                        # Third strip string of spaces 
                        notes_orig = unit_orig_2.strip()
                         
                    else:
                        notes_orig  = ""

                    # Person (role=4010) in origination 
                    # If there is a personname encoded in the <origination> element, the contents 
                    # of the whole element are picked up and placed in the notes field of the Manuscript field.
                    prov_pers = manu.find("./did/origination/persname[@role='4010']")
                    if prov_pers != None and prov_pers != "":
                        pers_name = prov_pers.text
                        intro = ""
                        if manu_obj.notes != "": 
                            intro = "{}. ".format(manu_obj.notes) 
                            manu_obj.notes = "{}// Please view information from <origination> about person [{}]".format(intro, notes_orig)
                            manu_obj.save()

                    # In case there is or are locations encoded in the <origination> element, they are 
                    # interpreted as possible provenances and linked to the manuscript if they are already in the
                    # Provenance table.
                    
                    # There can be notes for each provenance but they need to be for one manuscript only.
                    # This means that multiple manuscripts can be linked to the same provenance record 
                    # but each manuscript can have a unique notes field in the ProvenanceMan table.

                    # Find locations (role=4010) in origination                                                
                    for prov in manu.findall("./did/origination/corpname[@role='4010']"):
                        pname = prov.text
                                                
                        # First we need to check if the provenance that is found for a specific manuscript exists.
                        # If not, this cannot be added automatically to the Provenance table, this needs to be done
                        # manually by the team and this message with the provenance locations should be stored 
                        # in the notes field of the manuscript table. 
                     
                        # The complete contents of the <origination> field are to be stored in the ProvenanceMan table
                        # in case of a known Provenance, if not, in the notes field of the manuscript.                          
                   
                        # Try find the provenance that is found
                        provfound = Provenance.objects.filter(name__iexact=pname).first()
                     
                        # If there is no provenance name match, check if there is a name 
                        # that matches in the location table
                        if provfound == None:                           
                            provfound = Provenance.objects.filter(location__name__iexact=pname).first() 
                            
                            # If there is also no existing provenance found via the location id,  
                            # the provenance should be added to the manuscript manually. The message to do so, 
                            # and the complete contents of <orignation> are added to manu_obj.notes    
                            if provfound == None:                                                            
                                intro = ""
                                if manu_obj.notes != "": 
                                    intro = "{}. ".format(manu_obj.notes) 
                                    manu_obj.notes = "{}// Please set provenance manually  [{}] // [{}]".format(intro, pname, notes_orig)
                                    manu_obj.save()   
                        else: 
                            # In case there is a provfound, check for a link, if so, nothing should happen, 
                            # than there is already a link between a manuscript and a provenance
                            manuprovlink = ProvenanceMan.objects.filter(manuscript = manu_obj, provenance = provfound).first()
                            # If the provenance already exists than only a link should be 
                            # made between manuscript and provfound, and notes should be added.
                            if manuprovlink == None:
                                ProvenanceMan.objects.create(manuscript=manu_obj, provenance=provfound, note=notes_orig) 

                    # Get the XML FILENAME of the range of manuscripts

                    # Look for the filename of the XML in which the manuscripts are stored
                    # The filename needs to be added to each manuscript  
                    unitfilename = manu_info.find("./eadid")
                    if unitfilename != None and unitfilename != "":
                        manu_obj.filename = unitfilename.text
                   
                 
                    # Get the URL of the manuscript
                            
                    # Look for URL of the manuscript - if it exists   
                    # The URL needs to be added to the manuscript 
                    uniturl = manu.find("./dao")
                    if uniturl != None and uniturl != "":
                        url_low = uniturl.attrib.get('href')
                    else:
                        url_low = ""
                    
                    # Check if there is a higher level extent available, in case of combined manuscripts.  
                    if manuidno_number <= manuidno_end:                     
                        url_final = url_high + url_low # werkt nu wel
                        if url_final != None and url_final != "":
                            # Create new ManuscriptExt object to store 
                            mext = ManuscriptExt.objects.create(manuscript=manu_obj, url=url_final)
                    else:
                        url_final = url_low
                        if url_final != None and url_final != "":
                            # Create new ManuscriptExt object to store 
                            mext = ManuscriptExt.objects.create(manuscript=manu_obj, url=url_final)
                                 
                    # Get the DATE(s) of the manuscript             
                    
                    # Look for the date of the manuscript - if it exists
                    unitdate = manu.find("./did/unitdate")

                    if unitdate is None:
                        unit_yearstart_low = ""
                        unit_yearfinish_low = ""
                        pass

                    elif unitdate != None and unitdate != "" and 'normal' in unitdate.attrib:
                        unitdate_normal = unitdate.attrib.get('normal')
                        ardate = unitdate_normal.split("/")
                        if len(ardate) == 1:
                            unit_yearstart_low = int(unitdate_normal)
                            unit_yearfinish_low = int(unitdate_normal)
                        else:
                            unit_yearstart_low = int(ardate[0])
                            unit_yearfinish_low = int(ardate[1])

                    elif unitdate != None and unitdate != "" and 'normal' not in unitdate.attrib:
                        unitdate_complete = unitdate.text
                        if "-" in unitdate_complete and not "X" in unitdate_complete:
                            # use regex to split up string, will result in list with 4 items. 
                            ardate = re.split('[\-\(\)]', unitdate_complete)
                    
                            # use positions 3 and to to grab the first and last year # 5304 gaat hier mis
                            unit_yearstart_low = ardate[-3] 
                            unit_yearfinish_low = ardate[-2]
                        # In case of two Roman numerals, with an "-" in between:
                        elif "-" in unitdate_complete and "X" in unitdate_complete:
                            # Split on "e"
                            split1 = unitdate_complete.split('e ')
                            # Take the first part
                            part1 = split1[0]                      
                            # Strip part1, here is the first Roman numeral:
                            unit_centurystart_low = part1.strip()

                            # Match the Roman numerals for unit_yearstart_low and 
                            # unit_yearfinish_low with the corresponding Arabic numerals:                      
                            if unit_centurystart_low =="IX":
                                unit_yearstart_low = "900"
                            elif unit_centurystart_low =="X":
                                unit_yearstart_low = "1000"
                            elif unit_centurystart_low =="XI":
                                unit_yearstart_low = "1100"
                            elif unit_centurystart_low =="XII":
                                unit_yearstart_low = "1200"
                            elif unit_centurystart_low =="XIII":
                                unit_yearstart_low = "1300"

                            # Now we look for the second one: dit loopt nog niet                            
                            part2 = split1[1]
                            # 
                            part2_stripped=part2.strip()
                            # Split it
                            part2_split = re.split('[\-\(\)]', part2_stripped)
                            # Take the second part
                            unit_centuryfinish_low = part2_split[1]                            
                            
                            # Match the Roman numerals for unit_yearstart_low and 
                            # unit_yearfinish_low with the corresponding Arabic numerals:                              
                            if unit_centuryfinish_low =="IX":
                                unit_yearfinish_low = "900"
                            elif unit_centuryfinish_low =="X":
                                unit_yearfinish_low = "1000"
                            elif unit_centuryfinish_low =="XI":
                                unit_yearfinish_low = "1100"
                            elif unit_centuryfinish_low =="XII":
                                unit_yearfinish_low = "1200"
                            elif unit_centuryfinish_low =="XIII":
                                unit_yearfinish_low = "1300"
                            
                        # use the century indication in Roman numerals to create "virtual" 
                        # start and finish years
                        elif "-" not in unitdate_complete:
                            ardate = unitdate_complete.split('e ')
                            if len(ardate) < 3:  
                                unit_century_low = ardate[0]
                                if unit_century_low == "IX":
                                    unit_yearstart_low = "800"
                                    unit_yearfinish_low = "900"
                                elif unit_century_low == "X":
                                    unit_yearstart_low = "900"
                                    unit_yearfinish_low = "1000"
                                elif unit_century_low == "XI":
                                    unit_yearstart_low = "1000"
                                    unit_yearfinish_low = "1100"
                                elif unit_century_low == "XII":
                                    unit_yearstart_low = "1100"
                                    unit_yearfinish_low = "1200"
                                elif unit_century_low == "XIII":
                                    unit_yearstart_low = "1200"
                                    unit_yearfinish_low = "1300"
                    
                    # Check if there is a higher level date available, in case of combined manuscripts
                    if manuidno_number <= manuidno_end:
                        if unit_yearstart_low == "":
                            unit_yearstart = unit_yearstart_high
                            unit_yearfinish = unit_yearfinish_high
                        elif unit_yearstart_low != "":
                            unit_yearstart = unit_yearstart_low
                            unit_yearfinish = unit_yearfinish_low
                    else:
                        unit_yearstart = unit_yearstart_low
                        unit_yearfinish = unit_yearfinish_low
                                                            
                    # Create new Daterange object, store yearstart and year finish, only if there is a unitdate available.                     
                    if unit_yearstart != "":
                        drange = Daterange.objects.create(manuscript=manu_obj, yearstart = unit_yearstart, yearfinish = unit_yearfinish)
                        errHandle.Status(drange)
                    
                    
                    # Issue #479: a new manuscript gets assigned to a user's default project(s)
                    projects = profile.get_defaults()
                    manu_obj.set_projects(projects)

                    # OLD CODE from before issue #479
                    #  # Add id's of project, source, library, city and country to the Manuscript table.                                            
                    #  project = Project.get_default(username) 
                    #
                    #  # Add project id to the manuscript                               
                    #  manu_obj.project = project
                    # -------------------------------

                    # This is probably not the best way to do this...
                    unitlibrary_id = 1160 # Bibliothèque nationale de France, Manuscrits
                    unitcity_id = 616 # Paris
                    unitcountry_id = 21 # France

                    # Add library id to the manuscript
                    manu_obj.library_id = unitlibrary_id
                
                    # Add city id to the manuscript
                    manu_obj.lcity_id =  unitcity_id
                
                    # Add country id to the manuscript
                    manu_obj.lcountry_id = unitcountry_id
                
                    # Get the NOTES/COMMENTS 
                                       
                    # Find notes/comments in scopecontents only when there is a <c> element with manifestations
                    # Example: Latin 196 1920 maar dan anders...

                    # First get the contents 
                    check_on_c_element = manu.findall("./c")
                    # See if there are nested <c> elements...
                    if len(check_on_c_element) > 0: # 5304
                        # and if there are, pick up the <p> elements in scopecontents, these are NOT manifestations
                        # but should be considered as notes/comments belonging to the manuscript
                        for unit_p in manu.findall("./scopecontent/p"):
                            if len(unit_p) > 0: 
                                note = ElementTree.tostring(unit_p, encoding="unicode", method='text') # Laatste is heel handig!!
                                errHandle.Status(note)
                                # Maybe clean string from elements and stuff
                                # Maybe change the sequence
                                note_1 = re.sub("[\n\s]+"," ", note)
                                note_2 = note_1.replace('<p>', '')
                                note_3 = note_2.replace('</p>', '')
                                                              
                                # Extra for Latin 1920 ??                                

                                # Get profile      
                                profile = Profile.get_user_profile(username) 
                                otype = "manu"
                                                                
                                # Create new Comment object, add profile, otype and the comment
                                comment_obj = Comment.objects.create(profile=profile, content=note_3, otype=otype)
                                # Add new comment to the manuscript                            
                                manu_obj.comments.add(comment_obj)

                    else:
                        pass
                        
                    # MANIFESTATIONS 
                     
                    # In this part the manifestations or sermons are picked up and stored in the database
                    # but only when they are marked as such. For most manuscripts this is not the case.
                    
                    # MsItem is used to stucture the sequence of the sermons and sermonheads.
                    
                    # After a  discussion with Erwin we decided it would make no sense to make sermons of 
                    # the contents of <scopecontents> since we do not know when these contents are sermons. 

                    # Large parts of the code below can be deleted because it was meant to store ALL separate contents 
                    # of scopecontent as sermons. This implies that only sermons and sermonheads are to be stored
                    # in the database when they are described like in Latin 196.

                    # IN CASE THERE ARE NO NESTED <c> ELEMENTS (SermDescr)
                    
                    # If there are no nested <c> elements, and thus no sermons that are properly described the contents of
                    # <scopecontents>, the element in which the sermons can be found if available are to be placed in the
                    # notes field of MANUSCRIPT table in the database, after the ancienne cotes.
                    # This way all information on the sermons can be found when manually adding the sermons.                   

                    # Hier komt Latin 3267 en gaat het ergens mis, 

                    if len(check_on_c_element) < 1: 
                     
                        # Find the scopecontent element if it exists.
                        scopecontent_element = manu.find("./scopecontent")
                        # Process the scopecontent element:
                        if scopecontent_element != None and scopecontent_element != "":
                        
                            # First get all the text from <scopecontent>
                            scopecontent_1 = ''.join(scopecontent_element.itertext())
                                 
                            # Second clean the string
                            scopecontent_2 = re.sub("[\n\s]+"," ", scopecontent_1)
                                                        
                            # Third strip string of spaces 
                            scopecontent_3 = scopecontent_2.strip()
                            errHandle.Status(scopecontent_3)

                            # Now the combined old shelfmarks can be stored in the database in the notes field
                            # If there is no section <scopecontent> then only the ancienne cotes should be stored. 
                                                      
                            intro = ""
                            if manu_obj.notes != "": 
                                intro = "{}. ".format(manu_obj.notes) 
                                manu_obj.notes = "{}// Please add possible sermons manually (from <scopecontents>) [{}]".format(intro, scopecontent_3)
                                manu_obj.save() # tot hier goed en daarna mis, maar waarom? moet die manu_obj.save hier staan?
                            else:
                                manu_obj.notes = scopecontent_3


                    # IN CASE OF NESTED <c> ELEMENTS (SermHead, DateRange, SermDescr)
                    # than these elements should be processed as sermons (Latin 1920 gaat hier mis, len=2, idem 2710, 5304 )

                    elif len(check_on_c_element) > 0: 
                        # Create list to store the parents of the msitems (of the manifestations)
                        msitems_parents = []
                        # Loop trough all <c> elements                        
                        for unit_c in manu.findall("./c"):
                            
                            # First: find FOLIO

                            # For Latin 196
                            sermon_head = unit_c.find("./head")

                            # For Latin 1920
                            sermon_id = unit_c.find("./did/unitid")

                            # For Latin 2710: no id or head

                            # Check if there is a head or id available
                            if sermon_head == None and sermon_id== None:
                                serm_folio = ""                                
                            elif sermon_head != None and sermon_head != "":
                                serm_folio = sermon_head.text
                            elif sermon_id != None and sermon_id != "":
                                    serm_folio = sermon_id.text
                                
                            # Second: find DATE 
                                                        
                            # Date should be stored at the Manuscript level (in Daterange) 
                            # Find out if there is a date and in what way the date is structured.
                            sermon_date = unit_c.find("./did/unitdate")

                            # If there is no date, add 9999 to mark it
                            if sermon_date is None:
                                sermon_yearstart = "9999"
                                sermon_yearfinish = "9999"
                                pass
                            
                            # If there is a date with "normal" as attribute, process it.                                                   
                            elif sermon_date != None and sermon_date != "" and 'normal' in sermon_date.attrib:
                                sermon_date_normal = sermon_date.attrib.get('normal')
                                ardate = sermon_date_normal.split("/")
                                # If there is only one year, the same is used for start and finish
                                if len(ardate) == 1:
                                    sermon_yearstart = int(unitdate_normal)
                                    sermon_yearfinish = int(unitdate_normal)
                                # If there is more than one year, the first is used for start and 
                                # and the second for finish
                                else:
                                    sermon_yearstart = int(ardate[0])
                                    sermon_yearfinish = int(ardate[1])

                            # If there is a date without "normal" as attribute, process it in a different way
                            elif sermon_date != None and sermon_date != "" and 'normal' not in sermon_date.attrib:
                                sermon_date_complete = sermon_date.text
                                # See if there is an indication of a range in the date
                                # If there is no range, we assume that Roman numerals are used
                                if "-" not in sermon_date_complete:
                                    date_split = sermon_date_complete.split('e ')
                                    if len(date_split) < 3:  # Mis met 5304
                                        # Take the first of the list
                                        sermon_century = date_split[0]
                                        # See what century in Roman numerals is refered to and
                                        # store the beginning of that century in yearstart and the
                                        # end in yearfinish
                                        if sermon_century == "V":
                                            sermon_yearstart = "400"
                                            sermon_yearfinish = "500"
                                        elif sermon_century == "VI":
                                            sermon_yearstart = "500"
                                            sermon_yearfinish = "600"
                                        elif sermon_century == "VII":
                                            sermon_yearstart = "700"
                                            sermon_yearfinish = "800"
                                        elif sermon_century == "IX":
                                            sermon_yearstart = "800"
                                            sermon_yearfinish = "900"
                                        elif sermon_century == "X":
                                            sermon_yearstart = "900"
                                            sermon_yearfinish = "1000"
                                        elif sermon_century == "XI":
                                            sermon_yearstart = "1000"
                                            sermon_yearfinish = "1100"
                                        elif sermon_century == "XII":
                                            sermon_yearstart = "1100"
                                            sermon_yearfinish = "1200"
                                        elif sermon_century == "XIII":
                                            sermon_yearstart = "1200"
                                            sermon_yearfinish = "1300"
                                    elif len(date_split) == 3:  # 5304
                                        # Take the first of the list
                                        sermon_century = date_split[0]
                                        # See what century in Roman numerals is refered to and
                                        # store the beginning of that century in yearstart and the
                                        # end in yearfinish
                                        if sermon_century == "V":
                                            sermon_yearstart = "400"
                                            sermon_yearfinish = "500"
                                        elif sermon_century == "VI":
                                            sermon_yearstart = "500"
                                            sermon_yearfinish = "600"
                                        elif sermon_century == "VII":
                                            sermon_yearstart = "700"
                                            sermon_yearfinish = "800"
                                        elif sermon_century == "IX":
                                            sermon_yearstart = "800"
                                            sermon_yearfinish = "900"
                                        elif sermon_century == "X":
                                            sermon_yearstart = "900"
                                            sermon_yearfinish = "1000"
                                        elif sermon_century == "XI":
                                            sermon_yearstart = "1000"
                                            sermon_yearfinish = "1100"
                                        elif sermon_century == "XII":
                                            sermon_yearstart = "1100"
                                            sermon_yearfinish = "1200"
                                        elif sermon_century == "XIII":
                                            sermon_yearstart = "1200"
                                            sermon_yearfinish = "1300"
                            # Create new Daterange object, store yearstart and year finish with a link to the manuscript
                            # only when 9999 is not in sermon_yearstart
                            if sermon_yearstart != "9999":
                                drange = Daterange.objects.create(manuscript=manu_obj, yearstart = sermon_yearstart, yearfinish = sermon_yearfinish)
                                errHandle.Status(drange)
                            
                            # Third: find section TITLE
                            
                            # Here the complete contents of the <unittitle> element for each <c> element are processed 
                            # and stored in the database

                            sermon_title_comb = ""
                            # find alle section titles
                            for sermon_title in unit_c.findall("./did/unittitle"):
                                # First: grab ALL text from within the <unittitle> tage
                                sermon_title_1a = ''.join(sermon_title.itertext())                    
                                
                                # Second: clean the string
                                sermon_title_2a = re.sub("[\n\s]+"," ", sermon_title_1a)                      
                                
                                # Third: strip string of spaces 
                                sermon_title_3a = sermon_title_2a.strip()

                                # Add all sermon titles to one string and separate with a comma
                                sermon_title_comb += sermon_title_3a + ", "

                            # Get rid of the last comma at the end of the string
                            sermon_title_3_total = sermon_title_comb.rstrip(", ") 
                            errHandle.Status(sermon_title_3_total)
                                                       
                            # Now we have the folio/head and the title we can store them in SermHead
                                                                                   
                            # Create MsItem to store the correct sequence of title, head and manifestations 
                            # Use order to count the number of MsItems 
                            msitem_parent = MsItem.objects.create(manu=manu_obj, order=order) 
                            msitems_parents.append(msitem_parent)

                            # Add 1 to order
                            order += 1 
                           
                            # Store title and folio in SermHead with MsItem: TH: ok for Latin 1920                            
                            sermhead_obj = SermonHead.objects.create(msitem = msitem_parent, title = sermon_title_3_total, locus = serm_folio)
                                                       

                            # MANIFESTATIONS (with <c> element)
                            
                            # All separate elements are stored in title since we are not able to automate the splitting up
                            # of these titles in a proper way. 

                            # Grab contents in p under scopecontent in order to
                            # later on store the sermon manifestations
                            #scopecontent_p = unit_c.find("./scopecontent/p")
                            
                            # In case there are multiple <p> elements (Latin 2710 en 3267??)
                            for scopecontent_p in unit_c.findall("./scopecontent/p"):                         
                            # Latin 1920 geen scopecontent, 2710 meerdere elementen
                            #if scopecontent_p != None and scopecontent_p != "":                                                 
                            
                                # Create sermon manifestation title 
                                # (store only if there are no multiple sermon manifestations)                            
                                serm_manif_title = '%%'.join(scopecontent_p.itertext())
                                sermon_manif_titles_1 = ElementTree.tostring(scopecontent_p, encoding="unicode", method='text')

                                # Differentiate between scopecontent_p with 1 or more manifestaties, 
                                # separated with an <lb/> element, first 1 manifestation (scopecontent without <lb>)
                                if '<lb />' not in sermon_manif_titles_1:                           
                                    title_test = sermon_manif_titles_1
                                    #print(title_test)
                                
                                    # Maybe clean string from elements and stuff
                                    # Maybe change the sequence
                                    title = re.sub("[\n\s]+"," ", title_test)
                                    errHandle.Status(title)

                                    # Split the serm_manif_title up...
                                    # title_split_1 = serm_manif_title.split(" ")                             
                                
                                    # ...in order to grab the folio numbers...
                                    # folio_1 = title_split_1[1]
                                
                                    # ...and clean them up
                                    # folio_2 = re.sub(",", "", folio_1)
                                
                                    # Grab title (without folio), first split up serm_manif_title again...                               
                                    #title_split_2 = serm_manif_title.split(" ", 2)
                                    # ... and grab the third part
                                    #title_cleaned = title_split_2[2]                             
                                
                                    # Create a list to store the msitems from the manifestations
                                    # for processing later on                            
                                    msitems_children = []

                                    # Create MsItem to store the correct sequence of title, head and manifestations
                                    # Use order to count the number of MsItems next parent child
                                    # Nu zit het nummer van de parent al 
                                    msitem = MsItem.objects.create(manu=manu_obj, order=order, parent= msitem_parent)
                                
                                    # Add each msitem for each manifestation to the list
                                    msitems_children.append(msitem)

                                    # Add 1 to order
                                    order += 1

                                    # Store manifestations in SermDescr with MsItem, this means title, locus 
                                    # and the complete manifestation in note                                
                                    serm_obj = SermonDescr.objects.create(manu = manu_obj, msitem = msitem, title = title, note = serm_manif_title)
                             
                                # Second, with multiple manifesations:                                                        
                                elif '<lb />' in sermon_manif_titles_1:                               
                                    # Create list that gets wiped clean with each new <c> element
                                    sermon_manif_titles_3 = []

                                    # Split up sermon_manif_titles_1 into a list to get all elements separated by the <lb> elements
                                    # Each element is considered to be a manifestation
                                    sermon_manif_titles_2 = sermon_manif_titles_1.split('<lb />')
                                
                                    # Iterate over the list and clean up he                                
                                    for title in sermon_manif_titles_2:
                                        title_1 = re.sub("[\n\s]+"," ", title)
                                                                        
                                        # Get rid of all the elements
                                        title_2a = re.sub('<[^>]+>', '', title_1)
                                    
                                        # Strip the title
                                        title_2b = title_2a.strip()                                   

                                        # Add the cleaned title to the list
                                        if title_2b != "":
                                            sermon_manif_titles_3.append(title_2b)
                                                                        
                                    # Create a list to store the msitems from the manifestations
                                    # for processing later on                                                            
                                    msitems_children = []

                                    # Opslaan van de inhoud van de lijst
                                    # Create new Sermon Description 
                                    for title in sermon_manif_titles_3:                                    
                                        # Create MsItem to store the correct sequence of title, head and manifestations
                                        # Use order to count the number of MsItems, add the parent of the item
                                        # What happens if there is not a parent?
                                        msitem = MsItem.objects.create(manu=manu_obj, order=order, parent= msitem_parent)

                                        # Add each msitem for each manifestation to the list
                                        msitems_children.append(msitem)

                                        # Add 1 to order
                                        order += 1

                                        # Store manifestations in title in SermDescr with MsItems:
                                        # order moet ook hier erin komen te staan volgens mij
                                        serm_obj = SermonDescr.objects.create(manu = manu_obj, msitem = msitem, title = title)
                            
                                    # Now all children are in msitem_children!                            
                                    # Lijkt te werken voor de manifestaties, next_id voor manifestaties ook
                                    # next_id nog te implementeren voor niveau sermhead (verwijst naar eigen niveau)                            
                                    with transaction.atomic():
                                        for idx, msitem in enumerate(msitems_children):
                                            # Treat the first child
                                            if idx==0:
                                                # Set the first child of the msitem parent!
                                                msitem_parent.firstchild = msitem
                                                msitem_parent.save()
                                            # Treat the next T: laatste lijkt niet te kloppen, die verwijst naar boven
                                            if idx < len(msitems_children) - 1:
                                                msitem.next = msitems_children[idx+1]
                                                msitem.save()
                            else:
                                pass
                            # The last part related to the MsItems is adding the next_id to 
                            # the msitem parents (not the last one!)                             
                        with transaction.atomic():
                            for idx, msitem in enumerate(msitems_parents):
                                # Treat the next 
                                if idx < len(msitems_parents) - 1: 
                                    msitem.next = msitems_parents[idx+1] 
                                    msitem.save()                             
                        # Create new Daterange object, store yearstart and year finish                     
                        drange = Daterange.objects.create(manuscript=manu_obj, yearstart = sermon_yearstart, yearfinish = sermon_yearfinish)

                    # Save the results
                    manu_obj.save()
                
                    # Look for external references TH: ERUIT
                    #for extref in manu.findall("./bibliography/bibref/extref"):
                    #    if extref is None:
                    #        continue
                    #    url = extref.attrib.get('href')
                    #    if url != None:
                    #        # Create new ManuscriptExt object
                    #        mext = ManuscriptExt.objects.create(manuscript=manu_obj, url=url)
              
        # After all manuscripts that are requested in the shelfmarkset
        # are processed, the shelfmarks are stored in a CSV-file, together with the 
        # name of the xml-file that was processed    
        filename = os.path.abspath(os.path.join(MEDIA_DIR, 'processed_manuscripts.csv'))
        with open(filename, 'a', newline='') as csvfile:
            manuwriter = csv.writer(csvfile)
            for manu in lst_manus:
                timestamp = get_current_datetime().strftime("%d/%b/%Y %H:%M")
                manuwriter.writerow([manu, manu_obj.filename, timestamp])
                
    except:
        sError = errHandle.get_error_message()
        oBack['filename'] = filename
        oBack['status'] = 'error'
        oBack['msg'] = sError
    
    # Return the object that has been created
    return oBack


# =============== The OLD functions that WERE available in [urls.py] ===========
def import_ead(request):
    """Import one or more XML files that each contain one or more EAD items from Archives Et Manuscripts"""
       
    # Initialisations
    # NOTE: do ***not*** add a breakpoint until *AFTER* form.is_valid
    arErr = []
    error_list = []
    transactions = []
    data = {'status': 'ok', 'html': ''}
    template_name = 'reader/import_manuscripts.html' # Adapt because of multiple descriptions in 1 xml?
    obj = None
    data_file = ""
    bClean = False
    username = request.user.username

    # Check if the user is authenticated and if it is POST
    if request.user.is_authenticated and request.method == 'POST' and user_is_ingroup(request, 'passim_uploader'):
    
        # Remove previous status object for this user
        Status.objects.filter(user=username).delete()
        
        # Create a status object 
        oStatus = Status(user=username, type="ead", status="preparing")
        oStatus.save()

        form = UploadFilesForm(request.POST, request.FILES)
        lResults = []
        if form.is_valid():
            # NOTE: from here a breakpoint may be inserted!
            print('import_ead: valid form') 

            # Create a SourceInfo object for this extraction
            source = SourceInfo(url="https://ccfr.bnf.fr/", collector=username, profile = profile) 
            source.save()
            file_list = []

            # Get the contents of the imported file
            files = request.FILES.getlist('files_field')
            if files != None:
                for data_file in files:
                    filename = data_file.name
                    file_list.append(filename)

                    # Set the status
                    oStatus.set("reading", msg="file={}".format(filename))

                    # Get the source file
                    if data_file == None or data_file == "":
                        arErr.append("No source file specified for the selected project")
                    else:
                        # Check the extension
                        arFile = filename.split(".")
                        extension = arFile[len(arFile)-1]

                        # Further processing depends on the extension
                        oResult = None
                        if extension == "xml":
                            # This is an XML file
                            oResult = read_ecodex(username, data_file, filename, arErr, source=source) 

                        # Determine a status code
                        statuscode = "error" if oResult == None or oResult['status'] == "error" else "completed"
                        if oResult == None:
                            arErr.append("There was an error. No manuscripts have been added")
                        else:
                            lResults.append(oResult)                        

            # Adapt the 'source' to tell what we did
            source.code = "Imported using the [import_ead??] function on these XML files: {}".format(", ".join(file_list)) 
            source.save()
            # Indicate we are ready
            oStatus.set("ready")
            # Get a list of errors
            error_list = [str(item) for item in arErr]

            # Create the context
            context = dict(
                statuscode=statuscode,
                results=lResults,
                error_list=error_list
                )

            if len(arErr) == 0:
                # Get the HTML response
                data['html'] = render_to_string(template_name, context, request)
            else:
                data['html'] = "Please log in before continuing"


        else:
            data['html'] = 'invalid form: {}'.format(form.errors)
            data['status'] = "error"
    else:
        data['html'] = 'Only use POST and make sure you are logged in and authorized for uploading'
        data['status'] = "error"
 
    # Return the information
    return JsonResponse(data)


def import_ecodex(request):
    """Import one or more XML files that each contain one manuscript definition from e-codices, from Switzerland"""

    # Initialisations
    # NOTE: do ***not*** add a breakpoint until *AFTER* form.is_valid
    arErr = []
    error_list = []
    transactions = []
    data = {'status': 'ok', 'html': ''}
    template_name = 'reader/import_manuscripts.html'
    obj = None
    data_file = ""
    bClean = False
    username = request.user.username

    # Check if the user is authenticated and if it is POST
    if request.user.is_authenticated and request.method == 'POST' and user_is_ingroup(request, 'passim_uploader'):

        # Remove previous status object for this user
        Status.objects.filter(user=username).delete()
        # Create a status object
        oStatus = Status(user=username, type="ecodex", status="preparing")
        oStatus.save()

        def add_manu(lst_manual, lst_read, status="", msg="", user="", name="", url="", yearstart="", yearfinish="",
                     library="", idno="", filename=""):
            oInfo = {}
            oInfo['status'] = status
            oInfo['msg'] = msg
            oInfo['user'] = user
            oInfo['name'] = name
            oInfo['url'] = url
            oInfo['yearstart'] = yearstart
            oInfo['yearfinish'] = yearfinish
            oInfo['library'] = library
            oInfo['idno'] = idno
            oInfo['filename'] = filename
            if status == "error":
                lst_manual.append(oInfo)
            else:
                lst_read.append(oInfo)
            return True

        form = UploadFilesForm(request.POST, request.FILES)
        lResults = []
        if form.is_valid():
            # NOTE: from here a breakpoint may be inserted!
            print('import_ecodex: valid form')
            oErr = ErrHandle()
            try:
                # The list of headers to be shown
                lHeader = ['status', 'msg', 'name', 'yearstart', 'yearfinish', 'library', 'idno', 'filename', 'url']

                # Create a SourceInfo object for this extraction
                source = SourceInfo(url="http://e-codices.unifr.ch", collector=username)
                source.save()
                file_list = []

                # Get the contents of the imported file
                files = request.FILES.getlist('files_field')
                if files != None:
                    for data_file in files:
                        filename = data_file.name
                        file_list.append(filename)

                        # Set the status
                        oStatus.set("reading", msg="file={}".format(filename))

                        # Get the source file
                        if data_file == None or data_file == "":
                            arErr.append("No source file specified for the selected project")
                        else:
                            # Check the extension
                            arFile = filename.split(".")
                            extension = arFile[len(arFile)-1]

                            lst_manual = []
                            lst_read = []

                            # Further processing depends on the extension
                            oResult = None
                            if extension == "xml":
                                # This is an XML file
                                oResult = read_ecodex(username, data_file, filename, arErr, source=source)

                                if oResult == None or oResult['status'] == "error":
                                    # Process results
                                    add_manu(lst_manual, lst_read, status=oResult['status'], msg=oResult['msg'], user=oResult['user'],
                                                 filename=oResult['filename'])
                                else:
                                    # Get the results from oResult
                                    obj = oResult['obj']
                                    # Process results
                                    add_manu(lst_manual, lst_read, status=oResult['status'], user=oResult['user'],
                                                 name=oResult['name'], yearstart=obj.yearstart,
                                                 yearfinish=obj.yearfinish,library=obj.library.name,
                                                 idno=obj.idno,filename=oResult['filename'])

                            elif extension == "txt":
                                # Set the status
                                oStatus.set("reading list", msg="file={}".format(filename))
                                # (1) Read the TXT file
                                lines = []
                                bFirst = True
                                for line in data_file:
                                    # Get a good view of the line
                                    sLine = line.decode("utf-8").strip()
                                    if bFirst:
                                        if "\ufeff" in sLine:
                                            sLine = sLine.replace("\ufeff", "")
                                        bFirst = False
                                    lines.append(sLine)
                                # (2) Walk through the list of XML file names
                                for idx, xml_url in enumerate(lines):
                                    xml_url = xml_url.strip()
                                    if xml_url != "" and ".xml" in xml_url:
                                        # Set the status
                                        oStatus.set("reading XML", msg="{}: file={}".format(idx, xml_url))
                                        # (3) Download the file from the internet and save it 
                                        bOkay, sResult = download_file(xml_url)
                                        if bOkay:
                                            # We have the filename
                                            xml_file = sResult
                                            name = xml_url.split("/")[-1]
                                            # (4) Read the e-codex manuscript
                                            oResult = read_ecodex(username, xml_file, name, arErr, source=source)
                                            # (5) Check before continuing
                                            if oResult == None or oResult['status'] == "error":
                                                msg = "unknown"  
                                                if 'msg' in oResult: 
                                                    msg = oResult['msg']
                                                elif 'status' in oResult:
                                                    msg = oResult['status']
                                                arErr.append("Import-ecodex: file {} has not been loaded ({})".format(xml_url, msg))
                                                # Process results
                                                add_manu(lst_manual, lst_read, status="error", msg=msg, user=oResult['user'],
                                                             filename=oResult['filename'])
                                            else:
                                                # Get the results from oResult
                                                obj = oResult['obj']
                                                # Process results
                                                add_manu(lst_manual, lst_read, status=oResult['status'], user=oResult['user'],
                                                             name=oResult['name'], yearstart=obj.yearstart,
                                                             yearfinish=obj.yearfinish,library=obj.library.name,
                                                             idno=obj.idno,filename=oResult['filename'])

                                        else:
                                            aErr.append("Import-ecodex: failed to download file {}".format(xml_url))

                            # Create a report and add it to what we return
                            oContents = {'headers': lHeader, 'list': lst_manual, 'read': lst_read}
                            oReport = Report.make(username, "iecod", json.dumps(oContents))
                                
                            # Determine a status code
                            statuscode = "error" if oResult == None or oResult['status'] == "error" else "completed"
                            if oResult == None:
                                arErr.append("There was an error. No manuscripts have been added")
                            else:
                                lResults.append(oResult)

                # Adapt the 'source' to tell what we did 
                source.code = "Imported using the [import_ecodex] function on these XML files: {}".format(", ".join(file_list))
                source.save()
                # Indicate we are ready
                oStatus.set("ready")
                # Get a list of errors
                error_list = [str(item) for item in arErr]

                # Create the context
                context = dict(
                    statuscode=statuscode,
                    results=lResults,
                    error_list=error_list
                    )

                if len(arErr) == 0:
                    # Get the HTML response
                    data['html'] = render_to_string(template_name, context, request)
                else:
                    data['html'] = "Please log in before continuing"
            except:
                msg = oErr.get_error_message()
                oErr.DoError("import_ecodex")
                data['html'] = msg
                data['status'] = "error"

        else:
            data['html'] = 'invalid form: {}'.format(form.errors)
            data['status'] = "error"
    else:
        data['html'] = 'Only use POST and make sure you are logged in and authorized for uploading'
        data['status'] = "error"
 
    # Return the information
    return JsonResponse(data)

# ============== End of OLD functions ==========================================


class ReaderImport(View):
    # Initialisations
    arErr = []
    error_list = []
    transactions = []
    data = {'status': 'ok', 'html': ''}
    template_name = 'reader/import_manuscripts.html'
    obj = None
    oStatus = None
    data_file = ""
    bClean = False
    import_type = "undefined"
    sourceinfo_url = "undefined"
    username = ""
    mForm = UploadFilesForm
    
    def post(self, request, pk=None):
        # A POST request means we are trying to SAVE something
        self.initializations(request, pk)

        # Explicitly set the status to OK
        self.data['status'] = "ok"

        username = request.user.username
        self.username = username

        if self.checkAuthentication(request):
            # Remove previous status object for this user
            Status.objects.filter(user=username).delete()
            # Create a status object
            oStatus = Status(user=username, type=self.import_type, status="preparing")
            oStatus.save()
            # Make sure the status is available
            self.oStatus = oStatus

            lResults = []

            # Get profile 
            profile = Profile.get_user_profile(username) 
                    
            # Create a SourceInfo object for this extraction
            source = SourceInfo.objects.create(url=self.sourceinfo_url, collector=username, profile = profile)

            # The list of headers to be shown
            lHeader = ['status', 'msg', 'name', 'yearstart', 'yearfinish', 'library', 'idno', 'filename', 'url']

            if self.mForm is None:
                # Process the request
                bOkay, code = self.process_files(request, source, lResults, lHeader)

                if bOkay:
                    # Adapt the 'source' to tell what we did 
                    source.code = code
                    oErr.Status(code)
                    source.save()
                    # Indicate we are ready
                    oStatus.set("readyclose")
                    # Get a list of errors
                    error_list = [str(item) for item in self.arErr]

                    statuscode = "error" if len(error_list) > 0 else "completed"

                    # Create the context
                    context = dict(
                        statuscode=statuscode,
                        results=lResults,
                        error_list=error_list
                        )
                else:
                    self.arErr.append(code)

                if len(self.arErr) == 0:
                    # Get the HTML response
                    self.data['html'] = render_to_string(self.template_name, context, request)
                else:
                    lHtml = []
                    for item in self.arErr:
                        lHtml.append(item)
                    self.data['html'] = "There are errors: {}".format("\n".join(lHtml))
            else:
                form = self.mForm(request.POST, request.FILES)
                if form.is_valid():
                    # NOTE: from here a breakpoint may be inserted!
                    print('import_{}: valid form'.format(self.import_type))
                    oErr = ErrHandle()
                    try:

                        # Process the request
                        bOkay, code = self.process_files(request, source, lResults, lHeader)

                        if bOkay:
                            # Adapt the 'source' to tell what we did 
                            source.code = code
                            oErr.Status(code)
                            source.save()
                            # Indicate we are ready
                            oStatus.set("readyclose")
                            # Get a list of errors
                            error_list = [str(item) for item in self.arErr]

                            statuscode = "error" if len(error_list) > 0 else "completed"

                            # Create the context
                            context = dict(
                                statuscode=statuscode,
                                results=lResults,
                                error_list=error_list
                                )
                        else:
                            self.arErr.append(code)

                        if len(self.arErr) == 0:
                            # Get the HTML response
                            self.data['html'] = render_to_string(self.template_name, context, request)
                        else:
                            lHtml = []
                            for item in self.arErr:
                                lHtml.append(item)
                            self.data['html'] = "There are errors: {}".format("\n".join(lHtml))
                    except:
                        msg = oErr.get_error_message()
                        oErr.DoError("import_{}".format(self.import_type))
                        self.data['html'] = msg
                        self.data['status'] = "error"

                else:
                    self.data['html'] = 'invalid form: {}'.format(form.errors)
                    self.data['status'] = "error"
        
            # NOTE: do ***not*** add a breakpoint until *AFTER* form.is_valid
        else:
            self.data['html'] = "Please log in before continuing"

        # Return the information
        return JsonResponse(self.data)

    def initializations(self, request, object_id):
        # Clear errors
        self.arErr = []
        # COpy the request
        self.request = request

        # Get the parameters
        if request.POST:
            self.qd = request.POST
        else:
            self.qd = request.GET
        # ALWAYS: perform some custom initialisations
        self.custom_init()

    def custom_init(self):
        pass    

    def checkAuthentication(self,request):
        # first check for authentication
        if not request.user.is_authenticated:
            # Provide error message
            self.data['html'] = "Please log in to work on this project"
            return False
        elif not user_is_ingroup(request, 'passim_uploader'):
            # Provide error message
            self.data['html'] = "Sorry, you do not have the rights to upload anything"
            return False
        else:
            return True

    def add_manu(self, lst_manual, lst_read, status="", msg="", user="", name="", url="", yearstart="", yearfinish="",
                    library="", idno="", filename=""):
        oInfo = {}
        oInfo['status'] = status
        oInfo['msg'] = msg
        oInfo['user'] = user
        oInfo['name'] = name
        oInfo['url'] = url
        oInfo['yearstart'] = yearstart
        oInfo['yearfinish'] = yearfinish
        oInfo['library'] = library
        oInfo['idno'] = idno
        oInfo['filename'] = filename
        if status == "error":
            lst_manual.append(oInfo)
        else:
            lst_read.append(oInfo)
        return True

    def process_files(self, request, source, lResults, lHeader):
        bOkay = True
        code = ""
        return bOkay, code


class ReaderEcodex(ReaderImport):
    """Specific parameters for importing ECODEX"""

    import_type = "ecodex"
    sourceinfo_url = "http://e-codices.unifr.ch"

    def process_files(self, request, source, lResults, lHeader):
        file_list = []
        oErr = ErrHandle()
        bOkay = True
        code = ""
        oStatus = self.oStatus
        try:
            # Make sure we have the username
            username = self.username

            # Get the contents of the imported file
            files = request.FILES.getlist('files_field')
            if files != None:
                for data_file in files:
                    filename = data_file.name
                    file_list.append(filename)

                    # Set the status
                    oStatus.set("reading", msg="file={}".format(filename))

                    # Get the source file
                    if data_file == None or data_file == "":
                        self.arErr.append("No source file specified for the selected project")
                    else:
                        # Check the extension
                        arFile = filename.split(".")
                        extension = arFile[len(arFile)-1]

                        lst_manual = []
                        lst_read = []

                        # Further processing depends on the extension
                        oResult = None
                        if extension == "xml":
                            # This is an XML file
                            oResult = read_ecodex(username, data_file, filename, self.arErr, source=source)

                            if oResult == None or oResult['status'] == "error":
                                # Process results
                                self.add_manu(lst_manual, lst_read, status=oResult['status'], msg=oResult['msg'], user=oResult['user'],
                                                filename=oResult['filename'])
                            else:
                                # Get the results from oResult
                                obj = oResult['obj']
                                # Process results
                                self.add_manu(lst_manual, lst_read, status=oResult['status'], user=oResult['user'],
                                                name=oResult['name'], yearstart=obj.yearstart,
                                                yearfinish=obj.yearfinish,library=obj.library.name,
                                                idno=obj.idno,filename=oResult['filename'])

                        elif extension == "txt":
                            # Set the status
                            oStatus.set("reading list", msg="file={}".format(filename))
                            # (1) Read the TXT file
                            lines = []
                            bFirst = True
                            for line in data_file:
                                # Get a good view of the line
                                sLine = line.decode("utf-8").strip()
                                if bFirst:
                                    if "\ufeff" in sLine:
                                        sLine = sLine.replace("\ufeff", "")
                                    bFirst = False
                                lines.append(sLine)
                            # (2) Walk through the list of XML file names
                            for idx, xml_url in enumerate(lines):
                                xml_url = xml_url.strip()
                                if xml_url != "" and ".xml" in xml_url:
                                    # Set the status
                                    oStatus.set("reading XML", msg="{}: file={}".format(idx, xml_url))
                                    # (3) Download the file from the internet and save it 
                                    bOkay, sResult = download_file(xml_url)
                                    if bOkay:
                                        # We have the filename
                                        xml_file = sResult
                                        name = xml_url.split("/")[-1]
                                        # (4) Read the e-codex manuscript
                                        oResult = read_ecodex(username, xml_file, name, self.arErr, source=source)
                                        # (5) Check before continuing
                                        if oResult == None or oResult['status'] == "error":
                                            msg = "unknown"  
                                            if 'msg' in oResult: 
                                                msg = oResult['msg']
                                            elif 'status' in oResult:
                                                msg = oResult['status']
                                            self.arErr.append("Import-ecodex: file {} has not been loaded ({})".format(xml_url, msg))
                                            # Process results
                                            self.add_manu(lst_manual, lst_read, status="error", msg=msg, user=oResult['user'],
                                                            filename=oResult['filename'])
                                        else:
                                            # Get the results from oResult
                                            obj = oResult['obj']
                                            # Process results
                                            self.add_manu(lst_manual, lst_read, status=oResult['status'], user=oResult['user'],
                                                            name=oResult['name'], yearstart=obj.yearstart,
                                                            yearfinish=obj.yearfinish,library=obj.library.name,
                                                            idno=obj.idno,filename=oResult['filename'])

                                    else:
                                        self.aErr.append("Import-ecodex: failed to download file {}".format(xml_url))

                        # Create a report and add it to what we return
                        oContents = {'headers': lHeader, 'list': lst_manual, 'read': lst_read}
                        oReport = Report.make(username, "iecod", json.dumps(oContents))
                                
                        # Determine a status code
                        statuscode = "error" if oResult == None or oResult['status'] == "error" else "completed"
                        if oResult == None:
                            self.arErr.append("There was an error. No manuscripts have been added")
                        else:
                            lResults.append(oResult)
            code = "Imported using the [import_ecodex] function on these XML files: {}".format(", ".join(file_list))
        except:
            bOkay = False
            code = oErr.get_error_message()
        return bOkay, code


class ReaderEad(ReaderImport):
    """Specific parameters for importing EAD"""

    import_type = "ead"
    sourceinfo_url = "https://ccfr.bnf.fr/"
    # Dit moet dus deels aangepast worden
    def process_files(self, request, source, lResults, lHeader):
        file_list = []
        oErr = ErrHandle()
        bOkay = True
        code = ""
        oStatus = self.oStatus
        try:
            # Make sure we have the username
            username = self.username

            # Get the contents of the imported file
            files = request.FILES.getlist('files_field')
            if files != None:
                for data_file in files:
                    filename = data_file.name
                    file_list.append(filename)

                    # Set the status
                    oStatus.set("reading", msg="file={}".format(filename))

                    # Get the source file
                    if data_file == None or data_file == "":
                        self.arErr.append("No source file specified for the selected project")
                    else:
                        # Check the extension
                        arFile = filename.split(".")
                        extension = arFile[len(arFile)-1]

                        lst_manual = []
                        lst_read = []

                        # Further processing depends on the extension
                        oResult = None
                        if extension == "xml":
                            # This is an XML file
                            oResult = read_ead(username, data_file, filename, self.arErr, source=source)
                            # Tot HIER in read_ead aanpassen 
                            if oResult == None or oResult['status'] == "error":
                                # Process results
                                self.add_manu(lst_manual, lst_read, status=oResult['status'], msg=oResult['msg'], user=oResult['user'],
                                                filename=oResult['filename'])
                            else:
                                # Get the results from oResult
                                lst_obj = oResult.get('lst_obj')
                                if lst_obj != None:
                                    for obj in lst_obj:
                                        # Process results
                                        library_name = "" if obj.library == None else obj.library.name
                                        self.add_manu(lst_manual, lst_read, status=oResult['status'], user=oResult['user'],
                                                        name=obj.name, yearstart=obj.yearstart,
                                                        yearfinish=obj.yearfinish,library=library_name,
                                                        idno=obj.idno,filename=filename)

                        elif extension == "txt":
                            # Set the status
                            oStatus.set("reading list", msg="file={}".format(filename))
                            # (1) Read the TXT file
                            lines = []
                            bFirst = True
                            for line in data_file:
                                # Get a good view of the line
                                sLine = line.decode("utf-8").strip()
                                if bFirst:
                                    if "\ufeff" in sLine:
                                        sLine = sLine.replace("\ufeff", "")
                                    bFirst = False
                                lines.append(sLine)
                            # (2) Walk through the list of XML file names
                            for idx, xml_url in enumerate(lines):
                                xml_url = xml_url.strip()
                                if xml_url != "" and ".xml" in xml_url:
                                    # Set the status
                                    oStatus.set("reading XML", msg="{}: file={}".format(idx, xml_url))
                                    # (3) Download the file from the internet and save it 
                                    bOkay, sResult = download_file(xml_url)
                                    if bOkay:
                                        # We have the filename
                                        xml_file = sResult
                                        name = xml_url.split("/")[-1]
                                        # (4) Read the ead manuscript
                                        oResult = read_ead(username, xml_file, name, self.arErr, source=source)
                                        # (5) Check before continuing
                                        if oResult == None or oResult['status'] == "error":
                                            msg = "unknown"  
                                            if 'msg' in oResult: 
                                                msg = oResult['msg']
                                            elif 'status' in oResult:
                                                msg = oResult['status']
                                            self.arErr.append("Import-ead: file {} has not been loaded ({})".format(xml_url, msg))
                                            # Process results
                                            self.add_manu(lst_manual, lst_read, status="error", msg=msg, user=oResult['user'],
                                                            filename=oResult['filename'])
                                        else:
                                            # Get the results from oResult
                                            obj = oResult['obj']
                                            # Process results
                                            self.add_manu(lst_manual, lst_read, status=oResult['status'], user=oResult['user'],
                                                            name=oResult['name'], yearstart=obj.yearstart,
                                                            yearfinish=obj.yearfinish,library=obj.library.name,
                                                            idno=obj.idno,filename=oResult['filename'])

                                    else:
                                        aErr.append("Import-ead: failed to download file {}".format(xml_url))

                        # Create a report and add it to what we return
                        oContents = {'headers': lHeader, 'list': lst_manual, 'read': lst_read}
                        oReport = Report.make(username, "iead", json.dumps(oContents))
                                
                        # Determine a status code
                        statuscode = "error" if oResult == None or oResult['status'] == "error" else "completed"
                        if oResult == None:
                            self.arErr.append("There was an error. No manuscripts have been added")
                        else:
                            lResults.append(oResult)
            code = "Imported using the [import_ead] function on these XML files: {}".format(", ".join(file_list))
        except: 
            bOkay = False
            code = oErr.get_error_message()
        return bOkay, code


class ManuEadDownload(BasicPart):
    MainModel = Manuscript
    template_name = "seeker/download_status.html"
    action = "download"
    dtype = "csv"       # downloadtype

    def custom_init(self):
        """Calculate stuff"""
        
        dt = self.qd.get('downloadtype', "")
        if dt != None and dt != '':
            self.dtype = dt

    def get_data(self, prefix, dtype, response=None):
        """Gather the data as CSV, including a header line and comma-separated"""

        # Initialize
        lData = []
        sData = ""
        # The name of the file where EAD progress is being monitored
        filename = os.path.abspath(os.path.join(MEDIA_DIR, 'processed_manuscripts.csv'))
        
        # Load the contents
        lData = []
        with open(filename, "r") as fp:
            sData = fp.read() 
            arData = sData.split("\n") 
            for sLine in arData: 
                if sLine.strip() != "" and "," in sLine:
                    arLine = sLine.split(",")
                    oLine = dict(idno=arLine[0], filename=arLine[1], timestamp=arLine[2])
                    lData.append(oLine) 

        if dtype == "json":
            # convert to string
            sData = json.dumps(lData, indent=2)
        else:
            # Create CSV string writer
            output = StringIO()
            delimiter = "\t" if dtype == "csv" else ","
            csvwriter = csv.writer(output, delimiter=delimiter, quotechar='"')
            # Headers
            headers = ['idno', 'filename','timestamp']
            csvwriter.writerow(headers)
            for obj in lData:
                idno = obj.get('idno')
                filename = obj.get('filename')
                timestamp = obj.get('timestamp')
                row = [idno, filename, timestamp]
                csvwriter.writerow(row)

            # Convert to string 
            sData = output.getvalue()
            output.close()

        return sData


class EqualGoldHuwaToJson(BasicPart):
    """Convert (part of) HUWA database into EqualGold objects and download the resulting JSON"""

    MainModel = EqualGold
    template_name = "seeker/download_status.html"
    action = "download"
    dtype = "json"       # downloadtype
    prefix_type = "simple"

    # Specify the relationships
    relationships = [
        {'id': 1, 'linktype': 'neq'},
        {'id': 2, 'linktype': 'prt'},
        {'id': 3, 'linktype': 'ech'},
        {'id': 4, 'linktype': 'neq'},
        {'id': 5, 'linktype': 'neq'},
        {'id': 6, 'linktype': 'neq'},
        {'id': 7, 'linktype': 'neq'},
        {'id': 8, 'linktype': 'neq'},
        {'id': 9, 'linktype': 'neq'},
        {'id': 10, 'linktype': 'neq'},
        {'id': 11, 'linktype': 'neq'},
        {'id': 12, 'linktype': 'neq'},
        {'id': 13, 'linktype': 'neq'},
        {'id': 14, 'linktype': 'neq'},
        {'id': 15, 'linktype': 'neq'},
        {'id': 16, 'linktype': 'neq'},
        {'id': 17, 'linktype': 'neq'},
        {'id': 18, 'linktype': 'neq'},
        {'id': 19, 'linktype': 'neq'},
        ]

    def custom_init(self):
        """Calculate stuff"""
        
        dt = self.qd.get('downloadtype', "")
        if dt != None and dt != '':
            self.dtype = dt

    def get_data(self, prefix, dtype, response=None):
        """Gather the data as CSV, including a header line and comma-separated"""

        def get_table_list(lTable, opera_id, sField):
            lBack = []
            for oItem in lTable:
                if oItem['opera'] == opera_id:
                    lBack.append( oItem[sField])
            return lBack

        def get_table_field(lTable, id, sField, sIdField="id"):
            sBack = ""
            if id != 0:
                for oItem in lTable:
                    if oItem[sIdField] == id:
                        sBack = oItem[sField]
                        break
            return sBack

        # Initialize
        lData = []
        sData = ""
        huwa_tables = ["opera", 'clavis', 'frede', 'cppm', 'desinit', 'incipit',
            'autor', 'autor_opera', 'datum_opera']

        oErr = ErrHandle()
        table_info = {}
        author_info = {}
        try:
            # Read the Huwa to Passim author JSON
            lst_authors = self.read_authors()

            # Get the author id for 'Undecided'
            undecided = Author.objects.filter(name__iexact="undecided").first()

            # Read the HUWA db as tables
            table_info = self.read_huwa()

            # Load the tables that we need
            tables = self.get_tables(table_info, huwa_tables)

            # Walk through the table with AF information
            for idx, oOpera in enumerate(tables['opera']):
                opera_id = oOpera['id']
                # Take over any information that should
                oSsg = dict(id=idx+1, opera=opera_id)

                # Get the signature(s)
                signaturesA = []
                other = oOpera.get("abk")
                if not other is None and other != "":
                    signaturesA.append(dict(editype="ot", code=other))
                clavis = get_table_list(tables['clavis'], opera_id, "name")
                for sig in clavis:
                    signaturesA.append(dict(editype="cl", code="CPL {}".format(sig)))
                frede = get_table_list(tables['frede'], opera_id, "name")
                for sig in frede:
                    signaturesA.append(dict(editype="gr", code=sig))
                cppm = get_table_list(tables['cppm'], opera_id, "name")
                for sig in cppm:
                    signaturesA.append(dict(editype="cl", code="CPPM {}".format(sig)))
                oSsg['signaturesA'] = signaturesA

                # Get the Incipit and the Explicit
                oSsg['incipit'] = get_table_field(tables['incipit'], int(oOpera.get('incipit')), "incipit_text")
                oSsg['explicit'] = get_table_field(tables['desinit'], int(oOpera.get('desinit')), "desinit_text")

                # Make good notes for further processing
                oSsg['note_langname'] = oOpera.get("opera_langname","")
                oSsg['notes'] = oOpera.get("bemerkungen", "")

                # Get to the [datum_opera]
                oSsg['date_estimate'] = get_table_field(tables['datum_opera'], opera_id, "datum", "opera")

                # Get the *AUTHOR* (obligatory) for this entry
                huwa_autor_id = get_table_field(tables['autor_opera'], opera_id, "autor", "opera")
                if huwa_autor_id == "": 
                    passim_author = undecided
                else:
                    passim_author = self.get_passim_author(lst_authors, huwa_autor_id, tables['autor'])
                    if passim_author is None:
                        # What to do now?
                        passim_author = undecided
                oSsg['author'] = dict(id=passim_author.id, name= passim_author.name)

                # Add this to the list of SSGs
                lData.append(oSsg)

            # Convert lData to stringified JSON
            if dtype == "json":
                # convert to string
                sData = json.dumps(lData, indent=2)
        except:
            msg = oErr.get_error_message()
            oErr.DoError("HuwaEqualGoldToJson/get_data")

        return sData

    def read_huwa(self):
        oErr = ErrHandle()
        table_info = {}
        try:
            # Get the location of the HUWA database
            huwa_db = os.path.abspath(os.path.join(MEDIA_DIR, "passim", "huwa_database_for_PASSIM.db"))
            with sqlite3.connect(huwa_db) as db:
                standard_fields = ['erstdatum', 'aenddatum', 'aenderer', 'bemerkungen', 'ersteller']

                cursor = db.cursor()
                db_results = cursor.execute("SELECT name FROM sqlite_master WHERE type='table';").fetchall()
                tables = [x[0] for x in db_results]

                count_tbl = len(tables)

                # Walk all tables
                for table_name in tables:
                    oInfo = {}
                    # Find out what fields this table has
                    db_results = cursor.execute("PRAGMA table_info('{}')".format(table_name)).fetchall()
                    fields = []
                    for field in db_results:
                        field_name = field[1]
                        fields.append(field_name)

                        field_info = dict(type=field[2],
                                          not_null=(field[3] == 1),
                                          default=field[4])
                        oInfo[field_name] = field_info
                    oInfo['fields'] = fields
                    oInfo['links'] = []

                    # Read the table
                    table_contents = cursor.execute("SELECT * FROM {}".format(table_name)).fetchall()
                    oInfo['contents'] = table_contents

                    table_info[table_name] = oInfo

                # Close the database again
                cursor.close()
        except:
            msg = oErr.get_error_message()
            oErr.DoError("HuwaEqualGoldToJson/read_huwa")
        # Return the table that we found
        return table_info

    def read_authors(self):
        oErr = ErrHandle()
        lst_authors = []
        try:
            authors_json = os.path.abspath(os.path.join(MEDIA_DIR, "passim", "huwa_passim_author.json"))
            with open(authors_json, "r", encoding="utf-8") as f:
                lst_authors = json.load(f)
        except:
            msg = oErr.get_error_message()
            oErr.DoError("HuwaEqualGoldToJson/read_authors")
        # Return the table that we found
        return lst_authors

    def get_passim_author(self, lst_authors, huwa_id, tbl_autor):
        """Return the Passim author ID for [huwa_id]"""

        oErr = ErrHandle()
        passim = None
        try:
            shuwa_id = str(huwa_id)
            passim_id = None
            for item in lst_authors:
                if item['huwa_id'] == shuwa_id:
                    # Found it!
                    passim_id = item['passim_id']
                    break
            if passim_id is None:
                # Did not find it: 
                sName = ""
                for item in tbl_autor:
                    if item['id'] == huwa_id:
                        sName = item['name']
                        break
                if sName == "":
                    # There is a problem
                    oErr.Status("Cannot process HUWA author with id: {}".format(huwa_id))
                else:
                    # Check this in Passim table Author
                    author = Author.find_or_create(sName)
                    passim = author
            else:
                # Also get to the actual item
                passim = Author.objects.filter(id=passim_id).first()
        except:
            msg = oErr.get_error_message()
            oErr.DoError("HuwaEqualGoldToJson/get_passim_author")
        # Return the author id
        return passim

    def get_tables(self, table_info, lst_names):
        """Read all tables in [lst_names] from [table_info]"""

        oErr = ErrHandle()
        oTables = {}
        try:
            for sName in lst_names:
                oTable = table_info[sName]
                lFields = oTable['fields']
                lContent = oTable['contents']
                lTable = []
                for lRow in lContent:
                    oNew = {}
                    for idx, oPart in enumerate(lRow):
                        oNew[lFields[idx]] = oPart
                    lTable.append(oNew)
                oTables[sName] = lTable
        except:
            msg = oErr.get_error_message()
            oErr.DoError("HuwaEqualGoldToJson/get_table")

        return oTables


