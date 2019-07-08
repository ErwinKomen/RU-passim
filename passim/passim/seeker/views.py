"""
Definition of views for the SEEKER app.
"""

from django.contrib import admin
from django.contrib.auth import login, authenticate
from django.contrib.auth.models import Group
from django.core.urlresolvers import reverse
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.db import transaction
from django.db.models import Q
import operator
from functools import reduce

from django.db.models.functions import Lower
from django.forms import formset_factory, modelformset_factory, inlineformset_factory
from django.http import HttpRequest, HttpResponse, HttpResponseRedirect
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render, redirect
from django.template.loader import render_to_string
from django.views.generic.detail import DetailView
from django.views.generic.base import RedirectView
from django.views.generic import ListView, View
from django.views.decorators.csrf import csrf_exempt
from datetime import datetime
from time import sleep

from passim.settings import APP_PREFIX, MEDIA_DIR
from passim.utils import ErrHandle
from passim.seeker.forms import SearchCollectionForm, SearchManuscriptForm, SearchSermonForm, LibrarySearchForm, SignUpForm, \
                                AuthorSearchForm, UploadFileForm, UploadFilesForm, ManuscriptForm, SermonForm, SermonGoldForm, \
                                SelectGoldForm, SermonGoldSameForm, SermonGoldSignatureForm, AuthorEditForm, \
                                SermonGoldEditionForm, SermonGoldFtextlinkForm, SermonDescrGoldForm, SearchUrlForm, \
                                SermonDescrSignatureForm, SermonGoldKeywordForm, EqualGoldLinkForm, EqualGoldForm, \
                                ReportEditForm
from passim.seeker.models import get_current_datetime, process_lib_entries, adapt_search, get_searchable, get_now_time, add_gold2equal, add_equal2equal, Country, City, Author, Manuscript, \
    User, Group, Origin, SermonDescr, SermonGold,  Nickname, NewsItem, SourceInfo, SermonGoldSame, SermonGoldKeyword, Signature, Edition, Ftextlink, \
    EqualGold, EqualGoldLink, Location, LocationName, LocationIdentifier, LocationRelation, LocationType, \
    Report, SermonDescrGold, Visit, Profile, Keyword, SermonSignature, Status, Library, LINK_EQUAL, LINK_PRT

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

# Some constants that can be used
paginateSize = 20
paginateSelect = 15
paginateValues = (100, 50, 20, 10, 5, 2, 1, )

# Global debugging 
bDebug = False

cnrs_url = "http://medium-avance.irht.cnrs.fr"

def treat_bom(sHtml):
    """REmove the BOM marker except at the beginning of the string"""

    # Check if it is in the beginning
    bStartsWithBom = sHtml.startswith(u'\ufeff')
    # Remove everywhere
    sHtml = sHtml.replace(u'\ufeff', '')
    # Return what we have
    return sHtml

def csv_to_excel(sCsvData, response):
    """Convert CSV data to an Excel worksheet"""

    # Start workbook
    wb = openpyxl.Workbook()
    ws = wb.get_active_sheet()
    ws.title="Data"

    # Start accessing the string data 
    f = StringIO(sCsvData)
    reader = csv.reader(f, delimiter=",")

    # Read the header cells and make a header row in the worksheet
    headers = next(reader)
    for col_num in range(len(headers)):
        c = ws.cell(row=1, column=col_num+1)
        c.value = headers[col_num]
        c.font = openpyxl.styles.Font(bold=True)
        # Set width to a fixed size
        ws.column_dimensions[get_column_letter(col_num+1)].width = 5.0        

    row_num = 1
    lCsv = []
    for row in reader:
        # Keep track of the EXCEL row we are in
        row_num += 1
        # Walk the elements in the data row
        # oRow = {}
        for idx, cell in enumerate(row):
            c = ws.cell(row=row_num, column=idx+1)
            c.value = row[idx]
            c.alignment = openpyxl.styles.Alignment(wrap_text=False)
    # Save the result in the response
    wb.save(response)
    return response

def user_is_authenticated(request):
    # Is this user authenticated?
    username = request.user.username
    user = User.objects.filter(username=username).first()
    return user.is_authenticated()

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

def add_visit(request, name, is_menu):
    """Add the visit to the current path"""

    username = "anonymous" if request.user == None else request.user.username
    if username != "anonymous":
        Visit.add(username, name, request.path, is_menu)

def process_visit(request, name, is_menu, **kwargs):
    """Process one visit and return updated breadcrumbs"""

    username = "anonymous" if request.user == None else request.user.username
    if username != "anonymous" and request.user.username != "":
        # Add the visit
        Visit.add(username, name, request.get_full_path(), is_menu, **kwargs)
        # Get the updated path list
        p_list = Profile.get_stack(username)
    else:
        p_list = []
        p_list.append({'name': 'Home', 'url': reverse('home')})
    # Return the breadcrumbs
    # return json.dumps(p_list)
    return p_list

def get_previous_page(request):
    """Find the previous page for this user"""

    username = "anonymous" if request.user == None else request.user.username
    if username != "anonymous" and request.user.username != "":
        # Get the current path list
        p_list = Profile.get_stack(username)
        if len(p_list) < 2:
            prevpage = request.META.get('HTTP_REFERER') 
        else:
            p_item = p_list[len(p_list)-2]
            prevpage = p_item['url']
            # Possibly add arguments
            if 'kwargs' in p_item:
                # First strip off any arguments (anything after ?) in the url
                if "?" in prevpage:
                    prevpage = prevpage.split("?")[0]
                bFirst = True
                for k,v in p_item['kwargs'].items():
                    if bFirst:
                        addsign = "?"
                        bFirst = False
                    else:
                        addsign = "&"
                    prevpage = "{}{}{}={}".format(prevpage, addsign, k, v)
    else:
        prevpage = request.META.get('HTTP_REFERER') 
    # Return the path
    return prevpage

def home(request):
    """Renders the home page."""

    assert isinstance(request, HttpRequest)
    # Specify the template
    template_name = 'index.html'
    # Define the initial context
    context =  {'title':'RU-passim',
                'year':get_current_datetime().year,
                'pfx': APP_PREFIX,
                'site_url': admin.site.site_url}
    context['is_passim_uploader'] = user_is_ingroup(request, 'passim_uploader')
    context['is_passim_editor'] = user_is_ingroup(request, 'passim_editor')

    # Process this visit
    context['breadcrumbs'] = process_visit(request, "Home", True)

    # Create the list of news-items
    lstQ = []
    lstQ.append(Q(status='val'))
    newsitem_list = NewsItem.objects.filter(*lstQ).order_by('-saved', '-created')
    context['newsitem_list'] = newsitem_list

    # Gather the statistics
    context['count_sermon'] = SermonDescr.objects.all().count()
    context['count_manu'] = Manuscript.objects.all().count()

    # Render and return the page
    return render(request, template_name, context)

def contact(request):
    """Renders the contact page."""
    assert isinstance(request, HttpRequest)
    context =  {'title':'Contact',
                'message':'Shari Boodts',
                'year':get_current_datetime().year,
                'pfx': APP_PREFIX,
                'site_url': admin.site.site_url}
    context['is_passim_uploader'] = user_is_ingroup(request, 'passim_uploader')

    # Process this visit
    context['breadcrumbs'] = process_visit(request, "Contact", True)

    return render(request,'contact.html', context)

def more(request):
    """Renders the more page."""
    assert isinstance(request, HttpRequest)
    context =  {'title':'More',
                'year':get_current_datetime().year,
                'pfx': APP_PREFIX,
                'site_url': admin.site.site_url}
    context['is_passim_uploader'] = user_is_ingroup(request, 'passim_uploader')

    # Process this visit
    context['breadcrumbs'] = process_visit(request, "More", True)

    return render(request,'more.html', context)

def bibliography(request):
    """Renders the more page."""
    assert isinstance(request, HttpRequest)
    context =  {'title':'Bibliography',
                'year':get_current_datetime().year,
                'pfx': APP_PREFIX,
                'site_url': admin.site.site_url}
    context['is_passim_uploader'] = user_is_ingroup(request, 'passim_uploader')

    # Process this visit
    context['breadcrumbs'] =  process_visit(request, "Bibliography", True)

    return render(request,'bibliography.html', context)

def about(request):
    """Renders the about page."""
    assert isinstance(request, HttpRequest)
    context =  {'title':'About',
                'message':'Radboud University passim utility.',
                'year':get_current_datetime().year,
                'pfx': APP_PREFIX,
                'site_url': admin.site.site_url}
    context['is_passim_uploader'] = user_is_ingroup(request, 'passim_uploader')

    # Process this visit
    context['breadcrumbs'] = process_visit(request, "About", True)

    return render(request,'about.html', context)

def short(request):
    """Renders the page with the short instructions."""

    assert isinstance(request, HttpRequest)
    template = 'short.html'
    context = {'title': 'Short overview',
               'message': 'Radboud University passim short intro',
               'year': get_current_datetime().year}
    context['is_passim_uploader'] = user_is_ingroup(request, 'passim_uploader')
    return render(request, template, context)

def nlogin(request):
    """Renders the not-logged-in page."""
    assert isinstance(request, HttpRequest)
    context =  {    'title':'Not logged in', 
                    'message':'Radboud University passim utility.',
                    'year':get_current_datetime().year,}
    context['is_passim_uploader'] = user_is_ingroup(request, 'passim_uploader')
    return render(request,'nlogin.html', context)

def sync_entry(request):
    """-"""
    assert isinstance(request, HttpRequest)

    # Gather info
    context = {'title': 'SyncEntry',
               'message': 'Radboud University PASSIM'
               }
    template_name = 'seeker/syncentry.html'

    # Add the information in the 'context' of the web page
    return render(request, template_name, context)

def sync_start(request):
    """Synchronize information"""

    oErr = ErrHandle()
    data = {'status': 'starting'}
    try:
        # Get the user
        username = request.user.username
        # Get the synchronization type
        get = request.GET
        synctype = ""
        if 'synctype' in get:
            synctype = get['synctype']

        if synctype == '':
            # Formulate a response
            data['status'] = 'no sync type specified'

        else:
            # Remove previous status objects for this combination of user/type
            lstQ = []
            lstQ.append(Q(user=username))
            lstQ.append(Q(type=synctype))
            qs = Status.objects.filter(*lstQ)
            qs.delete()

            # Create a status object for this combination of synctype/user
            oStatus = Status(user=username, type=synctype, status="preparing")
            oStatus.save()

            # Formulate a response
            data['status'] = 'done'

            if synctype == "entries":
                # Use the synchronisation object that contains all relevant information
                oStatus.set("loading")

                # Update the models with the new information
                oResult = process_lib_entries(oStatus)
                if oResult == None or oResult['result'] == False:
                    data.status = 'error'
                elif oResult != None:
                    data['count'] = oResult

    except:
        oErr.DoError("sync_start error")
        data['status'] = "error"

    # Return this response
    return JsonResponse(data)

def sync_progress(request):
    """Get the progress on the /crpp synchronisation process"""

    oErr = ErrHandle()
    data = {'status': 'preparing'}

    try:
        # Get the user
        username = request.user.username
        # Get the synchronization type
        get = request.GET
        synctype = ""
        if 'synctype' in get:
            synctype = get['synctype']

        if synctype == '':
            # Formulate a response
            data['status'] = 'error'
            data['msg'] = "no sync type specified" 

        else:
            # Formulate a response
            data['status'] = 'UNKNOWN'

            # Get the appropriate status object
            # sleep(1)
            oStatus = Status.objects.filter(user=username, type=synctype).first()

            # Check what we received
            if oStatus == None:
                # There is no status object for this type
                data['status'] = 'error'
                data['msg'] = "Cannot find status for {}/{}".format(
                    username, synctype)
            else:
                # Get the last status information
                data['status'] = oStatus.status
                data['msg'] = oStatus.msg
                data['count'] = oStatus.count

        # Return this response
        return JsonResponse(data)
    except:
        oErr.DoError("sync_start error")
        data = {'status': 'error'}

    # Return this response
    return JsonResponse(data)

def search_sermon(request):
    """Search for a sermon"""

    # Set defaults
    template_name = "seeker/sermon.html"

    # Get a link to a form
    searchForm = SearchSermonForm()

    # Other initialisations
    currentuser = request.user
    authenticated = currentuser.is_authenticated()

    # Create context and add to it
    context = dict(title="Search sermon",
                   authenticated=authenticated,
                   searchForm=searchForm)
    context['is_passim_uploader'] = user_is_ingroup(request, 'passim_uploader')

    # Create and show the result
    return render(request, template_name, context)

def search_collection(request):
    """Search for a collection"""

    # Set defaults
    template_name = "seeker/collection.html"

    # Get a link to a form
    searchForm = SearchCollectionForm()

    # Other initialisations
    currentuser = request.user
    authenticated = currentuser.is_authenticated()

    # Create context and add to it
    context = dict(title="Search collection",
                   authenticated=authenticated,
                   searchForm=searchForm)
    context['is_passim_uploader'] = user_is_ingroup(request, 'passim_uploader')

    # Create and show the result
    return render(request, template_name, context)

def signup(request):
    """Provide basic sign up and validation of it """

    if request.method == 'POST':
        form = SignUpForm(request.POST)
        if form.is_valid():
            # Save the form
            form.save()
            # Create the user
            username = form.cleaned_data.get('username')
            raw_password = form.cleaned_data.get('password1')
            # also make sure that the user gets into the STAFF,
            #      otherwise he/she may not see the admin pages
            user = authenticate(username=username, 
                                password=raw_password,
                                is_staff=True)
            user.is_staff = True
            user.save()
            # Add user to the "passim_user" group
            gQs = Group.objects.filter(name="passim_user")
            if gQs.count() > 0:
                g = gQs[0]
                g.user_set.add(user)
            # Log in as the user
            login(request, user)
            return redirect('home')
    else:
        form = SignUpForm()
    return render(request, 'signup.html', {'form': form})

def do_clavis(request):
    # Create a regular expression
    r_number = re.compile( r'^[[]?(\d+)[]]?')

    # Walk the whole signature list
    with transaction.atomic():
        for obj in Signature.objects.all():
            # Check the type
            if obj.editype == "cl":
                # This is clavis -- get the code
                code = obj.code
                if r_number.match(code):
                    # This is only a number
                    obj.code = "CPPM {}".format(code)
                    obj.save()
    # Return an appropriate page
    return home(request)

def do_stype(request):
    """Add stype on the appropriate places"""

    oErr = ErrHandle()
    try:
        assert isinstance(request, HttpRequest)
        # Specify the template
        template_name = 'tools.html'
        # Define the initial context
        context =  {'title':'RU-passim-tools',
                    'year':get_current_datetime().year,
                    'pfx': APP_PREFIX,
                    'site_url': admin.site.site_url}
        context['is_passim_uploader'] = user_is_ingroup(request, 'passim_uploader')
        context['is_passim_editor'] = user_is_ingroup(request, 'passim_editor')

        # Only passim uploaders can do this
        if not context['is_passim_uploader']: return reverse('home')

        # Indicate the necessary tools sub-part
        context['tools_part'] = "Repair Stype definitions"

        # Process this visit
        context['breadcrumbs'] = process_visit(request, "Stype", True)

        # Create list to be returned
        result_list = []

        # Phase 1: Manuscript
        with transaction.atomic():
            added = 0
            for item in Manuscript.objects.all():
                if item.stype == "-":
                    item.stype = "imp"
                    item.save()
                    added += 1
            result_list.append({'part': 'Manuscript changed stype', 'result': added})

        # Phase 2: SermonDescr
        with transaction.atomic():
            added = 0
            for item in SermonDescr.objects.all():
                if item.stype == "-":
                    item.stype = "imp"
                    item.save()
                    added += 1
            result_list.append({'part': 'SermonDescr changed stype', 'result': added})

        # Phase 3: SermonGold
        with transaction.atomic():
            added = 0
            for item in SermonGold.objects.all():
                if item.stype == "-":
                    item.stype = "imp"
                    item.save()
                    added += 1
            result_list.append({'part': 'SermonGold changed stype', 'result': added})

        context['result_list'] = result_list
    
        # Render and return the page
        return render(request, template_name, context)
    except:
        msg = oErr.get_error_message()
        oErr.DoError("goldtogold")
        return reverse('home')

