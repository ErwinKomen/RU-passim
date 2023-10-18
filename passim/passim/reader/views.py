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
from datetime import datetime, timedelta
import operator 
from operator import itemgetter
from functools import reduce
from time import sleep 
import fnmatch, copy
import sys, os
import base64
import json
import csv, re
import requests
import openpyxl
import sqlite3
import glob
import lxml.etree as ET
from openpyxl.utils.cell import get_column_letter
from io import StringIO
from itertools import chain

# Imports needed for working with XML and other file formats
from xml.dom import minidom
# See: http://effbot.org/zone/celementtree.htm
import xml.etree.ElementTree as ElementTree
 
# ======= imports from my own application ======
from passim.settings import APP_PREFIX, MEDIA_DIR, WRITABLE_DIR
from passim.utils import ErrHandle, RomanNumbers
from passim.reader.forms import UploadFileForm, UploadFilesForm
from passim.seeker.models import Manuscript, SermonDescr, Status, SourceInfo, ManuscriptExt, Provenance, ProvenanceMan, \
    EqualGold, Signature, SermonGold, Project2, EqualGoldExternal, EqualGoldProject, EqualGoldLink, EqualGoldKeyword, \
    Library, Location, SermonSignature, Author, Feast, Daterange, Comment, Profile, MsItem, SermonHead, Origin, \
    Collection, CollectionSuper, CollectionGold, LocationRelation, LocationType, Information, \
    Script, Scribe, SermonGoldExternal, SermonGoldKeyword, SermonDescrExternal,  \
    Report, Keyword, ManuscriptKeyword, ManuscriptProject, STYPE_IMPORTED, get_current_datetime, EXTERNAL_HUWA_OPERA
from passim.reader.models import Edition, Literatur

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

def read_trans_eqg(username, data_file, filename, arErr, xmldoc=None, sName = None, source=None):
    """Import the sermon transcription part of an XML in TEI-P5 format
        
    This approach makes use of *lxml*
    """

    oErr = ErrHandle()
    oBack = {'status': 'ok', 'count': 0, 'msg': "", 'user': username, 'lst_obj': []}
    try:

        oTranscription = read_transcription(data_file)
        if not oTranscription is None:
            title_passim = oTranscription.get("code")
            text_sermon = oTranscription.get("text")
            bibleref = oTranscription.get("bibleref")
            # Can we continue?
            if not title_passim is None and not text_sermon is None:
                eqg = EqualGold.objects.filter(code__iexact=title_passim).first()
                if not eqg is None:
                    bNeedSaving = False
                    # We now have the right object: Set the text
                    if eqg.fulltext != text_sermon:
                        eqg.fulltext = text_sermon
                        bNeedSaving = True
                    # Possibly adapt the bibleref
                    if eqg.bibleref != bibleref:
                        eqg.bibleref = bibleref
                        bNeedSaving = True

                    # Need saving?
                    if bNeedSaving:
                        eqg.save()
                        oErr.Status("read_trans_eqg [{}]: {}".format(title_passim, bibleref))


            # make sure that we return the transcription together with the other stuff
            for k,v in oTranscription.items():
                oBack[k] = v
    except:
        sError = oErr.get_error_message()
        oBack['filename'] = filename
        oBack['status'] = 'error'
        oBack['msg'] = sError

    # Return the object that has been created
    return oBack

def sync_transcriptions(oStatus):
    """Status-showing synchronisation of XML transcriptions"""

    oErr = ErrHandle()
    bResult = True
    msg = ""
    try:
        if oStatus is None:
            bResult = False
            msg = "Sync transcription is missing a status object"
        else:
            # Call the actual scanning with the status object
            oMsg = {}
            bResult = scan_transcriptions(oStatus, oMsg)
            if bResult:
                if oStatus != None: oStatus.set("finished")
            else:
                msg = oMsg.get("msg", "")
                if msg == "":
                    msg = "Sync transcriptions encountered a problem"
    except:
        msg = oErr.get_error_message()
        oErr.DoError("sync_transcriptions")
        bResult = False
    return bResult, msg

def scan_transcriptions(oStatus=None, oMsg=None):
    """Scan the agreed-upon server location for (new) transcription files"""

    oErr = ErrHandle()
    bResult = True
    SCAN_SUBDIR = "pasta/pasta/*.xml"
    SCAN_SUBDIR = "chocolate/pasta/xml_tei_src/*.xml"
    try:
        # Check if this needs doing
        next_time = Information.get_kvalue("next_stemma")
        now_time = str(get_current_datetime())

        rightnow = (not oStatus is None)

        if rightnow or next_time is None or now_time > next_time:
            print("It is time to scan for new transcriptions...")
            # (1) Now execute the scanning
            scan_dir = os.path.abspath(os.path.join(MEDIA_DIR, SCAN_SUBDIR))
            lst_xml = glob.glob(scan_dir)
            iTotal = len(lst_xml)
            iCount = 0
            for sFile in lst_xml:
                iCount += 1
                # If necessary, provide Status information
                if not oStatus is None:
                    oCount = dict(total=iTotal, current=iCount)
                    oStatus.set("verifying", oCount=oCount)

                # print("Looking at: [{}]".format(sFile))

                # ===== Debugging ===
                if "cae_s_177" in sFile.lower():
                    iStop = 1

                # Treat this file
                oTrans = read_transcription(sFile)
                status = oTrans.get("status")
                code = oTrans.get("code")
                equal_id = oTrans.get('equal_id') 
                obj = None
                if status == "ok" and not code is None:
                    # It has been read and needs to be added
                    text_sermon = oTrans.get("text")
                    bibleref = oTrans.get("biblerefs")
                    full_info = {}
                    for k,v in oTrans.items():
                        if k != "text":
                            full_info[k] = v
                    # Turn the fullinfo into a string
                    sFullInfo = json.dumps(full_info)
                    if not equal_id is None:
                        obj = EqualGold.objects.filter(id=equal_id).first()
                    elif not code is None and code != "" and not "no passim" in code.lower():
                        obj = EqualGold.objects.filter(code__iexact=code).first()
                    else:
                        # Okay, cannot process this one
                        iStop = 1

                    if not obj is None:
                        bNeedSaving = False
                        if obj.transcription is None or obj.transcription == "" or obj.transcription.name is None:
                            obj.transcription = sFile
                        # We now have the right object: Set the text
                        if obj.fulltext != text_sermon:
                            obj.fulltext = text_sermon
                            bNeedSaving= True
                        if obj.fullinfo != sFullInfo:
                            obj.fullinfo = sFullInfo
                            bNeedSaving= True
                        if obj.bibleref != bibleref:
                            obj.bibleref = bibleref
                            bNeedSaving = True
                        if bNeedSaving:
                            # Show we are updating
                            sXmlName = os.path.basename(sFile)
                            oErr.Status("Saving transcriptions: {} - {} [{}]".format(sXmlName, code, bibleref))
                            # Actually perform the update
                            obj.save()

            if not oStatus is None:
                oStatus.set("ended_xml_sync")
            # (2) Next task: scan the sgcount
            iCount = 0
            iTotal = EqualGold.objects.count()
            idx = 0
            print("Checking SG count for AF...")
            with transaction.atomic():
                for ssg in EqualGold.objects.all():
                    idx += 1
                    # If necessary, provide Status information
                    if not oStatus is None:
                        oCount = dict(total=iTotal, current=idx)
                        oStatus.set("SG-count", oCount=oCount)

                    iChanges = ssg.set_sgcount()
                    if iChanges > 0:
                        iCount += iChanges
                        print("# {} - sgcount: {}".format(idx, iCount))

            # If necessary, provide Status information
            if not oStatus is None:
                oCount = dict(total=iTotal)
                oStatus.set("Wrapup", oCount=oCount)

            # Show we are ready
            if not oStatus is None:
                oStatus.set("ok", msg="Everything has been synchronized")
            print("scan_transcriptions: ready")

            # Set new next time
            next_time = str(get_current_datetime() + timedelta(hours=24))
            Information.set_kvalue("next_stemma", next_time)

    except:
        msg = oErr.get_error_message()
        oErr.DoError("scan_transcriptions")
        bResult = False
        if not oMsg is None:
            oMsg['msg'] = msg
    return bResult

def read_transcription(data_file):
    """Read a sermon transcription part of an XML in TEI-P5 format
        
    This approach makes use of *lxml*
    """

    def process_para(item, html, info):
        """Process (possibly recursively) a paragraph that may include elements like <w> and <quote>
        
        Added: it may also have element <s>
        """

        oErr = ErrHandle()
        bResult = True
        local = []
        try:
            # Walk all elements
            if not item is None:
                for element in item.xpath("./child::*"):
                    tag = element.tag
                    attrib = element.attrib
                    if tag == "w":
                        # This is a word 
                        local.append(element.text)
                        # Check if this is punctuation or not
                        if attrib.get("pos", "").lower() == "punc":
                            # It is punctuation - any action?
                            pass
                        else:
                            # Keep track of wordcount
                            info['wordcount'] += 1
                    elif tag == "quote":
                        # This is a quote: get the @source attribute and the @n
                        quote_n = attrib.get('n', '*')
                        quote_source = attrib.get('source', '')
                        quote = []
                        for quote_el in element.xpath("./child::*"):
                            if quote_el.tag == "w":
                                quote.append(quote_el.text)
                        sQuoteBody = " ".join(quote)
                        sQuote = '<span class="fullquote" title="{}. {}: {}" >{}</span>'.format(
                            quote_n, quote_source, sQuoteBody, quote_n )
                        local.append(sQuote)
                    elif tag == "s":
                        # This is a <s> sentence definition that may contain <w> and <quote> elements
                        process_para(element, html, info)
                sPara = " ".join(local)
                html.append(sPara)
        except:
            msg = oErr.get_error_message()
            oErr.DoError("process_para")
            bResult = False
        return bResult

    def get_titles(docroot):
        sGr = ""
        sCl = ""
        sPassim = ""
        biblerefs = ""

        # Get the PASSIM code
        ítem_passim = docroot.xpath("//title[@type='passim']")
        if len(ítem_passim) > 0:
            sPassim = ítem_passim[0].text
        # Get a possible GRYSON code
        ítem_gr = docroot.xpath("//title[@type='gr']")
        if len(ítem_gr) > 0:
            sGr = ítem_gr[0].text
        # Get a possible CLAVIS code
        ítem_cl = docroot.xpath("//title[@type='cl']")
        if len(ítem_cl) > 0:
            sCl = ítem_cl[0].text
        # Get list of bible references
        bibitems = docroot.xpath("//keywords[@scheme='bible']/descendant::item")
        if len(bibitems) > 0:
            lst_ref = []
            for bibitem in bibitems:
                sText = bibitem.text
                if not sText is None and sText != "":
                    lst_ref.append(sText.replace("_", " "))
            # Return them in a sorted unique list that can readily be processed
            biblerefs = "; ".join(sorted(set(lst_ref)))

        return sPassim, sGr, sCl, biblerefs

    oErr = ErrHandle()
    oBack = {'status': 'ok', 'count': 0, 'msg': "", 'lst_obj': []}
    try:
        # Read and parse the data into a DOM element
        xmldoc = ET.parse(data_file)  
        change_time = os.path.getmtime(data_file)

        # Get the root
        root = xmldoc.getroot()

        # Clean up the namespace
        for elem in root.getiterator():
            if not (isinstance(elem, ET._Comment) or isinstance(elem, ET._ProcessingInstruction)):
                elem.tag = ET.QName(elem).localname
        ET.cleanup_namespaces(root)

        # Get the titles: Passim, GR, CL
        title_passim, title_gr, title_cl, biblerefs = get_titles(root)
        if title_passim != "" or title_gr != "" or title_cl != "":

            # Initially: assume this needs to be read again
            bReadFile = True

            # Get the passim item, based on the title
            if title_passim != "" and not "no passim" in title_passim.lower():
                obj = EqualGold.objects.filter(code__iexact=title_passim).first()
            elif title_gr != "":
                sig = Signature.objects.filter(code__iexact=title_gr, editype="gr").first()
                if not sig is None:
                    obj = sig.gold.equal
                    title_passim = obj.get_code()
            elif title_cl != "":
                sig = Signature.objects.filter(code__iexact=title_cl, editype="cl").first()
                if not sig is None:
                    obj = sig.gold.equal
                    title_passim = obj.get_code()
            # If there is a EqualGold that has been located...
            if not obj is None:
                # Get the information stored with this file
                sFullInfo = obj.fullinfo
                if sFullInfo is None or sFullInfo == "":
                    sFullInfo = "{}"
                oFullInfo = json.loads(sFullInfo)
                last_time = oFullInfo.get("change_time")

                bHasChanged = (not last_time is None and change_time <= last_time)
                bBibChanged = (biblerefs != "" and biblerefs != obj.bibleref)

                if not bHasChanged and not bBibChanged:
                    # The file has not changed
                    bReadFile = False

            # Need to read it?
            if bReadFile:

                # Get the list of sermon elements
                html = []
                info = dict(wordcount=0)
                sermon_items = root.xpath("//div[@type='sermon']/child::*")
                for sermon_item in sermon_items:
                    tag = sermon_item.tag
                    attrib = sermon_item.attrib
                    if tag == "head":
                        # This is one head at this moment
                        headtype = attrib.get('type', '')
                        level = "##" if headtype == "title" else "###"
                        html.append("{} {}".format(level, sermon_item.text))
                    elif tag == "div" and attrib.get("type", "") == "paragraph":
                        # Paragraph: add a newline
                        html.append("")
                        # This is a paragraph, that contains <head> and <p>
                        for subitem in sermon_item.xpath("./child::*"):
                            if subitem.tag == "head":
                                # This is another level head
                                html.append("#### {}".format(subitem.text))
                            elif subitem.tag == "p":
                                # This is a paragraph containing words and quotes
                                process_para(subitem, html, info)
                    elif tag == "div" and attrib.get("type", "") == "chapter":
                        # This is a new chapter, which can contain <head> and <p>
                        html.append("")
                        # This is a paragraph, that contains <head> and <p>
                        for subitem in sermon_item.xpath("./child::*"):
                            if subitem.tag == "head":
                                # This is another level head
                                html.append("#### {}".format(subitem.text))
                            elif subitem.tag == "p":
                                # This is a paragraph containing words and quotes
                                process_para(subitem, html, info)

                # Okay, we found all the elements, now store them.
                text_sermon = "\n".join(html)

                oBack['text'] = text_sermon
                oBack['count'] = oBack['count'] + 1
                oBack['tsize'] = len(text_sermon)
                oBack['code'] = title_passim
                oBack['gr'] = title_gr
                oBack['cl'] = title_cl
                oBack['wordcount'] = info.get("wordcount", 0)
                oBack['change_time'] = change_time
                oBack['biblerefs'] = biblerefs
                oBack['equal_id'] = None if obj is None else obj.id
            else:
                oBack['status'] = "skip"
       
    except:
        sError = oErr.get_error_message()
        oBack['filename'] = data_file
        oBack['status'] = 'error'
        oBack['msg'] = sError

    # Return the object that has been created
    return oBack

def get_huwa_opera_literature(opera_id, handschrift_id):
    lBack = Edition.get_opera_literature(opera_id, handschrift_id)
    return lBack

def read_kwcategories():
    """Load the JSON that specifies the keyword categories"""

    oErr = ErrHandle()
    lst_kwcat = {}
    try:
        kwcat_json = os.path.abspath(os.path.join(MEDIA_DIR, "passim", "passim_kwcat.json"))
        with open(kwcat_json, "r", encoding="utf-8") as f:
            lst_kwcat = json.load(f)
    except:
        msg = oErr.get_error_message()
        oErr.DoError("read_kwcategories")
    # Return the table that we found
    return lst_kwcat


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
        """Allow user to add code"""
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


