"""
Definition of views for the READER app.
"""

from django.apps import apps
from django.contrib import admin
from django.contrib.auth import login, authenticate
from django.contrib.auth.models import Group, User
from django.core.urlresolvers import reverse
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
from openpyxl.utils.cell import get_column_letter
from io import StringIO
from itertools import chain

# Imports needed for working with XML and other file formats
from xml.dom import minidom
# See: http://effbot.org/zone/celementtree.htm
import xml.etree.ElementTree as ElementTree


# ======= imports from my own application ======
from passim.settings import APP_PREFIX, MEDIA_DIR
from passim.utils import ErrHandle
from passim.reader.forms import UploadFileForm, UploadFilesForm
from passim.seeker.models import Manuscript, SermonDescr, Status, SourceInfo, ManuscriptExt, Provenance, ProvenanceMan, \
    Library, Location, SermonSignature, Author, Feast, Project, Daterange, Comment, Profile, MsItem, SermonHead, Origin, \
    Report, STYPE_IMPORTED

# ======= from RU-Basic ========================
from passim.basic.views import BasicList, BasicDetails

# =================== This is imported by seeker/views.py ===============
# OLD METHODS
#reader_uploads = [
#    {"title": "ecodex",  "label": "e-codices",     "url": "import_ecodex",  "type": "multiple", "msg": "Upload e-codices XML files"},
#    {"title": "ead",     "label": "EAD",           "url": "import_ead",     "type": "multiple","msg": "Upload 'archives et manuscripts' XML files"}
#    ]
# NEW METHODS
reader_uploads = [
    {"title": "ecodex", "label": "e-codices", "url": "import_ecodex", "type": "multiple","msg": "Upload e-codices XML files (n)"},
    {"title": "ead",    "label": "EAD",       "url": "import_ead",    "type": "multiple","msg": "Upload 'Archives et Manuscripts' XML files"}
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
    oBack = {'status': 'ok', 'count': 0, 'msg': "", 'user': username}
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
            
        # First the manuscript data will be extracted, then the parts about of specific XML in which each manuscript is stored 
        # last the data on the sermons
     
        # (1) Find all the MANUSCRIPTS in this XML document 
        # The list manu_list stores ALL manuscripts (both the ones on the highest level and the ones on the lower level, 
        # that are part of combined manuscripts).                       
        manu_list = xmldoc.findall("//c[did]")

        # Here the information on the XML is extracted
        manu_info = xmldoc.find("//eadheader")
        manuidno_end = "0"
        # Import wishlist.csv that holds the shelfmarks of the selected A+M manuscripts
        # Check shelfmarks in csv want Latin 1913 was latin 1913 en werd niet meegenomen.        
        with open('d:/wishlist_final.csv') as f:
            reader = csv.reader(f, dialect='excel', delimiter=';')
            
            # Make list of strings (instead of lists)
            shelfmark_list = list([row[0] for row in reader])
            
            # Delete the first row (with fieldname "Shelfmark")
            shelfmark_list.pop(0)
             
            # Make set of the list
            # sm_shelfmark is to be used to compare the shelfmark in all A+M XML's to
            shelfmark_set = set(shelfmark_list)  

        # Iterate through the list of ALL manuscripts          
        for manu in manu_list:
            # x are the underlying tags of the above mentioned tags, for instance <did> with: <unitid> (3x), KAN WEG
            # <unittitle>, <physdesc>, <langmaterial> and <unitdate>
            # x = str(manu.getchildren()) #  wat doet "str"?
            # y = manu.getchildren() # is dit okay? wat is het verschil?
            # z = manu.attrib 
            # print(z) TOT HIER

            # SHELFMARK of the manuscript
            # Get the shelfmark of this manuscript (assuming this level represents a whole manuscript)
            unitid = manu.find("./did/unitid[@type='cote']")
            if unitid is None:
                continue
                        
            # This is the shelfmark
            manuidno = unitid.text         
            print(manuidno)

            # NUMBER of the SHELFMARK of the manuscript
            # Store only the NUMBER of the shelfmark to aid in the adding 
            # of the higher level title (if this is the case) TH: check how this works when shelmarks are combined with letter
            # or "(1-2)" and so on and with a space for instance Latin 2445 A, maybe split on "Latin " TH: vooralsnog niet nodig
            # want het gaat om een nummer in een reeks, even zo laten zou ik zeggen

            if "-" not in manuidno:
                manuidno_list_2 = manuidno.split()         
                manuidno_number = manuidno_list_2[1]              
            
            # FIRST STORE DATA OF COMBINED MANUSCRIPTS

            # TITLE of a COMBINED MANUSCRIPT
        
            # Here the title of a combined manuscript (consisting of multiple manuscripts) is extracted. 
            # This title will later on be placed in front of the titles of manuscripts that are part of this combined
            # manuscript.      
            
            # Create a new string to add all parts of the title later in the process
            title_high_temp = ""
            #manuidno_end = "0" # dit werkt wel springt steeds op nul
            # Seek out the combined manuscripts (but steer away from manuscripts like "Latin 646B (1-2"
            if "-" in manuidno and not "(" in manuidno:
                # Store start and end shelfmarks to help check when the title of the 
                # combined manuscript must be added to the titles lower level manuscripts.  
                # Check on 646-646A, can go wrong...with the A
                # Also check on for instance Latin 760A (1), part of Latin 760A (1-3), same concept? Hier ook unitdate..
                # zie ook Latin 774A-C...maybe first check the contents of the wishlist
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
                
                # SUPPORT and BINDING of the manuscript (HIGH)
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
                # Hier loopt het nog niet voor die opgesplitste physfascets, niet alles wordt überhaupt 
                # meegenomen TH: moeten die meegenomen worden? 
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
                                
                # FORMAT of the manuscript (HIGH)
                # Look for the format of the manuscript - if it is exists 
                # (<dimensions>) 
                unitdimensions_high = manu.find("./did/physdesc/dimensions")
                if unitdimensions_high != None and unitdimensions_high != "":
                    unitdimensions_high_combined = unitdimensions_high.text
                # If there is no element here than the one from the former 
                # CM (combined manuscript) should be deleted
                else:
                    unitdimensions_high_combined = ""
                
                # EXTENT of the manuscript (HIGH)
                # Look for the extent of the manuscrpt - if it is exists 
                unitextent_high = manu.find("./did/physdesc/extent")
                if unitextent_high != None and unitextent_high != "":
                    unitextent_high_combined = unitextent_high.text
                # If there is no element here than the one from the former 
                # CM (combined manuscript) should be deleted
                else:
                    unitextent_high_combined = ""
                
                # ORIGIN of the manuscript (HIGH)                  
                # Look for the origin of the manuscript - if it exists                    
                unitorigin_high = manu.find("./did/physdesc/geogname")
                if unitorigin_high != None and unitorigin_high != "":
                    unitorigin_high_combined = unitorigin_high.text
                else:
                    unitorigin_high_combined = ""                    
                
                # DATE of the manuscript (HIGH) 
                unitdate_high = manu.find("./did/unitdate")
                    
                # in case of no unitdate on manuscript level, skippen (Latin 196)
                # Unitdate moet eigenlijk niet eens worden ingevoerd in Manuscript, dat moet via DateRange
                if unitdate_high is None:
                    unit_yearstart_high = "9999"
                    unit_yearfinish_high = "9999"
                    pass

                elif unitdate_high != None and unitdate_high != "" and 'normal' in unitdate_high.attrib:
                    unitdate_normal_high = unitdate_high.attrib.get('normal')
                    ardate_high = unitdate_normal_high.split("/")
                    if len(ardate_high) == 1:
                        unit_yearstart_high = int(unitdate_normal_high)
                        unit_yearfinish_high = int(unitdate_normal_high)
                    else:
                        unit_yearstart_high = int(ardate[0])
                        unit_yearfinish_high = int(ardate[1])

                elif unitdate_high != None and unitdate_high != "" and 'normal' not in unitdate_high.attrib:
                    unitdate_complete_high = unitdate.text
                    if "-" in unitdate_complete_high:
                        # use regex to split up string, will result in list with 4 items. 
                        ardate_high = re.split('[\-\(\)]', unitdate_complete_high)
                    
                        # use positions 3 and to to grab the first and last year
                        unit_yearstart_high = int(ardate[-3]) 
                        unit_yearfinish_high = int(ardate[-2])
                        # use the century indication in Roman numerals to create "virtual" 
                        # start and finish years TH: dit lijkt te werken                    
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
                                                                              
                # ANCIENNE COTES of the manuscript (HIGH)               
                # The old shelfmarks of the manuscript need to be stored in the notes section
                # of the manuscript
                # Create a new string for the storage of ancienne cotes
                old_sm_temp_high = ""
                # Find all old shelfmarks and store them in a string
                for unit_anccote_high in manu.findall("./did/unitid[@type='ancienne cote']"): 
                    old_sm_high = unit_anccote_high.text
                    old_sm_temp_high += old_sm_high + "_"
                                       
                # When all ancienne cotes in the list are handled and placed in one string
                # the underscores are replaced by a comma
                old_sm_temp_comma_high = ', '.join(old_sm_temp_high.split("_"))
                   
                # The last part is getting rid of the last comma at the end of the string
                unit_anccote_final_high = old_sm_temp_comma_high.rstrip(", ")      

                # PROVENANCE of the manuscript (HIGH)

                # Look for the provenance of the manuscript in both <custodhist> 
                # and <origination> elements met Erwin naar kijken

                # Provenance in ORIGINATION (HIGH) TO DO??

                # Provenance in CUSTODHIST (HIGH)
                # Look for the <custodhist> element of the manuscript - if it exists 
                unit_custodhist_high = manu.find("./custodhist/p")
                if unit_custodhist_high != None and unit_custodhist_high != "":
                    # First get all the text from <custodhist>
                    unit_custh_1_high = ''.join(unit_custodhist_high.itertext())                        
                    # Second clean the string
                    unit_custh_2_high = re.sub("[\n\s]+"," ", unit_custh_1_high)                        
                    # Third strip string of spaces 
                    unit_custh_3_high = unit_custh_2_high.strip()                        
                else:
                    unit_custh_3_high = ""
                                
                # Location(s??) (role=4010) in custodhist
                # Store in list, later to be used in the lower manuscripts
                prov_custh_high_list=[]
                for prov_custh_high in manu.findall("./custodhist/p/corpname[@role='4010']"):
                        provtemp_custh_high = prov_custh_high.text 
                        prov_custh_high_list.append(provtemp_custh_high)
                # URL of the manuscript (HIGH) TH: check
                            
                # Look for URL of the manuscript - if it exists                                        
                # Attrib techniek ook voor persname in scopecontent?
                # The URL needs to be added to the manuscript  TH: Ook in HIGH?
                uniturl_high = manu.find("./dao")
                if uniturl_high != None and uniturl_high != "":
                    url_high = uniturl_high.attrib.get('href')
                         
            # Now we return the iteration process
            # Check if the shelfmark that is listed in "shelfmark_set"
            if manuidno in shelfmark_set:
            # Create a new Manuscript if this is the case TH: deze werkwijze voor manifestaties gebruiken?
                manu_obj = Manuscript.objects.create()
                manu_obj.idno = manuidno
                # Add shelfmark to list of processed manuscripts
                lst_manus.append(manuidno)
                
                # TITLE(S) of the manuscript
                # Get the name of the manuscript - if it exists
                # E.g: <unittitle>Biblia sacra, pars.</unittitle>      

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

                    # Check if there is a higher level title available, in case of combined manuscripts.
                    # The number part of the shelfmark of each individual manuscript is used to check if
                    # it belongs to a combined manuscript. If not: only the title(s) of the manuscript itself
                    # will be stored. TH: let op, het kan zijn dat er helemaal geen sprake is van gecombineerde
                    # manuscripten, dan blijft manuidno_end leeg
                    
                    if manuidno_number <= manuidno_end:                     
                        unittitle_final = unittitle_high_combined + ", " + unittitle_stripped                    
                    else:
                        unittitle_final = unittitle_stripped
                        
                    # Now the title of the manuscript can be stored in the database
                    manu_obj.name = unittitle_final
                        
                    
                # ANCIENNE COTES of the manuscript                
                # The old shelfmarks of the manuscript need to be stored in the notes section
                # of the manuscript

                # Create a new string for the storage of ancienne cotes
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
                    
                    # Check if there is a CM, if so use the cotes from the CM 
                    # otherwise use the one from the manuscript itself TH: dit werkt
                    if manuidno_number <= manuidno_end:                     
                        if unit_anccote_final_low == "":
                            unit_anccote_final = unit_anccote_final_high
                        elif unit_anccote_final_low != "":
                            unit_anccote_final = unit_anccote_final_low
                    else:
                        unit_anccote_final = unit_anccote_final_low

                    # Now the combined old shelfmarks can be stored in the database as notes
                    manu_obj.notes = unit_anccote_final
                                                            
                    # SUPPORT and BINDING of the manuscript

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
                    # Hier loopt het nog niet voor die opgesplitste physfascets, niet alles wordt überhaupt 
                    # meegenomen TH: moeten die meegenomen worden? 
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
                        unitsupport_final = unitsupport_high_combined + ", " + unitsupport_low                    
                    else:
                        unitsupport_final = unitsupport_low  
                    
                    # Now the extent of the manuscript can be stored in the database
                    manu_obj.support = unitsupport_final


                    # Check if there is a higher level extent available, in case of combined manuscripts.
                    # TO DO Latin 813-814 is interessant, allerlei info op beide niveaus...ook origin, misschien dat dus ook mee
                    # nemen naar de lagere niveaus...
                    # FORMAT of the manuscript

                    # Look for the format of the manuscript - if it is exists 
                    # (<dimensions>) 
                    unitdimensions = manu.find("./did/physdesc/dimensions")
                    if unitdimensions != None and unitdimensions != "":
                        unitdimensions_low = unitdimensions.text
                    else:
                        unitdimensions_low = ""
                    
                    # Check if there is a higher level format available, in case of combined manuscripts.
                    # Onzeker of de eerste statement werkt als er wel een high maar geen unitdimensions_low is...
                    if manuidno_number <= manuidno_end:                     
                        unitdimensions_final = unitdimensions_high_combined + ", " + unitdimensions_low                 
                    else:
                        unitdimensions_final = unitdimensions_low  
                    
                    # Now the dimenssions of the manuscript can be stored in the database
                    manu_obj.format = unitdimensions_final

                    # EXTENT of the manuscript
                    # Look for the extent of the manuscript - if it is exists 
                    unitextent = manu.find("./did/physdesc/extent")
                    if unitextent != None and unitextent != "":
                        unitextent_low = unitextent.text
                    else:
                        unitextent_low = ""

                    # Check if there is a higher level extent available, in case of combined manuscripts.              
                    if manuidno_number <= manuidno_end:                     
                        unitextent_final = unitextent_high_combined + ", " + unitextent_low                    
                    else:
                        unitextent_final = unitextent_low  
                    
                    # Now the extent of the manuscript can be stored in the database
                    manu_obj.extent = unitextent_final
                    
                    # ORIGIN of the manuscript 
                    # Look for the origin of the manuscript - if it exists                    
                    unitorigin = manu.find("./did/physdesc/geogname")
                    if unitorigin != None and unitorigin != "":
                       unitorigin_low = unitorigin.text
                    else:
                        unitorigin_low = ""
                    
                    # Check if there is a higher level origin available, in case of combined manuscripts.              
                    if manuidno_number <= manuidno_end:                     
                        unitorigin_final = unitorigin_high_combined + " " + unitorigin_low                    
                    else:
                        unitorigin_final = unitorigin_low  
                  
                    # Check if unitorigin is not empty TH: moet dit niet overal gebeuren?
                    if unitorigin_final != None and unitorigin_final != "":
                                       
                        # Store the origin in a new Origin record, possibly add notes TH: overleg Erwin over link met LOCATION
                        origin = Origin.objects.create(name = unitorigin_final)

                        # Store the id of the origin in Manuscript
                        manu_obj.origin_id = origin

                    # PROVENANCE of the manuscript

                    # Look for the provenance of the manuscript in both <custodhist> 
                    # and <origination> elements met Erwin naar kijken

                    # Provenance in CUSTODHIST 

                    # Look for the <custodhist> element of the manuscript - if it exists 
                    unit_custodhist = manu.find("./custodhist/p")
                    if unit_custodhist != None and unit_custodhist != "":
                        # First get all the text from <custodhist>
                        unit_custh_1 = ''.join(unit_custodhist.itertext())
                        
                        # Second clean the string
                        unit_custh_2 = re.sub("[\n\s]+"," ", unit_custh_1)
                        
                        # Third strip string of spaces 
                        unit_custh_3 = unit_custh_2.strip()
                        
                    else:
                        unit_custh_3 = ""                                 

                    # Location(s??) (role=4010) in custodhist
                    # Dit werkt maar moet nog laten werken zonder locatie?                                                                
                    for prov_custh in manu.findall("./custodhist/p/corpname[@role='4010']"):
                        provtemp_custh = prov_custh.text                       
                        
                        if provtemp_custh != None:
                            # Create new Provenance with shelfmark added to it
                            prov_shelfmark = provtemp_custh + " " + manu_obj.idno

                            # Look for existing location first match?? Is dat wijselijk? Laten we dit maar even uitstellen
                            # Overleg Erwin TH: dit hier houden
                           
                            # Store the combination in a new provenances record and add notes if they exist
                            prov = Provenance.objects.create(name = prov_shelfmark, note = unit_custh_3)
                           
                            # Create new ProvenanceMan object to link manuscript to provenance(s)                       
                            prov_man = ProvenanceMan.objects.create(manuscript = manu_obj, provenance = prov)

                    # Take care of the provenances and notes from <custodhist> element from the CM if available
                    # unit_custh_3_high, prov_custh_high_list HIGH       
                    # see if there are provenances from the CM if there is one
                    if manuidno_number <= manuidno_end:
                        for prov_custh_high in prov_custh_high_list:
                            
                            prov_shelfmark_high = prov_custh_high + " " + manu_obj.idno
                        
                            # Store the combination in a new provenances record and add notes if they exist
                            prov = Provenance.objects.create(name = prov_shelfmark_high, note = unit_custh_3_high)
                        
                            # Create new ProvenanceMan object to link manuscript to provenance(s)                       
                            prov_man = ProvenanceMan.objects.create(manuscript = manu_obj, provenance = prov)
                            
                            
                    # Provenance in ORIGINATION 

                    # Look for the <origination> element of the manuscript - if it exists
                    # Bijvoorbeeld Latin 113, er is origination maar wordt niet opgeslagen omdat er geen locatie is?
                    # vraag voor SB Ik zou zeggen alles opslaan als er orignation is EVENTUEEL locatie apart als dat er
                    # maar niet van laten afhangen dus

                    unit_origination = manu.find("./did/origination")
                    if unit_origination != None and unit_origination != "":
                        # First get all the text from <origination>
                        unit_orig_1 = ''.join(unit_origination.itertext())
     
                        # Second clean the string
                        unit_orig_2 = re.sub("[\n\s]+"," ", unit_orig_1)
                  
                        # Third strip string of spaces 
                        unit_orig_3 = unit_orig_2.strip()
                 
                    else:
                        unit_orig_3 = ""
                    
                    # Locations (role=4010) in origination                                                
                    for prov in manu.findall("./did/origination/corpname[@role='4010']"):
                        provtemp = prov.text
               
                        if provtemp != None:
                           # We moeten kijken of de provenance niet bestaat, dan pas een nieuwe toevoegen
                           # Wat te doen met notes? Wellicht alles tussen de <origination> tags?
                            
                           # Create new Provenance with shelfmark added to it
                           prov_shelfmark = provtemp + " " + manu_obj.idno

                           # Look for existing location first match?? Is dat wijselijk? Laten we dit maar even uitstellen
                           
                           # Store the combination in a new provenances record and add notes if they exit TH: if empty?
                           prov = Provenance.objects.create(name = prov_shelfmark, note = unit_orig_3)
                           
                           # Create new ProvenanceMan object to link manuscript to provenance(s)                       
                           prov_man = ProvenanceMan.objects.create(manuscript = manu_obj, provenance = prov)
                         
                    # XML FILENAME of the range of manuscripts

                    # Look for the filename of the XML in which the manuscripts are stored
                    # The filename needs to be added to each manuscript  
                    unitfilename = manu_info.find("./eadid")
                    if unitfilename != None and unitfilename != "":
                        manu_obj.filename = unitfilename.text
                    
                    # URL of the manuscript
                            
                    # Look for URL of the manuscript - if it exists                                        
                    # Attrib techniek ook voor persname in scopecontent?
                    # The URL needs to be added to the manuscript  TH: Ook in HIGH?
                    uniturl = manu.find("./dao")
                    if uniturl != None and uniturl != "":
                        url = uniturl.attrib.get('href')
                        manu_obj.url = url                    
                   
                   # DATE(s) of the manuscript
                   # DONDERDAG mee verder, goed testen eerst Latin 196
                   # De if statement is niet juist volgens mij                      
                   # Try to get the date, e.g:
                   # <unitdate normal="1101/1200" era="ce" calendar="gregorian">XIIe siècle</unitdate>

                   # Exceptions: 
                
                   # <unitdate calendar="gregorian" era="ce">IXe s. (845-851)</unitdate>
                   # <unitdate calendar="gregorian" era="ce">IXe s. (fin?)</unitdate>
                   # <unitdate calendar="gregorian" era="ce">Ve s. (f. 9-16); VIIe s. (f. 1-8); IXe s. (f. 17-31)</unitdate>
                  
                    # Let op: het is mogelijk om meer dan 1 datum range op te slaan
                    print(manuidno)
                    unitdate = manu.find("./did/unitdate")
                    # start with unitdate = None
                    # in case of no unitdate on manuscript level, skippen (Latin 196)
                    # Unitdate moet eigenlijk niet eens worden ingevoerd in Manuscript, dat moet via DateRange
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
                        if "-" in unitdate_complete:
                            # use regex to split up string, will result in list with 4 items. 
                            ardate = re.split('[\-\(\)]', unitdate_complete)
                    
                            # use positions 3 and to to grab the first and last year
                            unit_yearstart_low = ardate[-3] 
                            unit_yearfinish_low = ardate[-2]
                            # use the century indication in Roman numerals to create "virtual" 
                            # start and finish years TH: dit lijkt te werken                    
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
                    
                    # Check if there is a higher level date available, in case of combined manuscripts.      
                    # Hier anders aanpakken        
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
                    # Dit gaat goed, ook igv de lager gelegen unitdates, in manuscript wordt vermoedelijk de eerste getoond van de 
                    # bijbehorende records in Daterange.
                    if unit_yearstart != "":
                        drange = Daterange.objects.create(manuscript=manu_obj, yearstart = unit_yearstart, yearfinish = unit_yearfinish)
                        print(drange)
                
                    # Add the id's of the project, library, lcountry and lcity:
                    unitproject_id = 1
                
                    # zie mail Erwin, dit moet anders Manuscript Details
                    # Dit moet ik nog eens uitzoeken, zou niet zo lastig moeten zijn
                    # Helper functies? Zie wat ik eerder heb gedaan met username??

                    #instance.project = Project.get_default(self.request.user.username)
                    #project_id = Project.get_default(username)
                               
                    unitlibrary_id = 1160 # Bibliothèque nationale de France, Manuscrits
                    unitcity_id = 616 # Paris
                    unitcountry_id = 21 # France
                
                    # Add project id to the manuscript                               
                    manu_obj.project_id = unitproject_id

                    # Add library id to the manuscript
                    manu_obj.library_id = unitlibrary_id
                
                    # Add city id to the manuscript
                    manu_obj.lcity_id =  unitcity_id
                
                    # Add country id to the manuscript
                    manu_obj.lcountry_id = unitcountry_id
                
                    # NOTES/COMMENTS    
                    
                    # Get to sermons, hier een lijst van te maken, helaas komt scopecontents twee keer voor bij 
                    # sommige manuscripten zoals LAtin 196
                    # Find notes/comments in scopecontents only when there is a <c> element with manifestations

                    # First get the contents 
                    check_on_c_element = manu.findall("./c")
                    # See if there are nested <c> elements...
                    if len(check_on_c_element) > 0: 
                        # and if there are, pick up the <p> elements in scopecontents, these are not manifestations
                        # but should be considerend as notes/comments.
                        for unit_p in manu.findall("./scopecontent/p"):
                            if len(unit_p) > 0: 
                                note = ElementTree.tostring(unit_p, encoding="unicode")
                                print(note)
                                # Maybe clean string from elements and stuff
                                # Maybe change the sequence
                                note_1 = re.sub("[\n\s]+"," ", note)
                                note_2 = note_1.replace('<p>', '')
                                note_3 = note_2.replace('</p>', '')

                                # Get profile 
                                # profile = get_user_profile(username)  TH methode                                    
                                profile = Profile.get_user_profile(username) # EK methode
                                otype = "sermo"
                                                                
                                # Create new Comment, add profile, otype and the comment
                                comment_obj = Comment.objects.create(profile=profile, content=note_3, otype=otype)
                                # Add new comment to the manuscript                            
                                manu_obj.comments.add(comment_obj)

                    else:
                        pass
                        
                    # MANIFESTATIONS
                     
                    # Hier nu ook met msitem rekening houden, hier zit de structuur in. 
                    # Elke manifestatie of sermhead heeft een eigen msitem, meer niet. 
                    # Eerst alles op orde brengen en de msitems aanmaken, dan nog een ronde over de
                    # lijsten heen en dan de relaties bepalen
                    # Stap 1 is aanmaken van een msitem bij elke sermhead en elke manifestatie
                    # Stap 2 is de relaties tussen die bepalen, in sermhead kun je alleen de title invullen, de 
                    # locus wordt automatisch bepaald....
                    # Automatisch aanmaken dus als eerste. 
                    # Zie voorbeeld 1773 en 113 (maar 1 p)
                    # Misschien zoeken naar alle vormen, bij 196 komt er meer dan 1 keer scopecontent voor
                    # Opties: 1. Scopecontent met 1 keer <p> met meerdere manifestaties gescheiden door <lb/>
                    # 2. Scopecontent met meer dan 1 keer <p> dat elke manifestatie markeerd

                    # Hoe dan ook: in eerste instantie staat alles dus in scopecontent, mogelijk meer dan 1 scopecontent per 
                    #manuscript. Dit is dus voor als er geen lager gelegen c niveau is..
                    # Dit voorleggen aan EK, eerst ff synchen
                    # Misschien eerst de variant zonder <c> check doen?
                    # Moet dan niet hier naar scopecontent op het hoogste niveau gekeken worden?
                    # Eigenlijk moet voor bijv Latin 113 hier worden ingesprongen
                    # Aangezien er in Latin 196 ook een scopecontent staat moet die genegeerd worden want er moet dan naar
                    # Zie aantekening shari, die moet wel meegenomen worden in notes oid, ok, geen punt aanpassen maar
                    # de <c> elementen gekeken worden
                    
                    # zie Latin 2027, nog een variant? Nu wordt de complete inhoud meegenomen, inclusief de elements, beter alleen
                    #  de tekst

                    # IN CASE THERE ARE NO NESTED <c> ELEMENTS (SermDescr)
                    # Check if there are titles, heads and manuscripts in nested <c> elements
                    # First if the above is not the case:
                    if len(check_on_c_element) < 1: 
                        # print("This part works!")
                        # Create a list to store the msitems from the manifestations
                        # for processing later on                            
                        msitems_children = []

                        # Create a list to store the titles of the manifestations
                        # for processing later on
                        sermon_manif_titles_3 = []
                        # Go through all <p> elements
                        for unit_p in manu.findall("./scopecontent/p"):
                            sermon_manif_titles_1 = ElementTree.tostring(unit_p, encoding="unicode")
                            if unit_p is None:
                                pass
                        # In case in the <p> element the manifestations are separated by a <lb/> as a 
                        # selfclosing element, for example with Latin 113:     WOENSDAG mee verder  
                        # # https://stackoverflow.com/questions/57622731/python-extract-attributes-from-a-self-closing-element-with-same-name-as-other-e  
                            elif '<lb />' in sermon_manif_titles_1:  
                                # DIT IS NIEUW
                                #for unit_lb in unit_p.findall(".//lb"):
                                #    lb_serm_manif_title_join = ''.join(unit_lb.itertext())
                                #    print (lb_serm_manif_title_join)

                                # DIT IS OUD, met NIEUW te integreren
                                
                                # Here a list is made by splitting up sermon_manif_titles_1
                                sermon_manif_titles_2 = sermon_manif_titles_1.split('<lb />')
                            # Clean titles and store in new list 
                            # is dit nodig?? Would it be possible to see if some parts could be extracted?
                            # Folia, author,title inc en expl? Terwijl elk deel langskomt? Dus alleen als er aan bepaalde
                            # voorwaarden wordt voldaan. Als er een ":" is, split en deel[0] is folio? 
                                for title in sermon_manif_titles_2:
                                    title_1 = re.sub("[\n\s]+"," ", title)
                                    #title_2 = re.sub('<[^>]+>', '', title_2)
                                    title_2 = title_1.strip()
                                    
                                    # Store the titles in a new list
                                    sermon_manif_titles_3.append(title_2)   
                                #for title in sermon_manif_titles_3:
                                    # How to extract the folio?
                                 #   titles_spaced = title.split("ff. ")
                                  #  title_folio = titles_spaced[0]
                                   # print(title_folio)
                                        # how to extract the inc?
                                        # my_string="hello python world , i'm a beginner "
                                # print my_string.split("world",1)[1] 
                                # Menna: dat wat uit de string voor title gehaald kan worden kan ook uit string weggehaald worden
                                    
                                    # Create MsItem to store the correct sequence of title, head and manifestations
                                    # Use order to count the number of MsItems
                                    msitem = MsItem.objects.create(manu=manu_obj, order=order)

                                    # Add each msitem for each manifestation to the list
                                    msitems_children.append(msitem)

                                    # Add 1 to order
                                    order += 1
                                    # Store manifestations in title in SermDescr with MsItems:
                                    serm_obj = SermonDescr.objects.create(manu = manu_obj, msitem = msitem, title = title)
                        
                            # In case the manifestations are better described in scopecontent 
                            # for instance Latin 309 and 330, 1788 example?):
                            # TH: dit werkt maar hoe de folio eruit? 
                            elif '<lb />' not in sermon_manif_titles_1:
                                
                                # First go through all manifestations (all <p> elements)
                                serm_manif_title_join = ''.join(unit_p.itertext())
                                serm_manif_title = re.sub("[\n\s]+"," ", serm_manif_title_join)
                                sermon_manif_titles_3.append(serm_manif_title)
                                

                                # Check if there is also a head/folio
                                # Hoe werkt dit in de bestaande loop? bekijkt dus al elk <p> element
                                # dus steeds in dat element kijken?? Hoe kan ik dat <num> deel uit serm_manif_title halen? 
                                # Overleg met Erwin na eerst zelf te kijken
                                sermon_head = unit_p.find("./num")
                                if sermon_head != None and sermon_head != "":
                                    serm_folio = sermon_head.text
                                    print(serm_folio)
                                else: 
                                    serm_folio = ''
                                
                                # Create MsItem to store the correct sequence of title, head and manifestations
                                # Use order to count the number of MsItems
                                msitem = MsItem.objects.create(manu=manu_obj, order=order)

                                # Add each msitem for each manifestation to the list
                                msitems_children.append(msitem)

                                # Add 1 to order
                                order += 1
                                # Store manifestations in title in SermDescr with MsItem:
                                serm_obj = SermonDescr.objects.create(manu = manu_obj, msitem = msitem, title = serm_manif_title, locus = serm_folio)
                    
                    # Now the next_id's need to be taken care of for the msitems in this manuscript
                    # TH: dit werkt, alleen next want geen parents en dus ook geen first children
                        with transaction.atomic():
                            for idx, msitem in enumerate(msitems_children):
                            # Treat the next
                                if idx < len(msitems_children) - 1:
                                    msitem.next = msitems_children[idx+1]
                                    msitem.save()            

                    
                    # IN CASE OF NESTED <c> ELEMENTS (SermHead, DateRange, SermDescr)
                    # Check if the manuscript is structured as Latin 196 (with one or more 
                    # manifestations within the <c> elements)
                    elif len(check_on_c_element) > 0: 
                        # Create list to store the parents of the msitems (of the manifestations)
                        msitems_parents = []
                        # Loop trough all <c> elements                        
                        for unit_c in manu.findall("./c"):
                            
                            # First: find folio
                            # Bij Latin 1970 gaat dit mis, is sowieso een aparte zo te zien
                            # ook geen unittitle en gedoe met jaartal ff uit de lijst
                            sermon_head = unit_c.find("./head")

                            if sermon_head != None and sermon_head != "":
                                serm_folio = sermon_head.text
                                                        
                            # Second: find date 
                            # Date should be stored at the Manuscript level (in Daterange) 
                            sermon_date = unit_c.find("./did/unitdate")
                            # Find out if there is a date and in what way the date is structured.
                            if sermon_date is None:
                                sermon_yearstart = "9999"
                                sermon_yearfinish = "9999"
                                pass
                            
                            # HIER MOET NOG DE ANDERE OPTIE KOMEN, 'normal' in sermon_date.attrib:
                            # HIER DONDERDAG mee verder! aanpassen unitdate TH: Latin 1970 lijkt te werken
                            elif sermon_date != None and sermon_date != "" and 'normal' in sermon_date.attrib:
                                sermon_date_normal = sermon_date.attrib.get('normal')
                                ardate = sermon_date_normal.split("/")
                                if len(ardate) == 1:
                                    sermon_yearstart = int(unitdate_normal)
                                    sermon_yearfinish = int(unitdate_normal)
                                else:
                                    sermon_yearstart = int(ardate[0])
                                    sermon_yearfinish = int(ardate[1])

                            elif sermon_date != None and sermon_date != "" and 'normal' not in sermon_date.attrib:
                                sermon_date_complete = sermon_date.text
                                # See if there is an indication of a range in the date
                                # If there is no range, we assume for know Roman numerals are used
                                if "-" not in sermon_date_complete:
                                    date_split = sermon_date_complete.split('e ')
                                    if len(date_split) < 3:  
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
                            if sermon_yearstart != "9999":
                                drange = Daterange.objects.create(manuscript=manu_obj, yearstart = sermon_yearstart, yearfinish = sermon_yearfinish)
                                print(drange)
                            # Third: find section title
                            # TH: idealiter niet dat folio meenemen, check hoe het anders moet voorlopig wel even goed zo 
                                                        
                            sermon_unittitle = unit_c.find("./did/unittitle")
                            sermon_title_1 = ''.join(sermon_unittitle.itertext())
               
                            # Second clean the string
                            sermon_title_2 = re.sub("[\n\s]+"," ", sermon_title_1)
                      
                            # Third strip string of spaces TH: is dit nodig?
                            sermon_title_3 = sermon_title_2.strip()
                                                       
                            # Now we have the folio/head and the title we can store them in SermHead
                                                                                   
                            # Create MsItem to store the correct sequence of title, head and manifestations 
                            # Use order to count the number of MsItems 
                            msitem_parent = MsItem.objects.create(manu=manu_obj, order=order) 
                            msitems_parents.append(msitem_parent)

                            # Add 1 to order
                            order += 1 
                           
                            # Store title and folio in SermHead with MsItem:                            
                            sermhead_obj = SermonHead.objects.create(msitem = msitem_parent, title = sermon_title_3, locus = serm_folio)
                                                    
                            # MANIFESTATIONS (with <c> element)
                                                        
                            # Grab contents in p under scopecontent in order to
                            # later on store the sermon manifestations
                            scopecontent_p = unit_c.find("./scopecontent/p")
                            
                            # Zie ook 1788 dit is eigenlijk hetzelfde als boven, 

                            # Create sermon manifestation title 
                            # (store only if there are no multiple sermon manifestations)
                            # Moeten die %% er nog uit?
                            serm_manif_title = '%%'.join(scopecontent_p.itertext())
                            sermon_manif_titles_1 = ElementTree.tostring(scopecontent_p, encoding="unicode")
                                            
                            # Ahhhh, in LAtin 196 gaat het natuurlijk in <c> op verschillende wijzen

                            # Differentiatie between scopecontent_p with 1 or more manifestaties, 
                            # separated with an <lb/> element, first 1 manifestation:
                            if '<lb />' not in sermon_manif_titles_1:
                                print(serm_manif_title)
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
                                # Store manifestations in title in SermDescr with MsItem:
                                serm_obj = SermonDescr.objects.create(manu = manu_obj, msitem = msitem, title = serm_manif_title)
                                
                            # Dit lijkt goed te gaan maar is niet ideaal want er 
                            # blijven soms codes in de sermon zitten

                            # Second, with multiple manifesations:                                                        
                            elif '<lb />' in sermon_manif_titles_1:                                
                                # Split up the string maar er komt geen list uit. TH: werkt nog niet, wordt niet gesplitst!
                                sermon_manif_titles_3 = []
                                sermon_manif_titles_2 = sermon_manif_titles_1.split('<lb />')
                                # Clean titles and store in new list
                                # is dit nodig??
                                for title in sermon_manif_titles_2:
                                    title_1 = re.sub("[\n\s]+"," ", title)
                                    
                                    title_2 = title_1.strip()
                                    print(title_2)
                                    sermon_manif_titles_3.append(title_2)
                                                                   
                                # Create a list to store the msitems from the manifestations
                                # for processing later on                            
                                msitems_children = []

                                # Opslaan van de inhoud van de lijst
                                # Create new Sermon Description TH: werkt het nou goed? Nee, laatste title = "</p>"
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
                            # Dit handelt dus alleen in MsItems eea af!
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
                                                
                            # The last part related to the MsItems is adding the next_id to 
                            # the msitem parents (not the last one!)                             
                        with transaction.atomic():
                            for idx, msitem in enumerate(msitems_parents):
                                # Treat the next 
                                if idx < len(msitems_parents) - 1: 
                                    msitem.next = msitems_parents[idx+1] 
                                    msitem.save()                             
                        # Create new Daterange object, store yearstart and year finish
                        # CHECKEN DIT
                        drange = Daterange.objects.create(manuscript=manu_obj, yearstart = sermon_yearstart, yearfinish = sermon_yearfinish)

                    # Save the results
                    manu_obj.save()
                
                    # Look for external references TH tijdelijk even eruit!
                    for extref in manu.findall("./bibliography/bibref/extref"):
                        if extref is None:
                            continue
                        url = extref.attrib.get('href')
                        if url != None:
                            # Create new ManuscriptExt
                            mext = ManuscriptExt.objects.create(manuscript=manu_obj, url=url)
            
            # Take care of collection of manuscripts under one shelfmark for example: Latin 2013-2023

            
            pass
            
             
     #def read_msitem(msItem, oParent, lMsItem, level=0):
     #   """Recursively process one <msItem> and return in an object"""
        
     #   errHandle = ErrHandle()
     #   sError = ""
     #   nonlocal order
            
     #   level += 1
     #   order  += 1
     #   try:
     #       # Create a new item
     #       oMsItem = {}
     #       oMsItem['level'] = level
     #       oMsItem['order'] = order 
     #       oMsItem['childof'] = 0 if len(oParent) == 0 else oParent['order']

     #       # Already put it into the overall list
     #       lMsItem.append(oMsItem)

     #       # Check if we have a title
     #       if not 'unittitle' in oMsItem:
     #           # Perhaps we have a parent <msItem> that contains a title
     #           parent = msItem.parentNode
     #           if parent.nodeName == "msItem":
     #               # Check if this one has a title
     #               if 'unittitle' in parent.childNodes:
     #                   oMsItem['unittitle'] = getText(parent.childNodes['unittitle'])

     #       # If there is no author, then supply the default author (if that exists)
     #       if not 'author' in oMsItem and 'author' in oParent:
     #           oMsItem['author'] = oParent['author']

     #       # Process all child nodes
     #       lastChild = None
     #       lAdditional = []
     #       for item in msItem.childNodes:
     #           if item.nodeType == minidom.Node.ELEMENT_NODE:
     #               # Get the tag name of this item
     #               sTag = item.tagName
     #               # Action depends on the tag
     #               if sTag in mapItem:
     #                   oMsItem[mapItem[sTag]] = getText(item)
     #               elif sTag == "note":
     #                   if not 'note' in oMsItem:
     #                       oMsItem['note'] = ""
     #                   oMsItem['note'] = oMsItem['note'] + getText(item) + " "
     #               elif sTag == "msItem":
     #                   # This is another <msItem>, a child of mine
     #                   bResult, oChild, msg = read_msitem(item, oMsItem, lMsItem, level=level)
     #                   if bResult:
     #                       if 'firstChild' in oMsItem:
     #                           lastChild['next'] = oChild
     #                       else:
     #                           oMsItem['firstChild'] = oChild
     #                           lastChild = oChild
     #                   else:
     #                       sError = msg
     #                       break
     #               else:
     #                   # Add the text to 'additional'
     #                   sAdd = getText(item).strip()
     #                   if sAdd != "":
     #                       lAdditional.append(sAdd)
     #       # Process the additional stuff
     #       if len(lAdditional) > 0:
     #           oMsItem['additional'] = " | ".join(lAdditional)
     #       # Return what we made
     #       return True, oMsItem, "" 
     #   except:
     #       if sError == "":
     #           sError = errHandle.get_error_message()
     #       return False, None, sError
    
    #def add_msitem(msItem, type="recursive"):
    #    """Add one item to the list of sermons for this manuscript"""

    #    errHandle = ErrHandle()
    #    sError = ""
    #    nonlocal iSermCount

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

    # HIER DUS CODE TOEVOEGEN
    # TH: dit werkt dus van uit de browser denk ik
    # is wel anders want geen losse bestanden zoals bij de zwitserse site
    # Moet ik dit niet apart testen? Wat hieronder staat is nogal...weinig
    # ook bij Manuscript.codex kijken en andee delen genoemd in mail van Erwin read_ecodex in models.py
    # hoe zit dit samen?
    
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
        
        # Create a status object # TH: type goed aangepast?
        oStatus = Status(user=username, type="ead", status="preparing")
        oStatus.save()

        form = UploadFilesForm(request.POST, request.FILES)
        lResults = []
        if form.is_valid():
            # NOTE: from here a breakpoint may be inserted!
            print('import_ead: valid form') # TH: import_ aangepast import ead_am?

            # Create a SourceInfo object for this extraction
            source = SourceInfo(url="https://ccfr.bnf.fr/", collector=username) # TH: aanpassen, klopt niet, ccfr
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
                            oResult = read_ecodex(username, data_file, filename, arErr, source=source) # TH:aanpassen , models.py

                        # Determine a status code
                        statuscode = "error" if oResult == None or oResult['status'] == "error" else "completed"
                        if oResult == None:
                            arErr.append("There was an error. No manuscripts have been added")
                        else:
                            lResults.append(oResult)
            # Adapt the 'source' to tell what we did
            source.code = "Imported using the [import_ead??] function on these XML files: {}".format(", ".join(file_list)) # TH: aanpassen
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

                # Adapt the 'source' to tell what we did TH: waar staat import_ecodex?
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

            form = self.mForm(request.POST, request.FILES)
            lResults = []
            if form.is_valid():
                # NOTE: from here a breakpoint may be inserted!
                print('import_{}: valid form'.format(self.import_type))
                oErr = ErrHandle()
                try:
                    # The list of headers to be shown
                    lHeader = ['status', 'msg', 'name', 'yearstart', 'yearfinish', 'library', 'idno', 'filename', 'url']

                    # Create a SourceInfo object for this extraction
                    source = SourceInfo.objects.create(url=self.sourceinfo_url, collector=username)

                    # Process the request
                    bOkay, code = self.process_files(request, source, lResults, lHeader)

                    if bOkay:
                        # Adapt the 'source' to tell what we did 
                        source.code = code
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