def do_locations(request):
    """Add stype on the appropriate places"""

    oErr = ErrHandle()
    try:
        assert isinstance(request, HttpRequest)
        # Specify the template
        template_name = 'tools.html'
        # Define the initial context
        context =  {'title':'RU-passim-tools',
                    'year':get_current_datetime().year,
                    'pfx': APP_PREFIX,
                    'site_url': admin.site.site_url}
        context['is_passim_uploader'] = user_is_ingroup(request, 'passim_uploader')
        context['is_passim_editor'] = user_is_ingroup(request, 'passim_editor')

        # Only passim uploaders can do this
        if not context['is_passim_uploader']: return reverse('home')

        # Indicate the necessary tools sub-part
        context['tools_part'] = "Establish location definitions"

        # Process this visit
        context['breadcrumbs'] = process_visit(request, "Locations", True)

        # Create list to be returned
        result_list = []

        # Phase 1: Country
        name = "country"
        loctype_country = LocationType.objects.filter(name=name).first()
        idname = "idPaysEtab"
        added = 0
        if Location.objects.filter(loctype=loctype_country).count() == 0:
            with transaction.atomic():
                # locationtype = city
                for item in Country.objects.all():
                    # Get the details of this item
                    name = item.name
                    nameFR = item.nameFR
                    idvalue = item.idPaysEtab
                    # Create a location with these parameters
                    obj = Location(name=name, loctype=loctype_country)
                    obj.save()
                    added += 1
                    # Add the French name and identifier
                    if nameFR != None and nameFR != "":
                        lname = LocationName(name=nameFR, language="fre", location=obj)
                        lname.save()
                    if idvalue != None:
                        lidt = LocationIdentifier(idname=idname, idvalue=idvalue, location=obj)
                        lidt.save()

        # Phase 2: City
        name = "city"
        loctype_city = LocationType.objects.filter(name=name).first()
        idname = "idVilleEtab"
        if Location.objects.filter(loctype=loctype_city).count() == 0:
            last_country = None
            last_loc_country = None
            with transaction.atomic():
                # locationtype = city
                for item in City.objects.all().order_by('country__name'):
                    # Get the details of this item
                    name = item.name
                    idvalue = item.idVilleEtab
                    country = item.country
                    # Create a location with these parameters
                    obj = Location(name=name, loctype=loctype_city)
                    obj.save()
                    added += 1
                    # Add the French identifier
                    if idvalue != None and idvalue >= 0:
                        lidt = LocationIdentifier(idname=idname, idvalue=idvalue, location=obj)
                        lidt.save()
                    # Tie the city to the correct country object through a LocationRelation
                    if country != None:
                        if country != last_country:
                            loc = Location.objects.filter(name=country.name, loctype=loctype_country).first()
                            if loc != None:
                                last_loc_country = loc
                                last_country = country
                        # Implement relation
                        loc_rel = LocationRelation(container=last_loc_country, contained=obj)
                        loc_rel.save()

        # Phase 3: Library
        name = "library"
        loctype_lib = LocationType.objects.filter(name=name).first()
        qs = Library.objects.all().order_by('country__name', 'city__name')
        with transaction.atomic():
            for library in qs:
                if library.location == None:
                    city = library.city
                    country = library.country
                    if country != None:
                        countries = Location.objects.filter(name__iexact=country.name)
                    if city != None:
                    
                        # Find the city
                        lstQ = []
                        lstQ.append(Q(name__iexact=city.name))
                        if country != None:
                            lstQ.append(Q(relations_location__in=countries))
                        obj = Location.objects.filter(*lstQ).first()
                        # qs = Location.objects.filter(name__iexact=city.name).filter(relations_location__in=countries)
                        if obj == None:
                            # Cannot find the location of this library...
                            iStop = 1
                        else:
                            # Set the location in Library
                            library.location = obj
                            library.save()
                            added += 1

        # Wrapping it up
        context['result_list'] = result_list

        # Render and return the page
        return render(request, template_name, context)
    except:
        msg = oErr.get_error_message()
        oErr.DoError("do_locations")
        return reverse('home')

def do_goldtogold(request):
    """Perform gold-to-gold relation repair -- NEW method that uses EqualGold"""

    oErr = ErrHandle()
    try:
        assert isinstance(request, HttpRequest)
        # Specify the template
        template_name = 'tools.html'
        # Define the initial context
        context =  {'title':'RU-passim-tools',
                    'year':get_current_datetime().year,
                    'pfx': APP_PREFIX,
                    'site_url': admin.site.site_url}
        context['is_passim_uploader'] = user_is_ingroup(request, 'passim_uploader')
        context['is_passim_editor'] = user_is_ingroup(request, 'passim_editor')

        # Only passim uploaders can do this
        if not context['is_passim_uploader']: return reverse('home')

        # Indicate the necessary tools sub-part
        context['tools_part'] = "Repair gold-to-gold links"

        # Process this visit
        context['breadcrumbs'] = process_visit(request, "GoldToGold", True)

        added = 0
        lst_total = []
        lst_total.append("<table><thead><tr><th>item</th><th>src</th><th>dst</th><th>linktype</th><th>addtype</th><th>Path</th></tr>")
        lst_total.append("<tbody>")

        method = "goldspread" 

        # Step #1: remove all unnecessary links
        oErr.Status("{} step #1".format(method))
        qs = SermonGoldSame.objects.all()
        lst_delete = []
        for relation in qs:
            if relation.src == relation.dst:
                lst_delete.append(relation.id)
        oErr.Status("Step 1: removing {} links".format(len(lst_delete)))
        if len(lst_delete) > 0:
            SermonGoldSame.objects.filter(Q(id__in=lst_delete)).delete()

        # Step #2: create groups of equals
        oErr.Status("{} step #2".format(method))
        lst_group = []      # List of groups, where each group is a list of equal-related gold-sermons
        qs_eqs = SermonGoldSame.objects.filter(linktype=LINK_EQUAL ).order_by('src')
        for idx, relation in enumerate(qs_eqs):
            src = relation.src
            dst = relation.dst
            # Find out in which group this one fits
            bGroup = False
            for group in lst_group:
                # Find a connection within this group
                for obj in group:
                    id = obj.id
                    if id == src.id or id == dst.id:
                        # We found the group
                        bGroup = True
                        break
                if bGroup:
                    # Add them if needed
                    if relation.src not in group: group.append(relation.src)
                    if relation.dst not in group: group.append(relation.dst)
                    # And then break from the larger one
                    break
            # Did we fit this into a group?
            if not bGroup:
                # Create a new group with two members
                group = [relation.src, relation.dst]
                lst_group.append(group)

        # Make sure the members of the groups get into the same EqualGold, if that is not the case yet
        # Step #2b: add equal groups
        for group in lst_group:
            if len(group) > 0:
                # Check the first item from the group
                first = group[0]
                if first.equal == None:
                    # Create a new equality group and add them all to it
                    eqg = EqualGold()
                    eqg.save()
                    with transaction.atomic():
                        for item in group:
                            item.equal = eqg
                            item.save()

        # Step #3: add individual equals
        oErr.Status("{} step #3".format(method))
        # Visit all SermonGold instances and create eqg's for those that don't have one yet
        for gold in SermonGold.objects.all():
            if gold.equal == None:
                eqg = EqualGold()
                eqg.save()
                gold.equal = eqg
                gold.save()

        # -- or can a SermonGold be left without an equality group, if he is not equal to anything (yet)?

        # Step #4 (new): copy 'partial' and other near links to linke between groups
        oErr.Status("{} step #4a".format(method))
        for linktype in LINK_PRT:
            lst_prt_add = []    # List of partially equals relations to be added
            # Get all links of the indicated type
            qs_prt = SermonGoldSame.objects.filter(linktype=linktype).order_by('src__id')
            # Walk these links
            for obj_prt in qs_prt:
                # Get the equal groups of the link
                src_eqg = obj_prt.src.equal
                dst_eqg = obj_prt.dst.equal
                # Translate the link to one between equal-groups
                oLink = {'src': src_eqg, 'dst': dst_eqg}
                if oLink not in lst_prt_add: lst_prt_add.append(oLink)
                # And the reverse link
                oLink = {'src': dst_eqg, 'dst': src_eqg}
                if oLink not in lst_prt_add: lst_prt_add.append(oLink)
            # Add all the relations in lst_prt_add
            with transaction.atomic():
                for idx, item in enumerate(lst_prt_add):
                    # Make sure it doesn't yet exist
                    obj = EqualGoldLink.objects.filter(linktype=linktype, src=item['src'], dst=item['dst']).first()
                    if obj == None:
                        obj = EqualGoldLink(linktype=linktype, src=item['src'], dst=item['dst'])
                        obj.save()
        
        lst_total.append("</tbody></table>")

        # Create list to be returned
        result_list = []
        result_list.append({'part': 'Number of added relations', 'result': added})
        # result_list.append({'part': 'All additions', 'result': json.dumps(lst_total)})
        result_list.append({'part': 'All additions', 'result': "\n".join(lst_total)})

        context['result_list'] = result_list
    
        # Render and return the page
        return render(request, template_name, context)
    except:
        msg = oErr.get_error_message()
        oErr.DoError("goldtogold")
        return reverse('home')

def do_goldtogold_ORIGINAL(request):
    """Perform gold-to-gold relation repair"""

    oErr = ErrHandle()
    try:
        assert isinstance(request, HttpRequest)
        # Specify the template
        template_name = 'tools.html'
        # Define the initial context
        context =  {'title':'RU-passim-tools',
                    'year':get_current_datetime().year,
                    'pfx': APP_PREFIX,
                    'site_url': admin.site.site_url}
        context['is_passim_uploader'] = user_is_ingroup(request, 'passim_uploader')
        context['is_passim_editor'] = user_is_ingroup(request, 'passim_editor')

        # Only passim uploaders can do this
        if not context['is_passim_uploader']: return reverse('home')

        # Indicate the necessary tools sub-part
        context['tools_part'] = "Repair gold-to-gold links"

        # Process this visit
        context['breadcrumbs'] = process_visit(request, "GoldToGold", True)

        added = 0
        lst_total = []
        lst_total.append("<table><thead><tr><th>item</th><th>src</th><th>dst</th><th>linktype</th><th>addtype</th><th>Path</th></tr>")
        lst_total.append("<tbody>")

        method = "goldspread" 

        # Step #1: remove all unnecessary links
        oErr.Status("{} step #1".format(method))
        qs = SermonGoldSame.objects.all()
        lst_delete = []
        for relation in qs:
            if relation.src == relation.dst:
                lst_delete.append(relation.id)
        oErr.Status("Step 1: removing {} links".format(len(lst_delete)))
        if len(lst_delete) > 0:
            SermonGoldSame.objects.filter(Q(id__in=lst_delete)).delete()

        # Step #2: create groups of equals
        oErr.Status("{} step #2".format(method))
        lst_group = []      # List of groups, where each group is a list of equal-related gold-sermons
        qs_eqs = SermonGoldSame.objects.filter(linktype=LINK_EQUAL ).order_by('src')
        for idx, relation in enumerate(qs_eqs):
            src = relation.src
            dst = relation.dst
            # Find out in which group this one fits
            bGroup = False
            for group in lst_group:
                # Find a connection within this group
                for obj in group:
                    id = obj.id
                    if id == src.id or id == dst.id:
                        # We found the group
                        bGroup = True
                        break
                if bGroup:
                    # Add them if needed
                    if relation.src not in group: group.append(relation.src)
                    if relation.dst not in group: group.append(relation.dst)
                    # And then break from the larger one
                    break
            # Did we fit this into a group?
            if not bGroup:
                # Create a new group with two members
                group = [relation.src, relation.dst]
                lst_group.append(group)
        # Create a list of objects that have been done
        lst_done = []
        for group in lst_group:
            for obj in group:
                lst_done.append(obj.id)
        # Add individuals to the list of groups if they have not yet been 'done'
        for obj in SermonGold.objects.exclude(id__in=lst_done):
            lst_group.append([obj])
                    
        # Step #3: spread 'equals' within each group
        oErr.Status("{} step #3".format(method))
        lst_add = []    # List of equals relations to be added
        for group in lst_group:
            # Consider each id in group
            for src in group:
                # Check for all possible destination id's
                for dst in group:
                    # Make sure they're not equal
                    if src.id != dst.id:
                        # Check if this relation exists
                        obj = qs.filter(src=src, dst=dst).first()
                        if obj == None:
                            lst_add.append({'src': src, 'dst': dst})
        with transaction.atomic():
            for idx, item in enumerate(lst_add):
                obj = SermonGoldSame(linktype=LINK_EQUAL, src=item['src'], dst=item['dst'])
                obj.save()
                lst_total.append("<tr><td>{}</td><td>{}</td><td>{}</td><td>{}</td><td>{}</td><td>{}</td></tr>".format( 
                    (idx+1), item['src'].siglist, item['dst'].siglist, LINK_EQUAL, "add", "" ))

        # Step #4: spread 'partial' links within groups of equals
        oErr.Status("{} step #4".format(method))
        for linktype in LINK_PRT:
            lst_prt_add = []    # List of partially equals relations to be added
            qs_prt = SermonGoldSame.objects.filter(linktype=linktype).order_by('src__id')
            for group in lst_group:
                # DEBUGGING - check the length of this group
                if len(group) == 1:
                    iStop = True

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
                    lst_total.append("<tr><td>{}</td><td>{}</td><td>{}</td><td>{}</td><td>{}</td><td>{}</td></tr>".format( 
                        (idx+1), item['src'].siglist, item['dst'].siglist, linktype, "add", "" ))


        lst_total.append("</tbody></table>")

        # Create list to be returned
        result_list = []
        result_list.append({'part': 'Number of added relations', 'result': added})
        # result_list.append({'part': 'All additions', 'result': json.dumps(lst_total)})
        result_list.append({'part': 'All additions', 'result': "\n".join(lst_total)})

        context['result_list'] = result_list
    
        # Render and return the page
        return render(request, template_name, context)
    except:
        msg = oErr.get_error_message()
        oErr.DoError("goldtogold")
        return reverse('home')

@csrf_exempt
def get_countries(request):
    """Get a list of countries for autocomplete"""

    data = 'fail'
    method = "useLocation"
    if request.is_ajax():
        sName = request.GET.get('country', '')
        if sName == "": sName = request.GET.get('country_ta', "")
        lstQ = []
        lstQ.append(Q(name__icontains=sName))
        if method == "useLocation":
            loctype = LocationType.find("country")
            lstQ.append(Q(loctype=loctype))
            countries = Location.objects.filter(*lstQ).order_by('name')
        else:
            countries = Country.objects.filter(*lstQ).order_by('name')
        results = []
        for co in countries:
            co_json = {'name': co.name, 'id': co.id }
            results.append(co_json)
        data = json.dumps(results)
    else:
        data = "Request is not ajax"
    mimetype = "application/json"
    return HttpResponse(data, mimetype)

@csrf_exempt
def get_cities(request):
    """Get a list of cities for autocomplete"""

    data = 'fail'
    method = "useLocation"
    if request.is_ajax():
        # Get the user-specified 'country' and 'city' strings
        country = request.GET.get('country', "")
        if country == "": country = request.GET.get('country_ta', "")
        city = request.GET.get("city", "")
        if city == "": city = request.GET.get('city_ta', "")

        # build the query
        lstQ = []
        if method == "useLocation":
            # Start as broad as possible: country
            qs_loc = None
            if country != "":
                loctype_country = LocationType.find("country")
                lstQ.append(Q(name=country))
                lstQ.append(Q(loctype=loctype_country))
                qs_country = Location.objects.filter(*lstQ)
                # Fine-tune on city...
                loctype_city = LocationType.find("city")
                lstQ = []
                lstQ.append(Q(name__icontains=city))
                lstQ.append(Q(loctype=loctype_city))
                lstQ.append(Q(relations_location__in=qs_country))
                cities = Location.objects.filter(*lstQ)
            else:
                loctype_city = LocationType.find("city")
                lstQ.append(Q(name__icontains=city))
                lstQ.append(Q(loctype=loctype_city))
                cities = Location.objects.filter(*lstQ)
        elif method == "slowLocation":
            # First of all: city...
            loctype_city = LocationType.find("city")
            lstQ.append(Q(name__icontains=city))
            lstQ.append(Q(loctype=loctype_city))
            # Do we have a *country* specification?
            if country != "":
                loctype_country = LocationType.find("country")
                lstQ.append(Q(relations_location__name=country))
                lstQ.append(Q(relations_location__loctype=loctype_country))
            # Combine everything
            cities = Location.objects.filter(*lstQ).order_by('name')
        else:
            if country != "":
                lstQ.append(Q(country__name__icontains=country))
            lstQ.append(Q(name__icontains=city))
            cities = City.objects.filter(*lstQ).order_by('name')
        results = []
        for co in cities:
            co_json = {'name': co.name, 'id': co.id }
            results.append(co_json)
        data = json.dumps(results)
    else:
        data = "Request is not ajax"
    mimetype = "application/json"
    return HttpResponse(data, mimetype)
    
@csrf_exempt
def get_libraries(request):
    """Get a list of libraries for autocomplete"""

    data = 'fail'
    method = "useLocation"
    if request.is_ajax():
        # Get the user-specified 'country' and 'city' strings
        country = request.GET.get('country', "")
        if country == "": country = request.GET.get('country_ta', "")
        city = request.GET.get("city", "")
        if city == "": city = request.GET.get('city_ta', "")
        lib = request.GET.get("library", "")
        if lib == "": lib = request.GET.get('libname_ta', "")

        # build the query
        lstQ = []
        if method == "useLocation":
            # Start as broad as possible: country
            qs_loc = None
            if country != "":
                loctype_country = LocationType.find("country")
                lstQ.append(Q(name=country))
                lstQ.append(Q(loctype=loctype_country))
                qs_country = Location.objects.filter(*lstQ)
                # What about city?
                if city == "":
                    qs_loc = qs_country
                else:
                    loctype_city = LocationType.find("city")
                    lstQ = []
                    lstQ.append(Q(name__icontains=city))
                    lstQ.append(Q(loctype=loctype_city))
                    lstQ.append(Q(relations_location__in=qs_country))
                    qs_loc = Location.objects.filter(*lstQ)
            elif city != "":
                loctype_city = LocationType.find("city")
                lstQ.append(Q(name__icontains=city))
                lstQ.append(Q(loctype=loctype_city))
                qs_loc = Location.objects.filter(*lstQ)

            # Start out with the idea to look for a library by name:
            lstQ = []
            if lib != "": lstQ.append(Q(name__icontains=lib))
            if qs_loc != None: lstQ.append(Q(location__in=qs_loc))

            # Combine everything
            libraries = Library.objects.filter(*lstQ).order_by('name')
        else:
            if country != "": lstQ.append(Q(country__name__icontains=country))
            if city != "": lstQ.append(Q(city__name__icontains=city))
            if lib != "": lstQ.append(Q(name__icontains=lib))
            libraries = Library.objects.filter(*lstQ).order_by('name')
        results = []
        for co in libraries:
            co_json = {'name': co.name, 'id': co.id }
            results.append(co_json)
        data = json.dumps(results)
    else:
        data = "Request is not ajax"
    mimetype = "application/json"
    return HttpResponse(data, mimetype)

