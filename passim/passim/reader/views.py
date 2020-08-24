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
import xml.etree.cElementTree as ElementTree


# ======= imports from my own application ======
from passim.settings import APP_PREFIX, MEDIA_DIR
from passim.utils import ErrHandle
from passim.reader.forms import UploadFileForm, UploadFilesForm
from passim.seeker.models import Manuscript, SermonDescr, Status, SourceInfo, ManuscriptExt, Provenance, ProvenanceMan, \
    Library, Location, SermonSignature, Author, \
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
                if 'feast' in msItem and sermon.feast != msItem['feast']: sermon.feast = msItem['feast'] ; bNeedSaving = True
                # OLD (doesn't exist in e-codices)if 'keyword' in msItem and sermon.keyword != msItem['keyword']: sermon.keyword = msItem['keyword'] ; bNeedSaving = True
                if 'bibleref' in msItem and sermon.bibleref != msItem['bibleref']: sermon.bibleref = msItem['bibleref'] ; bNeedSaving = True
                if 'additional' in msItem and sermon.additional != msItem['additional']: sermon.additional = msItem['additional'] ; bNeedSaving = True
                if 'note' in msItem and sermon.note != msItem['note']: sermon.note = msItem['note'] ; bNeedSaving = True
                if 'order' in msItem and sermon.order != msItem['order']: sermon.order = msItem['order'] ; bNeedSaving = True

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
            
        # Eerst de algemene info in de XML? Nee, beter eerst de specifieke en dan steeds terug naar de bovenste
        # algemene delen van de XML 
     
        # (1) Find all the manuscripts in this XML document (use ecodex) 
        # This is the highest "c" level, there is at least one level "c" lower
        # Latin 12 (1-3), 14 etc. Maar werkt dit wel? manu_list heeft niet zoveel results
        #
        manu_list = xmldoc.find("//dsc").getchildren()
        
        # Go through list of manu's highest level, example: <did>, <custodhist>, <bibliography>, <scope content>, 
        # <bibliography>, <control access> (3x), <c> (with the sub manuscripts!)
        for manu in manu_list:
            # x are the underlying tags of the above mentioned tags, for instance <did> with: <unitid> (3x),
            # <unittitle>, <physdesc>, <langmaterial> and <unitdate>
            x = str(manu.getchildren()) #  wat doet "str"?
            y = manu.getchildren() # is dit okay? wat is het verschil?
            z = manu.attrib 
            print(z)

            # Get the shelfmark of this manuscript (assuming this level represents a whole manuscript)
            unitid = manu.find("./did/unitid[@type='cote']")
            if unitid != None and unitid != "":
                # THis is the shelfmark
                manuidno = unitid.text

                # Create a new Manuscript
                manu_obj = Manuscript.objects.create()
                manu_obj.idno = manuidno

                # Get the name of the manuscript - if it exists
                # E.g: <unittitle>Biblia sacra, pars.</unittitle>
                unittitle = manu.find("./did/unittitle")
                if unittitle != None and unittitle != "":
                    manu_obj.name = unittitle.text

                # Try to get the date, e.g:
                #   <unitdate normal="1101/1200" era="ce" calendar="gregorian">XIIe siècle</unitdate>
                unitdate = manu.find("./did/unitdate")
                if unitdate != None and unitdate != "" and 'normal' in unitdate.attrib:
                    unitdate_normal = unitdate['attrib']
                    ardate = unitdate_normal.split("/")
                    if len(ardate) == 1:
                        manu_obj.yearstart = int(unitdate_normal)
                        manu_obj.yearfinish = int(unitdate_normal)
                    else:
                        manu_obj.yearstart = int(ardate[0])
                        manu_obj.yearfinish = int(ardate[1])


                # Save the results
                manu_obj.save()

                # Look for external references
                for extref in manu.findall("./bibliography/bibref/extref"):
                    url = extref.attrib.get('href')
                    if url != None:
                        # Create new ManuscriptExt
                        mext = ManuscriptExt.objects.create(manuscript=manu_obj, url=url)

            #did = manu.findall("./did/unitid")

            ## Find the manuscripts within the manuscripts? 
            #for letter in y:
            #    new_list = y.findall('.')   # hier gaat het niet goed  
            #    for new in new_list:
            #        a = new.getchildren()

            #pass


            # if 
          
            # Process all XML elements of this manuscript TH: op dit moment zit er nog niks in
            # What are the elements? Title first 
            # Moet je dan de lijst met id's gebruiken?
        #    for id 
            
        #    title = 

        #    # Get the title
                       
        #    oInfo['name'] = getText(title)
        #    # Get the main title, to prevent it from remaining empty
        #    title_list = xmldoc.getElementsByTagName("titleStmt")
        #if title_list.length > 0:
        #    # Get the first title
        #    title = title_list[0]
        #    oInfo['name'] = getText(title)
               

         
 
        #if dsc.length > 0:
               
        #    # Set the method to process [msItem]
        #    itemProcessing = "recursive"
        #    lItems = []
        #    # order = 0

        #    # Action depends on the processing type
        #    if itemProcessing == "recursive":
        #        # Get to the *first* (and only) [c] item
        #        high_c = dsc.getElementsByTagName("c")
        #        for cOne in high_c:
        #            for item in cOne.childNodes:
        #                if item.nodeType == minidom.Node.ELEMENT_NODE and item.tagName == "c":
        #                    # Now we have one 'top-level' <msItem> instance
        #                    manu_high = item
        #                    # Process this top-level item 
        #                    bResult, oMsItem, msg = read_msitem(msItem, {}, lst_msitem)
        #                    # Add to the list of items -- provided it is not empty
        #                    if len(oMsItem) > 0:
        #                        lItems.append(oMsItem)    

        

        


        # dit moet weg, itereren over de childnotes
       

        # de manuscripten zijn gelaagd, iig twee lagen, zie bijv Latin 12 (1-3)
        # Latin 12 1 - 3 vallen na elkaar onder Latin 12 (1-3)
        # je kunt hier niet xmldoc.getElements gebruiken omdat er steeds meer dan 1 is in elke file, met die
        # methode pak je alles in 1 keer.

        

            
            ## Try to get an URL from each description 
            #url = ""
            #dao_list = xmldoc.getElementsByTagName("dao")
            #for dao in dao_list:
            #    if 'href' in dao_list.attributes: # tot hier gaat het goed, daarna niet meer
            #        url = dao_list.attributes["href"].value
            #oInfo['url'] = url
        
            ## Try to get a main author
            #mainAuthor = ""
            #authors = xmldoc.getElementsByTagName("persName")
            #for person in authors:
            #    # Check if this is linked as author
            #    if 'role' in person.attributes and person.attributes['role'].value == "0070":
            #        mainAuthor = getText(person)
            #        # Don't look further: the first author is the *main* author of it 
            #        # TH: geldt dit ook hier? Wat gebeurt er eigenlijk met deze naam?
            #        break

            ## Get the main title, to prevent it from remaining empty
            #title_list = xmldoc.getElementsByTagName("unittitle")
            #if title_list.length > 0:
            #    # Get the first title
            #    title = title_list[0]
            #    oInfo['name'] = getText(title)
            
            ## Try to get the identifier
            #unitid_list = xmldoc.getElementsByTagName("unitid")
            #if unitid_list.length > 0:
            #    # Get the first unitid
            #    id = unitid_list[0]
            #    oInfo['name'] = getText(id) 
        
           

            
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