class ReaderTransEqgImport(ReaderImport):
    """Read a transcription for a Passim SSG/AF into the appropriate field"""


    import_type = "xtranseqg"
    sourceinfo_url = "https://github.com/glsch"
    template_name = "reader/import_transeqg.html"

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
                            oResult = read_trans_eqg(username, data_file, filename, self.arErr, source=source)

                            if oResult == None or oResult['status'] == "error":
                                # Add to [lstRead]
                                oTranscription = dict(code="error", tsize=0, filename=filename, msg = oResult['msg'])
                                lst_read.append(oTranscription)
                            else:
                                # Get the results from oResult
                                code = oResult.get("code")
                                tsize = oResult.get("tsize")
                                oResult['filename'] = filename

                                if not code is None:
                                    obj = EqualGold.objects.filter(code__iexact=code).first()
                                    if not obj is None:
                                        url = reverse("equalgold_details", kwargs={'pk': obj.id})
                                        oResult['code'] = '<span><a class="nostyle" href="{}">{}</a></span>'.format(
                                            url, code)


                                # Add to [lstRead]
                                oTranscription = dict(code=code, tsize=tsize, filename=filename)
                                lst_read.append(oTranscription)

                        # Create a report and add it to what we return
                        oContents = {'headers': lHeader, 'list': lst_manual, 'read': lst_read}
                        oReport = Report.make(username, "itreqg", json.dumps(oContents))
                                
                        # Determine a status code
                        statuscode = "error" if oResult == None or oResult['status'] == "error" else "completed"
                        if oResult == None:
                            self.arErr.append("There was an error. No transcriptions have been added to a SSG")
                        else:
                            lResults.append(oResult)
            code = "Imported using the [import_trans_eqg] function on these XML files: {}".format(", ".join(file_list))
        except:
            bOkay = False
            code = oErr.get_error_message()
            oErr.DoError("")
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
    dtype = "json"          # downloadtype
    prefix_type = "simple"
    import_type = "ssg"     # Options: 'ssg', 'manu'
    downloadname = "huwa_ssg"

    # Specify the relationships (see issue #526)
    relationships = [
        {'rel_id': 0,  'dir': 'no',  'linktypes': ['eqs'],        'spectypes': []},               # Equals
        {'rel_id': 1,  'dir': 'no',  'linktypes': ['neq'],        'spectypes': []},               # Nearly equals
        {'rel_id': 2,  'dir': 'no',  'linktypes': ['prt'],        'spectypes': []},               # Partially equals
        {'rel_id': 3,  'dir': 'no',  'linktypes': ['ech'],        'spectypes': []},               # echoes
        {'rel_id': 4,  'dir': 'yes', 'linktypes': [],             'spectypes': ['usd', 'udd']},   # uses/used by (direct)
        {'rel_id': 5,  'dir': 'yes', 'linktypes': [],             'spectypes': ['usi', 'udi']},   # uses/used by (indirect)
        {'rel_id': 6,  'dir': 'no',  'linktypes': [],             'spectypes': ['com']},          # common source
        {'rel_id': 7,  'dir': 'no',  'linktypes': [],             'spectypes': ['uns']},          # unspecified
        {'rel_id': 8,  'dir': 'yes', 'linktypes': ['rel'],        'spectypes': ['cso', 'cdo']},   # comments on / commented on
        {'rel_id': 9,  'dir': 'yes', 'linktypes': ['prt'],        'spectypes': ['pto', 'pth']},   # is part of / has as its part
        {'rel_id': 10, 'dir': 'no',  'linktypes': ['rel'],        'spectypes': ['cap']},          # capitula
        {'rel_id': 11, 'dir': 'yes', 'linktypes': ['prt'],        'spectypes': ['pto', 'pth']},   # Excerpt (use keyword 'excerpt')
        {'rel_id': 12, 'dir': 'no',  'linktypes': [],             'spectypes': []},               # additional text follows
        {'rel_id': 13, 'dir': 'no',  'linktypes': ['rel'],        'spectypes': ['tki']},          # tabula/key/index
        {'rel_id': 14, 'dir': 'no',  'linktypes': ['rel'],        'spectypes': ['pro']},          # prologue
        {'rel_id': 15, 'dir': 'yes', 'linktypes': ['neq', 'prt'], 'spectypes': ['tro', 'tra']},   # translation of / translated as
        {'rel_id': 16, 'dir': 'no',  'linktypes': ['ech'],        'spectypes': ['pas']},          # paraphrases
        {'rel_id': 17, 'dir': 'no',  'linktypes': ['rel'],        'spectypes': ['epi']},          # epilogue
        {'rel_id': 18, 'dir': 'yes', 'linktypes': ['ech'],        'spectypes': ['pad']},          # paraphrased
        {'rel_id': 19, 'dir': 'no',  'linktypes': [],             'spectypes': []},               # collection (no HC, but compilations?)
        ]

    def custom_init(self):
        """Calculate stuff"""
        
        dt = self.qd.get('downloadtype', "")
        if dt != None and dt != '':
            if dt == "json_manu":
                self.dtype = "json"
                self.import_type = "manu"
            else:
                self.dtype = dt

    def get_edition(self):
        """Get one edition"""

        oEdition = None
        oErr = ErrHandle()
        try:
            # Start getting all needed information for this edition
            oEdition = dict(edition=edition_id)
            pp = get_edipp(edition)
            if not pp is None and pp != "":
                oEdition['pp'] = pp
            # Find corresponding literature
            literatur_id = edition.get('literatur')
            if not literatur_id is None and literatur_id > 0:
                literatur = oLiteratur.get(str(literatur_id))
                # If possible get a title from here
                literaturtitel = literatur.get("titel")
                if not literaturtitel is None and literaturtitel != "":
                    oEdition['literaturtitel'] = literaturtitel

                # Get from here: jahr, band
                jahr = literatur.get("jahr")
                band = literatur.get("band")
                if not jahr is None and jahr != "": oEdition['year'] = jahr
                if not band is None and band != "": oEdition['band'] = band

                # Calculate the 'ort' from here
                oLoc = get_ort(literatur.get("ort"), oOrt, oLand, oHuwaLand)
                if not oLoc is None:
                    oEdition['location'] = copy.copy(oLoc)

                # Find corresponding [reihe]
                reihe_id = literatur.get("reihe")
                if not reihe_id is None:
                    reihe = oReihe.get(str(reihe_id))
                    reihetitel = reihe.get("reihetitel")
                    reihekurz = reihe.get("reihekurz")
                    if not reihetitel is None and reihetitel != "": oEdition['reihetitel'] = reihetitel
                    if not reihekurz is None and reihekurz != "": oEdition['reihekurz'] = reihekurz
                # Look for the verfasser(author)
                verfasser_id = literatur.get("verfasser")
                if not verfasser_id is None:
                    verfasser = oVerfasser.get(str(verfasser_id))
                    if not verfasser is None:
                        author = []
                        name = verfasser.get("name")
                        vorname = verfasser.get("vorname")
                        if not name is None and name != "":
                            author.append(name.strip())
                        if not vorname is None and vorname != "":
                            author.append(vorname.strip())
                        if len(author) > 0:
                            oEdition['author'] = dict(full=", ".join(author), name=name)
                            if not vorname is None and vorname != "":
                                oEdition['author']['firstname'] = vorname
                # Check if this 'edition' has any items in 'loci'
                lst_loci = []
                for oItem in tables['loci']:
                    if oItem.get("editionen") == edition_id:
                        # Need to add a LOCI item
                        oLoci = dict(page=oItem.get('seite_col'), line=oItem.get("zeile"))
                        cap = oItem.get("cap")
                        if not cap is None:
                            oLoci['cap'] = cap
                        # Possibly add incipit and/or explicit
                        incipit = oIncipit[str(oItem.get("incipit"))]
                        explicit = oExplicit[str(oItem.get("desinit"))]
                        if not incipit is None and incipit != "":
                            oLoci['incipit'] = incipit
                        if not explicit is None and explicit != "":
                            oLoci['explicit'] = explicit

                        # Add this to the list
                        lst_loci.append(oLoci)
                # Do we have a list?
                if len(lst_loci) > 0:
                    # Yes, there is a list: add it to this edition
                    oEdition['loci'] = copy.copy(lst_loci)
        except:
            msg = oErr.get_error_message()
            oErr.DoError("get_edition")

        return oEdition

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

        def get_table_item(lTable, id, sIdField="id"):
            oBack = None
            if isinstance(id, str): id = int(id)
            if id != 0:
                for oItem in lTable:
                    if oItem[sIdField] == id:
                        oBack = oItem
                        break
            return oBack

        def get_table_items(lTable, id, sIdField="id"):
            lBack = []
            if isinstance(id, str): id = int(id)
            if id != 0:
                for oItem in lTable:
                    if oItem[sIdField] == id:
                        lBack.append(copy.copy(oItem))
                        #break
            return lBack

        def get_table_fk_count(lTable, id, sIdField):
            iCount = 0
            if id != 0:
                for oItem in lTable:
                    if oItem[sIdField] == id:
                        iCount += 1
            if iCount < 0:
                iStop = 1
            return iCount

        def get_city_land(ort_id, tables, oHuwaLand):
            """Get the city and country from the [ort] id"""

            oBack = {}
            oErr = ErrHandle()
            try:
                lst_ort = tables['ort']
                lst_land = tables['land']
                oOrt = get_table_item(lst_ort, ort_id)
                if not oOrt is None:
                    # Found the location
                    oBack['city'] = oOrt.get("ortsname")
                    oBack['citynote'] = oOrt.get("bemerkungen")
                    # Look for country
                    land_id = oOrt.get("land")
                    oLand = get_table_item(lst_land, land_id)
                    if not oLand is None:
                        # Found the country
                        name = oLand.get("landname")
                        if not name is None and name != "":
                            oBack['country'] = name
                            if name in oHuwaLand:
                                oBack['country'] = oHuwaLand[oBack['country']]

            except:
                msg = oErr.get_error_message()
                oErr.DoError("EqualGoldHuwaToJson/get_data/get_city_land")
            # Return the info we have
            return oBack

        def get_ort(ort_id, ort, land, oHuwaLand):
            """Get the city and country from the [ort] id"""

            oBack = {}
            oErr = ErrHandle()
            try:
                if isinstance(ort_id, int):
                    ort_id = str(ort_id)
                # Get the ort
                oOrt = ort.get(ort_id)
                if not oOrt is None:
                    # Found the location
                    ortsname = oOrt.get("ortsname")
                    if not ortsname is None and ortsname != "":
                        oBack['city'] = oOrt.get("ortsname")
                    bem = oOrt.get("bemerkungen")
                    if not bem is None and bem != "":
                        oBack['citynote'] = oOrt.get("bemerkungen")
                    # Look for country
                    land_id = str(oOrt.get("land"))
                    oLand = land.get(land_id)
                    if not oLand is None:
                        # Found the country
                        name = oLand.get("landname")
                        if not name is None and name != "":
                            oBack['country'] = name
                            if name in oHuwaLand:
                                oBack['country'] = oHuwaLand[oBack['country']]
                # Check on the length of what we return
                if len(oBack) == 0:
                    oBack = None
            except:
                msg = oErr.get_error_message()
                oErr.DoError("EqualGoldHuwaToJson/get_data/get_ort")
            # Return the info we have
            return oBack

        def get_library_info(id, tables):
            """Get the country/city/library name information for bibliothek.id"""

            oLibrary = {}
            oErr = ErrHandle()
            try:
                lst_bibliothek = tables['bibliothek']
                lst_ort = tables['ort']
                lst_land = tables['land']

                oBiblio = get_table_item(lst_bibliothek, id)
                if not oBiblio is None:
                    # Found the library
                    bFoundLib = True
                    oLibrary = dict(
                        name=oBiblio.get('bibl_name'),
                        short = oBiblio.get('bibl_kurz'),
                        url = oBiblio.get('url'),
                        note = oBiblio.get("bemerkungen"))
                    # Look for city and country
                    ort_id = oBiblio.get("ort")
                    oOrt = get_table_item(lst_ort, ort_id)
                    if not oOrt is None:
                        # Found the location
                        oLibrary['city'] = oOrt.get("ortsname")
                        oLibrary['citynote'] = oOrt.get("bemerkungen")
                        # Look for country
                        land_id = oOrt.get("land")
                        oLand = get_table_item(lst_land, land_id)
                        if not oLand is None:
                            # Found the country
                            name = oLand.get("landname")
                            if not name is None and name != "":
                                oLibrary['country'] = name

            except:
                msg = oErr.get_error_message()
                oErr.DoError("EqualGoldHuwaToJson/get_data/get_library_info")
            # Return the info we have
            return oLibrary

        def get_or_create_library(bibliothek_id, lib_name, lib_city, lib_country):
            oErr = ErrHandle()
            lib_id = None
            try:
                # (1) Get the Passim lib_country
                obj_country = Location.get_location(country=lib_country)
                country_set = [ obj_country ]
                # (2) Get the Passim lib_city
                obj_city = obj = Location.objects.filter(
                    name__iexact=lib_city, loctype__name="city", relations_location__in=country_set).first()
                if obj_city is None:
                    # Add the city and the country it is in
                    loctype = LocationType.objects.filter(name="city").first()
                    if not loctype is None:
                        obj_city = Location.objects.create(name=lib_city, loctype=loctype)
                        # Create a relation that the city is in the specified country
                        obj_rel = LocationRelation.objects.create(container=obj_country, contained=obj_city)
                            
                # Try to get it
                obj_lib = Library.objects.filter(name__iexact=lib_name, lcity=obj_city, lcountry=obj_country).first()
                if obj_lib is None:
                    # Add the library in the country/city
                    obj_lib = Library.objects.create(
                        name=lib_name, snote="Added from HUWA bibliothek ID {}".format(bibliothek_id),
                        lcity=obj_city, lcountry=obj_country, location=obj_city
                        )
                # Make sure we have the exact information for this library available
                lib_city = obj_lib.lcity.name
                lib_country = obj_lib.lcountry.name
                lib_id = obj_lib.id
            except:
                msg = oErr.get_error_message()
                oErr.DoError("EqualGoldHuwaToJson/get_data/get_or_create_library")
            # Return the appropriate information
            return lib_id, lib_city, lib_country

        def add_existing(sKey):
            if not sKey in existing_dict:
                existing_dict[sKey] = 1
            else:
                existing_dict[sKey] += 1

        def add_sig_to_list(signatures, lst_sig, editype, code_format):
            oErr = ErrHandle()
            try:
                if not lst_sig is None:
                    if isinstance(lst_sig, int):
                        if lst_sig == 0:
                            return;
                        lst_sig = [ str(lst_sig) ]
                    elif isinstance(lst_sig, str):
                        lst_sig = lst_sig.split(";")
                    for sig in lst_sig:
                        oAdd = dict(editype=editype, code=code_format.format(sig))
                        signatures.append(oAdd)
            except:
                msg = oErr.get_error_message()
                oErr.DoError("add_sig_to_list")

        def add_sig_to_dict(signatures, sig_dict, opera_id):
            oErr = ErrHandle()
            try:
                # walk all the signatures
                for sig in signatures:
                    # Turn this signature into one string
                    full_sig = "{}: {}".format(sig['editype'], sig['code'])
                    # Do we have an entry?
                    if full_sig in sig_dict:
                        lst_id = sig_dict[full_sig]
                    else:
                        lst_id = []
                    # Add this entry
                    lst_id.append(opera_id)
                    # Put it back in the dictionary
                    sig_dict[full_sig] = lst_id

            except:
                msg = oErr.get_error_message()
                oErr.DoError("add_sig_to_dict")

        def add_sig_replacing(signatures, item, key, number, editype):
            oErr = ErrHandle()
            try:
                element = item.get(key)
                if not element is None:
                    # Convert Clavis
                    # transformed = re.sub(r'\#.*', number, element)
                    transformed = rHashTag.sub(number, element).strip()
                    # Remove final ',' if needed
                    if transformed[-1] == ",":
                        transformed = transformed.strip(",")
                    oAdd = dict(editype=editype, code=transformed)
                    signatures.append(oAdd)
            except:
                msg = oErr.get_error_message()
                oErr.DoError("add_sig_replacing")

        def get_author(oInhalt, tables, lst_authors):
            """Get the PASSIM author id via the inhalt record"""

            author_id = None
            msg = ""
            oErr = ErrHandle()
            try:
                # Get the right tables
                lst_inms = tables['inms']
                lst_autor_inms = tables['autor_inms']
                lst_autor = tables['autor']

                # Look in [inms] for the field [inhalt]
                inhalt_id = oInhalt.get("id")
                oInms = get_table_item(lst_inms, inhalt_id, "inhalt")
                if not oInms is None:
                    # Look for the corresponding record in autor_inms
                    oAutorInms = get_table_item(lst_autor_inms, oInms['id'], "inms")
                    if not oAutorInms is None:
                        # Look for the correct 'gold' Autor
                        oAutor = get_table_item(lst_autor, oAutorInms['autor'], "id")
                        if not oAutor is None:
                            # At least get its name
                            msg = oAutor['name']
                            # We found the HUWA autor id
                            autor_id = oAutor['id']
                            if not autor_id is None:
                                # Try find the Passim AUTHOR 
                                oAuthorConv = get_table_item(lst_authors, autor_id, "huwa_id")
                                if not oAuthorConv is None:
                                    # Now get the proper passim id
                                    author_id = oAuthorConv['passim_id']
                                    # And get the proper PASSIM author name
                                    msg = oAuthorConv['name']
                pass
            except:
                msg = oErr.get_error_message()
                oErr.DoError("get_author")

            return author_id, msg

        def get_extent(oHandschrift, oFF, oZB):
            """Derive an Extent description of the manuscript"""

            sBack = ""
            oErr = ErrHandle()
            html = []
            try:
                # use fields fol_pag, folbl, vors_vorne, vors_hinten, col, col_breite, zeilen
                fol_pag = oHandschrift.get("fol_pag", "")
                folbl = oHandschrift.get("folbl", "")
                vors_vorne = oHandschrift.get("vors_vorne", "")
                vors_hinten = oHandschrift.get("vors_hinten", "")
                col = oHandschrift.get("col", "")
                col_breite = oHandschrift.get("col_breite", "")
                zeilen = oHandschrift.get("zeilen", "")
                sId = str(oHandschrift.get("id", ""))

                if folbl != "":
                    if fol_pag != "":
                        html.append("{} {}".format(folbl, fol_pag))
                    else:
                        html.append("{} pp.".format(folbl))
                if vors_vorne != "":
                    if len(html) == 0:
                        html.append(vors_vorne)
                    else:
                        html.append(", {}".format(vors_vorne))
                    if vors_hinten != "":
                        html.append("-{}".format(vors_hinten))
                elif vors_hinten != "":
                    if len(html) == 0:
                        html.append(vors_hinten)
                    else:
                        html.append(", {}".format(vors_hinten))
                if col != "":
                    if len(html) != 0: html.append(" ")
                    html.append("{} cols".format(col))
                    if col_breite != "":
                        html.append(" ({} mm wide)".format(col_breite))
                if zeilen != "":
                    if len(html) != 0: html.append(" ")
                    html.append("{} lines per page/column".format(zeilen))
                    # Check for zeilen bemerkungen
                    if sId in oZB:
                        zeilenbem = oZB[sId]
                        # Append to the above
                        html.append(" (note: {})".format(zeilenbem))

                # Look for comments
                if sId in oFF:
                    note = oFF[sId]
                    html.append(" Note: {}".format(note))

                # Combine into string
                sBack = "".join(html)
            except:
                msg = oErr.get_error_message()
                oErr.DoError("get_extent")
            return sBack

        def get_format(oHandschrift, oFormat):
            """Derive a Format description of the manuscript"""

            sBack = ""
            html = []
            oErr = ErrHandle()
            try:
                # use fields format, hs_breite, schrift_hoehe, schrift_breite
                format = oHandschrift.get("format", "")
                hs_breite = oHandschrift.get("hs_breite", "")
                schrift_hoehe = oHandschrift.get("schrift_hoehe", "")
                schrift_breite = oHandschrift.get("schrift_breite", "")
                sId = str(oHandschrift.get("id", ""))
                
                if hs_breite != "" and format != "":
                    html.append("Ms: {} x {} mm".format(format, hs_breite))
                if schrift_breite != "" and schrift_hoehe != "":
                    if "var" in schrift_breite or "var" in schrift_hoehe:
                        html.append("Text: variable")
                    else:
                        html.append("Text: {} x {} mm".format(schrift_hoehe, schrift_breite))

                # Look for comments
                if sId in oFormat:
                    note = oFormat[sId]
                    html.append(" Note: {}".format(note))

                # Combine into string
                sBack = " ".join(html)
            except:
                msg = oErr.get_error_message()
                oErr.DoError("get_format")
            return sBack

        def get_good_string(oSsg, field, second=None):
            """Get a good string from [oSsg]"""

            sBack = oSsg[field]
            if not sBack is None:
                if not second is None:
                    sBack = sBack[second]
                elif isinstance(sBack, int):
                    sBack = str(sBack)
            if sBack == None or sBack == "":
                sBack = "'-"
            elif sBack[0] == "=":
                sBack = "'{}".format(sBack)
            return sBack

        def get_edipp(oEdi):
            """Get a from until page range from table [editionen]"""

            sBack = ""
            oErr = ErrHandle()
            try:
                lst_seiten = str(oEdi.get("seiten", "")).split('.')
                von_rv = str(oEdi.get("seitenattr", ""))
                lst_bis = str(oEdi.get("bis", "")).split('.')
                bis_rv = str(oEdi.get("bisattr", ""))

                seiten = None if int(lst_seiten[0]) == 0 else lst_seiten[0]
                bis = None if int(lst_bis[0]) == 0 else lst_bis[0]

                html = []
                # Calculate from
                lst_from = []
                if von_rv != "": lst_from.append(von_rv)
                if not seiten is None: lst_from.append(seiten)
                sFrom = "".join(lst_from)

                # Calculate until
                lst_until = []
                if bis_rv != "": lst_until.append(bis_rv)
                if not bis is None: lst_until.append(bis)
                sUntil = "".join(lst_until)

                # Combine the two
                if sFrom == sUntil:
                    sBack = sFrom
                else:
                    sBack = "{}-{}".format(sFrom, sUntil)

            except:
                msg = oErr.get_error_message()
                oErr.DoError("get_locus")

            return sBack

        def get_locus(oInhalt):
            """Get a complete LOCUS string combining von_bis, von_rv and bis_f, bis_rv"""

            sBack = ""
            oErr = ErrHandle()
            oRom = RomanNumbers()
            try:
                lst_von_bis = str(oInhalt.get("von_bis", "")).split(".")
                von_rv = str(oInhalt.get("von_rv", ""))
                lst_bis_f = str(oInhalt.get("bis_f", "")).split(".")
                bis_rv = str(oInhalt.get("bis_rv", ""))

                von_bis = None if int(lst_von_bis[0]) == 0 else lst_von_bis[0]
                bis_f = None if int(lst_bis_f[0]) == 0 else lst_bis_f[0]

                # Treat negative numbers (see issue #532)
                if not von_bis is None and re.match(r'-\d+', von_bis):
                    order_num = int(von_bis)
                    if order_num < -110: order_num = -110
                    if order_num < 0:
                        # Add 110 + 1 and turn into romans
                        von_bis = oRom.intToRoman(order_num+110+1)
                if not bis_f is None and re.match(r'-\d+', bis_f):
                    order_num = int(bis_f)
                    if order_num < -110: order_num = -110
                    if order_num < 0:
                        # Add 110 + 1 and turn into romans
                        bis_f = oRom.intToRoman(order_num+110+1)

                html = []
                # Calculate from
                lst_from = []
                if von_rv != "": lst_from.append(von_rv)
                if not von_bis is None: lst_from.append(von_bis)
                sFrom = "".join(lst_from)

                # Calculate until
                lst_until = []
                if bis_rv != "": lst_until.append(bis_rv)
                if not bis_f is None: lst_until.append(bis_f)
                sUntil = "".join(lst_until)

                # Combine the two
                if sFrom == sUntil:
                    sBack = sFrom
                else:
                    sBack = "{}-{}".format(sFrom, sUntil)

            except:
                msg = oErr.get_error_message()
                oErr.DoError("get_locus")

            return sBack

        def get_manu_count(lst_inhalt, opera_id):
            """Count the number of times [opera_id] occurs in [oInhalt]"""

            count = 0
            oErr = ErrHandle()
            try:
                for oInhalt in lst_inhalt:
                    opera = oInhalt.get("opera")
                    if opera == opera_id:
                        count += 1
            except:
                msg = oErr.get_error_message()
                oErr.DoError("get_manu_count")

            return count

        def get_opera_signatures(oOpera, lst_notes, opera_passim, huwa_conv_sig):
            """Given the opera, get the signature(s) it points to in a list"""

            signaturesA = []
            oErr = ErrHandle()
            debug_level = 1
            try:
                # Get the opera ID
                opera_id = oOpera['id']
                # Get the signature(s)
                if bUseOperaPassim and opera_id in opera_passim:
                    # Get the relevant record
                    oOperaNew = opera_passim[opera_id]
                    # Look for clavis/frede/cppm
                    add_sig_to_list(signaturesA, oOperaNew.get("clavis"), "cl", "CPL {}")
                    add_sig_to_list(signaturesA, oOperaNew.get("frede"), "gr", "{}")
                    add_sig_to_list(signaturesA, oOperaNew.get("cppm"), "cl", "CPPM {}")

                    other = oOperaNew.get("abk", "")
                    if not other is None and other != "" and len(signaturesA) == 0:
                        # Check if we can convert this
                        bFound = False
                        number = ""
                        for item in huwa_conv_sig:
                            mask = item['mask']
                            huwa = item['huwa']
                            m = re.match(mask, other)
                            if m:
                                bFound = True
                                # Now get the number
                                if len(m.groups(0)) > 0:
                                    number = m.groups(0)[0]
                                    if huwa.count('#') > 1:
                                        iStop = 1
                                    
                                # Show what we are doing
                                if debug_level > 1:
                                    oErr.Status("HUWA=[{}] with number={} for other={}".format(huwa, number, other))
                                # Now we can break from the loop
                                break
                        if bFound:
                            # Look for clavis/frede/cppm
                            add_sig_replacing(signaturesA, item, "clavis", number, "cl")
                            add_sig_replacing(signaturesA, item, "gryson", number, "gr")
                            add_sig_replacing(signaturesA, item, "other", number, "ot")

                        elif bAcceptNewOtherSignatures:
                            # Check how long this [other] is
                            if len(other) > 10:
                                # Just add it to notes
                                lst_notes.append("abk: {}".format(other))
                            else:
                                # THis is 10 characters or below, so it could actually be a real code
                                signaturesA.append(dict(editype="ot", code=other))
                        else:
                            # Just add it to notes
                            lst_notes.append("abk: {}".format(other))
                    # Look for possible field [correction of abk]
                    for k, v in oOperaNew.items():
                        if "correction" in k and "abk" in k:
                            # There is a correction: put it into notes
                            lst_notes.append("{}: {}".format(k, v))
                else:
                    other = oOpera.get("abk", "")
                    if not other is None and other != "":
                        signaturesA.append(dict(editype="ot", code=other))
                    clavis = get_table_list(tables['clavis'], opera_id, "name")
                    add_sig_to_list(signaturesA, clavis, "cl", "CPL {}")

                    frede = get_table_list(tables['frede'], opera_id, "name")
                    add_sig_to_list(signaturesA, frede, "gr", "{}")

                    cppm = get_table_list(tables['cppm'], opera_id, "name")
                    add_sig_to_list(signaturesA, cppm, "cl", "CPPM {}")
                # What we return is the list in [signaturesA] - check if these exist already
                for item in signaturesA:
                    code = item['code']
                    editype = item['editype']
                    lst_sig = Signature.objects.filter(code=code, editype=editype).values('gold_id', 'gold__equal_id')
                    if not lst_sig is None and len(lst_sig) > 0:
                        obj_sig = lst_sig[0]
                        #gold = obj_sig.gold
                        #equal = gold.equal
                        item['gold'] = obj_sig['gold_id'] # gold.id
                        item['ssg'] = obj_sig['gold__equal_id'] # equal.id
            except:
                msg = oErr.get_error_message()
                oErr.DoError("get_opera_signatures")
                signaturesA = []

            return signaturesA

        def get_provenance(oHandschrift, oHerkunftBesitzer):
            oBack = {}
            sId = str(oHandschrift.get("id", ""))
            if sId in oHerkunftBesitzer:
                oBack = oHerkunftBesitzer[sId]
            return oBack

        def get_signatures(oSsg, editype):
            """Get a list of signatures as string from this object"""

            sBack = ""
            lSig = []
            for oSig in oSsg.get("signaturesA"):
                if oSig['editype'] == editype:
                    lSig.append(oSig['code'])

            sBack = json.dumps(lSig)
            return sBack

        def get_ssg(opera_id):
            """Given the opera ID, try to get the SSG as it has been imported already"""

            obj = None
            oErr = ErrHandle()
            try:
                external = EqualGoldExternal.objects.filter(externalid=opera_id).first()
                if external is None:
                    # Try to find SG
                    external = SermonGoldExternal.objects.filter(externalid=opera_id).first()
                    if not external is None:
                        obj = external.gold.equal
                else:
                    obj = external.equal
            except:
                msg = oErr.get_error_message()
                oErr.DoError("get_ssg")
            return obj

        def get_support(oHandschrift, oSupport, sMatBem):
            sBack = ""
            oErr = ErrHandle()
            try:
                material = oHandschrift.get("material")
                html = []
                if not material is None and material != "":
                    html.append(oSupport[str(material)])
                if not sMatBem is None and sMatBem != "":
                    html.append(sMatBem)
                sBack = "; ".join(html)
            except:
                msg = oErr.get_error_message()
                oErr.DoError("get_support")
            return sBack

        def lib_match(sHuwa, sLib):
            """"""
            bResult = False
            if sHuwa is None:
                bResult = (not sLib is None)
            elif sLib is None:
                bResult = False
            else:
                bResult = (sHuwa == sLib)
            return bResult

        # Initialize
        oHuwaLand = { "Algerien": "Algeria", "Australien": "Australia", "Belgien": "Belgium",
            "Deutschland": "Germany", "Dänemark": "Denmark", "Finnland": "Finland", "Frankreich": "France",
            "Irland": "Ireland", "Italien": "Italy", "Kanada": "Canada", "Luxembourg": "Luxembourg",
            "Niederlande": "Netherlands","Polen": "Poland", "Portugal": "Portugal", "Rumänien": "Romania",
            "Russland": "Russia","Schweden": "Sweden", "Schweiz": "Switzerland", "Slowakei": "Slovakia",
            "Spanien": "Spain", "Tschechien": "Czechia", "Tunesien": "Tunisia", "USA": "United States",
            "Ungarn": "Hungary", "United Kingdom": "United Kingdom", "Vaticano": "Vatican", "Österreich": "Austria" }
        oData = {}
        sData = ""
        bAcceptNewOtherSignatures = False

        # the huwa_tables depend on the import type
        if self.import_type == "manu":
            # Note that sermons use the tables 'inc' and 'des' for the incipit and explicit
            huwa_tables = ["opera", 'clavis', 'frede', 'cppm', 'des', 'inc', 'inms', 'autor_inms',
                'autor', 'autor_opera', 'datum_opera', 'inhalt', 'handschrift', 'bibliothek', 'ort', 'land',
                'material', 'tit', 'annus', 'ff_bem', 'format_bem', 'hs_notiz',
                'schreiber_name', 'schreiber', 'schrift_name', "schrift", 'herkunft_besitzer_name', 'herkunft_besitzer', 
                'fasc', 'faszikel', 'infine', 'mat_bem', 'saec_bem', 'siglen', 'siglen_edd', 'zeilen_bem', 'zweitsignatur'
                ]
        elif self.import_type == "edilit":
            # Tables needed to read the Editions and Literature for opera SSGs
            huwa_tables = ["literatur", "editionen", "verfasser", "reihe", "ort", "land", 'siglen', "siglen_edd",
                           "loci", "bloomfield", "schoenberger", "stegmueller", "huwa", "incipit", "desinit"]
        elif self.import_type == "opera":
            # Tables needed to process the information in BHL, BHM, THLL and RETR 
            huwa_tables = ["bhl", "bhm", "thll", "retr"]
        elif self.import_type == "retr":
            # Tables needed to process the information in RETR 
            huwa_tables = ["retr"]
        elif self.import_type == "indiculum":
            # Tables needed to process the information in RETR 
            huwa_tables = ["opera", 'desinit', 'incipit', "indiculum", "identifik"]
        elif self.import_type == "nebenwerk":
            # Tables needed to process the information in NEBENWERK 
            huwa_tables = ["opera", 'nebenwerk']
        else:
            huwa_tables = ["opera", 'clavis', 'frede', 'cppm', 'desinit', 'incipit',
                'autor', 'autor_opera', 'datum_opera']

        oErr = ErrHandle()
        table_info = {}
        author_info = {}
        existing_dict = {}
        sig_matching = {}
        bDoCounting = True
        bAddUnusedSermonFields = False
        bUseOperaPassim = True
        rHasNumber = re.compile(r'.*[0-9].*')
        rHashTag = re.compile(r'\#.*')

        count_manu_zero = 0     # Number of items linked to ZERO manuscripts
        count_manu_one = 0      # Number of items linked to just one manuscript
        count_manu_many_num = 0 # Number of items linked to many manuscripts - with number in ABK
        count_manu_many_oth = 0 # Number of items linked to many manuscripts - without number in ABK

        try:
            # (1) Read the Huwa to Passim author JSON
            lst_authors = self.read_authors()

            # (2) Read the Huwa inter-opera relations JSON
            lst_relations = self.read_relations()

            # (3) Get the author id for 'Undecided'
            undecided = Author.objects.filter(name__iexact="undecided").first()

            # (4) Read the HUWA db as tables
            table_info = self.read_huwa()

            # (5) Load the tables that we need
            tables = self.get_tables(table_info, huwa_tables)

            # (5b) Load the 'opera_passim' object, which is needed for correct Clavis / Frede / Cppm
            opera_passim = self.read_opera_passim()

            # (5c) Load the 'huwa_conv_sig' object: calculate Clavis/Frede/Cppm based on [abk]
            huwa_conv_sig = self.read_huwa_conv_sig()

            # What if we are reading Manuscript information?
            if self.import_type == "manu":
                # Make sure we have a more fitting download name
                self.downloadname = "huwa_manu"

                # Initialize counters
                count_manu = 0
                count_serm = 0

                # (5d) Make sure that the Scribes are in the right table and accessible by id
                schreiber_name = self.read_scribes(tables.get("schreiber_name"))

                # (5e) Make sure that the Scripts are in the right table and accessible by id
                schrift_name = self.read_scripts(tables.get("schrift_name"))

                # (6) Read the Huwa library information
                oLibraryInfo = self.read_libraries()
                oLibHuwaPassim = oLibraryInfo['huwapassim']
                oLibHuwaOnly = oLibraryInfo.get("huwaonly")
                oLibHuwaConv = oLibraryInfo.get("conversion")

                ## (6b) Read the Edilit information
                #oEdilitItems = self.read_huwa_edilit()

                # Read other HUWA info: annus = year of 'handschrift'
                oDates = {}
                for oAnnus in tables['annus']:
                    handschrift_id = str(oAnnus.get("handschrift"))
                    # The year (range) may only contain number + hyphen
                    annus_name = re.sub('[^0-9\-]', '', oAnnus.get("annus_name", ""))
                    # Add to dictionary
                    oDates[handschrift_id] = annus_name

                # Read other HUWA info: title of sermon(s)
                oTitles = {}
                for oTit in tables['tit']:
                    inhalt = str(oTit.get("inhalt"))
                    sTitle = oTit.get("tit_text", "")
                    oTitles[inhalt] = sTitle

                # Transform the Inhalt table into a dictionary around [handschrift]
                oInhaltHandschrift = {}
                oInhaltOpera = {}
                for oInhalt in tables['inhalt']:
                    # (1) process handschrift
                    handschrift_id = str(oInhalt.get("handschrift"))
                    if not handschrift_id in oInhaltHandschrift:
                        oInhaltHandschrift[handschrift_id] = []
                    # Add it
                    oInhaltHandschrift[handschrift_id].append(oInhalt)
                    # (2) Process opera
                    opera_id = str(oInhalt.get("opera"))
                    if not opera_id in oInhaltOpera:
                        oInhaltOpera[opera_id] = 0
                    # Add it
                    oInhaltOpera[opera_id] += 1

                # Process [fasc]
                oFascHandschrift = {}
                for oFasc in tables['fasc']:
                    handschrift_id = str(oFasc.get("handschrift"))
                    if not handschrift_id in oFascHandschrift:
                        oFascHandschrift[handschrift_id] = []
                    oFascHandschrift[handschrift_id].append(str(oFasc['fasc_name']))

                # Turn [faszikel] into a dictionary
                oFaszikels = {str(x['id']): x['faszikel_name'] for x in tables['faszikel']}

                # Turn [infine] into a dictionary
                oInfines = {str(x['id']): x['infine_text'] for x in tables['infine']}

                # Turn [mat_bem] into a dictionary
                oMatBemHandschrift = {str(x['handschrift']): x['name'] for x in tables['mat_bem']}

                # Turn [saec_bem] into a dictionary
                oSaecBemHandschrift = {}
                for oSaecBem in tables['saec_bem']:
                    handschrift_id = str(oSaecBem.get("handschrift"))
                    if not handschrift_id in oSaecBemHandschrift:
                        oSaecBemHandschrift[handschrift_id] = []
                    # Add the whole object there, with fields @name and @bemerkungen
                    oSaecBemHandschrift[handschrift_id].append(oSaecBem)

                # Turn [zeilen_bem] into a dictionary
                oZeilenBemHandschrift = {}
                for oZeilenBem in tables['zeilen_bem']:
                    handschrift_id = str(oZeilenBem.get("handschrift"))
                    if not handschrift_id in oZeilenBemHandschrift:
                        oZeilenBemHandschrift[handschrift_id] = []
                    # Add the whole object there, with fields @name and @bemerkungen
                    oZeilenBemHandschrift[handschrift_id].append(oZeilenBem)

                # Turn [zweitsignatur] into a dictionary
                oZweitSigHandschrift = {}
                for oZweitSig in tables['zweitsignatur']:
                    handschrift_id = str(oZweitSig.get("handschrift"))
                    if not handschrift_id in oZweitSigHandschrift:
                        oZweitSigHandschrift[handschrift_id] = []
                    # Add the whole object there, with fields @name and @bemerkungen
                    oZweitSigHandschrift[handschrift_id].append(oZweitSig)

                # Transform the ff_bem table into a dictionary around [handschrift]
                oFFbemHandschrift = {}
                for oBem in tables['ff_bem']:
                    handschrift_id = str(oBem.get("handschrift"))
                    oFFbemHandschrift[handschrift_id] = oBem['name']
                    bem = oBem['bemerkungen']
                    if not bem is None and bem != "":
                        oFFbemHandschrift[handschrift_id] = "{} ({})".format(oFFbemHandschrift[handschrift_id] , bem)

                # Transform the format_bem table into a dictionary around [handschrift]
                oFormatBemHandschrift = {}
                for oBem in tables['format_bem']:
                    handschrift_id = str(oBem.get("handschrift"))
                    oFormatBemHandschrift[handschrift_id] = oBem['name']
                    bem = oBem['bemerkungen']
                    if not bem is None and bem != "":
                        oFormatBemHandschrift[handschrift_id] = "{} ({})".format(oFormatBemHandschrift[handschrift_id] , bem)

                # Get the Herkunft tables sorted out
                oHerkunftBesitzerName = {}
                oHerkunftBesitzer = {}
                for oHBN in tables['herkunft_besitzer_name']:
                    region = oHBN.get('region', '')
                    name = oHBN.get('name', '')
                    ort_id = str(oHBN.get('ort', ''))
                    sId = str(oHBN.get("id"))
                    combi = {}
                    if not region is None and region != "":
                        combi['region'] = region
                    if not name is None and name != "":
                        combi['name'] = name
                    if ort_id != '0':
                        oLoc = get_city_land(ort_id, tables, oHuwaLand)
                        if 'city' in oLoc: combi['lcity'] = oLoc.get('city')
                        if 'country' in oLoc: combi['lcountry'] = oLoc.get('country')

                    oHerkunftBesitzerName[sId] = combi
                for oHB in tables['herkunft_besitzer']:
                    sId = str(oHB.get("handschrift"))
                    combi = {}
                    hbn_id = str(oHB.get('herkunft_besitzer_name', ''))
                    if hbn_id in oHerkunftBesitzerName:
                        combi['prov_loc'] = oHerkunftBesitzerName[hbn_id]
                    oldsig = oHB.get("altesignatur", "")
                    if oldsig != "": 
                        combi['prov_oldsig'] = oldsig
                    note = oHB.get("bemerkungen", "")
                    if note != "": 
                        combi['prov_note'] = note
                    oHerkunftBesitzer[sId] = combi

                # Transform the hs_notiz table into a dictionary around [handschrift]
                oNotizHandschrift = {}
                for oNotiz in tables['hs_notiz']:
                    handschrift_id = str(oNotiz.get("handschrift"))
                    bem = oNotiz.get('bemerkungen', "")
                    tekst = oNotiz.get('text', "")
                    lst_note = []
                    if bem != "":
                        lst_note.append(bem)
                    if tekst != "":
                        lst_note.append("Text: {}".format(tekst))
                    notes = "; ".join(lst_note)
                    if len(lst_note) > 0:
                        oNotizHandschrift[handschrift_id] = notes

                # Transform the [schreiber] table into a dictionary around [handschrift]
                oScribeHandschrift = {}
                for oScribe in tables['schreiber']:
                    handschrift_id = str(oScribe.get("handschrift"))
                    bem = oScribe.get('bemerkungen', "")
                    scr_id = str(oScribe.get("schreiber_name", ""))
                    # Check if there is an entry
                    if scr_id in schreiber_name:
                        # add it 
                        oScrBem = dict(name=schreiber_name[scr_id], note=bem)
                        oScribeHandschrift[handschrift_id] = oScrBem

                # Transform the [schrift] table into a dictionary around [handschrift]
                oScriptHandschrift = {}
                for oScript in tables['schrift']:
                    handschrift_id = str(oScript.get("handschrift"))
                    bem = oScript.get('bemerkungen', "")
                    sct_id = str(oScript.get("schrift_name", ""))
                    # Check if there is an entry
                    if sct_id in schrift_name:
                        # add it 
                        oScriptBem = dict(name=schrift_name[sct_id], note=bem)
                        oScriptHandschrift[handschrift_id] = oScriptBem

                # Transform the DES table into a dictionary around [inhalt]
                oInhaltDes = {}
                for oDes in tables['des']:
                    inhalt_id = str(oDes['inhalt'])
                    oInhaltDes[inhalt_id] = oDes['des_text']

                # Transform the INC table into a dictionary around [inhalt]
                oInhaltInc = {}
                for oInc in tables['inc']:
                    inhalt_id = str(oInc['inhalt'])
                    oInhaltInc[inhalt_id] = oInc['inc_text']

                # Change the materials into a dictionary
                oSupport = {}
                for oMat in tables['material']:
                    mat_name = oMat['material_name']
                    if not oMat is None and oMat != "":
                        oSupport[str(oMat['id'])] = mat_name

                # (7) Walk through the Manuscript tables: handschrift + inhalt
                count_manuscript = len(tables['handschrift'])
                # lst_manuscript = []
                lst_manu_string = []
                lst_manu_string.append('[')     # NOTE: this will be a simple [] JSON list, 
                                                #       which is what ManuscriptUploadJson is expecting!
                for idx, oHandschrift in enumerate(tables['handschrift']):
                    # Show where we are
                    if idx % 100 == 0:
                        oErr.Status("EqualGoldHuwaToJson manuscripts: {}/{}".format(idx+1, count_manuscript))

                    # Take over any information that should be
                    idno = oHandschrift.get("signatur", "")
                    handschrift_id = oHandschrift.get("id")
                    sHandschriftId = str(handschrift_id)

                    # If this [handschrift_id] has id '0', then skip it (see issue #532, responses CW)
                    if handschrift_id == 0:
                        # Skip this one, and continue with the next manuscript
                        continue

                    # NOTE: no need to supply [stype], since that must be set when reading the JSON
                    oManuscript = dict(id=idx+1, idno=idno, externals=[dict(externalid=handschrift_id, externaltype="huwop")],
                                       keywords = ['HUWA'], datasets = ['HUWA_manuscripts'],)
                    count_manu += 1

                    # Physical features of the manuscript:
                    # (1) Support = material
                    oManuscript['support'] = get_support(oInhaltHandschrift, oSupport, oMatBemHandschrift.get(sHandschriftId))
                    # (2) Extent: use fields fol_pag, folbl, vors_vorne, vors_hinten, col, col_breite, zeilen
                    oManuscript['extent'] = get_extent(oHandschrift, oFFbemHandschrift, oZeilenBemHandschrift)
                    # (3) Format: use fields format, hs_breite, schrift_hoehe, schrift_breite
                    oManuscript['format'] = get_format(oHandschrift, oFormatBemHandschrift)

                    # Start adding notes to Hanschrift
                    sNotes = oHandschrift.get("bemerkungen", "")
                    if sNotes != "": 
                        oManuscript['notes'] = sNotes

                    # Possibly add to the manuscript notes
                    if sHandschriftId in oNotizHandschrift:
                        notiz = oNotizHandschrift[sHandschriftId]
                        if notiz != "":
                            notes = oManuscript.get("notes")
                            if not notes is None and notes != "":
                                notes = "{}; {}".format(notes, notiz)
                            else:
                                notes = notiz
                            oManuscript['notes'] = notes

                    # See if we can do something with the dating
                    sDateRange = None
                    if sHandschriftId in oDates:
                        # Get the (more exact) date from this place
                        sDateRange = oDates.get(sHandschriftId).strip()
                    if sDateRange is None or sDateRange == "":
                        iSaeculum = oHandschrift.get("saeculum", -1)
                        if iSaeculum > 0:
                            # Get the date and do something with it
                            iYearStart = iSaeculum * 100
                            iYearEnd = iYearStart + 99
                            sDateRange = "{}-{}".format(iYearStart, iYearEnd)
                            # oManuscript['date'] = sDateRange
                    if not sDateRange is None and sDateRange != "":
                        oManuscript['date'] = sDateRange

                    # Possibly add Zweitsignatur
                    lst_zweits = oZweitSigHandschrift.get(sHandschriftId, [])
                    if len(lst_zweits) > 0:
                        lst_zwcombi = []
                        for oZweits in lst_zweits:
                            # Combine the name and the remark
                            bem = oZweits.get("bemerkungen", "")
                            sZweits = oZweits.get("name", "")
                            if bem == "":
                                lst_zwcombi.append(sZweits)
                            else:
                                lst_zwcombi.append("{} ({})".format(sZweits, bem))
                        # Combine into a semicolumn separated string
                        sCombi = "Old shelfmark(s): {}".format("; ".join(lst_zwcombi))
                        # Add as notes
                        notes = oManuscript.get("notes")
                        if not notes is None and notes != "":
                            notes = "{}; {}".format(notes, sCombi)
                        else:
                            notes = sCombi
                        oManuscript['notes'] = notes

                    # Figure out library and location
                    bibliothek_id = oHandschrift.get("bibliothek")
                    if not bibliothek_id is None:
                        lib_id = None

                        sBibliothekId = str(bibliothek_id)

                        # A library has been specified for this manuscript
                        if sBibliothekId in oLibHuwaPassim:
                            library_id = oLibHuwaPassim[str(bibliothek_id)]
                            library = Library.objects.filter(id=library_id).first()
                            lib_name = ""
                            lib_city = ""
                            lib_country = ""
                            if not library is None:
                                lib_name = library.name
                                if not library.lcity is None:
                                    lib_city = library.lcity.name
                                if not library.lcountry is None:
                                    lib_country = library.lcountry.name
                                lib_id = library.id
                        elif sBibliothekId in oLibHuwaOnly:
                            # This library is known in HUWA, but not in Passim: try to add it
                            oLibrary = oLibHuwaOnly[sBibliothekId]
                            # Always get the pre-defined details
                            lib_name = oLibrary.get("library", "")
                            lib_city = oLibrary.get("city", "")
                            lib_country = oLibrary.get("country", "")

                            if lib_name != "" and lib_city != "" and lib_country != "":
                                lib_id, lib_city, lib_country = get_or_create_library(bibliothek_id, lib_name, lib_city, lib_country)
                        else:
                            # Get the details of this library
                            oLibrary = get_library_info(bibliothek_id, tables)
                            # Always get the pre-defined details
                            lib_name = oLibrary.get("name", "")
                            lib_city = oLibrary.get("city", "")
                            lib_country = oLibrary.get("country", "")
                            if lib_country != "" and lib_country in oHuwaLand:
                                lib_country = oHuwaLand[lib_country]

                            # Check whether there is a conversion attempt in "lib_huwa_new-jan2023"
                            if lib_name != "" and lib_city != "":
                                for oConvert in oLibHuwaConv:
                                    # Get the passim data
                                    oPassim = oConvert.get("passim")
                                    pas_lib = oPassim.get("library")
                                    pas_country = oPassim.get("country")
                                    pas_city = oPassim.get("city")
                                    # Get the huwa data
                                    oHuwa = oConvert.get("huwa")
                                    huwa_lib = oHuwa.get("library")
                                    huwa_country = oHuwa.get("country")
                                    huwa_city = oHuwa.get("city")

                                    if lib_match(huwa_lib, lib_name) and lib_match(huwa_country, lib_country) and lib_match(huwa_city, lib_city):

                                        # Apply Possible corrections
                                        if not pas_lib is None: huwa_lib = pas_lib
                                        if not pas_country is None: huwa_country = pas_country
                                        if not pas_city is None: huwa_city = pas_city

                                        # Make sure we have a 'full match':
                                        if not huwa_lib is None and not huwa_country is None and not huwa_city is None:
                                            # We found a correction to look up in passim
                                            lib_id, lib_city, lib_country = get_or_create_library(bibliothek_id, lib_name, lib_city, huwa_country)
                                            break

                            # NOTE: do *NOT* attempt to add this library.
                            #       it requires manual correction

                        # Add this information in the Passim Manuscript object
                        oManuscript['library_id'] = lib_id
                        oManuscript['library'] = lib_name
                        oManuscript['lcity'] = lib_city
                        oManuscript['lcountry'] = lib_country

                        # Possibly process the correspondence between a HUWA library id and a Passim library id
                        if not lib_id is None:
                            pass

                    # Possibly add provenance
                    oManuscript['provenance'] = get_provenance(oHandschrift, oHerkunftBesitzer)

                    # Possible add scribe information
                    if sHandschriftId in oScribeHandschrift:
                        oManuscript['scribeinfo'] = oScribeHandschrift[sHandschriftId]

                    # Possible add script information
                    if sHandschriftId in oScriptHandschrift:
                        oManuscript['scriptinfo'] = oScriptHandschrift[sHandschriftId]

                    # Test on bibliothek = 2 (see issue #532)
                    if bibliothek_id == 2:
                        # Do not process this manuscript further
                        continue

                    # Other manuscript info: date
                    if sHandschriftId in oDates:
                        oManuscript['date'] = oDates[sHandschriftId]       
                        
                    # Manuscript codico info: faszikel
                    faszikel_name = oFaszikels.get(sHandschriftId)
                    codico_items = []
                    if not faszikel_name is None and faszikel_name != "":
                        codico_items.append("Faszikel {}".format(faszikel_name))
                    if sHandschriftId in oFascHandschrift:
                        sCombi = ", ".join(oFascHandschrift[sHandschriftId])
                        codico_items.append("Fasc {}".format(sCombi))
                    sCodicoName = ""
                    if len(codico_items) > 0:
                        sCodicoName = "; ".join(codico_items)
                    oManuscript['codico_name'] = sCodicoName

                    # Process Saec_Bem into codico_notes
                    codico_notes = []
                    oSaecBems = oSaecBemHandschrift.get(sHandschriftId)
                    if not oSaecBems is None:
                        for oSaecBem in oSaecBems:
                            sBem = oSaecBem.get("bemerkungen")
                            sName = oSaecBem.get("name")
                            lCombi = []
                            if not sName is None:
                                lCombi.append(sName)
                            if not sBem is None:
                                lCombi.append("({})".format(sBem))
                            codico_notes.append(" ".join(lCombi))
                        oManuscript['codico_notes'] = "; ".join(codico_notes)

                    # Get and walk through the contents of this Handschrift
                    lst_inhalt = oInhaltHandschrift.get(sHandschriftId, [])

                    # Sort the list on the basis of `von_bis` (see issue #532)
                    lst_inhalt = sorted(lst_inhalt, key=lambda x: x['von_bis'])
                    order = 1
                    lst_sermons = []
                    for idx, oInhalt in enumerate(lst_inhalt):
                        # Get the opera id
                        opera_id=oInhalt.get("opera")
                        sOperaId = str(opera_id)
                        inhalt_id = oInhalt.get("id")
                        # Get the Opera table
                        if opera_id in opera_passim:
                            oOpera = opera_passim[opera_id]
                            lst_notes = []

                            # Get all the necessary information of this Sermon Manifestation
                            lst_note = []
                            lst_note.append(oOpera.get("abk", ""))
                            lst_note.append(oOpera.get("opera_langname", ""))

                            lst_note.append(oInhalt.get("bemerkungen", ""))
                            lst_note.append(oOpera.get("bemerkungen", ""))
                            note = "\n".join([x for x in lst_note if x != ""])
                            # note = "\n".join(lst_note)

                            postscriptum = oInfines.get(str(inhalt_id), None)

                            ## Get a possible list of editions + siglen
                            #lst_sigle = oOperaSiglen.get(sOperaId, [])

                            # Convert locus information into a Passim locus string
                            locus = get_locus(oInhalt)
                            # Getting the author also works differently
                            author_id, author_name = get_author(oInhalt, tables, lst_authors)
                            # If this is none, try 'autor_opera'
                            if author_id is None:
                                huwa_autor_id = get_table_field(tables['autor_opera'], opera_id, "autor", "opera")
                                if huwa_autor_id != "": 

                                    # ================== DEBUGGING =========================
                                    if huwa_autor_id == 3:
                                        iStop = 1
                                    # ======================================================

                                    passim_author = self.get_passim_author(lst_authors, huwa_autor_id, tables['autor'])
                                    if not passim_author is None:
                                        author_id = passim_author.id
                                        author_name = passim_author.name

                            # Get the incipit
                            # incipit = get_table_field(tables['inc'], inhalt_id, "inc_text", sIdField="inhalt")
                            incipit = oInhaltInc.get(str(inhalt_id), "")
                            # Get the explicit
                            #explicit = get_table_field(tables['des'], inhalt_id, "des_text", sIdField="inhalt")
                            explicit = oInhaltDes.get(str(inhalt_id), "")

                            # Get signatures (or should that go via the SSG link, since they are automatic ones?)
                            signaturesA = get_opera_signatures(oOpera, lst_notes, opera_passim, huwa_conv_sig)
                            # Count the number of manuscripts in which this opera occurs
                            # manu_count = get_manu_count(tables['inhalt'], opera_id)
                            manu_count = oInhaltOpera.get(str(opera_id), 0)   
                            
                            # Get possible title
                            title = ""
                            # Look at the inhalt_id
                            sInhaltId = str(inhalt_id)
                            if sInhaltId in oTitles:
                                title = oTitles[sInhaltId]

                            # Combine into a Sermon record
                            # NOTE: no need to set [stype], since that must be set when reading the JSON
                            oSermon = dict(
                                type = "Plain", locus = locus, postscriptum=postscriptum,
                                author = author_name, author_id = author_id, 
                                title = title, incipit = incipit, explicit = explicit,
                                note = note, keywords = ['HUWA'], datasets = ['HUWA_sermons'],
                                signaturesA = signaturesA, manu_count=manu_count,
                                # siglen = lst_sigle,
                                externals=[dict(externalid=opera_id, externaltype="huwop")],
                                )
                            if bAddUnusedSermonFields:
                                # Add sermon fields that this routine does not fill in
                                oSermon['sectiontitle'] = None
                                # oSermon['postscriptum'] = None - is now filled above
                                oSermon['brefs'] = None
                                oSermon['quote'] = ""
                                oSermon['feast'] = ""
                                oSermon['additional'] = ""
                                oSermon['literature'] = ""
                                oSermon['ssglinks'] = ""
                                oSermon['keywordsU'] = []
                                oSermon['signaturesM'] = []
                                # oSermon['signaturesA'] = []
                            count_serm += 1

                            # Check if we can see what [ssglinks] are needed by looking at the opera_id
                            ssglinks = [x['equal_id'] for x in EqualGoldExternal.objects.filter(externaltype="huwop", externalid=opera_id).values("equal_id")]
                            if len(ssglinks) > 0:
                                oSermon['ssglinks'] = ssglinks

                            # Add the sermon to the list
                            lst_sermons.append(oSermon)
                            # Make sure we retain the correct order
                            order += 1

                    # Walk through the sermons and create correct msitems
                    lst_msitems = []
                    order = 1
                    for idx, oSermon in enumerate(lst_sermons):
                        if idx + 1 == len(lst_sermons):
                            sNext = ""
                        else:
                            sNext = order + 1
                        oMsItem = dict(
                            order = order, parent = "", firstchild = "", next = sNext, sermon = oSermon
                            )
                        lst_msitems.append(oMsItem)

                        order += 1
                    # Add the msitem list to the manuscript
                    oManuscript['msitems'] = lst_msitems

                    # Add this to the list of Manuscripts
                    # lst_manuscript.append(oManuscript)

                    # Serialize the Manuscript into JSON
                    sComma = "" if idx + 1 >= count_manuscript else ","
                    lst_manu_string.append("{}{}".format(json.dumps(oManuscript, indent=2), sComma))

                # Check the latest object, that it doesn't end with a comma
                sManuLatest = lst_manu_string[-1]
                if sManuLatest[-1] == ",":
                    # Remove that comma
                    sManuLatest = sManuLatest[:-1]
                    lst_manu_string[-1] = sManuLatest
                # (11) combine the sections into one object
                # oData['manuscripts'] = lst_manuscript
                lst_manu_string.append("]")

                # Provide the counts in the log
                print("EqualGoldHuwaToJson MANU counts: {} manuscripts, {} sermons".format(count_manu, count_serm))

            elif self.import_type == "edilit":
                # Make sure we have a more fitting download name
                self.downloadname = "huwa_edilit"

                # (5d) Make sure that the Editions are in the right table and accessible by id
                editionen = tables.get("editionen")

                lst_specific = [
                    {'table': 'bloomfield', 
                     'author': {'full': 'Bloomfield, Morton W.', 'name': 'Bloomfield', 'firstname': 'Morton W.'}, 
                     'pp_field': 'pp',
                     'title': 'Incipits of Latin works on the virtues and vices, 1100-1500 A.D.',
                     'year': '1979', 'location': 'Cambridge, MA'},
                    {'table': 'schoenberger', 
                     'author': {'full': 'Schönberger, R. and Kible, B. (eds.)', 'name': 'Schönberger', 'firstname': 'R.'},  
                     'pp_field': 'pp',
                     'title': 'Repertorium edierter Texte des Mittelalters aus dem Bereich der Philosophie und angrenzender Gebiete',
                     'year': '1994', 'location': 'Berlin'},
                    {'table': 'stegmueller', 
                     'author': {'full': 'Stegmüller, F.', 'name': 'Stegmüller', 'firstname': 'F.'},  
                     'pp_field': 'pp',
                     'title': 'Repertorium Biblicum Medii Aevi',
                     'year': '1950-1980', 'location': 'Madrid'},
                    {'table': 'huwa', 'author': {'full': 'HUWA', 'name': 'HUWA'},  'pp_field': 'title'},
                    ]

                # Transform tables into dictionaries: literatur, reihe, ort, land, verfasser
                oLiteratur = {str(x['id']):x for x in tables['literatur']}
                oReihe = { str(x['id']):x for x in tables['reihe']}
                oOrt = { str(x['id']):x for x in tables['ort']}
                oLand = { str(x['id']):x for x in tables['land']}
                oVerfasser = { str(x['id']):x for x in tables['verfasser']}
                oIncipit = { str(x['id']):x['incipit_text'] for x in tables['incipit']}
                oExplicit = { str(x['id']):x['desinit_text'] for x in tables['desinit']}

                # Turn [siglen] into a dictionary, centered on editionen id
                oSiglenEdition = {}
                for oSiglen in tables['siglen']:
                    editionen_id = str(oSiglen.get("editionen"))
                    if not editionen_id in oSiglenEdition:
                        oSiglenEdition[editionen_id] = []
                    # Add the whole object there, with fields @name and @bemerkungen and @handschrift
                    oSiglenEdition[editionen_id].append(oSiglen)

                # Process [siglen_edd]
                oSiglenEddItems = {}
                for oSiglenEdd in tables['siglen_edd']:
                    editionen_id = str(oSiglenEdd.get("editionen"))
                    if not editionen_id in oSiglenEddItems:
                        oSiglenEddItems[editionen_id] = []
                    # Add the whole object there, with fields @name and @bemerkungen
                    oSiglenEddItems[editionen_id].append(oSiglenEdd)

                # Start creating a list of edition literature
                lst_ssg_edi = []

                # Process each edition
                count_edilit = len(editionen)
                for idx, edition in enumerate(editionen):
                    # Show where we are
                    if idx % 100 == 0:
                        oErr.Status("EqualGoldHuwaToJson edilit: {}/{}".format(idx+1, count_edilit))

                    # at least get the opera id
                    opera_id = edition.get("opera")
                    edition_id = edition.get("id")

                    # =========== DEBUG ====================
                    if opera_id == 38:
                        iStop = 1
                    # ======================================

                    # Start getting all needed information for this edition
                    oEdition = dict(opera=opera_id, edition=edition_id)
                    pp = get_edipp(edition)
                    if not pp is None and pp != "":
                        oEdition['pp'] = pp
                    # Also get all separate parts
                    oPages = dict(seiten=edition.get("seiten"), seitenattr=edition.get("seitenattr"),
                                  bis=edition.get("bis"), bisattr=edition.get("bisattr"),
                                  titel=edition.get("titel"))
                    oEdition['pages'] = oPages
                    # Find corresponding literature
                    literatur_id = edition.get('literatur')
                    if not literatur_id is None and literatur_id > 0:
                        # Indicate which table is being used
                        oEdition['huwaid'] = literatur_id
                        oEdition['huwatable'] = "literatur"

                        # Get the information from the literatur table
                        literatur = oLiteratur.get(str(literatur_id))
                        # If possible get a title from here
                        literaturtitel = literatur.get("titel")
                        if not literaturtitel is None and literaturtitel != "":
                            oEdition['literaturtitel'] = literaturtitel

                        # Get from here: jahr, band
                        jahr = literatur.get("jahr")
                        band = literatur.get("band")
                        if not jahr is None and jahr != "": oEdition['year'] = jahr
                        if not band is None and band != "": oEdition['band'] = band

                        # Calculate the 'ort' from here
                        oLoc = get_ort(literatur.get("ort"), oOrt, oLand, oHuwaLand)
                        if not oLoc is None:
                            oEdition['location'] = copy.copy(oLoc)

                        # Find corresponding [reihe]
                        reihe_id = literatur.get("reihe")
                        if not reihe_id is None:
                            reihe = oReihe.get(str(reihe_id))
                            reihetitel = reihe.get("reihetitel")
                            reihekurz = reihe.get("reihekurz")
                            if not reihetitel is None and reihetitel != "": oEdition['reihetitel'] = reihetitel
                            if not reihekurz is None and reihekurz != "": oEdition['reihekurz'] = reihekurz
                        # Look for the verfasser(author)
                        verfasser_id = literatur.get("verfasser")
                        if not verfasser_id is None:
                            verfasser = oVerfasser.get(str(verfasser_id))
                            if not verfasser is None:
                                author = []
                                name = verfasser.get("name")
                                vorname = verfasser.get("vorname")
                                if not name is None and name != "":
                                    author.append(name.strip())
                                if not vorname is None and vorname != "":
                                    author.append(vorname.strip())
                                if len(author) > 0:
                                    oEdition['author'] = dict(full=", ".join(author), name=name)
                                    if not vorname is None and vorname != "":
                                        oEdition['author']['firstname'] = vorname
                        # Check if this 'edition' has any items in 'loci'
                        lst_loci = []
                        for oItem in tables['loci']:
                            if oItem.get("editionen") == edition_id:
                                # Need to add a LOCI item
                                oLoci = dict(page=oItem.get('seite_col'), line=oItem.get("zeile"))
                                cap = oItem.get("cap")
                                if not cap is None:
                                    oLoci['cap'] = cap
                                # Possibly add incipit and/or explicit
                                incipit = oIncipit[str(oItem.get("incipit"))]
                                explicit = oExplicit[str(oItem.get("desinit"))]
                                if not incipit is None and incipit != "":
                                    oLoci['incipit'] = incipit
                                if not explicit is None and explicit != "":
                                    oLoci['explicit'] = explicit

                                # Add this to the list
                                lst_loci.append(oLoci)
                        # Do we have a list?
                        if len(lst_loci) > 0:
                            # Yes, there is a list: add it to this edition
                            oEdition['loci'] = copy.copy(lst_loci)

                        # Is there a [sigle]?
                        sEditionId = str(edition_id)
                        lst_siglen = []
                        # Check for [siglen]
                        if sEditionId in oSiglenEdition:
                            # Get the list
                            lst_siglen_edi = oSiglenEdition[sEditionId]
                            # Process this list
                            for oSiglenItem in lst_siglen_edi:
                                # Retrieve all important elements
                                handschrift_id = oSiglenItem.get("handschrift")
                                sigle = oSiglenItem.get("sigle")
                                bem = oSiglenItem.get("bemerkungen")
                                # Create and add an appropriate item to [lst_siglen]
                                oItem = dict(handschrift=handschrift_id, sigle=sigle)
                                if not bem is None and bem != "": oItem['bem'] = bem
                                lst_siglen.append(oItem)
                        if len(lst_siglen) > 0:
                            oEdition['siglen'] = lst_siglen

                        # Check for [siglen_edd]
                        lst_siglen_edd = []
                        if sEditionId in oSiglenEddItems:
                            lst_siglen_edd_item = oSiglenEddItems[sEditionId]
                            for oSiglenEdd in lst_siglen_edd_item:
                                siglen_literatur = oSiglenEdd.get("literatur_x")
                                sigle = oSiglenEdd.get("sigle")
                                bem = oSiglenEdd.get("bemerkungen")
                                oItem = dict(literatur=siglen_literatur, sigle=sigle)
                                if not bem is None and bem != "": oItem['bem'] = bem
                                lst_siglen_edd.append(oItem)
                        if len(lst_siglen_edd) > 0:
                            oEdition['siglen_edd'] = lst_siglen_edd

                    # Add this item to the list
                    lst_ssg_edi.append(oEdition)

                    # Look at other tables via the opera id
                    if not opera_id is None and opera_id > 0:

                        # Look for schoenberger, bloomfield and stegmueller and huwa
                        for oSpecific in lst_specific:
                            table_name = oSpecific.get("table")
                            pp_field = oSpecific.get("pp_field")
                            author = oSpecific.get("author")
                            title = oSpecific.get("title")
                            location = oSpecific.get("location")
                            year = oSpecific.get("year")
                            for oItem in tables[table_name]:
                                if oItem.get('opera') == opera_id:
                                    # Add this one
                                    oEdition = dict(opera=opera_id)
                                    # Indicate which table is being used
                                    oEdition['huwaid'] = oItem.get("id")
                                    oEdition['huwatable'] = table_name
                                    # Fill in the details from the [oItem]
                                    name_field = oItem.get("name")
                                    oEdition[pp_field] = name_field

                                    # Fill in details from above
                                    oEdition['author'] = copy.copy(author)
                                    if not title is None: oEdition['title'] = copy.copy(title)
                                    if not location is None: oEdition['location'] = copy.copy(location)
                                    if not year is None: oEdition['year'] = copy.copy(year)

                                    # Add this item to the list
                                    lst_ssg_edi.append(oEdition)

                # Show the amount of stuff that has been gathered
                count = len(lst_ssg_edi)
                oErr.Status("EqualGoldHuwaToJson EDILIT count: {}".format(count))

            elif self.import_type == "ssg":
                # (8) Walk through the table with AF+Sermon information
                signature_dict = {}     # Each entry contains a list of OPERA ids that have this signature
                lst_opera = []
                count_opera = len(tables['opera'])
                for idx, oOpera in enumerate(tables['opera']):
                    opera_id = oOpera['id']
                    # Take over any information that should
                    oSsg = dict(id=idx+1, opera=opera_id)

                    # Show where we are
                    if idx % 100 == 0:
                        oErr.Status("EqualGoldHuwaToJson opera's: {}/{}".format(idx+1, count_opera))

                    # Get the signature(s)
                    signaturesA = []
                    lst_notes = []
                    if bUseOperaPassim and opera_id in opera_passim:
                        # Get the relevant record
                        oOperaNew = opera_passim[opera_id]
                        # Look for clavis/frede/cppm
                        add_sig_to_list(signaturesA, oOperaNew.get("clavis"), "cl", "CPL {}")
                        add_sig_to_list(signaturesA, oOperaNew.get("frede"), "gr", "{}")
                        add_sig_to_list(signaturesA, oOperaNew.get("cppm"), "cl", "CPPM {}")

                        other = oOperaNew.get("abk", "")
                        if not other is None and other != "" and len(signaturesA) == 0:
                            # Check if we can convert this
                            bFound = False
                            number = ""
                            for item in huwa_conv_sig:
                                mask = item['mask']
                                huwa = item['huwa']
                                m = re.match(mask, other)
                                if m:
                                    bFound = True
                                    # Now get the number
                                    if len(m.groups(0)) > 0:
                                        number = m.groups(0)[0]
                                        if huwa.count('#') > 1:
                                            iStop = 1
                                    
                                    # Show what we are doing
                                    oErr.Status("HUWA=[{}] with number={} for other={}".format(huwa, number, other))
                                    # Now we can break from the loop
                                    break
                            if bFound:
                                # Look for clavis/frede/cppm
                                add_sig_replacing(signaturesA, item, "clavis", number, "cl")
                                add_sig_replacing(signaturesA, item, "gryson", number, "gr")
                                add_sig_replacing(signaturesA, item, "other", number, "ot")

                            elif bAcceptNewOtherSignatures:
                                # Check how long this [other] is
                                if len(other) > 10:
                                    # Just add it to notes
                                    lst_notes.append("abk: {}".format(other))
                                else:
                                    # THis is 10 characters or below, so it could actually be a real code
                                    signaturesA.append(dict(editype="ot", code=other))
                            else:
                                # Just add it to notes
                                lst_notes.append("abk: {}".format(other))
                        # Look for possible field [correction of abk]
                        for k, v in oOperaNew.items():
                            if "correction" in k and "abk" in k:
                                # There is a correction: put it into notes
                                lst_notes.append("{}: {}".format(k, v))
                    else:
                        other = oOpera.get("abk", "")
                        if not other is None and other != "":
                            signaturesA.append(dict(editype="ot", code=other))
                        clavis = get_table_list(tables['clavis'], opera_id, "name")
                        add_sig_to_list(signaturesA, clavis, "cl", "CPL {}")

                        frede = get_table_list(tables['frede'], opera_id, "name")
                        add_sig_to_list(signaturesA, frede, "gr", "{}")

                        cppm = get_table_list(tables['cppm'], opera_id, "name")
                        add_sig_to_list(signaturesA, cppm, "cl", "CPPM {}")

                    oSsg['signaturesA'] = signaturesA
                    # Process the signatures in the [signature_dict]
                    add_sig_to_dict(signaturesA, signature_dict, opera_id)

                    # Get the Incipit and the Explicit
                    oSsg['incipit'] = get_table_field(tables['incipit'], int(oOpera.get('incipit')), "incipit_text")
                    oSsg['explicit'] = get_table_field(tables['desinit'], int(oOpera.get('desinit')), "desinit_text")

                    # Make good notes for further processing
                    oSsg['note_langname'] = oOpera.get("opera_langname","")
                    remarks = oOpera.get("bemerkungen", "")
                    if remarks != "": lst_notes.append("Remarks: {}".format(remarks))
                    oSsg['notes'] = "\n".join(lst_notes)

                    # Get to the [datum_opera]
                    oSsg['date_estimate'] = get_table_field(tables['datum_opera'], opera_id, "datum", "opera")

                    # Get the *AUTHOR* (obligatory) for this entry
                    passim_author = undecided
                    huwa_autor_id = get_table_field(tables['autor_opera'], opera_id, "autor", "opera")
                    if huwa_autor_id != "": 
                        passim_author = self.get_passim_author(lst_authors, huwa_autor_id, tables['autor'])
                        if passim_author is None:
                            # What to do now?
                            passim_author = undecided
                    oSsg['author'] = dict(id=passim_author.id, name= passim_author.name)

                    if bDoCounting:
                        # Check if the [abq] field contains a number or not
                        bAbqHasNumber = False
                        if rHasNumber.match(other): bAbqHasNumber = True

                        # Get the number of manuscripts linked to this particular opera entry
                        oSsg['manuscripts'] = get_table_fk_count(tables['inhalt'], opera_id, "opera")
                        manu_type = "-"
                        if oSsg['manuscripts'] == 0:
                            count_manu_zero += 1
                            manu_type = "zero_links" # "zero links"
                        elif oSsg['manuscripts'] == 1:
                            count_manu_one += 1
                            manu_type = "one_link" # "one link"
                        elif oSsg['manuscripts'] > 1:
                            if bAbqHasNumber:
                                count_manu_many_num += 1
                                manu_type = "many_links_ABK_num" # "many links ABK has number"
                            else:
                                count_manu_many_oth += 1
                                manu_type = "many_links_ABK_txt" # "many links ABK text only"
                        oSsg['manu_type'] = manu_type

                        # Check if there already is a SSG with the inc/expl
                        qs = EqualGold.objects.filter(incipit__iexact=oSsg['incipit'], explicit__iexact=oSsg['explicit'])
                        count = qs.count()
                        if count == 0:
                            existing_ssg = dict(id=None, type="ssgmN: no inc/exp match")
                            add_existing("ssgmN")
                        elif count == 1:
                            # This must be a match
                            obj = qs.first()
                            existing_ssg = dict(id=obj.id, code=obj.code, type="ssgmF: full inc/exp match")
                            add_existing("ssgmF")
                        elif count > 1 and (oSsg['incipit'] == "" or oSsg['explicit'] == ""):
                            existing_ssg = dict(id=None, type="ssgmE: empty inc or exp")
                            add_existing("ssgmE")
                        else:
                            # Check further on the author
                            obj = qs.filter(author=passim_author).first()
                            if obj is None:
                                # Found matching inc/exp, but not a matching author
                                existing_ssg = [dict(id=x.id, code=x.code, type="ssgmAM: author mismatch") for x in qs]
                                add_existing("ssgmAM")
                            else:
                                existing_ssg = dict(id=obj.id, code=obj.code, type="ssgmFA: full inc/exp/author match")
                                add_existing("ssgmFA")
                        oSsg['existing_ssg'] = existing_ssg

                        same_sig_ssgs = []
                        if len(signaturesA) > 0:
                            # Build a Q-expression
                            expr = ( Q(code__iexact=signaturesA[0]['code']) & Q(editype=signaturesA[0]['editype']) )
                            for oSig in signaturesA[1:]:
                                expr |= ( Q(code__iexact=oSig['code']) & Q(editype=oSig['editype']) )
                        
                            # Get a list of signature id's
                            sig_ids = [x['id'] for x in Signature.objects.filter(expr).values('id')]

                            if len(sig_ids) > 0:
                                # Check if there already is a SSG with one of the signatures in the list
                                qs = EqualGold.objects.filter(equal_goldsermons__goldsignatures__id__in=sig_ids).distinct().values('id')
                                # same_sig_ssgs = qs.count()
                                # Better: give a list of SSG ids with the same sigs
                                same_sig_ssgs = [x['id'] for x in qs]

                        # Add the results of the SSG match
                        oSsg['same_sig_ssgs'] = same_sig_ssgs

                    # Add this to the list of SSGs
                    lst_opera.append(oSsg)

                # (9) Process the inter-opera relations 
                lst_opera_rel = []
                oRelationship = {x['rel_id']:x  for x in EqualGoldHuwaToJson.relationships }
                count_rel = len(lst_relations)
                for idx, oRel in enumerate(lst_relations):
                    # Show where we are
                    if idx % 100 == 0:
                        oErr.Status("EqualGoldHuwaToJson relations: {}/{}".format(idx+1, count_rel))

                    opera_src = oRel.get('opera_src')
                    opera_dst = oRel.get('opera_dst')
                    rel_id = oRel.get('rel_id')

                    # Make sure that the destination always is a list
                    opera_dst = [ opera_dst ] if isinstance(opera_dst, int) else opera_dst

                    # Get the row of this relation
                    oRel = oRelationship[rel_id]
                    linktypes = oRel.get("linktypes", [])
                    spectypes = oRel.get("spectypes", [])
                    bDirectional = (oRel.get("dir") == "yes")

                    # If this relation does *NOT* contain a linktype, then we cannot process it!!!
                    if len(linktypes) > 0:

                        # Start creating this opera relation
                        for dst in opera_dst:
                            for linktype in linktypes:
                                oOperaRel = dict(src=opera_src, dst=dst)
                                oReverse = None
                                if len(spectypes) == 0:
                                    oOperaRel['linktype'] = linktype
                                elif bDirectional and len(spectypes) > 1:
                                    oReverse = dict(src=dst, dst=opera_src)
                                    oOperaRel['linktype'] = linktype
                                    oOperaRel['spectype'] = spectypes[0]
                                    oReverse['linktype'] = linktype
                                    oReverse['spectype'] = spectypes[1]
                                    if rel_id == 11:
                                        # Signal excerpt
                                        oOperaRel['keyword'] = 'excerpt'
                                        oReverse['keyword'] = 'excerpt'
                                else:
                                    oOperaRel['linktype'] = linktype
                                    oOperaRel['spectype'] = spectypes[0]
                                # Add items to list
                                lst_opera_rel.append(oOperaRel)
                                if not oReverse is None:
                                    lst_opera_rel.append(oReverse)
                    else:
                        # Show that we are skipping this relation
                        msg = "download HUWA json: skip rel[{}] src={} to dst={} (no linktype)".format(rel_id, opera_src, str(opera_dst))
                        oErr.Status(msg)

                # (10) Calculate the signature status (see issue #533)
                for idx, oOperaSsg in enumerate(lst_opera):
                    sig_status = "unknown"
                    # Get the opera signatures
                    signaturesA = ["{}: {}".format(x['editype'], x['code']) for x in oOperaSsg['signaturesA'] ]

                    # Get matching existing Passim SSG/AFs via these signature(s)
                    same_sig_ssgs = oOperaSsg['same_sig_ssgs']

                    if len(same_sig_ssgs) == 0:
                        # There are no matching existing Passim SSGs
                        if len(signaturesA) == 0:
                            sig_status = "opera_ssg_0_0"
                        else:
                            sig_status = "opera_ssg_1_0"
                    elif len(signaturesA) == 0:
                        # There are no Opera signatures, but there are 
                        sig_status = "opera_ssg_0_1"
                    else:
                        # Get the signatures of the Passim SSG
                        signaturesP = [ "{}: {}".format(x.editype, x.code) for x in Signature.objects.filter(gold__equal__id__in=same_sig_ssgs) ]
                        count = 0
                        for sigA in signaturesA:
                            if sigA in signaturesP:
                                count += 1
                        if len(signaturesA) == len(signaturesP) and count == len(signaturesA):
                            # There is a full 1-1 match between Opara and Passim signatures
                            sig_status = "opera_ssg_1_1"
                        else:
                            if count == 0:
                                sig_status = "opera_ssg_0_n"
                            elif count == len(signaturesA):
                                # everything of Opera is in Passim, but Passim has more
                                sig_status = "opera_ssg_1_n"
                            else:
                                # There is an overlap between opera/passim signatures > 1
                                # but the number of Opera and Passim signatures is not entirely equal
                                sig_status = "opera_ssg_n_1"
                    if bDoCounting:
                        if not sig_status in sig_matching:
                            sig_matching[sig_status] = 0
                        sig_matching[sig_status] += 1

                    # Save the sig_status                
                    oOperaSsg['existing_ssg']['sig_status'] = sig_status

                # (11) combine the sections into one object
                oData['operas'] = lst_opera
                oData['opera_relations'] = lst_opera_rel
                oData['sig_dict'] = signature_dict

            elif self.import_type == "opera":
                # Make sure we have a more fitting download name
                self.downloadname = "huwa_bhlbhm"

                # This is the processing of BHL, BHM, THLL and RETR
                lst_specific = [
                    { "table": "bhl",  "prepend": "BHL", "editype": "cl"}, 
                    { "table": "bhm",  "prepend": "BHM", "editype": "ot"}, 
                    { "table": "thll", "prepend": "TLL", "editype": "ot"}
                    ]

                # Get to the proper project
                project = Project2.objects.filter(name__icontains="huwa").first()
                # Create a list for gold and super, so that they can be added to datasets
                lst_gold = []
                lst_super = []
                lst_bhlbhm = []
                lst_skip = []
                profile = Profile.get_user_profile(self.request.user.username)

                # Walk all the BHL, BHM, THLL
                for oInfo in lst_specific:
                    # Get the name of the table and the prepend information
                    sSigTableName = oInfo.get("table")
                    prepend = oInfo.get("prepend")
                    editype = oInfo.get("editype")

                    # Load this table
                    lst_sigtable = tables[sSigTableName]
                    # Walk all the items in this table
                    for oSigItem in lst_sigtable:
                        # Get the opera and the name
                        opera_id = oSigItem.get("opera")
                        sSigName = "{} {}".format(prepend, oSigItem.get("name") )

                        if sSigName == "BHL 793":
                            iStop = 4

                        # Find the SermonGold entry (if existing)
                        equal = None
                        gold = None
                        sig = None
                        bFound = False
                        for gold in SermonGold.objects.filter(goldexternals__externalid=opera_id):
                            # Take over this equal
                            equal =gold.equal
                            # Double check if the signature already occurs in any of these
                            bFound = False
                            for sig in Signature.objects.filter(gold=gold, editype=editype):
                                if sig.code.lower() == sSigName.lower():
                                    # Get out of the lower loop
                                    bFound = True
                                    break
                            if bFound:
                                # Get out of the main loop
                                break

                        # Has a combination of Gold + Signature been found?
                        if not bFound:
                            # Create a SG pointing to the right SSG
                            if equal is None:
                                equal = EqualGold.objects.filter(equalexternals__externalid=opera_id).first()
                            gold = SermonGold.objects.create(equal=equal)
                            if not equal is None:
                                # Take over author, incipit, explicit
                                gold.incipit = equal.incipit
                                gold.explicit = equal.explicit
                                gold.author = equal.author
                                gold.save()
                            else:
                                # Create an SSG for this Gold too??
                                # NO! There's no author/inc/exp, so no SSG can be created
                                pass
                            # Create a Signature tied to this Gold
                            sig = Signature.objects.create(code=sSigName, editype=editype, gold=gold)                           
                            # Make sure the Gold is properly tied to the opera in SermonGoldExternal
                            obj = SermonGoldExternal.objects.filter(externalid=opera_id, externaltype="huwop", gold=gold).first()
                            if obj is None:
                                obj = SermonGoldExternal.objects.create(externalid=opera_id, externaltype="huwop", gold=gold)
                            # Make sure the gold is tied to the proper Dataset of gold imports
                            lst_gold.append(gold)
                            lst_bhlbhm.append(dict(opera=opera_id, gold=gold.id, signature=sSigName, editype=editype))
                        elif sig is None and not gold is None:
                            # There already is a SG, but it doesn't yet have the new signature
                            sig = Signature.objects.create(code=sSigName, editype=editype, gold=gold)                           
                            # Make sure the Gold is properly tied to the opera in SermonGoldExternal
                            obj = SermonGoldExternal.objects.filter(externalid=opera_id, externaltype="huwop", gold=gold).first()
                            if obj is None:
                                obj = SermonGoldExternal.objects.create(externalid=opera_id, externaltype="huwop", gold=gold)
                            # Make sure the gold is tied to the proper Dataset of gold imports
                            lst_gold.append(gold)
                            lst_bhlbhm.append(dict(opera=opera_id, gold=gold.id, signature=sSigName, editype=editype))
                        else:
                            # There is no 
                            # The information is already known - no further action needed
                            iSkip = 3

                        # Find the EqualGold entry (if existing)
                        qs_ssg = EqualGold.objects.filter(equalexternals__externalid=opera_id)
                        if equal is None:
                            # Double check if no SG has been found too
                            if gold is None:
                                # No SG has been found - it is not possible to add the information!
                                oSkip = dict(signature=sSigName, opera=opera_id, action="skip", reason="No SSG and no SG yet")
                                lst_bhlbhm.append(oSkip)
                            else:
                                # Check if there is a signature already
                                sig = Signature.objects.filter(code=sSigName, editype=editype, gold=gold).first()
                                if sig is None:
                                    # There already is a SG, but it doesn't yet have the new signature
                                    sig = Signature.objects.create(code=sSigName, editype=editype, gold=gold)                           
                                    # Make sure the Gold is properly tied to the opera in SermonGoldExternal
                                    obj = SermonGoldExternal.objects.filter(externalid=opera_id, externaltype="huwop", gold=gold).first()
                                    if obj is None:
                                        obj = SermonGoldExternal.objects.create(externalid=opera_id, externaltype="huwop", gold=gold)
                                    # Make sure the gold is tied to the proper Dataset of gold imports
                                    lst_gold.append(gold)
                                    lst_bhlbhm.append(dict(opera=opera_id, gold=gold.id, signature=sSigName, editype=editype))
                                    # End then the SSG should be created too - on the basis of 
                                    equal = EqualGold.objects.create()

                                    # Then tie the SG to the SSG
                                    gold.equal = equal
                                    gold.save()
                        elif qs_ssg.count() == 0:
                            # There is an SSG tied to the SG, but none has been tied to the opera_id yet
                            # So create a new SG based on the 
                            pass
                        else:
                            # We have both an SSG tied to the SG already, and we have SSGs tied to the opera id
                            for ssg in qs_ssg:
                                # Double check if the signature already occurs in any of these
                                bFound = False
                                equal = ssg
                                for sig in Signature.objects.filter(gold__equal=ssg, editype=editype):
                                    if sig.code.lower() == sSigName.lower():
                                        bFound = True
                                        # Jump out of the inner loop
                                        break
                                if bFound:
                                    # Jump out of the outer loop
                                    break
                            # Check if the combination of SSG and Gold/Sig has been found
                            if not bFound:
                                # The [sSigName] has not been found as added to an SG yet
                                # Create a gold and add it
                                iSkip = 1
                            else:
                                # Okay, it has been found: there already is an SSG connected to this signature (via SG)
                                iSkip = 2
                            
                            iContinue = 1

                # Create a proper dataset for gold and for super with scope *team*
                sNowTime = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
                if len(lst_gold) > 0:
                    # Yes, create dataset
                    sDatasetGold = "Huwa SG import {}".format(sNowTime)
                    coll_gold = Collection.objects.create(
                        name=sDatasetGold, readonly=True, owner=profile,
                        scope="team", type="gold", settype="pd",
                        descrip="Automatically uploaded SG from HUWA JSON at {}".format(sNowTime))
                    with transaction.atomic():
                        for gold in lst_gold:
                            # Tie it to a new collection
                            CollectionGold.objects.create(gold=gold, collection=coll_gold)

                if len(lst_super) > 0:
                    # Yes, create a dataset
                    sDatasetSsg = "Huwa SSG/AF import {}".format(sNowTime)
                    coll_super = Collection.objects.create(
                        name=sDatasetSsg, readonly=True, owner=profile,
                        scope="team", type="super", settype="pd",
                        descrip="Automatically uploaded SSG/AF from HUWA JSON at {}".format(sNowTime))
                    with transaction.atomic():
                        for super in lst_super:
                            # Tie it to a new collection
                            CollectionSuper.objects.create(super=super, collection=coll_super)
                            # Check if it is tied to the project
                            obj = EqualGoldProject.objects.filter(project=project, equal=super).first()                        
                            if obj is None:
                                # Add it
                                obj = EqualGoldProject.objects.create(project=project, equal=super)

                # Make sure the correct list of things is returned
                # TODO!!!

            elif self.import_type == "retr":
                # Make sure we have a more fitting download name
                self.downloadname = "huwa_retr"
                oData = {}
                oData['skip'] = []
                oData['add'] = []
                count_skipped = 0
                count_added = 0

                # Note: this only looks at *existing* SGs to tackle...
                for oRetrTable in tables.get("retr"):
                    # Get the operaid, knoell and mutz
                    opera_id = oRetrTable.get("opera")
                    name_knoell = oRetrTable.get("name_knoell")
                    name_mutz = oRetrTable.get("name_mutz")

                    # Look for the SG that links to this opera
                    lst_gold = [x.gold for x in SermonGoldExternal.objects.filter(externalid=opera_id, externaltype="huwop")]
                    if len(lst_gold) == 0:
                        # Try to find a connection between SSG and Opera
                        equal_ids = [x.equal.id for x in EqualGoldExternal.objects.filter(externalid=opera_id, externaltype="huwop")]
                        lst_gold = [x for x in SermonGold.objects.filter(equal__id__in=equal_ids) ]
                    if len(lst_gold) == 0:
                        # We cannot process this one
                        oRetr = dict(opera=opera_id, action="skip")
                        oData['skip'].append(oRetr)
                        count_skipped += 1
                    else:
                        # We can process it
                        for gold in lst_gold:
                            # gold = obj.gold
                            oRetr = dict(opera=opera_id, action="add", gold=gold.id)
                            oData['add'].append(oRetr)
                            count_added += 1
                            retractationes = gold.retractationes
                            if retractationes is None:
                                lst_retractationes = []
                            else:
                                lst_retractationes = retractationes.split("\n")  #  json.loads(retractationes)
                            # Add knoell and mutz
                            lst_retractationes.append("P. Knöll (ed.), Retractationes, CSEL 36 (1902): **{}**".format(name_knoell))
                            lst_retractationes.append("A. Mutzenbecher (ed.), Retractationum Libri II, CCSL 57 (1984): **{}**".format(name_mutz))
                            # Put this back into the gold object
                            gold.retractationes = "\n".join(lst_retractationes) # json.dumps(lst_retractationes, indent=2)
                            gold.save()
                oData['count_skip'] = count_skipped
                oData['count_add'] = count_added

            elif self.import_type == "indiculum":
                # Make sure we have a more fitting download name
                self.downloadname = "huwa_indiculum"
                oData = {}
                oData['gold'] = []
                oData['super'] = []

                # Get to the proper project
                project = Project2.objects.filter(name__icontains="huwa").first()
                # Create a list for gold and super, so that they can be added to datasets
                lst_gold = []
                lst_super = []
                lst_newgold = []
                lst_newsuper = []
                profile = Profile.get_user_profile(self.request.user.username)

                # Make sure to load the opera, identifik and indiculum tables
                lst_identifik = tables.get("identifik")
                lst_indiculum = tables.get("indiculum")
                lst_opera = tables.get("opera")
                lst_desinit = tables.get("desinit")
                lst_incipit = tables.get("incipit")
                oIndiculums = {str(x['id']):x for x in lst_indiculum }
                oOperas = {str(x['id']):x for x in lst_opera }
                oDesinits = {str(x['id']):x for x in lst_desinit }
                oIncipits = {str(x['id']):x for x in lst_incipit }

                # Other initializations
                editype="ot"

                author = Author.objects.filter(name__iexact="Augustinus Hipponensis").first()
                kw = Keyword.objects.filter(name="deperditus").first()

                # ====== DEBUGGING ==============
                lst_missing_ind = [3, 2, 8, 12, 13, 376, 15, 16, 19, 25, 30, 32, 33, 343, 338]

                # Keep track of indiculum id's that have been processed
                lst_indiculum_ids = []

                # Process everything that is in [identifik]
                for oIdentifik in lst_identifik:
                    opera_id = oIdentifik.get("opera")
                    indiculum_id = oIdentifik.get("indiculum")
                    
                    # ========= DEBUG ===================
                    if int(indiculum_id) in lst_missing_ind:
                        iStop = 1
                    # ===================================

                    # Only continue if the opera_id is 'real' as well as the indiculum_id
                    if opera_id > 0 and indiculum_id != '0':
                        # NOTE: this batch has an OPERA, so contains more information

                        # Get the right indiculum
                        oIndiculum = oIndiculums[str(indiculum_id)]
                        indiculum_signatur = oIndiculum.get('indiculum_signatur')
                        indiculum_genus = oIndiculum.get('indiculum_genus')
                        indiculum_nummer = oIndiculum.get('indiculum_nummer')

                        if indiculum_signatur != 0:
                            # Define the signatures
                            lst_possidius = []
                            lst_possidius.append("Possidius {}".format(indiculum_signatur))
                            if indiculum_genus != 0:
                                lst_possidius.append(", {}".format(indiculum_genus))
                            lst_possidius.append(" {}".format(indiculum_nummer))
                            code_p = "".join(lst_possidius)

                            code_t = oIndiculum.get('text', '').strip()

                            # Determine incipit and explicit
                            inc = ""
                            exp = ""
                            oOpera = oOperas.get(str(opera_id))
                            if not oOpera is None:
                                oIncipit = oIncipits.get(str(oOpera['incipit']))
                                oDesinit = oDesinits.get(str(oOpera['desinit']))
                                if not oIncipit is None:
                                    inc = oIncipit.get("incipit_text")
                                if not oDesinit is None:
                                    exc = oDesinit.get("desinit_text")

                            # Find or create the signature
                            sig_p = Signature.objects.filter(editype=editype, code__iexact=code_p).first()
                            sig_t = Signature.objects.filter(editype=editype, code__iexact=code_t).first()
                            if sig_t is None and code_t != "":
                                sig_t = Signature.objects.filter(editype=editype, code__iexact=code_t.replace("ev", "eu")).first()
                            if sig_p is None:
                                # There is no corresponding SG yet, so create it, but first create the correct SSG
                                equal = EqualGold.objects.create(author=author, incipit=inc, explicit=exc)
                                # Next create the correct SG
                                gold = SermonGold.objects.create(equal=equal, author=author, incipit=inc, explicit=exc)
                                # Only now create the correct Signature
                                sig_p = Signature.objects.create(editype=editype, code=code_p, gold = gold)

                                if sig_t is None and code_t != "":
                                    # First check on the number of signatures associated with the gold
                                    sig_count = gold.goldsignatures.count()
                                    if sig_count == 1:
                                        # We only have the Possidius code: extend it
                                        sig_t = Signature.objects.create(editype=editype, code=code_t, gold = gold)

                                # Make [gold] and [equal] part of the right Project
                                lst_super.append(equal)
                                lst_gold.append(gold)
                                lst_newsuper.append(dict(equal=equal.id, sig_p=code_p, incipit=inc, explicit=exc))
                                lst_newgold.append(dict(gold=gold.id, sig_p=code_p, incipit=inc, explicit=exc))

                                # Indicate where we have them from
                                SermonGoldExternal.objects.create(externalid=opera_id, externaltype="huwop", gold=gold)
                                EqualGoldExternal.objects.create(externalid=opera_id, externaltype="huwop", equal=equal)

                                # Add proper keyword
                                SermonGoldKeyword.objects.create(gold=gold, keyword=kw)
                                EqualGoldKeyword.objects.create(equal=equal, keyword=kw)

                            elif sig_t is None and code_t != "":
                                # First check on the number of signatures associated with the gold
                                sig_count = sig_p.gold.goldsignatures.count()
                                if sig_count == 1:
                                    # There is a sig_p, but no sig_t. Hook this to the same gold
                                    sig_t = Signature.objects.create(editype=editype, code=code_t, gold = sig_p.gold)
                            else:
                                # The Signature already exists, so nothing needs to be done here
                                pass


                            # Add the indiculum id to those that have been processed
                            lst_indiculum_ids.append(indiculum_id)

                # Process all the indiculums that were not treated previously
                for oIndiculum in lst_indiculum:
                    indiculum_id = oIdentifik.get("indiculum")
                    if not indiculum_id in lst_indiculum_ids:
                        # Yes, process this one - but note: we are not able to tie it to a particular SG/SSG via OPERA
                        # Get the right indiculum
                        oIndiculum = oIndiculums[str(indiculum_id)]
                        indiculum_signatur = oIndiculum.get('indiculum_signatur')
                        indiculum_genus = oIndiculum.get('indiculum_genus')
                        indiculum_nummer = oIndiculum.get('indiculum_nummer')

                        if indiculum_signatur != 0:
                            # Define the signatures
                            lst_possidius = []
                            lst_possidius.append("Possidius {}".format(indiculum_signatur))
                            if indiculum_genus != 0:
                                lst_possidius.append(", {}".format(indiculum_genus))
                            lst_possidius.append(" {}".format(indiculum_nummer))
                            code_p = "".join(lst_possidius)

                            code_t = oIndiculum.get('text').strip()

                            # Find or create the signature
                            sig_p = Signature.objects.filter(editype=editype, code__iexact=code_p).first()
                            sig_t = Signature.objects.filter(editype=editype, code__iexact=code_t).first()
                            if sig_t is None:
                                sig_t = Signature.objects.filter(editype=editype, code__iexact=code_t.replace("ev", "eu")).first()
                            if sig_p is None:
                                # There is no corresponding SG yet, so create it, but first create the correct SSG
                                equal = EqualGold.objects.create(author=author)
                                # Next create the correct SG
                                gold = SermonGold.objects.create(equal=equal, author=author)
                                # Only now create the correct Signature
                                sig_p = Signature.objects.create(editype=editype, code=code_p, gold = gold)

                                if sig_t is None and code_t != "":
                                    # First check on the number of signatures associated with the gold
                                    sig_count = gold.goldsignatures.count()
                                    if sig_count == 1:
                                        # We only have the Possidius code: extend it
                                        sig_t = Signature.objects.create(editype=editype, code=code_t.replace("ev", "eu"), gold = gold)

                                # Add proper keyword
                                SermonGoldKeyword.objects.create(gold=gold, keyword=kw)
                                EqualGoldKeyword.objects.create(equal=equal, keyword=kw)

                                # Make [gold] and [equal] part of the right Project
                                lst_super.append(equal)
                                lst_gold.append(gold)
                                lst_newsuper.append(dict(equal=equal.id, sig_p=code_p))
                                lst_newgold.append(dict(gold=gold.id, sig_p=code_p))
                            elif sig_t is None:
                                # First check on the number of signatures associated with the gold
                                sig_count = sig_p.gold.goldsignatures.count()
                                if sig_count == 1:
                                    # There is a sig_p, but no sig_t. Hook this to the same gold
                                    sig_t = Signature.objects.create(editype=editype, code=code_t, gold = sig_p.gold)

                # Create a proper dataset for gold and for super with scope *team*
                sNowTime = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
                if len(lst_gold) > 0:
                    # Yes, create dataset
                    sDatasetGold = "Huwa SG import {}".format(sNowTime)
                    coll_gold = Collection.objects.create(
                        name=sDatasetGold, readonly=True, owner=profile,
                        scope="team", type="gold", settype="pd",
                        descrip="Automatically uploaded SG from HUWA JSON at {}".format(sNowTime))
                    with transaction.atomic():
                        for gold in lst_gold:
                            # Tie it to a new collection
                            CollectionGold.objects.create(gold=gold, collection=coll_gold)

                if len(lst_super) > 0:
                    # Yes, create a dataset
                    sDatasetSsg = "Huwa SSG/AF import {}".format(sNowTime)
                    coll_super = Collection.objects.create(
                        name=sDatasetSsg, readonly=True, owner=profile,
                        scope="team", type="super", settype="pd",
                        descrip="Automatically uploaded SSG/AF from HUWA JSON at {}".format(sNowTime))
                    with transaction.atomic():
                        for super in lst_super:
                            # Tie it to a new collection
                            CollectionSuper.objects.create(super=super, collection=coll_super)
                            # Check if it is tied to the project
                            obj = EqualGoldProject.objects.filter(project=project, equal=super).first()                        
                            if obj is None:
                                # Add it
                                obj = EqualGoldProject.objects.create(project=project, equal=super)

                # Make sure the correct list of things is returned
                oData['super'] = lst_newsuper
                oData['gold'] = lst_newgold
                oData['count_super'] = len(oData['super'])
                oData['count_gold'] = len(oData['gold'])
           
            elif self.import_type == "nebenwerk":
                # Make sure we have a more fitting download name
                self.downloadname = "huwa_nebenwerk" 
                oData = {}
                oData['gold'] = []
                oData['super'] = []
                oData['skip'] = []

                # Get to the proper project
                project = Project2.objects.filter(name__icontains="huwa").first()
                # Create a list for gold and super, so that they can be added to datasets
                lst_gold = []
                lst_super = []
                profile = Profile.get_user_profile(self.request.user.username)
                
                # Make sure to load the opera and nebenwerk tables
                lst_nebenwerk = tables.get("nebenwerk")
                lst_opera = tables.get("opera")
                oOperas = {str(x['id']):x for x in lst_opera }

                # process everything that is in [nebenwerk]
                for oNebenwerk in lst_nebenwerk:
                    # Get the stuff from this table
                    id = oNebenwerk.get("id")
                    opera_id = oNebenwerk.get("opera")
                    ist_von = oNebenwerk.get("ist_von")
                    hauptwerk_id = oNebenwerk.get("hauptwerk")
                    remark = oNebenwerk.get("bemerkungen")

                    # Find the SSG directly, if possible, otherwise via SG
                    ssg_low = get_ssg(opera_id)
                    ssg_main = get_ssg(hauptwerk_id)
                    # If both are existing
                    if not ssg_low is None and not ssg_main is None:
                        # Necessary: find a possible S that was imported from HUWA and is linked to this SSG
                        sermons = [x.sermon for x in SermonDescrExternal.objects.filter(externalid=opera_id, externaltype="huwop")]
                        # Process all these sermons
                        if len(sermons) == 0:
                            # Cannot process them
                            oData['skip'].append(dict(nebenwerk=id, opera=opera_id, hauptwerk=hauptwerk_id,
                                                      msg="No sermondescr with opera id {}".format(opera_id)))
                        else:
                            for sermon in sermons:
                                # Check link from low to main

                                pass

                    else:
                        # Cannot process them
                        oData['skip'].append(dict(nebenwerk=id, opera=opera_id, hauptwerk=hauptwerk_id, 
                                                  msg="One of opera or hauptwerk not in SSGs"))

            # Convert oData to stringified JSON
            if dtype == "json":
                if self.import_type == "manu":
                    # Combine the lst_manu_string
                    sData = "\n".join(lst_manu_string)
                elif self.import_type == "edilit":
                    sData = json.dumps(lst_ssg_edi, indent=2)
                elif self.import_type == "opera":
                    sData = json.dumps(lst_bhlbhm, indent=2)
                elif self.import_type in ["retr", "indiculum"]:
                    sData = json.dumps(oData, indent=2)
                else:
                    # convert to string
                    sData = json.dumps(oData, indent=2)

            elif dtype == "csv" or dtype == "xlsx":
                # 

                # Create CSV string writer
                output = StringIO()
                delimiter = "\t" if dtype == "csv" else ","
                csvwriter = csv.writer(output, delimiter=delimiter, quotechar='"')

                # Determine the headers
                headers = ['opera', 'sig_Clavis', 'sig_Gryson', 'sig_Other', 'inc', 'exp', 'note_langname', 'notes', 
                           'date_estimate', 'author_name', 'count_manu', 'manu_type', 'existing_ssg', 'sig_status']
                # Output this header row
                csvwriter.writerow(headers)

                # Process all objects in the data
                lData = oData.get("operas")
                for oSsg in lData:
                    # Start an output row
                    row = []

                    # Append all field values into this row (as TEXT)
                    row.append(get_good_string(oSsg, 'opera'))
                    row.append(get_signatures(oSsg, 'cl'))
                    row.append(get_signatures(oSsg, 'gr'))
                    row.append(get_signatures(oSsg, 'ot'))
                    row.append(get_good_string(oSsg,'incipit'))
                    row.append(get_good_string(oSsg,'explicit'))
                    row.append(get_good_string(oSsg,'note_langname'))
                    row.append(get_good_string(oSsg,'notes'))
                    row.append(get_good_string(oSsg,'date_estimate'))
                    row.append(get_good_string(oSsg,'author','name'))
                    row.append(get_good_string(oSsg,'manuscripts'))
                    row.append(get_good_string(oSsg,'manu_type'))
                    row.append(get_good_string(oSsg,'existing_ssg','type'))
                    row.append(get_good_string(oSsg,'existing_ssg','sig_status'))

                    # Output this row
                    csvwriter.writerow(row)

                # Convert to string
                sData = output.getvalue()
                output.close()

            if bDoCounting and self.import_type == "ssg":
                # Also show results of counting:
                oErr.Status("Potential SSGs with manuscripts: 0={}, 1={}, many (with num)={} many (no num)={}".format(
                    count_manu_zero, count_manu_one, count_manu_many_num, count_manu_many_oth))
                # Show the existing stuff
                for k,v in existing_dict.items():
                    oErr.Status("Existing {}: {}".format(k,v))
                # Show the signature matching
                for k,v in sig_matching.items():
                    oErr.Status("Signature status {}: {}".format(k,v))

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
        """Load the JSON that specifies the relationship between HUWA and Passim author"""

        oErr = ErrHandle()
        lst_authors = []
        try:
            authors_json = os.path.abspath(os.path.join(MEDIA_DIR, "passim", "huwa_passim_author.json"))
            with open(authors_json, "r", encoding="utf-8") as f:
                lst_interim = json.load(f)

            # Make sure that all the 'huwa_id' fields are integers and not string
            for oAuthor in lst_interim:
                if isinstance(oAuthor['huwa_id'], str):
                    sHuwaIds = oAuthor['huwa_id'].replace(" ", "")
                    arHuwaIds = re.split(r"[\;\/]", sHuwaIds)
                    for sHuwaId in arHuwaIds:
                        iHuwaId = int(sHuwaId.strip())
                        oOneAuthor = copy.copy(oAuthor)
                        oOneAuthor['huwa_id'] = iHuwaId
                        lst_authors.append(oOneAuthor)
                else:
                    lst_authors.append(copy.copy(oAuthor))
        except:
            msg = oErr.get_error_message()
            oErr.DoError("HuwaEqualGoldToJson/read_authors")
        # Return the table that we found
        return lst_authors

    def read_libraries(self):
        """Load the JSON that specifies the relationship between HUWA and Passim libraries"""

        oErr = ErrHandle()
        oLibraryInfo = {}
        try:
            libraries_json = os.path.abspath(os.path.join(MEDIA_DIR, "passim", "huwa_passim_library.json"))
            with open(libraries_json, "r", encoding="utf-8") as f:
                oLibraryInfo = json.load(f)
        except:
            msg = oErr.get_error_message()
            oErr.DoError("HuwaEqualGoldToJson/read_libraries")
        # Return the table that we found
        return oLibraryInfo

    def read_opera_passim(self):
        """Load the JSON that specifies the inter-SSG relations according to Opera id's """

        oErr = ErrHandle()
        dict_operapassim = {}
        try:
            lst_operapassim = None
            operapassim_json = os.path.abspath(os.path.join(MEDIA_DIR, "passim", "Opera_passim_MR.json"))
            with open(operapassim_json, "r", encoding="utf-8") as f:
                oOperaPassim = json.load(f)
            # Process the list into a dictionary
            if not oOperaPassim is None:
                dict_operapassim = {x['id']: x for x in oOperaPassim['opera_passim']}
        except:
            msg = oErr.get_error_message()
            oErr.DoError("HuwaEqualGoldToJson/read_opera_passim")
        # Return the table that we found
        return dict_operapassim

    def read_huwa_conv_sig(self):
        """Load the JSON that specifies how [abk] may translated into Clavis/Gryson/Cppm"""

        oErr = ErrHandle()
        lst_huwa_conv_sig = []
        try:
            huwa_conv_sig_json = os.path.abspath(os.path.join(MEDIA_DIR, "passim", "huwa_conv_sig.json"))
            with open(huwa_conv_sig_json, "r", encoding="utf-8") as f:
                lst_huwa_conv_sig = json.load(f)
            # Add the 'mask' to each item
            for item in lst_huwa_conv_sig:
                mask = item['huwa'].replace("#", r"(\d[\d\s\,\-]*)(.*)")
                item['mask'] = mask
        except:
            msg = oErr.get_error_message()
            oErr.DoError("HuwaEqualGoldToJson/read_huwa_conv_sig")
        # Return the table that we found
        return lst_huwa_conv_sig

    def read_relations(self):
        """Load the JSON that specifies the inter-SSG relations according to Opera id's """

        oErr = ErrHandle()
        lst_relations = []
        try:
            relations_json = os.path.abspath(os.path.join(MEDIA_DIR, "passim", "huwa_relations.json"))
            with open(relations_json, "r", encoding="utf-8") as f:
                lst_relations = json.load(f)
        except:
            msg = oErr.get_error_message()
            oErr.DoError("HuwaEqualGoldToJson/read_relations")
        # Return the table that we found
        return lst_relations

    def read_scribes(self, lst_schreiber_name):
        """Either read the scribe names from the lst, or make them available otherwise"""

        oErr = ErrHandle()
        oScribe = {}
        try:
            for oItem in lst_schreiber_name:
                id = oItem.get("id")
                name = oItem.get("name", "").strip()
                note = oItem.get("bemerkungen", "").strip()
                if id == 3:
                    # This is a special one
                    name = "Unknown"
                # See if this one already exists
                obj = Scribe.objects.filter(name__iexact=name).first()
                if obj is None:
                    # Create it
                    if note == "":
                        obj = Scribe.objects.create(name=name, external=id)
                    else:
                        obj = Scribe.objects.create(name=name, external=id, note=note)
                # Add an entry for this scribe into the dictionary
                oScribe[str(id)] = name
        except:
            msg = oErr.get_error_message()
            oErr.DoError("HuwaEqualGoldToJson/read_scribes")
        # Return the dictionary
        return oScribe

    def read_scripts(self, lst_schrift_name):
        """Either read the script names from the lst, or make them available otherwise"""

        oErr = ErrHandle()
        oScript = {}
        try:
            for oItem in lst_schrift_name:
                id = oItem.get("id")
                name = oItem.get("name", "").strip()
                if id == 8:
                    # This is a special one
                    name = "Unknown"
                # See if this one already exists
                obj = Script.objects.filter(name__iexact=name).first()
                if obj is None:
                    # Create it
                    obj = Script.objects.create(name=name, external=id)
                # Add an entry for this script into the dictionary
                oScript[str(id)] = name
        except:
            msg = oErr.get_error_message()
            oErr.DoError("HuwaEqualGoldToJson/read_scripts")
        # Return the dictionary
        return oScript

    def get_passim_author(self, lst_authors, huwa_id, tbl_autor):
        """Return the Passim author ID for [huwa_id]"""

        oErr = ErrHandle()
        passim = None
        try:
            shuwa_id = str(huwa_id)
            if isinstance(huwa_id, str):
                ihuwa_id = int(huwa_id)
            else:
                ihuwa_id = huwa_id
            passim_id = None
            for item in lst_authors:
                if item['huwa_id'] == ihuwa_id:  # shuwa_id:
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