@csrf_exempt
def get_origins(request):
    """Get a list of origin names for autocomplete"""

    data = 'fail'
    if request.is_ajax():
        sName = request.GET.get('name', '')
        lstQ = []
        lstQ.append(Q(name__icontains=sName))
        origins = Origin.objects.filter(*lstQ).order_by('name')
        results = []
        for co in origins:
            co_json = {'name': co.name, 'id': co.id }
            results.append(co_json)
        data = json.dumps(results)
    else:
        data = "Request is not ajax"
    mimetype = "application/json"
    return HttpResponse(data, mimetype)

def get_manuscripts(request):
    """Get a list of manuscripts"""

    data = 'fail'
    errHandle = ErrHandle()
    # Only allow AJAX calls with POST
    if request.is_ajax() and request.method == "POST":
        get = request.POST
        # Get parameters city and library
        city = get.get("city", "")
        lib = get.get("library", "")

        url = "{}/Manuscrits/manuscritforetablissement".format(cnrs_url)
        data = "idEtab={}&idVille={}".format(lib, city)
        data = {"idEtab": lib, "idVille": city}
        #data = []
        #data.append({'name': 'idEtab', 'value': lib})
        #data.append({'name': 'idVille', 'value': city})
        try:
            r = requests.post(url, data=data)
        except:
            sMsg = errHandle.get_error_message()
            errHandle.DoError("Request problem")
            return False
        if r.status_code == 200:
            # Return positively
            reply = demjson.decode(r.text.replace("\t", " "))
            if reply != None and "items" in reply:
                results = []
                for item in reply['items']:
                    if item['name'] != "":
                        results.append(item['name'])
                data = json.dumps(results)
    else:
        data = "Request is not ajax"
    # Prepare and return data
    mimetype = "application/json"
    return HttpResponse(data, mimetype)

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

@csrf_exempt
def get_manuidnos(request):
    """Get a list of manuscript identifiers for autocomplete"""

    oErr = ErrHandle()
    try:
        data = 'fail'
        if request.is_ajax():
            idno = request.GET.get("name", "")
            lstQ = []
            lstQ.append(Q(idno__icontains=idno))
            items = Manuscript.objects.filter(*lstQ).order_by("idno").distinct()
            results = []
            for co in items:
                co_json = {'name': co.idno, 'id': co.id }
                results.append(co_json)
            data = json.dumps(results)
        else:
            data = "Request is not ajax"
    except:
        msg = oErr.get_error_message()
        data = "error: {}".format(msg)
    mimetype = "application/json"
    return HttpResponse(data, mimetype)

@csrf_exempt
def get_authors(request):
    """Get a list of authors for autocomplete"""

    data = 'fail'
    if request.is_ajax():
        author = request.GET.get("name", "")
        lstQ = []
        lstQ.append(Q(name__icontains=author)|Q(abbr__icontains=author))
        authors = Author.objects.filter(*lstQ).order_by('name')
        results = []
        for co in authors:
            co_json = {'name': co.name, 'id': co.id }
            results.append(co_json)
        data = json.dumps(results)
    else:
        data = "Request is not ajax"
    mimetype = "application/json"
    return HttpResponse(data, mimetype)

@csrf_exempt
def get_nicknames(request):
    """Get a list of nicknames for autocomplete"""

    oErr = ErrHandle()
    try:
        data = 'fail'
        if request.is_ajax():
            author = request.GET.get("name", "")
            lstQ = []
            lstQ.append(Q(name__icontains=author))
            authors = Nickname.objects.filter(*lstQ).order_by('name')
            results = []
            for co in authors:
                co_json = {'name': co.name, 'id': co.id }
                results.append(co_json)
            data = json.dumps(results)
        else:
            data = "Request is not ajax"
    except:
        msg = oErr.get_error_message()
        data = "error: {}".format(msg)
    mimetype = "application/json"
    return HttpResponse(data, mimetype)

@csrf_exempt
def get_gldincipits(request):
    """Get a list of Gold-sermon incipits for autocomplete"""

    oErr = ErrHandle()
    try:
        data = 'fail'
        if request.is_ajax():
            author = request.GET.get("name", "")
            lstQ = []
            lstQ.append(Q(srchincipit__icontains=author))
            items = SermonGold.objects.filter(*lstQ).values("srchincipit").distinct().all().order_by('srchincipit')
            # items = SermonGold.objects.order_by("incipit").distinct()
            # items = SermonGold.objects.filter(*lstQ).order_by('incipit').distinct()
            results = []
            for idx, co in enumerate(items):
                val = co['srchincipit']
                co_json = {'name': val, 'id': idx }
                results.append(co_json)
            data = json.dumps(results)
        else:
            data = "Request is not ajax"
    except:
        msg = oErr.get_error_message()
        data = "error: {}".format(msg)
    mimetype = "application/json"
    return HttpResponse(data, mimetype)

@csrf_exempt
def get_srmincipits(request):
    """Get a list of manifestation-sermon incipits for autocomplete"""

    oErr = ErrHandle()
    try:
        data = 'fail'
        if request.is_ajax():
            author = request.GET.get("name", "")
            lstQ = []
            lstQ.append(Q(srchincipit__icontains=author))
            items = SermonDescr.objects.filter(*lstQ).values("srchincipit").distinct().all().order_by('srchincipit')
            results = []
            for idx, co in enumerate(items):
                val = co['srchincipit']
                co_json = {'name': val, 'id': idx }
                results.append(co_json)
            data = json.dumps(results)
        else:
            data = "Request is not ajax"
    except:
        msg = oErr.get_error_message()
        data = "error: {}".format(msg)
    mimetype = "application/json"
    return HttpResponse(data, mimetype)

@csrf_exempt
def get_gldexplicits(request):
    """Get a list of Gold-sermon explicits for autocomplete"""

    oErr = ErrHandle()
    try:
        data = 'fail'
        if request.is_ajax():
            author = request.GET.get("name", "")
            lstQ = []
            lstQ.append(Q(srchexplicit__icontains=author))
            items = SermonGold.objects.filter(*lstQ).values("srchexplicit").distinct().all().order_by('srchexplicit')
            results = []
            for idx, co in enumerate(items):
                val = co['srchexplicit']
                co_json = {'name': val, 'id': idx }
                results.append(co_json)
            data = json.dumps(results)
        else:
            data = "Request is not ajax"
    except:
        msg = oErr.get_error_message()
        data = "error: {}".format(msg)
    mimetype = "application/json"
    return HttpResponse(data, mimetype)

@csrf_exempt
def get_srmexplicits(request):
    """Get a list of Manifestation-sermon explicits for autocomplete"""

    oErr = ErrHandle()
    try:
        data = 'fail'
        if request.is_ajax():
            author = request.GET.get("name", "")
            lstQ = []
            lstQ.append(Q(srchexplicit__icontains=author))
            items = SermonDescr.objects.filter(*lstQ).values("srchexplicit").distinct().all().order_by('srchexplicit')
            results = []
            for idx, co in enumerate(items):
                val = co['srchexplicit']
                co_json = {'name': val, 'id': idx }
                results.append(co_json)
            data = json.dumps(results)
        else:
            data = "Request is not ajax"
    except:
        msg = oErr.get_error_message()
        data = "error: {}".format(msg)
    mimetype = "application/json"
    return HttpResponse(data, mimetype)

@csrf_exempt
def get_gldsignatures(request):
    """Get a list of signature codes (SermonDescr) for autocomplete"""

    oErr = ErrHandle()
    try:
        data = 'fail'
        if request.is_ajax():
            # Get the editype, if that is specified
            editype = request.GET.get("type", "")
            # Get the complete code line, which could use semicolon-separation
            codeline = request.GET.get("name", "")
            codelist = codeline.split(";")
            codename = "" if len(codelist) == 0 else codelist[-1].strip()
            lstQ = []
            lstQ.append(Q(code__icontains=codename))
            if editype != "":
                lstQ.append(Q(editype=editype))
            items = Signature.objects.filter(*lstQ).order_by("code").distinct()
            results = []
            for co in items:
                co_json = {'name': co.code, 'id': co.id }
                results.append(co_json)
            data = json.dumps(results)
        else:
            data = "Request is not ajax"
    except:
        msg = oErr.get_error_message()
        data = "error: {}".format(msg)
    mimetype = "application/json"
    return HttpResponse(data, mimetype)

@csrf_exempt
def get_srmsignatures(request):
    """Get a list of signature codes (for SermonDescr) for autocomplete"""

    oErr = ErrHandle()
    try:
        data = 'fail'
        if request.is_ajax():
            codename = request.GET.get("name", "")
            editype = request.GET.get("type", "")
            lstQ = []
            lstQ.append(Q(code__icontains=codename))
            if editype != "":
                lstQ.append(Q(editype=editype))
            items = SermonSignature.objects.filter(*lstQ).order_by("code").distinct()
            results = []
            for co in items:
                co_json = {'name': co.code, 'id': co.id }
                results.append(co_json)
            data = json.dumps(results)
        else:
            data = "Request is not ajax"
    except:
        msg = oErr.get_error_message()
        data = "error: {}".format(msg)
    mimetype = "application/json"
    return HttpResponse(data, mimetype)

@csrf_exempt
def get_editions(request):
    """Get a list of edition codes for autocomplete"""

    oErr = ErrHandle()
    try:
        data = 'fail'
        if request.is_ajax():
            author = request.GET.get("name", "")
            lstQ = []
            lstQ.append(Q(name__icontains=author))
            items = Edition.objects.filter(*lstQ).order_by("name").distinct()
            results = []
            for co in items:
                co_json = {'name': co.name, 'id': co.id }
                results.append(co_json)
            data = json.dumps(results)
        else:
            data = "Request is not ajax"
    except:
        msg = oErr.get_error_message()
        data = "error: {}".format(msg)
    mimetype = "application/json"
    return HttpResponse(data, mimetype)

@csrf_exempt
def get_keywords(request):
    """Get a list of keywords for autocomplete"""

    oErr = ErrHandle()
    try:
        data = 'fail'
        if request.is_ajax():
            # Get the complete code line, which could use semicolon-separation
            kwline = request.GET.get("name", "")
            kwlist = kwline.split(";")
            kw = "" if len(kwlist) == 0 else kwlist[-1].strip()
            lstQ = []
            lstQ.append(Q(name__icontains=kw))
            items = Keyword.objects.filter(*lstQ).order_by("name").distinct()
            results = []
            for co in items:
                co_json = {'name': co.name, 'id': co.id }
                results.append(co_json)
            data = json.dumps(results)
        else:
            data = "Request is not ajax"
    except:
        msg = oErr.get_error_message()
        data = "error: {}".format(msg)
    mimetype = "application/json"
    return HttpResponse(data, mimetype)


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
    template_name = 'seeker/import_manuscripts.html' # Adapt because of multiple descriptions in 1 xml?
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
                            oResult = Manuscript.read_ecodex(username, data_file, filename, arErr, source=source) # TH:aanpassen , models.py

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

    pass

def import_ecodex(request):
    """Import one or more XML files that each contain one manuscript definition from e-codices, from Switzerland"""

    # Initialisations
    # NOTE: do ***not*** add a breakpoint until *AFTER* form.is_valid
    arErr = []
    error_list = []
    transactions = []
    data = {'status': 'ok', 'html': ''}
    template_name = 'seeker/import_manuscripts.html'
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
                                oResult = Manuscript.read_ecodex(username, data_file, filename, arErr, source=source)

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
                                            oResult = Manuscript.read_ecodex(username, xml_file, name, arErr, source=source)
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

def import_gold(request):
    """Import one or more Excel files that each contain one Gold-Sermon definition in Excel"""

    # Initialisations
    # NOTE: do ***not*** add a breakpoint until *AFTER* form.is_valid
    arErr = []
    error_list = []
    transactions = []
    data = {'status': 'ok', 'html': ''}
    template_name = 'seeker/import_gold.html'
    obj = None
    data_file = ""
    bClean = False
    username = request.user.username

    if request.user.is_authenticated and request.method == 'POST' and user_is_ingroup(request, 'passim_uploader'):

        # Remove previous status object for this user
        Status.objects.filter(user=username).delete()
        # Create a status object
        oStatus = Status(user=username, type="gold", status="preparing")
        oStatus.save()


        form = UploadFilesForm(request.POST, request.FILES)
        lResults = []
        if form.is_valid():
            # NOTE: from here a breakpoint may be inserted!
            print('import_gold: valid form')

            # Initialise a list of files to be processed
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
                        if extension == "xlsx":
                            # This is an Excel XLSX file
                            oResult = SermonGold.read_gold(username, data_file, filename, arErr, oStatus)
                            # Note: the [oResult] also contains a 'report' part

                        # Determine a status code
                        statuscode = "error" if oResult == None or oResult['status'] == "error" else "completed"
                        if oResult == None:
                            arErr.append("There was an error. No golden sermons have been added")
                        elif statuscode == "error" and 'msg' in oResult:
                            arErr.append(oResult['msg'])
                        else:
                            lResults.append(oResult)

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

            if statuscode == "error" and len(arErr) == 0:
                data['html'] = "Please log in before continuing"
            else:
                # Get the HTML response
                data['html'] = render_to_string(template_name, context, request)


        else:
            data['html'] = 'invalid form: {}'.format(form.errors)
            data['status'] = "error"
    else:
        data['html'] = 'Only use POST and make sure you are logged in and authorized for uploading'
        data['status'] = "error"

    # Return the information
    return JsonResponse(data)

@csrf_exempt
def import_authors(request):
    """Import a CSV file or a JSON file that contains author names"""


    # Initialisations
    # NOTE: do ***not*** add a breakpoint until *AFTER* form.is_valid
    arErr = []
    error_list = []
    transactions = []
    data = {'status': 'ok', 'html': ''}
    template_name = 'seeker/import_authors.html'
    obj = None
    data_file = ""
    bClean = False
    username = request.user.username

    # Check if the user is authenticated and if it is POST
    if not request.user.is_authenticated  or request.method == 'POST':
        form = UploadFileForm(request.POST, request.FILES)
        if form.is_valid():
            # NOTE: from here a breakpoint may be inserted!
            print('valid form')
            # Get the contents of the imported file
            data_file = request.FILES['file_source']
            filename = data_file.name

            # Get the source file
            if data_file == None or data_file == "":
                arErr.append("No source file specified for the selected project")
            else:
                # Check the extension
                arFile = filename.split(".")
                extension = arFile[len(arFile)-1]

                # Further processing depends on the extension
                if extension == "json":
                    # This is a JSON file
                    oResult = Author.read_json(username, data_file, arErr)
                else:
                    # Read the list of authors as CSV
                    oResult = Author.read_csv(username, data_file, arErr)

                # Determine a status code
                statuscode = "error" if oResult == None or oResult['status'] == "error" else "completed"
                if oResult == None:
                    arErr.append("There was an error. No authors have been added")

            # Get a list of errors
            error_list = [str(item) for item in arErr]

            # Create the context
            context = dict(
                statuscode=statuscode,
                results=oResult,
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
        data['html'] = 'Only use POST and make sure you are logged in'
        data['status'] = "error"
 
    # Return the information
    return JsonResponse(data)

def search_ecodex(request):
    arErr = []
    error_list = []
    data = {'status': 'ok', 'html': ''}
    username = request.user.username
    errHandle = ErrHandle()

    # Check if the user is authenticated and if it is POST
    if request.user.is_authenticated and request.method == 'POST' and user_is_ingroup(request, 'passim_editor'):
        # Create a regular expression
        r_href = re.compile(r'(href=[\'"]?)([^\'" >]+)')
        # Get the parameters
        if request.POST:
            qd = request.POST
        else:
            qd = request.GET
        if 'search_url' in qd:
            # Get the parameter
            s_url = qd['search_url']
            # Make a search request and get the result into a string
            try:
                r = requests.get(s_url)
            except:
                sMsg = errHandle.get_error_message()
                errHandle.DoError("Request problem")
                return False
            if r.status_code == 200:
                # Get the text into a list
                l_text = r.text.split('\n')
                lHtml = []
                iMatches = 0
                lHtml.append("<table><thead><tr><th>#</th><th>Part</th><th>Text</th><th>Version</th><th>XML</th></tr></thead>")
                lHtml.append("<tbody>")
                # Walk the text
                for line in l_text:
                    # Check if this line contains information
                    if ">Description<" in line:
                        # Extract the information from this line
                        match = r_href.search(line)
                        if match:
                            iMatches += 1
                            # Get the HREF 
                            href = match.group(2)
                            # Split into parts
                            parts = href.split("/")
                            # Find the 'description' part
                            for idx,part in enumerate(parts):
                                if part == "description":
                                    # Take array from one further
                                    idx += 1
                                    mparts = parts[idx:]
                                    break
                            # Reconstruct:
                            xml_name = "{}-{}".format(mparts[0], mparts[1])
                            version = ""
                            if len(mparts) > 2 and mparts[2] != "":
                                xml_name = "{}_{}".format(xml_name, mparts[2])
                                version = mparts[2]
                            xml_url = "{}/{}.xml".format("https://www.e-codices.unifr.ch/xml/tei_published", xml_name)

                            # Add to the HTML table
                            lHtml.append("<tr><td>{}</td><td>{}</td><td>{}</td><td>{}</td><td>{}</td></tr>".format(iMatches,mparts[0], mparts[1],version,xml_url))
                # We had all lines, now we need to return it in a good way
                lHtml.append("</tbody></table>")
                data['html'] = "\n".join(lHtml)
                data['status'] = "ok"
            else:
                data['html'] = "Website returns status code {}".format(r.status_code)
                data['status'] = "error"
        else:
            data['html'] = "Did not receive parameter search_url"
            data['status'] = "error"
    else:
        data['html'] = 'Only use POST and make sure you are logged in and authorized for uploading'
        data['status'] = "error"
 
    # Return the information
    return JsonResponse(data)

class BasicPart(View):
    """This is my own versatile handling view.

    Note: this version works with <pk> and not with <object_id>
    """

    # Initialisations
    arErr = []              # errors   
    template_name = None    # The template to be used
    template_err_view = None
    form_validated = True   # Used for POST form validation
    savedate = None         # When saving information, the savedate is returned in the context
    add = False             # Are we adding a new record or editing an existing one?
    obj = None              # The instance of the MainModel
    action = ""             # The action to be undertaken
    MainModel = None        # The model that is mainly used for this form
    form_objects = []       # List of forms to be processed
    formset_objects = []    # List of formsets to be processed
    previous = None         # Return to this
    bDebug = False          # Debugging information
    data = {'status': 'ok', 'html': ''}       # Create data to be returned    
    
    def post(self, request, pk=None):
        # A POST request means we are trying to SAVE something
        self.initializations(request, pk)

        # Explicitly set the status to OK
        self.data['status'] = "ok"
        
        if self.checkAuthentication(request):
            # Build the context
            context = dict(object_id = pk, savedate=None)
            # context['prevpage'] = get_prevpage(request)     #  self.previous
            context['authenticated'] = user_is_authenticated(request)
            context['is_passim_uploader'] = user_is_ingroup(request, 'passim_uploader')
            context['is_passim_editor'] = user_is_ingroup(request, 'passim_editor')
            # Action depends on 'action' value
            if self.action == "":
                if self.bDebug: self.oErr.Status("ResearchPart: action=(empty)")
                # Walk all the forms for preparation of the formObj contents
                for formObj in self.form_objects:
                    # Are we SAVING a NEW item?
                    if self.add:
                        # We are saving a NEW item
                        formObj['forminstance'] = formObj['form'](request.POST, prefix=formObj['prefix'])
                    else:
                        # We are saving an EXISTING item
                        # Determine the instance to be passed on
                        instance = self.get_instance(formObj['prefix'])
                        # Make the instance available in the form-object
                        formObj['instance'] = instance
                        # Get an instance of the form
                        formObj['forminstance'] = formObj['form'](request.POST, prefix=formObj['prefix'], instance=instance)

                # Initially we are assuming this just is a review
                context['savedate']="reviewed at {}".format(get_current_datetime().strftime("%X"))

                # Iterate again
                for formObj in self.form_objects:
                    prefix = formObj['prefix']
                    # Adapt if it is not readonly
                    if not formObj['readonly']:
                        # Check validity of form
                        if formObj['forminstance'].is_valid() and self.is_custom_valid(prefix, formObj['forminstance']):
                            # Save it preliminarily
                            instance = formObj['forminstance'].save(commit=False)
                            # The instance must be made available (even though it is only 'preliminary')
                            formObj['instance'] = instance
                            # Perform actions to this form BEFORE FINAL saving
                            bNeedSaving = formObj['forminstance'].has_changed()
                            if self.before_save(prefix, request, instance=instance, form=formObj['forminstance']): bNeedSaving = True
                            if formObj['forminstance'].instance.id == None: bNeedSaving = True
                            if bNeedSaving:
                                # Perform the saving
                                instance.save()
                                # Set the context
                                context['savedate']="saved at {}".format(get_current_datetime().strftime("%X"))
                                # Put the instance in the form object
                                formObj['instance'] = instance
                                # Store the instance id in the data
                                self.data[prefix + '_instanceid'] = instance.id
                                # Any action after saving this form
                                self.after_save(prefix, instance)
                            # Also get the cleaned data from the form
                            formObj['cleaned_data'] = formObj['forminstance'].cleaned_data
                        else:
                            self.arErr.append(formObj['forminstance'].errors)
                            self.form_validated = False
                            formObj['cleaned_data'] = None
                    else:
                        # Form is readonly

                        # Check validity of form
                        if formObj['forminstance'].is_valid() and self.is_custom_valid(prefix, formObj['forminstance']):
                            # At least get the cleaned data from the form
                            formObj['cleaned_data'] = formObj['forminstance'].cleaned_data


                    # Add instance to the context object
                    context[prefix + "Form"] = formObj['forminstance']
                # Walk all the formset objects
                for formsetObj in self.formset_objects:
                    prefix  = formsetObj['prefix']
                    if self.can_process_formset(prefix):
                        formsetClass = formsetObj['formsetClass']
                        form_kwargs = self.get_form_kwargs(prefix)
                        if self.add:
                            # Saving a NEW item
                            formset = formsetClass(request.POST, request.FILES, prefix=prefix, form_kwargs = form_kwargs)
                        else:
                            # Saving an EXISTING item
                            instance = self.get_instance(prefix)
                            qs = self.get_queryset(prefix)
                            if qs == None:
                                formset = formsetClass(request.POST, request.FILES, prefix=prefix, instance=instance, form_kwargs = form_kwargs)
                            else:
                                formset = formsetClass(request.POST, request.FILES, prefix=prefix, instance=instance, queryset=qs, form_kwargs = form_kwargs)
                        # Process all the forms in the formset
                        self.process_formset(prefix, request, formset)
                        # Store the instance
                        formsetObj['formsetinstance'] = formset
                        # Adapt the formset contents only, when it is NOT READONLY
                        if not formsetObj['readonly']:
                            # Is the formset valid?
                            if formset.is_valid():
                                has_deletions = False
                                # Make sure all changes are saved in one database-go
                                with transaction.atomic():
                                    # Walk all the forms in the formset
                                    for form in formset:
                                        # At least check for validity
                                        if form.is_valid() and self.is_custom_valid(prefix, form):
                                            # Should we delete?
                                            if 'DELETE' in form.cleaned_data and form.cleaned_data['DELETE']:
                                                # Check if deletion should be done
                                                if self.before_delete(prefix, form.instance):
                                                    # Delete this one
                                                    form.instance.delete()
                                                    # NOTE: the template knows this one is deleted by looking at form.DELETE
                                                    has_deletions = True
                                            else:
                                                # Check if anything has changed so far
                                                has_changed = form.has_changed()
                                                # Save it preliminarily
                                                sub_instance = form.save(commit=False)
                                                # Any actions before saving
                                                if self.before_save(prefix, request, sub_instance, form):
                                                    has_changed = True
                                                # Save this construction
                                                if has_changed: 
                                                    # Save the instance
                                                    sub_instance.save()
                                                    # Adapt the last save time
                                                    context['savedate']="saved at {}".format(get_current_datetime().strftime("%X"))
                                                    # Store the instance id in the data
                                                    self.data[prefix + '_instanceid'] = sub_instance.id
                                                    # Any action after saving this form
                                                    self.after_save(prefix, sub_instance)
                                        else:
                                            if len(form.errors) > 0:
                                                self.arErr.append(form.errors)
                                
                                # Rebuild the formset if it contains deleted forms
                                if has_deletions or not has_deletions:
                                    # Or: ALWAYS
                                    if qs == None:
                                        formset = formsetClass(prefix=prefix, instance=instance, form_kwargs=form_kwargs)
                                    else:
                                        formset = formsetClass(prefix=prefix, instance=instance, queryset=qs, form_kwargs=form_kwargs)
                                    formsetObj['formsetinstance'] = formset
                            else:
                                # Iterate over all errors
                                for idx, err_this in enumerate(formset.errors):
                                    if '__all__' in err_this:
                                        self.arErr.append(err_this['__all__'][0])
                                    elif err_this != {}:
                                        # There is an error in item # [idx+1], field 
                                        problem = err_this 
                                        for k,v in err_this.items():
                                            fieldName = k
                                            errmsg = "Item #{} has an error at field [{}]: {}".format(idx+1, k, v[0])
                                            self.arErr.append(errmsg)

                            # self.arErr.append(formset.errors)
                    else:
                        formset = []
                    # Add the formset to the context
                    context[prefix + "_formset"] = formset
            elif self.action == "download":
                # We are being asked to download something
                if self.dtype != "":
                    # Initialise return status
                    oBack = {'status': 'ok'}
                    sType = "csv" if (self.dtype == "xlsx") else self.dtype

                    # Get the data
                    sData = self.get_data('', self.dtype)
                    # Decode the data and compress it using gzip
                    bUtf8 = (self.dtype != "db")
                    bUsePlain = (self.dtype == "xlsx" or self.dtype == "csv")

                    # Create name for download
                    # sDbName = "{}_{}_{}_QC{}_Dbase.{}{}".format(sCrpName, sLng, sPartDir, self.qcTarget, self.dtype, sGz)
                    modelname = self.MainModel.__name__
                    obj_id = "n" if self.obj == None else self.obj.id
                    sDbName = "passim_{}_{}.{}".format(modelname, obj_id, self.dtype)
                    sContentType = ""
                    if self.dtype == "csv":
                        sContentType = "text/tab-separated-values"
                    elif self.dtype == "json":
                        sContentType = "application/json"
                    elif self.dtype == "xlsx":
                        sContentType = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

                    # Excel needs additional conversion
                    if self.dtype == "xlsx":
                        # Convert 'compressed_content' to an Excel worksheet
                        response = HttpResponse(content_type=sContentType)
                        response['Content-Disposition'] = 'attachment; filename="{}"'.format(sDbName)    
                        response = csv_to_excel(sData, response)
                    else:
                        response = HttpResponse(sData, content_type=sContentType)
                        response['Content-Disposition'] = 'attachment; filename="{}"'.format(sDbName)    

                    # Continue for all formats
                        
                    # return gzip_middleware.process_response(request, response)
                    return response
            elif self.action == "delete":
                # The user requests this to be deleted
                if self.before_delete():
                    # We have permission to delete the instance
                    self.obj.delete()
                    context['deleted'] = True

            # Allow user to add to the context
            context = self.add_to_context(context)

            # Check if 'afternewurl' needs adding
            # NOTE: this should only be used after a *NEW* instance has been made -hence the self.add check
            if 'afternewurl' in context and self.add:
                self.data['afternewurl'] = context['afternewurl']
            if 'afterdelurl' in context:
                self.data['afterdelurl'] = context['afterdelurl']

            # Make sure we have a list of any errors
            error_list = [str(item) for item in self.arErr]
            context['error_list'] = error_list
            context['errors'] = json.dumps( self.arErr)
            if len(self.arErr) > 0:
                # Indicate that we have errors
                self.data['has_errors'] = True
                self.data['status'] = "error"
            else:
                self.data['has_errors'] = False
            # Standard: add request user to context
            context['requestuser'] = request.user

            # Get the HTML response
            if len(self.arErr) > 0:
                if self.template_err_view != None:
                     # Create a list of errors
                    self.data['err_view'] = render_to_string(self.template_err_view, context, request)
                else:
                    self.data['error_list'] = error_list
                    self.data['errors'] = self.arErr
                self.data['html'] = ''
            elif self.action == "delete":
                self.data['html'] = "deleted" 
            else:
                # In this case reset the errors - they should be shown within the template
                sHtml = render_to_string(self.template_name, context, request)
                sHtml = treat_bom(sHtml)
                self.data['html'] = sHtml

            # At any rate: empty the error basket
            self.arErr = []
            error_list = []

        else:
            self.data['html'] = "Please log in before continuing"

        # Return the information
        return JsonResponse(self.data)
        
    def get(self, request, pk=None): 
        self.data['status'] = 'ok'
        # Perform the initializations that need to be made anyway
        self.initializations(request, pk)
        if self.checkAuthentication(request):
            context = dict(object_id = pk, savedate=None)
            context['prevpage'] = self.previous
            context['authenticated'] = user_is_authenticated(request)
            context['is_passim_uploader'] = user_is_ingroup(request, 'passim_uploader')
            context['is_passim_editor'] = user_is_ingroup(request, 'passim_editor')
            # Walk all the form objects
            for formObj in self.form_objects:        
                # Used to populate a NEW research project
                # - CREATE a NEW research form, populating it with any initial data in the request
                initial = dict(request.GET.items())
                if self.add:
                    # Create a new form
                    formObj['forminstance'] = formObj['form'](initial=initial, prefix=formObj['prefix'])
                else:
                    # Used to show EXISTING information
                    instance = self.get_instance(formObj['prefix'])
                    # We should show the data belonging to the current Research [obj]
                    formObj['forminstance'] = formObj['form'](instance=instance, prefix=formObj['prefix'])
                # Add instance to the context object
                context[formObj['prefix'] + "Form"] = formObj['forminstance']
            # Walk all the formset objects
            for formsetObj in self.formset_objects:
                formsetClass = formsetObj['formsetClass']
                prefix  = formsetObj['prefix']
                form_kwargs = self.get_form_kwargs(prefix)
                if self.add:
                    # - CREATE a NEW formset, populating it with any initial data in the request
                    initial = dict(request.GET.items())
                    # Saving a NEW item
                    formset = formsetClass(initial=initial, prefix=prefix, form_kwargs=form_kwargs)
                else:
                    # show the data belonging to the current [obj]
                    instance = self.get_instance(prefix)
                    qs = self.get_queryset(prefix)
                    if qs == None:
                        formset = formsetClass(prefix=prefix, instance=instance, form_kwargs=form_kwargs)
                    else:
                        formset = formsetClass(prefix=prefix, instance=instance, queryset=qs, form_kwargs=form_kwargs)
                # Process all the forms in the formset
                ordered_forms = self.process_formset(prefix, request, formset)
                if ordered_forms:
                    context[prefix + "_ordered"] = ordered_forms
                # Store the instance
                formsetObj['formsetinstance'] = formset
                # Add the formset to the context
                context[prefix + "_formset"] = formset
            # Allow user to add to the context
            context = self.add_to_context(context)
            # Make sure we have a list of any errors
            error_list = [str(item) for item in self.arErr]
            context['error_list'] = error_list
            context['errors'] = self.arErr
            # Standard: add request user to context
            context['requestuser'] = request.user
            
            # Get the HTML response
            sHtml = render_to_string(self.template_name, context, request)
            sHtml = treat_bom(sHtml)
            self.data['html'] = sHtml
        else:
            self.data['html'] = "Please log in before continuing"

        # Return the information
        return JsonResponse(self.data)
      
    def checkAuthentication(self,request):
        # first check for authentication
        if not request.user.is_authenticated:
            # Simply redirect to the home page
            self.data['html'] = "Please log in to work on this project"
            return False
        else:
            return True

    def rebuild_formset(self, prefix, formset):
        return formset

    def initializations(self, request, object_id):
        # Store the previous page
        #self.previous = get_previous_page(request)
        # Clear errors
        self.arErr = []
        # COpy the request
        self.request = request
        # Copy any object id
        self.object_id = object_id
        self.add = object_id is None
        # Get the parameters
        if request.POST:
            self.qd = request.POST
        else:
            self.qd = request.GET

        # Check for action
        if 'action' in self.qd:
            self.action = self.qd['action']

        # Find out what the Main Model instance is, if any
        if self.add:
            self.obj = None
        else:
            # Get the instance of the Main Model object
            self.obj =  self.MainModel.objects.filter(pk=object_id).first()
            # NOTE: if the object doesn't exist, we will NOT get an error here
        # ALWAYS: perform some custom initialisations
        self.custom_init()

    def get_instance(self, prefix):
        return self.obj

    def is_custom_valid(self, prefix, form):
        return True

    def get_queryset(self, prefix):
        return None

    def get_form_kwargs(self, prefix):
        return None

    def get_data(self, prefix, dtype):
        return ""

    def before_save(self, prefix, request, instance=None, form=None):
        return False

    def before_delete(self, prefix=None, instance=None):
        return True

    def after_save(self, prefix, instance=None):
        return True

    def add_to_context(self, context):
        return context

    def process_formset(self, prefix, request, formset):
        return None

    def can_process_formset(self, prefix):
        return True

    def custom_init(self):
        pass    
           

class PassimDetails(DetailView):
    """Extension of the normal DetailView class for PASSIM"""

    template_name = ""      # Template for GET
    template_post = ""      # Template for POST
    formset_objects = []    # List of formsets to be processed
    afternewurl = ""        # URL to move to after adding a new item
    prefix = ""             # The prefix for the one (!) form we use
    previous = None         # Start with empty previous page
    title = ""              # The title to be passedon with the context
    rtype = "json"          # JSON response (alternative: html)
    prefix_type = ""        # Whether the adapt the prefix or not ('simple')
    mForm = None            # Model form
    add = False             # Are we adding a new record or editing an existing one?

    def get(self, request, pk=None, *args, **kwargs):
        # Initialisation
        data = {'status': 'ok', 'html': '', 'statuscode': ''}
        # always do this initialisation to get the object
        self.initializations(request, pk)
        if not request.user.is_authenticated:
            # Do not allow to get a good response
            if self.rtype == "json":
                data['html'] = "(No authorization)"
                data['status'] = "error"
                response = JsonResponse(data)
            else:
                response = reverse('nlogin')
        else:
            context = self.get_context_data(object=self.object)

            # Possibly indicate form errors
            # NOTE: errors is a dictionary itself...
            if 'errors' in context and len(context['errors']) > 0:
                data['status'] = "error"
                data['msg'] = context['errors']

            if self.rtype == "json":
                # We render to the _name 
                sHtml = render_to_string(self.template_name, context, request)
                sHtml = sHtml.replace("\ufeff", "")
                data['html'] = sHtml
                response = JsonResponse(data)
            else:
                # This takes self.template_name...
                response = self.render_to_response(context)

        # Return the response
        return response

    def post(self, request, pk=None, *args, **kwargs):
        # Initialisation
        data = {'status': 'ok', 'html': '', 'statuscode': ''}
        # always do this initialisation to get the object
        self.initializations(request, pk)
        # Make sure only POSTS get through that are authorized
        if request.user.is_authenticated:
            context = self.get_context_data(object=self.object)
            # Check if 'afternewurl' needs adding
            if 'afternewurl' in context:
                data['afternewurl'] = context['afternewurl']
            # Check if 'afterdelurl' needs adding
            if 'afterdelurl' in context:
                data['afterdelurl'] = context['afterdelurl']
            # Possibly indicate form errors
            # NOTE: errors is a dictionary itself...
            if 'errors' in context and len(context['errors']) > 0:
                data['status'] = "error"
                data['msg'] = context['errors']
            # response = self.render_to_response(self.template_post, context)
            response = render_to_string(self.template_post, context, request)
            response = response.replace("\ufeff", "")
            data['html'] = response
        else:
            data['html'] = "(No authorization)"
            data['status'] = "error"

        # Return the response
        return JsonResponse(data)

    def initializations(self, request, pk):
        # Store the previous page
        # self.previous = get_previous_page(request)

        # Copy any pk
        self.pk = pk
        self.add = pk is None
        # Get the parameters
        if request.POST:
            self.qd = request.POST
        else:
            self.qd = request.GET

        # Check for action
        if 'action' in self.qd:
            self.action = self.qd['action']

        # Find out what the Main Model instance is, if any
        if self.add:
            self.object = None
        else:
            # Get the instance of the Main Model object
            # NOTE: if the object doesn't exist, we will NOT get an error here
            self.object = self.get_object()

    def before_delete(self, instance):
        """Anything that needs doing before deleting [instance] """
        return True, "" 

    def after_new(self, form, instance):
        """Action to be performed after adding a new item"""
        return True, "" 

    def before_save(self, instance):
        """Action to be performed after saving an item preliminarily, and before saving completely"""
        return True, "" 

    def add_to_context(self, context, instance):
        """Add to the existing context"""
        return context

    def process_formset(self, prefix, request, formset):
        return None

    def get_formset_queryset(self, prefix):
        return None

    def get_form_kwargs(self, prefix):
        return None

    def get_context_data(self, **kwargs):
        # Get the current context
        context = super(PassimDetails, self).get_context_data(**kwargs)

        # Check this user: is he allowed to UPLOAD data?
        context['authenticated'] = user_is_authenticated(self.request)
        context['is_passim_uploader'] = user_is_ingroup(self.request, 'passim_uploader')
        context['is_passim_editor'] = user_is_ingroup(self.request, 'passim_editor')
        # context['prevpage'] = get_previous_page(self.request) # self.previous

        # Define where to go to after deletion
        context['afterdelurl'] = get_previous_page(self.request)

        # Get the parameters passed on with the GET or the POST request
        get = self.request.GET if self.request.method == "GET" else self.request.POST
        initial = get.copy()
        self.qd = initial

        self.bHasFormInfo = (len(self.qd) > 0)

        # Set the title of the application
        context['title'] = self.title

        # Get the instance
        instance = self.object
        bNew = False
        mForm = self.mForm
        oErr = ErrHandle()

        # prefix = self.prefix
        if self.prefix_type == "":
            id = "n" if instance == None else instance.id
            prefix = "{}-{}".format(self.prefix, id)
        else:
            prefix = self.prefix

        # Check if this is a POST or a GET request
        if self.request.method == "POST":
            # Determine what the action is (if specified)
            action = ""
            if 'action' in initial: action = initial['action']
            if action == "delete":
                # The user wants to delete this item
                try:
                    bResult, msg = self.before_delete(instance)
                    if bResult:
                        # Remove this sermongold instance
                        instance.delete()
                    else:
                        # Removing is not possible
                        context['errors'] = {'delete': msg }
                except:
                    msg = oErr.get_error_message()
                    # Create an errors object
                    context['errors'] = {'delete':  msg }
                # And return the complied context
                return context
            
            # All other actions just mean: edit or new and send back

            # Do we have an existing object or are we creating?
            if instance == None:
                # Saving a new item
                frm = mForm(initial, prefix=prefix)
                bNew = True
            else:
                # Editing an existing one
                frm = mForm(initial, prefix=prefix, instance=instance)
            # Both cases: validation and saving
            if frm.is_valid():
                # The form is valid - do a preliminary saving
                instance = frm.save(commit=False)
                # Any checks go here...
                bResult, msg = self.before_save(instance)
                if bResult:
                    # Now save it for real
                    instance.save()
                else:
                    context['errors'] = {'save': msg }
            else:
                # We need to pass on to the user that there are errors
                context['errors'] = frm.errors
            # Check if this is a new one
            if bNew:
                # Any code that should be added when creating a new [SermonGold] instance
                bResult, msg = self.after_new(frm, instance)
                if not bResult:
                    # Removing is not possible
                    context['errors'] = {'new': msg }
                # Check if an 'afternewurl' is specified
                if self.afternewurl != "":
                    context['afternewurl'] = self.afternewurl
                
        else:
            # Check if this is asking for a new form
            if instance == None:
                # Get the form for the sermon
                frm = mForm(prefix=prefix)
            else:
                # Get the form for the sermon
                frm = mForm(instance=instance, prefix=prefix)
            # Walk all the formset objects
            for formsetObj in self.formset_objects:
                formsetClass = formsetObj['formsetClass']
                prefix  = formsetObj['prefix']
                form_kwargs = self.get_form_kwargs(prefix)
                if self.add:
                    # - CREATE a NEW formset, populating it with any initial data in the request
                    # Saving a NEW item
                    formset = formsetClass(initial=initial, prefix=prefix, form_kwargs=form_kwargs)
                else:
                    # show the data belonging to the current [obj]
                    qs = self.get_formset_queryset(prefix)
                    if qs == None:
                        formset = formsetClass(prefix=prefix, instance=instance, form_kwargs=form_kwargs)
                    else:
                        formset = formsetClass(prefix=prefix, instance=instance, queryset=qs, form_kwargs=form_kwargs)
                # Process all the forms in the formset
                ordered_forms = self.process_formset(prefix, self.request, formset)
                if ordered_forms:
                    context[prefix + "_ordered"] = ordered_forms
                # Store the instance
                formsetObj['formsetinstance'] = formset
                # Add the formset to the context
                context[prefix + "_formset"] = formset

        # Put the form and the formset in the context
        context['{}Form'.format(self.prefix)] = frm
        context['instance'] = instance

        # Possibly add to context by the calling function
        context = self.add_to_context(context, instance)

        # Return the calculated context
        return context


class ManuscriptEdit(BasicPart):
    """The details of one manuscript"""

    MainModel = Manuscript
    template_name = 'seeker/manuscript_edit.html'  
    title = "Manuscript" 
    afternewurl = ""
    # One form is attached to this 
    prefix = "manu"
    form_objects = [{'form': ManuscriptForm, 'prefix': prefix, 'readonly': False}]

    def before_save(self, prefix, request, instance = None, form = None):
        bNeedSaving = False
        if prefix == "manu":
            # Check if a new 'Origin' has been added
            if 'origname_ta' in form.changed_data:

                # TODO: check if this is not already taken care of...

                # Get its value
                sOrigin = form.cleaned_data['origname_ta']
                # Check if it is already in the Nicknames
                origin = Origin.find_or_create(sOrigin)
                if instance.origin != origin:
                    # Add it
                    instance.origin = origin
                    # Make sure that it is being saved
                    bNeedSaving = True
            # Is this a new manuscript?
            if self.add or instance.source == None:
                # Create a source info element
                source = SourceInfo(collector=request.user.username, code="Manually added") # TH: aanpassen, klopt niet, ccfr
                source.save()
                instance.source = source
                bNeedSaving = True

        return bNeedSaving

    def add_to_context(self, context):

        # Get the instance
        instance = self.obj

        # Construct the hierarchical list
        sermon_list = []
        maxdepth = 0
        if instance != None:
            # Create a well sorted list of sermons
            qs = instance.manusermons.filter(order__gte=0).order_by('order')
            prev_level = 0
            for sermon in qs:
                oSermon = {}
                oSermon['obj'] = sermon
                oSermon['nodeid'] = sermon.order + 1
                oSermon['childof'] = 1 if sermon.parent == None else sermon.parent.order + 1
                level = sermon.getdepth()
                oSermon['level'] = level
                oSermon['pre'] = (level-1) * 20
                # If this is a new level, indicate it
                oSermon['group'] = (sermon.firstchild != None)
                sermon_list.append(oSermon)
                # Bookkeeping
                if level > maxdepth: maxdepth = level
                prev_level = level
            # Review them all and fill in the colspan
            for oSermon in sermon_list:
                oSermon['cols'] = maxdepth - oSermon['level'] + 1
                if oSermon['group']: oSermon['cols'] -= 1

        # Add instances to the list, noting their childof and order
        context['sermon_list'] = sermon_list
        context['sermon_count'] = len(sermon_list)
        context['maxdepth'] = maxdepth
        # context['isnew'] = bNew

        context['afternewurl'] = reverse('search_manuscript')

        return context


class SermonDetails(PassimDetails):
    """The details of one sermon"""

    model = SermonDescr
    mForm = SermonForm
    template_name = 'seeker/sermon_details.html'    # Use this for GET and for POST requests
    template_post = 'seeker/sermon_details.html'
    prefix = "sermo"
    prefix_type = "simple"
    title = "Sermon" 
    afternewurl = ""
    rtype = "html"
    StogFormSet = inlineformset_factory(SermonDescr, SermonDescrGold,
                                         form=SermonDescrGoldForm, min_num=0,
                                         fk_name = "sermon",
                                         extra=0, can_delete=True, can_order=False)
    formset_objects = [{'formsetClass': StogFormSet, 'prefix': 'stog', 'readonly': False}]

    def before_delete(self, instance):

        oErr = ErrHandle()
        try:
            # (1) Check if there is an 'equality' link to another SermonGold

            # (2) If there is an alternative SermonGold: change all SermonDescr-to-this-Gold link to the alternative

            # (3) Remove all gold-to-gold links that include this one

            # (4) Remove all links from SermonDescr to this instance of SermonGold

            # All is well
            return True, "" 
        except:
            msg = oErr.get_error_message()
            return False, msg

    def after_new(self, form, instance):
        """Action to be performed after adding a new item"""
        # self.afternewurl = reverse('search_gold')
        return True, "" 

    def add_to_context(self, context, instance):
        """Add to the existing context"""

        # Process this visit and get the new breadcrumbs object
        context['breadcrumbs'] = process_visit(self.request, "Sermon details", False)
        context['prevpage'] = get_previous_page(self.request)

        # New:
        if instance.manu == None:
            context['manuscript_id'] = None
        else:
            context['manuscript_id'] = instance.manu.id


        return context


class SermonEdit(BasicPart):
    """The details of one manuscript"""

    MainModel = SermonDescr
    template_name = 'seeker/sermon_edit.html'  
    title = "Sermon" 
    afternewurl = ""
    # One form is attached to this 
    prefix = "sermo"
    form_objects = [{'form': SermonForm, 'prefix': prefix, 'readonly': False}]

    def custom_init(self):
        """Adapt the prefix for [sermo] to fit the kind of prefix provided by PassimDetails"""

        return True

    def add_to_context(self, context):

        # Get the instance
        instance = self.obj

        # Not sure if this is still needed
        context['msitem'] = instance

        # Make sure to pass on the manuscript_id
        manuscript_id = None
        if 'manuscript_id' in self.qd:
            manuscript_id = self.qd['manuscript_id']
            # Set the URL to be taken after saving
            context['afternewurl'] = reverse('manuscript_details', kwargs={'pk': manuscript_id})
        context['manuscript_id'] = manuscript_id

        # Define where to go to after deletion
        # context['afterdelurl'] = reverse("sermon_list")
        context['afterdelurl'] = get_previous_page(self.request)

        return context

    def after_save(self, prefix, instance = None):

        # Check if this is a new one
        if self.add:
            # This is a new one, so it should be coupled to the correct manuscript
            if 'manuscript_id' in self.qd:
                # It is there, so we can add it
                manuscript = Manuscript.objects.filter(id=self.qd['manuscript_id']).first()
                if manuscript != None:
                    # Adapt the SermonDescr instance
                    instance.manu = manuscript
                    # Calculate how many sermons there are
                    sermon_count = manuscript.manusermons.all().count()
                    # Make sure the new sermon gets changed
                    instance.order = sermon_count
                    instance.save()
                        
        
        # There's is no real return value needed here 
        return True


class SermonListView(ListView):
    """Search and list manuscripts"""
    
    model = SermonDescr
    paginate_by = 20
    template_name = 'seeker/sermon_list.html'
    entrycount = 0
    bDoTime = True
    bFilter = False     # Status of the filter
    page_function = "ru.passim.seeker.search_paged_start"
    order_cols = ['author__name;nickname__name', 'siglist', 'srchincipit;srchexplicit', 'manu__idno', '','']
    order_heads = [{'name': 'Author', 'order': 'o=1', 'type': 'str'}, 
                   {'name': 'Signature', 'order': 'o=2', 'type': 'str'}, 
                   {'name': 'Incipit ... Explicit', 'order': 'o=3', 'type': 'str'},
                   {'name': 'Manuscript', 'order': 'o=4', 'type': 'str'},
                   {'name': 'Locus', 'order': '', 'type': 'str'},
                   {'name': 'Links', 'order': '', 'type': 'str'},
                   {'name': 'Status', 'order': '', 'type': 'str'}]

    def get_context_data(self, **kwargs):
        # Call the base implementation first to get a context
        context = super(SermonListView, self).get_context_data(**kwargs)

        # Get parameters for the search
        initial = self.request.POST if self.request.POST else self.request.GET

        # Add a form that defines search criteria for a sermon
        # If there was a previous form, then its values are in 'initial', and they are taken over
        prefix='sermo'
        context['sermoForm'] = SermonForm(initial, prefix=prefix)
        # Make sure we evaluate the form, to get cleaned_data
        bFormOkay = context['sermoForm'].is_valid()

        # Determine the count 
        context['entrycount'] = self.entrycount # self.get_queryset().count()

        # Set the prefix
        context['app_prefix'] = APP_PREFIX

        # Make sure the paginate-values are available
        context['paginateValues'] = paginateValues

        if 'paginate_by' in initial:
            context['paginateSize'] = int(initial['paginate_by'])
        else:
            context['paginateSize'] = paginateSize

        # Need to pass on a pagination function
        context['page_function'] = self.page_function
        # Set the page number if needed
        if 'page_obj' in context and 'page' in initial and initial['page'] != "":
            # context['page_obj'].number = initial['page']
            page_num = int(initial['page'])
            context['page_obj'] = context['paginator'].page( page_num)
        context['has_filter'] = self.bFilter


        # Set the title of the application
        context['title'] = "Sermons"

        # Make sure we pass on the ordered heads
        context['order_heads'] = self.order_heads

        # Process this visit and get the new breadcrumbs object
        kwargs = {}
        for k,v in initial.items():
            if v != None and v != "" and k.lower() != "csrfmiddlewaretoken":
                kwargs[k] = v

        context['breadcrumbs'] = process_visit(self.request, "Sermons", False, **kwargs)
        context['prevpage'] = get_previous_page(self.request)

        # Check this user: is he allowed to UPLOAD data?
        context['authenticated'] = user_is_authenticated(self.request)
        context['is_passim_uploader'] = user_is_ingroup(self.request, 'passim_uploader')
        context['is_passim_editor'] = user_is_ingroup(self.request, 'passim_editor')

        # Return the calculated context
        return context

    def get_paginate_by(self, queryset):
        """
        Paginate by specified value in querystring, or use default class property value.
        """
        return self.request.GET.get('paginate_by', self.paginate_by)
  
    def get_queryset(self):
        # Measure how long it takes
        if self.bDoTime: iStart = get_now_time()

        # Get the parameters passed on with the GET or the POST request
        get = self.request.GET if self.request.method == "GET" else self.request.POST
        get = get.copy()
        self.qd = get

        self.bHasFormset = (len(get) > 0)

        # Fix the sort-order
        get['sortOrder'] = 'name'

        if self.bHasFormset:
            # Get the formset from the input
            lstQ = []

            sermoForm = SermonForm(self.qd, prefix='sermo')

            if sermoForm.is_valid():

                # Process the criteria from this form 
                oFields = sermoForm.cleaned_data

                # Check for author name -- which is in the typeahead parameter
                if 'author' in oFields and oFields['author'] != "" and oFields['author'] != None: 
                    val = oFields['author']
                    lstQ.append(Q(author=val))
                elif 'authorname' in oFields and oFields['authorname'] != ""  and oFields['authorname'] != None: 
                    val = adapt_search(oFields['authorname'])
                    lstQ.append(Q(author__name__iregex=val))

                # Check for incipit string
                if 'incipit' in oFields and oFields['incipit'] != "" and oFields['incipit'] != None: 
                    val = adapt_search(oFields['incipit'])
                    lstQ.append(Q(srchincipit__iregex=val))

                # Check for explicit string
                if 'explicit' in oFields and oFields['explicit'] != "" and oFields['explicit'] != None: 
                    val = adapt_search(oFields['explicit'])
                    lstQ.append(Q(srchexplicit__iregex=val))

                # Check for explicit string
                if 'manuidno' in oFields and oFields['manuidno'] != "" and oFields['manuidno'] != None: 
                    val = adapt_search(oFields['manuidno'])
                    lstQ.append(Q(manu__idno__iregex=val))

                # Check for Sermon Clavis [signature]
                if 'sigclavis' in oFields and oFields['sigclavis'] != "" and oFields['sigclavis'] != None: 
                    val = adapt_search(oFields['sigclavis'])
                    lstQ.append(Q(sermonsignatures__code__iregex=val))
                    editype = "cl"
                    lstQ.append(Q(sermonsignatures__editype=editype))

                # Check for Sermon Gryson [signature]
                if 'siggryson' in oFields and oFields['siggryson'] != "" and oFields['siggryson'] != None: 
                    val = adapt_search(oFields['siggryson'])
                    lstQ.append(Q(sermonsignatures__code__iregex=val))
                    editype = "gr"
                    lstQ.append(Q(sermonsignatures__editype=editype))

                # Calculate the final qs
                if len(lstQ) == 0:
                    # No filter: Just show everything
                    qs = SermonDescr.objects.all()
                else:
                    # There is a filter: apply it
                    qs = SermonDescr.objects.filter(*lstQ).distinct()
                    self.bFilter = True
            else:
                # TODO: communicate the error to the user???


                # Just show everything
                qs = SermonDescr.objects.all().distinct()

        else:
            # Just show everything
            qs = SermonDescr.objects.all().distinct()

        # Do sorting: Start with an initial order
        order = ['author__name', 'nickname__name', 'siglist', 'incipit', 'explicit']
        bAscending = True
        sType = 'str'
        if 'o' in self.qd:
            order = []
            iOrderCol = int(self.qd['o'])
            bAscending = (iOrderCol>0)
            iOrderCol = abs(iOrderCol)
            for order_item in self.order_cols[iOrderCol-1].split(";"):
                order.append(Lower(order_item))
            sType = self.order_heads[iOrderCol-1]['type']
            if bAscending:
                self.order_heads[iOrderCol-1]['order'] = 'o=-{}'.format(iOrderCol)
            else:
                # order = "-" + order
                self.order_heads[iOrderCol-1]['order'] = 'o={}'.format(iOrderCol)
        if sType == 'str':
            qs = qs.order_by(*order)
        else:
            qs = qs.order_by(*order)
        # Possibly reverse the order
        if not bAscending:
            qs = qs.reverse()

        # Time measurement
        if self.bDoTime:
            print("SermonListView get_queryset point 'a': {:.1f}".format( get_now_time() - iStart))
            # print("SermonGoldListView query: {}".format(qs.query))
            iStart = get_now_time()

        # Determine the length
        self.entrycount = len(qs)

        # Time measurement
        if self.bDoTime:
            print("SermonListView get_queryset point 'b': {:.1f}".format( get_now_time() - iStart))

        # Return the resulting filtered and sorted queryset
        return qs

    def post(self, request, *args, **kwargs):
        return self.get(request, *args, **kwargs)


class SermonLinkset(BasicPart):
    """The set of links from one gold sermon"""

    MainModel = SermonDescr
    template_name = 'seeker/sermon_linkset.html'
    title = "SermonLinkset"
    StogFormSet = inlineformset_factory(SermonDescr, SermonDescrGold,
                                         form=SermonDescrGoldForm, min_num=0,
                                         fk_name = "sermon",
                                         extra=0, can_delete=True, can_order=False)
    formset_objects = [{'formsetClass': StogFormSet, 'prefix': 'stog', 'readonly': False}]


class SermonSignset(BasicPart):
    """The set of signatures from one sermon (manifestation)"""

    MainModel = SermonDescr
    template_name = 'seeker/sermon_signset.html'
    title = "SermonSignset"
    SrmsignFormSet = inlineformset_factory(SermonDescr, SermonSignature,
                                         form=SermonDescrSignatureForm, min_num=0,
                                         fk_name = "sermon",
                                         extra=0, can_delete=True, can_order=False)
    formset_objects = [{'formsetClass': SrmsignFormSet, 'prefix': 'srmsign', 'readonly': False}]
    
    def add_to_context(self, context):
        context['edi_list'] = [{'type': 'gr', 'name': 'Gryson'},
                               {'type': 'cl', 'name': 'Clavis'},
                               {'type': 'ot', 'name': 'Other'}]
        return context


class ManuscriptDetails(PassimDetails):
    """Editable manuscript details"""

    model = Manuscript
    mForm = ManuscriptForm
    template_name = 'seeker/manuscript_details.html'    # Use this for GET requests
    template_post = 'seeker/manuscript_details.html'    # Use this for POST requests
    title = "Manuscript" 
    afternewurl = ""
    prefix = "manu"
    prefix_type = "simple"
    rtype = "html"      # Load this as straight forward html

    def add_to_context(self, context, instance):

        # Get the instance
        instance = self.object

        # Construct the hierarchical list
        sermon_list = []
        maxdepth = 0
        if instance != None:
            # Create a well sorted list of sermons
            qs = instance.manusermons.filter(order__gte=0).order_by('order')
            prev_level = 0
            for sermon in qs:
                oSermon = {}
                oSermon['obj'] = sermon
                oSermon['nodeid'] = sermon.order + 1
                oSermon['childof'] = 1 if sermon.parent == None else sermon.parent.order + 1
                level = sermon.getdepth()
                oSermon['level'] = level
                oSermon['pre'] = (level-1) * 20
                # If this is a new level, indicate it
                oSermon['group'] = (sermon.firstchild != None)
                sermon_list.append(oSermon)
                # Bookkeeping
                if level > maxdepth: maxdepth = level
                prev_level = level
            # Review them all and fill in the colspan
            for oSermon in sermon_list:
                oSermon['cols'] = maxdepth - oSermon['level'] + 1
                if oSermon['group']: oSermon['cols'] -= 1

        # Add instances to the list, noting their childof and order
        context['sermon_list'] = sermon_list
        context['sermon_count'] = len(sermon_list)
        context['maxdepth'] = maxdepth
        #context['isnew'] = bNew

        # Process this visit and get the new breadcrumbs object
        context['breadcrumbs'] = process_visit(self.request, "Manuscript details", False)
        context['prevpage'] = get_previous_page(self.request)

        context['afternewurl'] = reverse('search_manuscript')

        return context


class ManuscriptListView(ListView):
    """Search and list manuscripts"""
    
    model = Manuscript
    paginate_by = 20
    template_name = 'seeker/manuscript.html'
    entrycount = 0
    bDoTime = True
    # Define a formset for searching
    ManuFormset = formset_factory(SearchManuscriptForm, extra=0, min_num=1)

    def get_context_data(self, **kwargs):
        # Call the base implementation first to get a context
        context = super(ManuscriptListView, self).get_context_data(**kwargs)

        # Get parameters for the search
        initial = self.request.GET

        # Determine the formset to be passed on
        if self.bHasFormset:
            manu_formset = self.ManuFormset(initial, prefix='manu')
        else:
            manu_formset = self.ManuFormset(prefix='manu')
        context['manu_formset'] = manu_formset

        # Add a files upload form
        context['uploadform'] = UploadFilesForm()

        # Add a form to enter a URL
        context['searchurlform'] = SearchUrlForm()

        # Determine the count 
        context['entrycount'] = self.entrycount # self.get_queryset().count()

        # Set the prefix
        context['app_prefix'] = APP_PREFIX

        # Make sure the paginate-values are available
        context['paginateValues'] = paginateValues

        if 'paginate_by' in initial:
            context['paginateSize'] = int(initial['paginate_by'])
        else:
            context['paginateSize'] = paginateSize

        # Process this visit and get the new breadcrumbs object
        context['breadcrumbs'] = process_visit(self.request, "Manuscripts", True)
        context['prevpage'] = get_previous_page(self.request)

        # Set the title of the application
        context['title'] = "Manuscripts"

        # Check this user: is he allowed to UPLOAD data?
        context['authenticated'] = user_is_authenticated(self.request)
        context['is_passim_uploader'] = user_is_ingroup(self.request, 'passim_uploader')
        context['is_passim_editor'] = user_is_ingroup(self.request, 'passim_editor')

        # Return the calculated context
        return context

    def get_paginate_by(self, queryset):
        """
        Paginate by specified value in querystring, or use default class property value.
        """
        return self.request.GET.get('paginate_by', self.paginate_by)
  
    def get_queryset(self):
        # Measure how long it takes
        if self.bDoTime: iStart = get_now_time()

        # Get the parameters passed on with the GET or the POST request
        get = self.request.GET if self.request.method == "GET" else self.request.POST
        get = get.copy()
        self.qd = get

        self.bHasFormset = ('manu-TOTAL_FORMS' in get)

        # Fix the sort-order
        get['sortOrder'] = 'name'

        if self.bHasFormset:
            # Get the formset from the input
            lstQ = []

            manu_formset = self.ManuFormset(self.qd, prefix='manu')

            # Process the formset
            if manu_formset != None:
                # Validate it
                if manu_formset.is_valid():
                    #  Everything okay, continue
                    for sform in manu_formset:
                        # Process the criteria from this form 
                        oFields = sform.cleaned_data
                        lstThisQ = []

                        # Check for Manuscript [name]
                        if 'idno' in oFields and oFields['idno'] != "": 
                            val = adapt_search(oFields['idno'])
                            lstThisQ.append(Q(idno__iregex=val))

                        # Check for Manuscript [name]
                        if 'name' in oFields and oFields['name'] != "": 
                            val = adapt_search(oFields['name'])
                            lstThisQ.append(Q(name__iregex=val))

                        # Check for Manuscript [idno]
                        if 'gryson' in oFields and oFields['gryson'] != "": 
                            val = adapt_search(oFields['gryson'])
                            lstThisQ.append(Q(idno__iregex=val))

                        # Check for Manuscript [idno]
                        if 'clavis' in oFields and oFields['clavis'] != "": 
                            val = adapt_search(oFields['clavis'])
                            lstThisQ.append(Q(idno__iregex=val))

                        # Check for country name
                        if 'country' in oFields and oFields['country'] != "": 
                            val = adapt_search(oFields['country'])
                            lstThisQ.append(Q(library__country__name__iregex=val))

                        # Check for city name
                        if 'city' in oFields and oFields['city'] != "": 
                            val = adapt_search(oFields['city'])
                            lstThisQ.append(Q(library__city__name__iregex=val))

                        # Check for library name
                        if 'library' in oFields and oFields['library'] != "": 
                            val = adapt_search(oFields['library'])
                            lstThisQ.append(Q(library__name__iregex=val))

                        # Now add these criterya to the overall lstQ
                        if len(lstThisQ) > 0:
                            lstQ.append(reduce(operator.and_, lstThisQ))
                else:
                    # What to do when it is not valid?
                    pass

            # Calculate the final qs
            if len(lstQ) == 0:
                # Just show everything
                qs = Manuscript.objects.all()
            elif len(lstQ) == 1:
                # criteria = reduce(operator.or_, lstQ)
                qs = Manuscript.objects.filter(*lstQ).distinct()
            else:
                criteria = reduce(operator.or_, lstQ)
                qs = Manuscript.objects.filter(criteria).distinct()
        else:
            # Just show everything
            qs = Manuscript.objects.all()

        # Set the sort order
        qs = qs.order_by('library__country__name', 
                         'library__city__name', 
                         'library__name', 
                         'idno')

        # Time measurement
        if self.bDoTime:
            print("ManuscriptListView get_queryset point 'a': {:.1f}".format( get_now_time() - iStart))
            print("ManuscriptListView query: {}".format(qs.query))
            iStart = get_now_time()

        # Determine the length
        self.entrycount = len(qs)

        # Time measurement
        if self.bDoTime:
            print("ManuscriptListView get_queryset point 'b': {:.1f}".format( get_now_time() - iStart))

        # Return the resulting filtered and sorted queryset
        return qs


class SermonGoldListView(ListView):
    """Search and list manuscripts"""
    
    model = SermonGold
    paginate_by = 20
    template_name = 'seeker/sermongold.html'
    entrycount = 0
    bDoTime = True
    order_cols = ['author__name', 'siglist', 'srchincipit;srchexplicit', '', '', '']
    order_heads = [{'name': 'Author', 'order': 'o=1', 'type': 'str'}, 
                   {'name': 'Signature', 'order': 'o=2', 'type': 'str'}, 
                   {'name': 'Incipit ... Explicit', 'order': 'o=3', 'type': 'str'},
                   {'name': 'Editions', 'order': '', 'type': 'str'},
                   {'name': 'Links', 'order': '', 'type': 'str'},
                   {'name': 'Status', 'order': '', 'type': 'str'}]

    def get_context_data(self, **kwargs):
        # Call the base implementation first to get a context
        context = super(SermonGoldListView, self).get_context_data(**kwargs)

        # Get parameters for the search
        initial = self.request.GET

        # ONE-TIME adhoc = SermonGold.init_latin()

        # Add a files upload form
        context['goldForm'] = SermonGoldForm(prefix='gold')

        # Determine the count 
        context['entrycount'] = self.entrycount # self.get_queryset().count()

        # Set the prefix
        context['app_prefix'] = APP_PREFIX

        # Make sure the paginate-values are available
        context['paginateValues'] = paginateValues

        if 'paginate_by' in initial:
            context['paginateSize'] = int(initial['paginate_by'])
        else:
            context['paginateSize'] = paginateSize

        # Set the title of the application
        context['title'] = "Gold-Sermons"

        # Make sure we pass on the ordered heads
        context['order_heads'] = self.order_heads

        # Process this visit and get the new breadcrumbs object
        context['breadcrumbs'] = process_visit(self.request, "Gold sermons", False)
        context['prevpage'] = get_previous_page(self.request)

        # Check this user: is he allowed to UPLOAD data?
        context['authenticated'] = user_is_authenticated(self.request)
        context['is_passim_uploader'] = user_is_ingroup(self.request, 'passim_uploader')
        context['is_passim_editor'] = user_is_ingroup(self.request, 'passim_editor')

        # Return the calculated context
        return context

    def get_paginate_by(self, queryset):
        """
        Paginate by specified value in querystring, or use default class property value.
        """
        return self.request.GET.get('paginate_by', self.paginate_by)
  
    def get_queryset(self):
        # Measure how long it takes
        if self.bDoTime: iStart = get_now_time()

        # Get the parameters passed on with the GET or the POST request
        get = self.request.GET if self.request.method == "GET" else self.request.POST
        get = get.copy()
        self.qd = get

        self.bHasFormset = (len(get) > 0)

        sort_type = "exclude_signature"
        sort_type = "ordered_columns"

        # Fix the sort-order
        get['sortOrder'] = 'name'

        if self.bHasFormset:
            # Get the formset from the input
            lstQ = []

            goldForm = SermonGoldForm(self.qd, prefix='gold')

            if goldForm.is_valid():

                # Process the criteria from this form 
                oFields = goldForm.cleaned_data

                # Check for author name -- which is in the typeahead parameter
                if 'author' in oFields and oFields['author'] != "" and oFields['author'] != None: 
                    val = oFields['author']
                    lstQ.append(Q(author=val))
                elif 'authorname' in oFields and oFields['authorname'] != ""  and oFields['authorname'] != None: 
                    val = adapt_search(oFields['authorname'])
                    lstQ.append(Q(author__name__iregex=val))

                # Check for incipit string
                if 'incipit' in oFields and oFields['incipit'] != "" and oFields['incipit'] != None: 
                    val = adapt_search(oFields['incipit'])
                    lstQ.append(Q(srchincipit__iregex=val))

                # Check for explicit string
                if 'explicit' in oFields and oFields['explicit'] != "" and oFields['explicit'] != None: 
                    val = adapt_search(oFields['explicit'])
                    lstQ.append(Q(srchexplicit__iregex=val))

                # Check for SermonGold [signature]
                if 'signature' in oFields and oFields['signature'] != "" and oFields['signature'] != None: 
                    val = adapt_search(oFields['signature'])
                    lstQ.append(Q(goldsignatures__code__iregex=val))

                # Check for SermonGold [signature]
                if 'keyword' in oFields and oFields['keyword'] != "" and oFields['keyword'] != None: 
                    val = adapt_search(oFields['keyword'])
                    lstQ.append(Q(keywords__name__iregex=val))

                # Calculate the final qs
                if len(lstQ) == 0:
                    # Just show everything
                    qs = SermonGold.objects.all()
                else:
                    qs = SermonGold.objects.filter(*lstQ).distinct()
            else:
                # TODO: communicate the error to the user???


                # Just show everything
                qs = SermonGold.objects.all().distinct()

        else:
            # Just show everything
            qs = SermonGold.objects.all().distinct()

        # Do sorting
        if sort_type == "exclude_signature":
            # Sort the 'normal' way on author/incipit/explicit
            qs = qs.order_by('author__name', 'siglist', 'incipit', 'explicit')
        elif sort_type == "ordered_columns":
            # Start with an initial order
            order = ['author__name', 'siglist', 'incipit', 'explicit']
            bAscending = True
            sType = 'str'
            if 'o' in self.qd:
                order = []
                iOrderCol = int(self.qd['o'])
                bAscending = (iOrderCol>0)
                iOrderCol = abs(iOrderCol)
                for order_item in self.order_cols[iOrderCol-1].split(";"):
                    order.append(Lower(order_item))
                sType = self.order_heads[iOrderCol-1]['type']
                if bAscending:
                    self.order_heads[iOrderCol-1]['order'] = 'o=-{}'.format(iOrderCol)
                else:
                    # order = "-" + order
                    self.order_heads[iOrderCol-1]['order'] = 'o={}'.format(iOrderCol)
            if sType == 'str':
                qs = qs.order_by(*order)
            else:
                qs = qs.order_by(*order)
            # Possibly reverse the order
            if not bAscending:
                qs = qs.reverse()
        else:
            # Sort the python way
            qs = sorted(qs, key=lambda x: x.get_sermon_string())

        # Time measurement
        if self.bDoTime:
            print("SermonGoldListView get_queryset point 'a': {:.1f}".format( get_now_time() - iStart))
            # print("SermonGoldListView query: {}".format(qs.query))
            iStart = get_now_time()

        # Determine the length
        self.entrycount = len(qs)

        # Time measurement
        if self.bDoTime:
            print("SermonGoldListView get_queryset point 'b': {:.1f}".format( get_now_time() - iStart))

        # Return the resulting filtered and sorted queryset
        return qs


class SermonGoldSelect(BasicPart):
    """Facilitate searching and selecting one gold sermon"""

    MainModel = SermonGold
    template_name = "seeker/sermongold_select.html"

    # Pagination
    paginate_by = paginateSelect
    page_function = "ru.passim.seeker.gold_page"
    form_div = "select_gold_button" 
    entrycount = 0
    qs = None

    # One form is attached to this 
    source_id = None
    prefix = 'gsel'
    form_objects = [{'form': SelectGoldForm, 'prefix': prefix, 'readonly': True}]

    def get_instance(self, prefix):
        instance = None
        if prefix == "gsel":
            # The instance is the SRC of a link
            instance = self.obj
        return instance

    def add_to_context(self, context):
        """Anything that needs adding to the context"""

        # If possible add source_id
        if 'source_id' in self.qd:
            self.source_id = self.qd['source_id']
        context['source_id'] = self.source_id
        
        # Pagination
        self.do_pagination('gold')
        context['object_list'] = self.page_obj
        context['page_obj'] = self.page_obj
        context['page_function'] = self.page_function
        context['formdiv'] = self.form_div
        context['entrycount'] = self.entrycount

        # Add the result to the context
        context['results'] = self.qs
        context['authenticated'] = user_is_authenticated(self.request)
        context['is_passim_uploader'] = user_is_ingroup(self.request, 'passim_uploader')
        context['is_passim_editor'] = user_is_ingroup(self.request, 'passim_editor')

        # Return the updated context
        return context

    def do_pagination(self, prefix):
        # We need to calculate the queryset immediately
        self.get_queryset(prefix)

        # Paging...
        page = self.qd.get('page')
        page = 1 if page == None else int(page)
        # Create a list [page_obj] that contains just these results
        paginator = Paginator(self.qs, self.paginate_by)
        self.page_obj = paginator.page(page)        

    def get_queryset(self, prefix):
        qs = SermonGold.objects.none()
        if prefix == "gold":
            # Get the cleaned data
            oFields = None
            if 'cleaned_data' in self.form_objects[0]:
                oFields = self.form_objects[0]['cleaned_data']
            qs = SermonGold.objects.none()
            if oFields != None and self.request.method == 'POST':
                # There is valid data to search with
                lstQ = []

                # (1) Check for author name -- which is in the typeahead parameter
                if 'author' in oFields and oFields['author'] != "" and oFields['author'] != None: 
                    val = oFields['author']
                    lstQ.append(Q(author=val))
                elif 'authorname' in oFields and oFields['authorname'] != ""  and oFields['authorname'] != None: 
                    val = adapt_search(oFields['authorname'])
                    lstQ.append(Q(author__name__iregex=val))

                # (2) Process incipit
                if 'incipit' in oFields and oFields['incipit'] != "" and oFields['incipit'] != None: 
                    val = adapt_search(oFields['incipit'])
                    lstQ.append(Q(incipit__iregex=val))

                # (3) Process explicit
                if 'explicit' in oFields and oFields['explicit'] != "" and oFields['explicit'] != None: 
                    val = adapt_search(oFields['explicit'])
                    lstQ.append(Q(explicit__iregex=val))

                # (4) Process signature
                if 'signature' in oFields and oFields['signature'] != "" and oFields['signature'] != None: 
                    val = adapt_search(oFields['signature'])
                    lstQ.append(Q(goldsignatures__code__iregex=val))

                # Calculate the final qs
                if len(lstQ) == 0:
                    # Show everything excluding myself
                    qs = SermonGold.objects.all()
                else:
                    # Make sure to exclude myself, and then apply the filter
                    qs = SermonGold.objects.filter(*lstQ)

                # Always exclude the source
                if self.source_id != None:
                    qs = qs.exclude(id=self.source_id)

                sort_type = "fast_and_easy"

                if sort_type == "pythonic":
                    # Sort the python way
                    qs = sorted(qs, key=lambda x: x.get_sermon_string())
                elif sort_type == "too_much":
                    # Make sure sorting is done correctly
                    qs = qs.order_by('signature__code', 'author__name', 'incipit', 'explicit')
                elif sort_type == "fast_and_easy":
                    # Sort fast and easy
                    qs = qs.order_by('author__name', 'siglist', 'incipit', 'explicit')
            
            self.entrycount = qs.count()
            self.qs = qs
        # Return the resulting filtered and sorted queryset
        return qs


class SermonGoldEqualset(BasicPart):
    """The set of equality links from one gold sermon"""

    MainModel = SermonGold
    template_name = 'seeker/sermongold_eqset.html'
    title = "SermonGoldLinkset"
    GeqFormSet = inlineformset_factory(EqualGold, SermonGold, 
                                         form=EqualGoldForm, min_num=0,
                                         fk_name = "equal",
                                         extra=0, can_delete=True, can_order=False)
    formset_objects = [{'formsetClass': GeqFormSet, 'prefix': 'geq', 'readonly': False}]

    def get_queryset(self, prefix):
        qs = None
        if prefix == "geq":
            # Get all SermonGold instances with the same EqualGold
            equal = self.obj.equal
            qs = SermonGold.objects.filter(equal=equal).exclude(id=self.obj.id)
        return qs

    def get_instance(self, prefix):
        if prefix == "geq" or "geq" in prefix:
            return self.obj.equal
        else:
            return self.obj

    def process_formset(self, prefix, request, formset):
        if prefix == "geq":
            for form in formset:
                # Check if this has an instance
                if form.instance == None or form.instance.id == None:
                    # This has no SermonGold instance: retrieve it from the 'gold' value
                    if 'gold' in form.fields:
                        gold_id = form['gold'].data
                        if gold_id != "":
                            gold = SermonGold.objects.filter(id=gold_id).first()
                            form.instance = gold
        # No return value needed
        return True

    def remove_from_eqset(self, instance):
        # In fact, a new 'EqualGold' instance must be created
        geq = EqualGold()
        geq.save()
        # Set the SermonGold instance to this new equality set
        instance.equal = geq
        instance.save()
        # Check if we need to retain any partial or other links
        gdkeep = [x for x in self.qd if "gdkeep-" in x]
        for keep in gdkeep:
            eqgl = EqualGoldLink.objects.filter(id=self.qd[keep]).first()
            # Create a new link
            lnk = EqualGoldLink(src=geq, dst=eqgl.dst, linktype=eqgl.linktype)
            lnk.save()
        # Return positively
        return True

    def before_delete(self, prefix = None, instance = None):
        """Check if moving of non-equal links should take place"""

        # NOTE: this is already part of a transaction.atomic() area!!!
        bDoDelete = True
        if prefix != None and prefix == "geq" and instance != None:
            # No actual deletion of anything should take place...
            bDoDelete = False
            # Perform the operation
            self.remove_from_eqset(instance)
        return bDoDelete

    def before_save(self, prefix, request, instance = None, form = None):
        bNeedSaving = False
        if prefix == "geq":
            self.gold = None
            if 'gold' in form.cleaned_data:
                # Get the form's 'gold' value
                gold_id = form.cleaned_data['gold']
                if gold_id != "":
                    # Find the gold to attach to
                    gold = SermonGold.objects.filter(id=gold_id).first()
                    if gold != None and gold.id != instance.id:
                        self.gold = gold
        return bNeedSaving

    def after_save(self, prefix, instance = None):
        # The instance here is the geq-instance, so an instance of SermonGold
        # Now make sure all related material is updated

        if self.gold == None:
            # Add this gold sermon to the equality group of the target
            added, lst_res = add_gold2equal(instance, self.obj.equal)
        else:
            # The user wants to change the gold-sermon inside the equality set: 
            # (1) Keep track of the current equality set
            eqset = self.obj.equal
            # (2) Remove [instance] from the equality set
            self.remove_from_eqset(instance)
            # (3) Add [gold] to the current equality set
            added, lst_res = add_gold2equal(self.gold, eqset)
            # (4) Save changes to the instance
            self.obj.save()
            # bNeedSaving = True
        return True

    def add_to_context(self, context):
        # Get the EqualGold instances to which I am associated
        context['associations'] = self.obj.equal.equalgold_src.all()

        return context

    
class SermonGoldLinkset(BasicPart):
    """The set of other links from one SermonEqual item"""

    MainModel = SermonGold
    template_name = 'seeker/sermongold_linkset.html'
    title = "SermonGoldLinkset"
    GlinkFormSet = inlineformset_factory(EqualGold, EqualGoldLink,
                                         form=EqualGoldLinkForm, min_num=0,
                                         fk_name = "src",
                                         extra=0, can_delete=True, can_order=False)
    formset_objects = [{'formsetClass': GlinkFormSet, 'prefix': 'glink', 'readonly': False}]

    def custom_init(self):
        x = 1

    def get_instance(self, prefix):
        if prefix == "glink" or "glink" in prefix:
            return self.obj.equal
        else:
            return self.obj

    def process_formset(self, prefix, request, formset):
        if prefix == "glink":
            # Check the forms in the formset, and set the correct 'dst' values where possible
            for form in formset:
                if 'gold' in form.changed_data and 'dst' in form.fields and 'gold' in form.fields:
                    gold_id = form['gold'].data
                    dst_id = form['dst'].data
                    if gold_id != None and gold_id != "":
                        gold = SermonGold.objects.filter(id=gold_id).first()
                        if gold != None:
                            # Gaat niet: form['dst'].data = gold.equal
                            #            form['dst'].data = gold.equal.id
                            #            form.fields['dst'].initial = gold.equal.id
                            form.instance.dst = gold.equal
        # No need to return a value
        return True

    def before_delete(self, prefix = None, instance = None):
        id = instance.id
        return True

    def before_save(self, prefix, request, instance = None, form = None):
        bNeedSaving = False
        if prefix == "glink":
            if 'gold' in form.cleaned_data:
                # Get the form's 'gold' value
                gold_id = form.cleaned_data['gold']
                if gold_id != "":
                    # Find the gold to attach to
                    gold = SermonGold.objects.filter(id=gold_id).first()
                    if gold != None:
                        # The destination must be an EqualGold instance
                        instance.dst = gold.equal
                        bNeedSaving = True
        return bNeedSaving

    def after_save(self, prefix, instance = None):
        # The instance here is the glink-instance, so an instance of EqualGoldLink
        # Now make sure all related material is updated

        # WAS: added, lst_res = add_gold2gold(instance.src, instance.dst, instance.linktype)

        added, lst_res = add_equal2equal(self.obj, instance.dst, instance.linktype)
        return True


class SermonGoldSignset(BasicPart):
    """The set of signatures from one gold sermon"""

    MainModel = SermonGold
    template_name = 'seeker/sermongold_signset.html'
    title = "SermonGoldSignset"
    GsignFormSet = inlineformset_factory(SermonGold, Signature,
                                         form=SermonGoldSignatureForm, min_num=0,
                                         fk_name = "gold",
                                         extra=0, can_delete=True, can_order=False)
    formset_objects = [{'formsetClass': GsignFormSet, 'prefix': 'gsign', 'readonly': False}]
    
    def add_to_context(self, context):
        context['edi_list'] = [{'type': 'gr', 'name': 'Gryson'},
                               {'type': 'cl', 'name': 'Clavis'},
                               {'type': 'ot', 'name': 'Other'}]
        return context


class SermonGoldEdiset(BasicPart):
    """The set of critical text editions from one gold sermon"""

    MainModel = SermonGold
    template_name = 'seeker/sermongold_ediset.html'
    title = "SermonGoldEditions"
    GediFormSet = inlineformset_factory(SermonGold, Edition,
                                         form=SermonGoldEditionForm, min_num=0,
                                         fk_name = "gold",
                                         extra=0, can_delete=True, can_order=False)
    formset_objects = [{'formsetClass': GediFormSet, 'prefix': 'gedi', 'readonly': False}]


class SermonGoldKwset(BasicPart):
    """The set of keywords from one gold sermon"""

    MainModel = SermonGold
    template_name = 'seeker/sermongold_kwset.html'
    title = "SermonGoldKeywords"
    GkwFormSet = inlineformset_factory(SermonGold, SermonGoldKeyword,
                                         form=SermonGoldKeywordForm, min_num=0,
                                         fk_name = "gold",
                                         extra=0, can_delete=True, can_order=False)
    formset_objects = [{'formsetClass': GkwFormSet, 'prefix': 'gkw', 'readonly': False}]

    def before_save(self, prefix, request, instance = None, form = None):
        has_changed = False
        if prefix == "gkw":
            # Get the chosen keyword
            obj = form.cleaned_data['keyword']
            if obj == None:
                # Get the value entered for the keyword
                kw = form['name'].data
                # Check if this is an existing Keyword
                obj = Keyword.objects.filter(name__iexact=kw).first()
                if obj == None:
                    # Create it
                    obj = Keyword(name=kw.lower())
                    obj.save()
                # Now set the instance value correctly
                instance.keyword = obj
                has_changed = True

        return has_changed


class SermonGoldFtxtset(BasicPart):
    """The set of critical text editions from one gold sermon"""

    MainModel = SermonGold
    template_name = 'seeker/sermongold_ftxtset.html'
    title = "SermonGoldFulltextLinks"
    GftextFormSet = inlineformset_factory(SermonGold, Ftextlink,
                                         form=SermonGoldFtextlinkForm, min_num=0,
                                         fk_name = "gold",
                                         extra=0, can_delete=True, can_order=False)
    formset_objects = [{'formsetClass': GftextFormSet, 'prefix': 'gftxt', 'readonly': False}]


class SermonGoldDetails(PassimDetails):
    """The details of one sermon"""

    model = SermonGold
    mForm = SermonGoldForm
    template_name = 'seeker/sermongold_details.html'    # Use this for GET and for POST requests
    template_post = 'seeker/sermongold_details.html'
    prefix = "gold"
    title = "SermonGold" 
    afternewurl = ""
    rtype = "html"
    GlinkFormSet = inlineformset_factory(SermonGold, SermonGoldSame,
                                         form=SermonGoldSameForm, min_num=0,
                                         fk_name = "src",
                                         extra=0, can_delete=True, can_order=False)
    GsignFormSet = inlineformset_factory(SermonGold, Signature,
                                         form=SermonGoldSignatureForm, min_num=0,
                                         fk_name = "gold",
                                         extra=0, can_delete=True, can_order=False)
    formset_objects = [{'formsetClass': GlinkFormSet, 'prefix': 'glink', 'readonly': False},
                       {'formsetClass': GsignFormSet, 'prefix': 'gsign', 'readonly': False}]

    def before_delete(self, instance):

        oErr = ErrHandle()
        try:
            # (1) Check if there is an 'equality' link to another SermonGold

            # (2) If there is an alternative SermonGold: change all SermonDescr-to-this-Gold link to the alternative

            # (3) Remove all gold-to-gold links that include this one

            # (4) Remove all links from SermonDescr to this instance of SermonGold

            # All is well
            return True, "" 
        except:
            msg = oErr.get_error_message()
            return False, msg

    def after_new(self, form, instance):
        """Action to be performed after adding a new item"""
        # self.afternewurl = reverse('search_gold')
        return True, "" 

    def add_to_context(self, context, instance):
        """Add to the existing context"""

        # Start a list of related gold sermons
        lst_related = []
        # Do we have an instance?
        if instance != None:
            # There is an instance: get the list of SermonGold items to which I link
            relations = instance.get_relations()
            # Get a form for each of these relations
            for instance_rel in relations:
                linkprefix = "glink-{}".format(instance_rel.id)
                oForm = SermonGoldSameForm(instance=instance_rel, prefix=linkprefix)
                lst_related.append(oForm)

        # Add the list to the context
        context['relations'] = lst_related

        # Process this visit and get the new breadcrumbs object
        context['breadcrumbs'] = process_visit(self.request, "Gold-Sermon details", False)
        context['prevpage'] = get_previous_page(self.request)

        return context


class SermonGoldEdit(PassimDetails):
    """The details of one sermon"""

    model = SermonGold
    mForm = SermonGoldForm
    template_name = 'seeker/sermongold_edit.html'    # Use this for GET and for POST requests
    template_post = 'seeker/sermongold_edit.html'
    prefix = "gold"
    title = "SermonGold" 
    afternewurl = ""

    def before_delete(self, instance):

        oErr = ErrHandle()
        try:
            # (1) Check if there is an 'equality' link to another SermonGold

            # (2) If there is an alternative SermonGold: change all SermonDescr-to-this-Gold link to the alternative

            # (3) Remove all gold-to-gold links that include this one

            # (4) Remove all links from SermonDescr to this instance of SermonGold

            # All is well
            return True, "" 
        except:
            msg = oErr.get_error_message()
            return False, msg

    def after_new(self, form, instance):
        """Action to be performed after adding a new item"""

        # Set the 'afternew' URL
        self.afternewurl = reverse('search_gold')

        # Get the list of signatures
        signatures = form.cleaned_data['signature'].strip()
        if signatures != "":
            siglist = signatures.split(";")
            # Add a signature for each item
            for sigcode in siglist:
                # Make sure starting and tailing spaces are removed
                sigcode = sigcode.strip()
                editype = "cl" if ("CPPM" in sigcode or "CPL" in sigcode) else "gr"
                # Add signature
                obj = Signature(code=sigcode, editype=editype, gold=instance)
                obj.save()

        # Get the list of keywords
        keywords = form.cleaned_data['keyword'].strip()
        if keywords != "":
            kwlist = keywords.split(";")
            # Add a signature for each item
            for kw in kwlist:
                # Make sure starting and tailing spaces are removed
                kw = kw.strip().lower()
                # Check if it is already there
                obj = Keyword.objects.filter(name=kw).first()
                if obj == None:
                    # Add Keyword
                    obj = Keyword(name=kw)
                    obj.save()
                # This is a new instance: add the association with the gold sermon
                objlink = SermonGoldKeyword(gold=instance, keyword=obj)
                objlink.save()

        # Return positively
        return True, "" 

    def add_to_context(self, context, instance):
        """Add to the existing context"""

        # Process this visit and get the new breadcrumbs object
        context['breadcrumbs'] = process_visit(self.request, "Gold-Sermon edit", False)
        context['prevpage'] = get_previous_page(self.request)

        return context


class AuthorDetails(PassimDetails):
    """The details of one author"""

    model = Author
    mForm = AuthorEditForm
    template_name = 'seeker/author_details.html'
    template_post = 'seeker/author_details.html'
    prefix = 'author'
    title = "AuthorDetails"
    afternewurl = ""
    rtype = "html"  # GET provides a HTML form straight away

    def after_new(self, form, instance):
        """Action to be performed after adding a new item"""

        self.afternewurl = reverse('author_search')
        return True, "" 

    def add_to_context(self, context, instance):
        context['is_passim_editor'] = user_is_ingroup(self.request, 'passim_editor')
        # Process this visit and get the new breadcrumbs object
        context['breadcrumbs'] = process_visit(self.request, "Author details", False)
        context['prevpage'] = get_previous_page(self.request)
        return context


class AuthorEdit(PassimDetails):
    """The details of one author"""

    model = Author
    mForm = AuthorEditForm
    template_name = 'seeker/author_edit.html'
    template_post = 'seeker/author_edit.html'
    prefix = 'author'
    title = "AuthorEdit"
    afternewurl = ""
    rtype = "json"

    def after_new(self, form, instance):
        """Action to be performed after adding a new item"""

        self.afternewurl = reverse('author_search')
        return True, "" 

    def add_to_context(self, context, instance):
        context['is_passim_editor'] = user_is_ingroup(self.request, 'passim_editor')
        # Process this visit and get the new breadcrumbs object
        context['breadcrumbs'] = process_visit(self.request, "Author edit", False)
        return context


class AuthorListView(ListView):
    """Listview of authors"""

    model = Author
    paginate_by = 20
    template_name = 'seeker/author_list.html'
    entrycount = 0
    bDoTime = True

    def get_context_data(self, **kwargs):
        # Call the base implementation first to get a context
        context = super(AuthorListView, self).get_context_data(**kwargs)

        # Get parameters for the search
        initial = self.request.GET
        search_form = AuthorSearchForm(initial)

        context['searchform'] = search_form

        # Determine the count 
        context['entrycount'] = self.entrycount # self.get_queryset().count()

        # Set the prefix
        context['app_prefix'] = APP_PREFIX

        # Make sure the paginate-values are available
        context['paginateValues'] = paginateValues

        if 'paginate_by' in initial:
            context['paginateSize'] = int(initial['paginate_by'])
        else:
            context['paginateSize'] = paginateSize

        # Set the title of the application
        context['title'] = "Passim Authors"

        # Check this user: is he allowed to UPLOAD data?
        context['is_authenticated'] = user_is_authenticated(self.request)
        context['is_passim_uploader'] = user_is_ingroup(self.request, 'passim_uploader')
        context['is_passim_editor'] = user_is_ingroup(self.request, 'passim_editor')

        # Process this visit and get the new breadcrumbs object
        context['breadcrumbs'] = process_visit(self.request, "Authors", True)
        context['prevpage'] = get_previous_page(self.request)

        # Return the calculated context
        return context

    def get_paginate_by(self, queryset):
        """
        Paginate by specified value in querystring, or use default class property value.
        """
        return self.request.GET.get('paginate_by', self.paginate_by)
  
    def get_queryset(self):
        # Measure how long it takes
        if self.bDoTime: iStart = get_now_time()

        # Get the parameters passed on with the GET or the POST request
        get = self.request.GET if self.request.method == "GET" else self.request.POST
        get = get.copy()
        self.get = get

        # Fix the sort-order
        get['sortOrder'] = 'name'

        lstQ = []

        # Check for author [name]
        if 'name' in get and get['name'] != '':
            val = adapt_search(get['name'])
            # Search in both the name as well as the abbr field
            lstQ.append(Q(name__iregex=val) | Q(abbr__iregex=val))

        # Calculate the final qs
        qs = Author.objects.filter(*lstQ).order_by('name').distinct()

        # Time measurement
        if self.bDoTime:
            print("AuthorListView get_queryset point 'a': {:.1f}".format( get_now_time() - iStart))
            print("AuthorListView query: {}".format(qs.query))
            iStart = get_now_time()

        # Determine the length
        self.entrycount = len(qs)

        # Time measurement
        if self.bDoTime:
            print("AuthorListView get_queryset point 'b': {:.1f}".format( get_now_time() - iStart))

        # Return the resulting filtered and sorted queryset
        return qs
    

class LibraryListView(ListView):
    """Listview of libraries in countries/cities"""

    model = Library
    paginate_by = 20
    template_name = 'seeker/library_list.html'
    entrycount = 0
    bDoTime = True

    def get_context_data(self, **kwargs):
        # Call the base implementation first to get a context
        context = super(LibraryListView, self).get_context_data(**kwargs)

        # Get parameters for the search
        initial = self.request.GET
        context['searchform'] = LibrarySearchForm(initial)

        # Determine the count 
        context['entrycount'] = self.entrycount # self.get_queryset().count()

        # Set the prefix
        context['app_prefix'] = APP_PREFIX

        # Make sure the paginate-values are available
        context['paginateValues'] = paginateValues

        if 'paginate_by' in initial:
            context['paginateSize'] = int(initial['paginate_by'])
        else:
            context['paginateSize'] = paginateSize

        # Set the title of the application
        context['title'] = "Passim Libraries"

        # Check if user may upload
        context['is_authenticated'] = user_is_authenticated(self.request)
        context['is_passim_uploader'] = user_is_ingroup(self.request, 'passim_uploader')
        context['is_passim_editor'] = user_is_ingroup(self.request, 'passim_editor')

         # Process this visit and get the new breadcrumbs object
        context['breadcrumbs'] = process_visit(self.request, "Libraries", True)
        context['prevpage'] = get_previous_page(self.request)

        # Return the calculated context
        return context

    def get_paginate_by(self, queryset):
        """
        Paginate by specified value in querystring, or use default class property value.
        """
        return self.request.GET.get('paginate_by', self.paginate_by)
  
    def get_queryset(self):
        # Measure how long it takes
        if self.bDoTime: iStart = get_now_time()

        # Get the parameters passed on with the GET or the POST request
        get = self.request.GET if self.request.method == "GET" else self.request.POST
        get = get.copy()
        self.get = get

        # Fix the sort-order
        get['sortOrder'] = 'country'

        lstQ = []

        # Check for the library [country]
        if 'country' in get and get['country'] != '':
            val = adapt_search(get['country'])
            lstQ.append(Q(country__name__iregex=val) )

        # Check for the library [city]
        if 'city' in get and get['city'] != '':
            val = adapt_search(get['city'])
            lstQ.append(Q(city__name__iregex=val))

        # Check for the library [libtype] ('br' or 'pl')
        if 'libtype' in get and get['libtype'] != '':
            val = adapt_search(get['libtype'])
            lstQ.append(Q(libtype__iregex=val))

        # Check for library [name]
        if 'name' in get and get['name'] != '':
            val = adapt_search(get['name'])
            lstQ.append(Q(name__iregex=val))

        # Calculate the final qs
        qs = Library.objects.filter(*lstQ).order_by('country', 'city').distinct()

        # Time measurement
        if self.bDoTime:
            print("LibraryListView get_queryset point 'a': {:.1f}".format( get_now_time() - iStart))
            print("LibraryListView query: {}".format(qs.query))
            iStart = get_now_time()

        # Determine the length
        self.entrycount = len(qs)

        # Time measurement
        if self.bDoTime:
            print("LibraryListView get_queryset point 'b': {:.1f}".format( get_now_time() - iStart))

        # Return the resulting filtered and sorted queryset
        return qs


class LibraryListDownload(BasicPart):
    MainModel = Library
    template_name = "seeker/download_status.html"
    action = "download"
    dtype = "csv"       # downloadtype

    def custom_init(self):
        """Calculate stuff"""
        
        dt = self.qd.get('downloadtype', "")
        if dt != None and dt != '':
            self.dtype = dt

    def add_to_context(self, context):
        # Provide search URL and search name
        #context['search_edit_url'] = reverse("seeker_edit", kwargs={"object_id": self.basket.research.id})
        #context['search_name'] = self.basket.research.name
        return context

    def get_queryset(self, prefix):

        # Get parameters
        country = self.qd.get("country", "")
        city = self.qd.get("city", "")
        library = self.qd.get("library", "")

        # Construct the QS
        lstQ = []
        loc_qs = None

        # if country != "": lstQ.append(Q(country__name__iregex=adapt_search(country)))
        # if city != "": lstQ.append(Q(city__name__iregex=adapt_search(city)))

        if country != "":
            lstQ = []
            lstQ.append(Q(name__iregex=adapt_search(country)))
            lstQ.append(Q(loctype__name="country"))
            country_qs = Location.objects.filter(*lstQ)
            if city == "":
                loc_qs = country_qs
            else:
                lstQ = []
                lstQ.append(Q(name__iregex=adapt_search(city)))
                lstQ.append(Q(loctype__name="city"))
                loc_qs = Location.objects.filter(*lstQ)
        elif city != "":
            lstQ = []
            lstQ.append(Q(name__iregex=adapt_search(city)))
            lstQ.append(Q(loctype__name="city"))
            loc_qs = Location.objects.filter(*lstQ)

        lstQ = []
        if library != "": lstQ.append(Q(name__iregex=adapt_search(library)))
        if loc_qs != None: lstQ.append(Q(location__in=loc_qs))

        qs = Library.objects.filter(*lstQ).order_by('country__name', 'city__name', 'name')

        return qs

    def get_data(self, prefix, dtype):
        """Gather the data as CSV, including a header line and comma-separated"""

        # Initialize
        lData = []
        sData = ""

        if dtype == "json":
            # Loop
            for lib in self.get_queryset(prefix):
                country = ""
                city = ""
                if lib.country: country = lib.country.name
                if lib.city: city = lib.city.name
                row = {"id": lib.id, "country": lib.country.name, "city": lib.city.name, "library": lib.name, "libtype": lib.libtype}
                lData.append(row)
            # convert to string
            sData = json.dumps(lData)
        else:
            # Create CSV string writer
            output = StringIO()
            delimiter = "\t" if dtype == "csv" else ","
            csvwriter = csv.writer(output, delimiter=delimiter, quotechar='"')
            # Headers
            headers = ['id', 'country', 'city', 'library', 'libtype']
            csvwriter.writerow(headers)
            qs = self.get_queryset(prefix)
            if qs.count() > 0:
                # Loop
                for lib in qs:
                    row = [lib.id, lib.get_country_name(), lib.get_city_name(), lib.name, lib.libtype]
                    csvwriter.writerow(row)

            # Convert to string
            sData = output.getvalue()
            output.close()

        return sData


class AuthorListDownload(BasicPart):
    MainModel = Author
    template_name = "seeker/download_status.html"
    action = "download"
    dtype = "csv"       # downloadtype

    def custom_init(self):
        """Calculate stuff"""
        
        dt = self.qd.get('downloadtype', "")
        if dt != None and dt != '':
            self.dtype = dt

    def add_to_context(self, context):
        # Provide search URL and search name
        #context['search_edit_url'] = reverse("seeker_edit", kwargs={"object_id": self.basket.research.id})
        #context['search_name'] = self.basket.research.name
        return context

    def get_queryset(self, prefix):

        # Get parameters
        name = self.qd.get("name", "")

        # Construct the QS
        lstQ = []
        if name != "": lstQ.append(Q(name__iregex=adapt_search(name)))
        qs = Author.objects.filter(*lstQ).order_by('name')

        return qs

    def get_data(self, prefix, dtype):
        """Gather the data as CSV, including a header line and comma-separated"""

        # Initialize
        lData = []
        sData = ""

        if dtype == "json":
            # Loop
            for author in self.get_queryset(prefix):
                row = {"id": author.id, "name": author.name}
                lData.append(row)
            # convert to string
            sData = json.dumps(lData)
        else:
            # Create CSV string writer
            output = StringIO()
            delimiter = "\t" if dtype == "csv" else ","
            csvwriter = csv.writer(output, delimiter=delimiter, quotechar='"')
            # Headers
            headers = ['id', 'name']
            csvwriter.writerow(headers)
            # Loop
            for author in self.get_queryset(prefix):
                row = [author.id, author.name]
                csvwriter.writerow(row)

            # Convert to string
            sData = output.getvalue()
            output.close()

        return sData


class ReportListView(ListView):
    """Listview of reports"""

    model = Report
    paginate_by = 20
    template_name = 'seeker/report_list.html'
    entrycount = 0
    bDoTime = True

    def get_context_data(self, **kwargs):
        # Call the base implementation first to get a context
        context = super(ReportListView, self).get_context_data(**kwargs)

        # Get parameters
        initial = self.request.GET

        # Prepare searching
        #search_form = ReportSearchForm(initial)
        #context['searchform'] = search_form

        # Determine the count 
        context['entrycount'] = self.entrycount # self.get_queryset().count()

        # Set the prefix
        context['app_prefix'] = APP_PREFIX

        # Make sure the paginate-values are available
        context['paginateValues'] = paginateValues

        if 'paginate_by' in initial:
            context['paginateSize'] = int(initial['paginate_by'])
        else:
            context['paginateSize'] = paginateSize

        # Set the title of the application
        context['title'] = "Passim reports"

        # Check if user may upload
        context['is_authenticated'] = user_is_authenticated(self.request)
        context['is_passim_uploader'] = user_is_ingroup(self.request, 'passim_uploader')
        context['is_passim_editor'] = user_is_ingroup(self.request, 'passim_editor')

        # Process this visit and get the new breadcrumbs object
        context['breadcrumbs'] = process_visit(self.request, "Upload reports", True)
        context['prevpage'] = get_previous_page(self.request)

        # Return the calculated context
        return context

    def get_paginate_by(self, queryset):
        """
        Paginate by specified value in querystring, or use default class property value.
        """
        return self.request.GET.get('paginate_by', self.paginate_by)
  
    def get_queryset(self):
        # Get the parameters passed on with the GET or the POST request
        get = self.request.GET if self.request.method == "GET" else self.request.POST
        get = get.copy()
        self.get = get

        # Calculate the final qs
        qs = Report.objects.all().order_by('-created')

        # Determine the length
        self.entrycount = len(qs)

        # Return the resulting filtered and sorted queryset
        return qs


class ReportDetailsView(PassimDetails):
    model = Report
    mForm = ReportEditForm
    template_name = 'seeker/report_details.html'
    prefix = 'report'
    title = "ReportDetails"
    rtype = "html"

    def add_to_context(self, context, instance):
        context['is_passim_editor'] = user_is_ingroup(self.request, 'passim_editor')
        # Process this visit and get the new breadcrumbs object
        context['breadcrumbs'] = process_visit(self.request, "Author edit", False)
        context['prevpage'] = get_previous_page(self.request)
        return context


class ReportDownload(BasicPart):
    MainModel = Report
    template_name = "seeker/download_status.html"
    action = "download"
    dtype = "csv"       # Download Type

    def custom_init(self):
        """Calculate stuff"""
        
        dt = self.qd.get('downloadtype', "")
        if dt != None and dt != '':
            self.dtype = dt

    def get_data(self, prefix, dtype):
        """Gather the data as CSV, including a header line and comma-separated"""

        # Initialize
        lData = []

        # Unpack the report contents
        sData = self.obj.contents

        if dtype == "json":
            # no need to do anything: the information is already in sData
            pass
        else:
            # Convert the JSON to a Python object
            oContents = json.loads(sData)
            # Get the headers and the list
            headers = oContents['headers']

            # Create CSV string writer
            output = StringIO()
            delimiter = "\t" if dtype == "csv" else ","
            csvwriter = csv.writer(output, delimiter=delimiter, quotechar='"')

            # Write Headers
            csvwriter.writerow(headers)

            # Two lists
            todo = [oContents['list'], oContents['read'] ]
            for lst_report in todo:

                # Loop
                for item in lst_report:
                    row = []
                    for key in headers:
                        if key in item:
                            row.append(item[key])
                        else:
                            row.append("")
                    csvwriter.writerow(row)

            # Convert to string
            sData = output.getvalue()
            output.close()

        return sData