class ManuscriptHuwaToJson(EqualGoldHuwaToJson):
    """Read HUWA manuscripts from database into JSON"""

    import_type = "manu"


class EqualGoldHuwaLitToJson(EqualGoldHuwaToJson):
    """Read HUWA literature for SSG from database into JSON"""

    import_type = "edilit"


class EqualGoldHuwaOpera(EqualGoldHuwaToJson):
    """Post-processing of HUWA opera-tied BHL, BHM, THLL, RETR - also create JSON"""

    import_type = "opera"


class EqualGoldHuwaRetr(EqualGoldHuwaToJson):
    """Post-processing of HUWA opera-tied RETR - also create JSON"""

    import_type = "retr"


class EqualGoldHuwaIndiculum(EqualGoldHuwaToJson):
    """Post-processing of HUWA opera-tied INDICULUM - also create JSON"""

    import_type = "indiculum"


class EqualGoldHuwaNebenwerk(EqualGoldHuwaToJson):
    """Post-processing of HUWA table [nebenwerk] that ties SSG to SSG"""

    import_type = "nebenwerk"


class ReaderEqualGold(View):
    arErr = []
    error_list = []
    transactions = []
    data = {'status': 'ok', 'html': ''}
    template_name = 'reader/import_ssgs.html'
    obj = None
    oStatus = None
    data_file = ""
    bClean = False
    import_type = "undefined"
    sourceinfo_url = "undefined"
    username = ""
    mForm = UploadFilesForm

    def custom_init(self):
        """Allow user to add code"""
        pass    

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
            lHeader = ['status', 'msg', 'filename', 'ssg', 'siglist']

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

    def process_files(self, request, source, lResults, lHeader):
        """This is a wrapper, that needs to be specified for each individual import function"""

        bOkay = True
        code = ""
        return bOkay, code


class ReaderHuwaImport(ReaderEqualGold):
    """HUWA import SSGs via a JSON file"""

    import_type = "huwajson"
    sourceinfo_url = "http://www.ru.nl"
    opera_equal = None

    def process_files(self, request, source, lResults, lHeader):
        """Process a JSON file for HUWA import"""

        bOkay = True
        code = ""
        oStatus = self.oStatus
        file_list = []
        oErr = ErrHandle()
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
                        if extension == "json":
                            # This is a JSON file
                            oResult = self.read_json(username, data_file, filename, self.arErr, source=source)

                            if oResult['count'] > 0:
                                for item in oResult['imported']:
                                    lst_read.append(copy.copy(item))

                        # Create a report and add it to what we return
                        oContents = {'headers': lHeader, 'list': lst_manual, 'read': lst_read}
                        oReport = Report.make(username, "ijson", json.dumps(oContents))
                                
                        # Determine a status code
                        statuscode = "error" if oResult == None or oResult['status'] == "error" else "completed"
                        if oResult == None:
                            self.arErr.append("There was an error. No AFs (SSGs) have been added")
                        else:
                            # Create a list of results
                            if oResult['count'] > 0:
                                for item in oResult['imported']:
                                    lResults.append(copy.copy(item))

            code = "Imported using the import_type [huwajson] on these JSON file(s): {}".format(", ".join(file_list))

        except:
            bOkay = False
            code = oErr.get_error_message()
            oErr.DoError("ReaderHuwaImport/process_files")

        return bOkay, code

    def read_json(self, username, data_file, filename, arErr, jsondoc=None, sName = None, source=None):
        """Read one HUWA JSON file"""

        oErr = ErrHandle()
        oBack = {'status': 'ok', 'count': 0, 'msg': "", 'user': username}
        lst_imported = []
        lst_results = []
        msg = ""
        try:
            # This is a JSON file: Load the file into a variable
            sData = data_file.read()
            oOperaData = json.loads( sData.decode(encoding="utf-8"))

            # Think of a dataset name to connect all the input with
            sNowTime = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")

            # SSG collection
            sDatasetSsg = "Huwa SSG/AF import {}".format(sNowTime)
            coll_super = Collection.objects.filter(name=sDatasetSsg).first()
            if coll_super is None:
                profile = Profile.get_user_profile(self.request.user.username)
                coll_super = Collection.objects.create(
                    name=sDatasetSsg, readonly=True, owner=profile,
                    scope="team", type="super", settype="pd",
                    descrip="Automatically uploaded SSG/AF from HUWA JSON at {}".format(sNowTime))
            # Gold collection
            sDatasetGold = "Huwa SG import {}".format(sNowTime)
            coll_gold = Collection.objects.filter(name=sDatasetGold).first()
            if coll_gold is None:
                profile = Profile.get_user_profile(self.request.user.username)
                coll_gold = Collection.objects.create(
                    name=sDatasetGold, readonly=True, owner=profile,
                    scope="team", type="gold", settype="pd",
                    descrip="Automatically uploaded SG from HUWA JSON at {}".format(sNowTime))

            # Load the relations separately
            opera_relations = oOperaData.get("opera_relations")
            # Create an opera-equality relation dictionary
            oOperaEqual = self.get_relation_equals(opera_relations)
            self.opera_equal = oOperaEqual

            # Load the opera definitions
            operas = oOperaData.get("operas")

            # Figure out what the HUWA and the PASSIM project is
            project_huwa = Project2.objects.filter(name__icontains="huwa").first()
            if project_huwa is None:
                project_huwa = Project2.objects.create(name="HUWA/CSEL")
            project_passim = Project2.objects.filter(name__icontains="passim").first()

            # Now read and process the input according to issue #534
            num_operas = len(operas)
            for idx, oOpera in enumerate(operas):
                oImported = {}

                # Show where we are
                opera_id = oOpera.get('opera')

                #if idx % 100 == 0:
                #    oErr.Status("Huwa Import reading opera id={} {}/{}".format(opera_id, idx+1, num_operas))

                ## -------------- DEBUGGING ------
                #if opera_id == 6301:
                #    iStop = 1


                # Get the parameters that are needed
                existing_ssg = oOpera.get("existing_ssg")
                sig_status = existing_ssg.get("sig_status")
                ssg_type = existing_ssg.get("type").split(":")[0]
                manu_type = oOpera.get("manu_type")
                action = oOpera.get("action", "")
                bMakeSG = False

                # issue #558: opera with no links to inhalt that have been assigned a Gryson/Clavis-code in the "opera_passim" document.
                #     Note: the number of links to inhalt should not matter
                #           An opus with a link to inhalt is part of a manuscript
                #           An opus without link to inhalt is not part of a manuscript
                #           But in both cases the opus can turn out to be an SSG (in our terms)

                # ------ issue #533: this distinction disappears now -----------
                #if bDistinguishZeroLinks and manu_type == "zero_links":
                #    # This Opera has no links to inhalt
                #    # DOUBLE CHECK - at first we don't do anything with them
                #    pass

                ## First criterion: skip all manu_type 'zero_links']
                #elif manu_type != 'zero_links':
                #    # Second criterion: look at possible sig_status

                # Most importantly, check whether HUWA mentions any signatures
                if sig_status == "opera_ssg_0_0":
                    # No signature is given
                    # No further SSG/AF action needed, because:
                    # - if they have no link to a manuscript, they are useless anyway
                    # - if they *do* have a link to a manuscript, then they are just manifestations and there is no need for SG/SSG
                    pass
                elif sig_status == "opera_ssg_0_n":
                    # Check what the ACTION is for this one
                    if action == "new AF" or action == "":
                        # Indicate that a new SG must be made for these
                        bMakeSG = True
                        # Yes: import this one
                        oImported = self.import_one_json(oOpera,[project_huwa], bMakeSG, coll_super=coll_super, coll_gold=coll_gold)
                    elif action == "link_to AF":
                        # ONLY (!!!) create a link between the SSG and the OPERA number
                        oImported = self.link_ssg_to_opera(oOpera)
                elif sig_status == "opera_ssg_1_0":
                    # Indicate that a new SG must be made for these
                    bMakeSG = True
                    # Depending on ssg_type (though this appears to be irrelevant)
                    if ssg_type == "ssgmF":
                        # Yes: import this one
                        oImported = self.import_one_json(oOpera,[project_huwa], bMakeSG, coll_super=coll_super, coll_gold=coll_gold)
                    else:
                        # Yes: import this one
                        oImported = self.import_one_json(oOpera,[project_huwa], bMakeSG, coll_super=coll_super, coll_gold=coll_gold)
                elif sig_status == "opera_ssg_1_1":
                    # Indicate that a new SG must be made for these
                    bMakeSG = True
                    if ssg_type in ["ssgmF", "ssgmE"]:
                        # Import through matching of HUWA/PASSIM AFs through their Gryson/Clavis code
                        oImported = self.import_one_json(oOpera,[project_huwa], bMakeSG, coll_super=coll_super, coll_gold=coll_gold)
                    else:
                        # This is now subset [ssg11n] - it may be imported (will be checked online)
                        oImported = self.import_one_json(oOpera,[project_huwa], bMakeSG, coll_super=coll_super, coll_gold=coll_gold)
                elif sig_status == "opera_ssg_1_n":
                    # Issue #533: may be imported and will be checked online
                    oImported = self.import_one_json(oOpera,[project_huwa], bMakeSG, coll_super=coll_super, coll_gold=coll_gold)
                elif sig_status == "opera_ssg_n_1":
                    # Issue #533: may be imported and will be checked online
                    oImported = self.import_one_json(oOpera,[project_huwa], bMakeSG, coll_super=coll_super, coll_gold=coll_gold)
                # Process the [oImported]
                if not oImported is None and oImported.get("msg") in ["read", "linked", "skipped"]:
                    sExtra = ""
                    if oImported.get("msg") == "read":
                        # Get author info
                        sExtra = " ({}/{})".format(oImported.get("author"), oImported.get("number"))
                    oErr.Status("Huwa Import processing opera id={} as [{}] ({}/{}){}".format(
                        opera_id, oImported.get("msg"), idx+1, num_operas, sExtra))
                    lst_imported.append(oImported)

            # Check if any relations from the list [opera_relations] can be added
            count_relations = self.add_relations(opera_relations)

            # Add the list to the stuff we return
            oBack['imported'] = lst_imported
            oBack['name'] = filename
            oBack['filename'] = filename
            oBack['count'] = len(lst_imported)
        except:
            msg = oErr.get_error_message()
            oErr.DoError("read_json")
            oResult['status'] = 'error'
            oResult['msg'] = msg

        return oBack

    def get_relation_equals(self, opera_relations):
        """Create a dictionary with the opera ID as key for equal relationships"""

        oErr = ErrHandle()
        oEqual = {}
        try:
            # Walk the list of relations
            for oRelation in opera_relations:
                src_id = oRelation.get("src")
                dst_id = oRelation.get("dst")
                linktype = oRelation.get("linktype")
                if linktype == "eqs":
                    # Add this equal relationship in the dictionary
                    src_str = str(src_id)
                    dst_str = str(dst_id)
                    # Add the one relationship
                    if not src_str in oEqual:
                        oEqual[src_str] = dst_id
                    # And add the reverse relationship
                    if not dst_str in oEqual:
                        oEqual[dst_str] = src_id
        except:
            msg = oErr.get_error_message()
            oErr.DoError("get_relation_equals")

        return oEqual

    def add_relations(self, opera_relations):
        """Given the list of relations, see if anything can be added"""

        def get_opera_ssg(opera_id):
            """Get the Passim SSG, given the opera ID"""

            ssg = None
            obj = EqualGoldExternal.objects.filter(externalid=opera_id, externaltype = EXTERNAL_HUWA_OPERA).first()
            if not obj is None:
                ssg = obj.equal
            return ssg

        oErr = ErrHandle()
        count_new = 0
        count_existing = 0
        count = 0
        bDebug = False
        
        try:
            # Take note of how many relations there are
            count_rel = len(opera_relations)

            # Walk the list of relations
            rel_num = 0
            for oRelation in opera_relations:
                src_id = oRelation.get("src")
                dst_id = oRelation.get("dst")
                linktype = oRelation.get("linktype")
                spectype = oRelation.get("spectype")
                keyword = oRelation.get("keyword")
                rel_num += 1

                # Retrieve the src and dst SSGs
                src = get_opera_ssg(src_id)
                if not src is None:
                    dst = get_opera_ssg(dst_id)
                    if not dst is None and not linktype is None and not spectype is None:
                        # All essential ingredients are there...

                        # If this is an [eqs] linktype, then it requires entirely different treatment
                        if linktype == "eqs":
                            # Check if the destination 
                            pass

                        else:
                        
                            # check if this relation already exists
                            link = EqualGoldLink.objects.filter(src=src, dst=dst, linktype=linktype, spectype=spectype).first()
                            if link is None:
                                # Create a link
                                link = EqualGoldLink.objects.create(src=src, dst=dst, linktype=linktype, spectype=spectype, alternatives="no")
                                count_new += 1
                                # Need to add a keyword, possibly?
                                if not keyword is None and keyword != "":
                                    kw_obj = Keyword.objects.filter(name__iexact=keyword).first()
                                    if kw_obj is None:
                                        kw_obj = Keyword.objects.create(name__iexact=keyword)
                                    # Check if there already is a kw link between [src] and [kw_obj]
                                    obj = EqualGoldKeyword.objects.filter(equal=src, keyword=kw_obj).first()
                                    if obj is None:
                                        obj = EqualGoldKeyword.objects.create(equal=src, keyword=kw_obj)
                            
                                oErr.Status("Add_relations src={} dst={}".format(src_id, dst_id))
                            else:
                                # Keep track of existing links
                                count_existing += 1
            # Report the counts
            oErr.Status("add_relations: new={}, existing={}, missing={}".format(count_new, count_existing, count_rel - count_new - count_existing))
            count = count_new + count_existing
        except:
            msg = oErr.get_error_message()
            oErr.DoError("add_relations")
        return count

    def link_ssg_to_opera(self, oOpera):
        """Make a link between one OPERA definition and an existing SSG/AF"""

        oErr = ErrHandle()
        oImported = dict(status="ok")
        try:
            # extract all parameters that *could* be relevant
            opera_id = oOpera.get("opera")
            same_sig_ssgs = oOpera.get("same_sig_ssgs")
            sig_status = oOpera['existing_ssg']['sig_status']
            existing_type = oOpera['existing_ssg']['type']
            manu_type = oOpera['manu_type']

            # Make a subset identifier
            existing_type = existing_type.split(":")[0]
            manu_type= manu_type.split("_")[0]
            subset = json.dumps(dict(sig=sig_status, manu=manu_type, existing=existing_type ))

            # See if we can make a link
            if len(same_sig_ssgs) > 0:
                ssg_id = same_sig_ssgs[0]
                # Get this SSG
                ssg = EqualGold.objects.filter(id=ssg_id).first()
                if not ssg is None:
                    # Double check if this has already been done...
                    obj = EqualGoldExternal.objects.filter(
                        equal=ssg, externalid=opera_id, externaltype=EXTERNAL_HUWA_OPERA).first()
                    if obj is None:
                        # Create a link between the SSG and the opera identifier
                        obj = EqualGoldExternal.objects.create(
                            equal=ssg, externalid=opera_id, externaltype=EXTERNAL_HUWA_OPERA,
                            subset = subset)
                        oImported['msg'] = "linked"
                        oImported['ssg'] = ssg.get_code()
                        oImported['gold'] = 'n/a'
                        oImported['siglist'] = 'n/a'

        except:
            msg = oErr.get_error_message()
            oErr.DoError("link_ssg_to_opera")
            oImported['status'] = "error"
            oImported['msg'] = msg

        return oImported

    def import_one_json(self, oOpera, projects, bMakeSG=False, coll_super=None, coll_gold=None):
        """Import one OPERA definition of a SSG/AF"""

        def add_signatures_to_sg(signatures, gold):
            oErr = ErrHandle()
            siglist = []
            sBack = ""
            try:
                for oSig in signatures:
                    # Create a signature that is linked to the correct SG
                    editype = oSig.get("editype")
                    code = oSig.get("code")
                    sig = Signature.objects.create(code=code, editype=editype, gold=gold)
                    siglist.append("{}: {}".format(editype,code))
                sBack = ", ".join(siglist)
            except:
                msg = oErr.get_error_message()
                oErr.DoError("add_signatures_to_sg")
            return sBack

        def get_firstsig(signatures):
            oErr = ErrHandle()
            sBack = ""
            try:
                if len(signatures) > 0:
                    oSig = signatures[0]
                    sBack = oSig.get("code")
            except:
                msg = oErr.get_error_message()
                oErr.DoError("get_firstsig")
            return sBack

        oErr = ErrHandle()
        oImported = dict(status="ok")

        try:
            # extract all parameters that *could* be relevant
            opera_id = oOpera.get("opera")
            signatures = oOpera.get("signaturesA")
            incipit = oOpera.get("incipit", "")
            explicit = oOpera.get("explicit", "")
            note_langname = oOpera.get("note_langname")
            notes = oOpera.get("notes")
            date_estimate = oOpera.get("date_estimate")
            author_id = oOpera.get("author").get("id")
            same_sig_ssgs = oOpera.get("same_sig_ssgs")
            sig_status = oOpera['existing_ssg']['sig_status']
            existing_type = oOpera['existing_ssg']['type']
            existing_id = oOpera['existing_ssg'].get("id")
            manu_type = oOpera['manu_type']

            # Check whether this OPERA has already been imported or not
            obj_ext = EqualGoldExternal.objects.filter(externaltype=EXTERNAL_HUWA_OPERA, externalid=opera_id).first()
            if not obj_ext is None:
                # This particular Opera has already been processed
                oImported['ssg'] = obj_ext.equal.get_code()
                oImported['msg'] = 'skipped'
                return oImported

            # Check if this opera equals another one
            equal_opera_id = None
            obj_ext = None
            if existing_id is None and not self.opera_equal is None:
                # We have a relations dictionary!
                str_opera = str(opera_id)
                if str_opera in self.opera_equal:

                    # There is another opera equalling this one
                    equal_opera_id = self.opera_equal[str_opera]
                    # Check if this has already been noted in the EqualGoldExternal table
                    obj_ext = EqualGoldExternal.objects.filter(externaltype=EXTERNAL_HUWA_OPERA, externalid=equal_opera_id).first()
                    if not obj_ext is None:
                        # Get the EqualGold object to which this one is equal
                        # Assigning it to existing_id means that *NO* SSG will be created, but only an SG
                        existing_id = obj_ext.equal.id

            # Make a subset identifier
            existing_type = existing_type.split(":")[0]
            manu_type= manu_type.split("_")[0]
            subset = json.dumps(dict(sig=sig_status, manu=manu_type, existing=existing_type ))

            oImported['opera'] = opera_id
            oImported['gold'] = "-"
            oImported['incipit'] = incipit
            oImported['explicit'] = explicit
            oImported['notes'] = notes
            oImported['ssgmatch'] = existing_type
            oImported['manutype'] = manu_type
            oImported['sigstatus'] = sig_status

            ssg = None
            gold = None

            if len(same_sig_ssgs) > 0:
                # There already may be one SSG with the same Signature(s)
                ssg = EqualGold.objects.filter(id__in=same_sig_ssgs).first()

            # If there is an existing SSG with the same Signature(s)...
            if ssg is None or oOpera.get("action") == "new AF":
                # Check if there is an existing SSG
                if existing_id is None:
                    # No, there are no SSGs with the same sig yet: this means we are CREATING a new SSG and a new SG for it

                    ssg = EqualGold.create_empty()

                    # (1) Set inc, exp, author
                    bNeedSaving = False
                    if incipit != "": ssg.incipit = incipit ; bNeedSaving = True
                    if explicit != "": ssg.explicit = explicit ; bNeedSaving = True
                    if not author_id is None: ssg.author_id = author_id
                else:
                    # There already is an SSG
                    ssg = EqualGold.objects.filter(id=existing_id).first()

                # (2) Add the existing SSG to the project HUWA
                for project in projects:
                    # Check if it is already connected to the indicated project
                    if EqualGoldProject.objects.filter(equal=ssg, project=project).count() == 0:
                        # If it isn't yet: add it
                        EqualGoldProject.objects.create(equal=ssg, project=project)

                # (3) Create an SG with the correct signature(s)                
                gold = SermonGold.objects.create(
                    author_id=author_id, incipit=incipit, explicit=explicit, equal=ssg)
                oImported['gold'] = gold.id

                # (3b) Make sure that there is a link between this SG and Opera
                SermonGoldExternal.objects.create(
                    gold=gold, externalid=opera_id, externaltype=EXTERNAL_HUWA_OPERA,
                    subset = subset)

                # (4) Add a keyword to the SG to indicate this is from HUWA
                kw_huwa = Keyword.objects.filter(name__contains="HUWA created", visibility="edi").first()
                if kw_huwa is None:
                    # Create a keyword
                    kw_huwa = Keyword.objects.create(name="HUWA created", visibility="edi")
                gold.keywords.add(kw_huwa)

                # Add all the signatures
                oImported['siglist'] = add_signatures_to_sg(signatures, gold)

                # (5) Save SSG to process changes
                ssg.stype = "imp"   # This has been imported
                ssg.atype = "acc"   # Acceptance type must be 'acc'
                ssg.firstsig = get_firstsig(signatures)
                ssg.save()
                oImported['ssg'] = ssg.get_code()
                oImported['author'] = ssg.get_author()
                oImported['number'] = ssg.get_number()

                # Create a link between the SSG and the opera identifier
                EqualGoldExternal.objects.create(
                    equal=ssg, externalid=opera_id, externaltype=EXTERNAL_HUWA_OPERA,
                    subset = subset)

                # Indicate that this one has been read
                oImported['msg'] = "read"

            else:
                # There already is an SSG that we can use as a basis!

                oImported['ssg'] = ssg.get_code()
                oImported['author'] = ssg.get_author()
                oImported['number'] = ssg.get_number()

                # Double check if this has already been done...
                obj = EqualGoldExternal.objects.filter(
                    equal=ssg, externalid=opera_id, externaltype=EXTERNAL_HUWA_OPERA).first()

                if obj is None:
                    # This one has not been imported yet...

                    # Note: see issue #534 - add existing SSG to list of projects + add SG and link it to SSG
                    # (1) Add the existing SSG to the project HUWA
                    for project in projects:
                        if EqualGoldProject.objects.filter(equal=ssg, project=project).count() == 0:
                            EqualGoldProject.objects.create(equal=ssg, project=project)

                    if bMakeSG:
                        # (2) Add an SG, linking it to the existing [ssg]
                        gold = SermonGold.objects.create(
                            author_id=author_id, incipit=incipit, explicit=explicit, equal=ssg)

                        oImported['gold'] = gold.id

                        # (3b) Make sure that there is a link between this SG and Opera
                        SermonGoldExternal.objects.create(
                            gold=gold, externalid=opera_id, externaltype=EXTERNAL_HUWA_OPERA,
                            subset = subset)

                        # (3) Add all the signatures, linking them to the correct SG
                        oImported['siglist'] = add_signatures_to_sg(signatures, gold)

                        # (4) Add a keyword to the SG to indicate this is from HUWA
                        kw_huwa = Keyword.objects.filter(name__contains="HUWA import", visibility="edi").first()
                        if kw_huwa is None:
                            # Create a keyword
                            kw_huwa = Keyword.objects.create(name="HUWA import", visibility="edi")
                        gold.keywords.add(kw_huwa)

                    # Create a link between the SSG and the opera identifier
                    EqualGoldExternal.objects.create(
                        equal=ssg, externalid=opera_id, externaltype=EXTERNAL_HUWA_OPERA,
                        subset = subset)

                    oImported['msg'] = "read"

            # Has something been added?
            if not ssg is None and not coll_super is None:
                # Check if this combination already exists
                obj_ssg_coll = CollectionSuper.objects.filter(collection=coll_super, super=ssg).first()
                if obj_ssg_coll is None:
                    # Add to collection
                    obj_ssg_coll = CollectionSuper.objects.create(collection=coll_super, super=ssg)
            if not gold is None and not coll_gold is None:
                # Check if this combination already exists
                obj_gold_coll = CollectionGold.objects.filter(collection=coll_gold, gold=gold).first()
                if obj_gold_coll is None:
                    # Add to collection
                    obj_gold_coll = CollectionGold.objects.create(collection=coll_gold, gold=gold)

        except:
            msg = oErr.get_error_message()
            oErr.DoError("import_one_json")
            oImported['status'] = "error"
            oImported['msg'] = msg

        return oImported

