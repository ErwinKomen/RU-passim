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

from passim.settings import APP_PREFIX
from passim.utils import ErrHandle
from passim.seeker.forms import SearchCollectionForm, SearchManuscriptForm, SearchSermonForm, LibrarySearchForm, SignUpForm, \
                                AuthorSearchForm, UploadFileForm, UploadFilesForm, ManuscriptForm, SermonForm, SermonGoldForm, \
                                SelectGoldForm, SermonGoldSameForm, SermonGoldSignatureForm, AuthorEditForm, \
                                SermonGoldEditionForm, SermonGoldFtextlinkForm
from passim.seeker.models import process_lib_entries, Status, Library, get_now_time, Country, City, Author, Manuscript, \
    User, Group, Origin, SermonMan, SermonDescr, SermonGold,  Nickname, NewsItem, SourceInfo, SermonGoldSame, Signature, Edition, Ftextlink

import fnmatch
import sys
import base64
import json
import csv
import requests
import demjson
import openpyxl
from openpyxl.utils.cell import get_column_letter
from io import StringIO

# Some constants that can be used
paginateSize = 20
paginateValues = (100, 50, 20, 10, 5, 2, 1, )

# Global debugging 
bDebug = False

cnrs_url = "http://medium-avance.irht.cnrs.fr"

def adapt_search(val):
    if val == None: return None
    # First trim
    val = val.strip()
    val = '^' + fnmatch.translate(val) + '$'
    return val

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

def home(request):
    """Renders the home page."""

    assert isinstance(request, HttpRequest)
    # Specify the template
    template_name = 'index.html'
    # Define the initial context
    context =  {'title':'RU-passim',
                'year':datetime.now().year,
                'pfx': APP_PREFIX,
                'site_url': admin.site.site_url}
    context['is_passim_uploader'] = user_is_ingroup(request, 'passim_uploader')

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
                'year':datetime.now().year,
                'pfx': APP_PREFIX,
                'site_url': admin.site.site_url}
    context['is_passim_uploader'] = user_is_ingroup(request, 'passim_uploader')
    return render(request,'contact.html', context)

def more(request):
    """Renders the more page."""
    assert isinstance(request, HttpRequest)
    context =  {'title':'More',
                'year':datetime.now().year,
                'pfx': APP_PREFIX,
                'site_url': admin.site.site_url}
    context['is_passim_uploader'] = user_is_ingroup(request, 'passim_uploader')
    return render(request,'more.html', context)

def bibliography(request):
    """Renders the more page."""
    assert isinstance(request, HttpRequest)
    context =  {'title':'Bibliography',
                'year':datetime.now().year,
                'pfx': APP_PREFIX,
                'site_url': admin.site.site_url}
    context['is_passim_uploader'] = user_is_ingroup(request, 'passim_uploader')
    return render(request,'bibliography.html', context)

def about(request):
    """Renders the about page."""
    assert isinstance(request, HttpRequest)
    context =  {'title':'About',
                'message':'Radboud University passim utility.',
                'year':datetime.now().year,
                'pfx': APP_PREFIX,
                'site_url': admin.site.site_url}
    context['is_passim_uploader'] = user_is_ingroup(request, 'passim_uploader')
    return render(request,'about.html', context)

def short(request):
    """Renders the page with the short instructions."""

    assert isinstance(request, HttpRequest)
    template = 'short.html'
    context = {'title': 'Short overview',
               'message': 'Radboud University passim short intro',
               'year': datetime.now().year}
    context['is_passim_uploader'] = user_is_ingroup(request, 'passim_uploader')
    return render(request, template, context)

def nlogin(request):
    """Renders the not-logged-in page."""
    assert isinstance(request, HttpRequest)
    context =  {    'title':'Not logged in', 
                    'message':'Radboud University passim utility.',
                    'year':datetime.now().year,}
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

@csrf_exempt
def get_countries(request):
    """Get a list of countries for autocomplete"""

    data = 'fail'
    if request.is_ajax():
        sName = request.GET.get('country', '')
        if sName == "": sName = request.GET.get('country_ta', "")
        lstQ = []
        lstQ.append(Q(name__icontains=sName))
        countries = Country.objects.filter(*lstQ).order_by('name')
        results = []
        for co in countries:
            # co_json = {'combi': "{}: {}".format(co.id, co.name)}
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
    if request.is_ajax():
        country = request.GET.get('country', "")
        if country == "": country = request.GET.get('country_ta', "")
        city = request.GET.get("city", "")
        if city == "": city = request.GET.get('city_ta', "")
        lstQ = []
        lstQ.append(Q(country__name__icontains=country))
        lstQ.append(Q(name__icontains=city))
        countries = City.objects.filter(*lstQ).order_by('name')
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
def get_libraries(request):
    """Get a list of libraries for autocomplete"""

    data = 'fail'
    if request.is_ajax():
        country = request.GET.get('country', "")
        if country == "": country = request.GET.get('country_ta', "")
        city = request.GET.get("city", "")
        if city == "": city = request.GET.get('city_ta', "")
        lib = request.GET.get("library", "")
        if lib == "": lib = request.GET.get('libname_ta', "")

        lstQ = []
        if country != "": lstQ.append(Q(country__name__icontains=country))
        if city != "": lstQ.append(Q(city__name__icontains=city))
        if lib != "": lstQ.append(Q(name__icontains=lib))
        countries = Library.objects.filter(*lstQ).order_by('name')
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

@csrf_exempt
def get_authors(request):
    """Get a list of authors for autocomplete"""

    data = 'fail'
    if request.is_ajax():
        author = request.GET.get("name", "")
        lstQ = []
        lstQ.append(Q(name__icontains=author))
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

    oErr = ErrHandle
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
def get_incipits(request):
    """Get a list of incipits for autocomplete"""

    oErr = ErrHandle()
    try:
        data = 'fail'
        if request.is_ajax():
            author = request.GET.get("name", "")
            lstQ = []
            lstQ.append(Q(incipit__icontains=author))
            items = SermonGold.objects.filter(*lstQ).values("incipit").distinct().all().order_by('incipit')
            # items = SermonGold.objects.order_by("incipit").distinct()
            # items = SermonGold.objects.filter(*lstQ).order_by('incipit').distinct()
            results = []
            for idx, co in enumerate(items):
                co_json = {'name': co['incipit'], 'id': idx }
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
def get_explicits(request):
    """Get a list of explicits for autocomplete"""

    oErr = ErrHandle()
    try:
        data = 'fail'
        if request.is_ajax():
            author = request.GET.get("name", "")
            lstQ = []
            lstQ.append(Q(explicit__icontains=author))
            items = SermonGold.objects.filter(*lstQ).values("explicit").distinct().all().order_by('explicit')
            # items = SermonGold.objects.order_by("explicit").distinct()
            # items = SermonGold.objects.filter(*lstQ).order_by('explicit').distinct()
            results = []
            for idx, co in enumerate(items):
                co_json = {'name': co['explicit'], 'id': idx }
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
def get_signatures(request):
    """Get a list of signature codes for autocomplete"""

    oErr = ErrHandle
    try:
        data = 'fail'
        if request.is_ajax():
            author = request.GET.get("name", "")
            lstQ = []
            lstQ.append(Q(code__icontains=author))
            items = Signature.objects.order_by("code").distinct()
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

    oErr = ErrHandle
    try:
        data = 'fail'
        if request.is_ajax():
            author = request.GET.get("name", "")
            lstQ = []
            lstQ.append(Q(name__icontains=author))
            items = Edition.objects.order_by("name").distinct()
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


        form = UploadFilesForm(request.POST, request.FILES)
        lResults = []
        if form.is_valid():
            # NOTE: from here a breakpoint may be inserted!
            print('import_ecodex: valid form')

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

                        # Further processing depends on the extension
                        oResult = None
                        if extension == "xml":
                            # This is an XML file
                            oResult = Manuscript.read_ecodex(username, data_file, filename, arErr, source=source)

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
                            oResult = SermonGold.read_gold(username, data_file, filename, arErr)

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
                context['savedate']="reviewed at {}".format(datetime.now().strftime("%X"))

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
                            if self.before_save(prefix, request, instance=instance): bNeedSaving = True
                            if formObj['forminstance'].instance.id == None: bNeedSaving = True
                            if bNeedSaving:
                                # Perform the saving
                                instance.save()
                                # Set the context
                                context['savedate']="saved at {}".format(datetime.now().strftime("%X"))
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
                                                    context['savedate']="saved at {}".format(datetime.now().strftime("%X"))
                                                    # Store the instance id in the data
                                                    self.data[prefix + '_instanceid'] = sub_instance.id
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
                    sDbName = "passim_libraries.{}".format(self.dtype)
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

            # Allow user to add to the context
            context = self.add_to_context(context)

            # Make sure we have a list of any errors
            error_list = [str(item) for item in self.arErr]
            context['error_list'] = error_list
            context['errors'] = self.arErr
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
    title = ""              # The title to be passedon with the context
    rtype = "json"          # JSON response (alternative: html)
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
            self.object = self.get_object()
            # NOTE: if the object doesn't exist, we will NOT get an error here


    def before_delete(self, instance):
        """Anything that needs doing before deleting [instance] """
        return True, "" 

    def after_new(self, instance):
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
        id = "n" if instance == None else instance.id
        prefix = "{}-{}".format(self.prefix, id)

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
                bResult, msg = self.after_new(instance)
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

        # Check this user: is he allowed to UPLOAD data?
        context['authenticated'] = user_is_authenticated(self.request)
        context['is_passim_uploader'] = user_is_ingroup(self.request, 'passim_uploader')
        context['is_passim_editor'] = user_is_ingroup(self.request, 'passim_editor')

        # Possibly add to context by the calling function
        context = self.add_to_context(context, instance)

        # Return the calculated context
        return context


class ManuscriptDetailsView(DetailView):
    """The details of one manuscript"""

    model = Manuscript
    template_name = 'seeker/manuscript_details.html'    # Use this for GET requests
    template_post = 'seeker/manuscript_info.html'       # Use this for POST requests
    # Define a formset for the sermons that are part of a manuscript
    # SermoFormset = modelformset_factory(SermonDescr, form=SermonForm, extra=0)

    def get(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            # Do not allow to get a good response
            response = nlogin(request)
        else:
            # Determine the object and the context
            if not 'pk' in kwargs or kwargs['pk'] == None:
                # This is a NEW sermon
                self.object = None
            else:
                self.object = self.get_object()
            context = self.get_context_data(object=self.object)
            response = self.render_to_response(context)
            #response.content = treat_bom(response.rendered_content)
        return response

    def post(self, request, *args, **kwargs):
        # Initialisation
        data = {'status': 'ok', 'html': '', 'statuscode': ''}
        # Make sure only POSTS get through that are authorized
        if request.user.is_authenticated:
            # Determine the object and the context
            if not 'pk' in kwargs or kwargs['pk'] == None:
                # This is a NEW sermon
                self.object = None
            else:
                self.object = self.get_object()
            context = self.get_context_data(object=self.object)
            # Possibly indicate form errors
            # NOTE: errors is a dictionary itself...
            if 'errors' in context and len(context['errors']) > 0:
                data['status'] = "error"
                data['msg'] = context['errors']
            # response = self.render_to_response(self.template_post, context)
            data['html'] = render_to_string(self.template_post, context, request)
        else:
            data['html'] = "(No authorization)"
            data['status'] = "error"

        # Return the response
        return JsonResponse(data)

    def get_context_data(self, **kwargs):
        # Get the current context
        context = super(ManuscriptDetailsView, self).get_context_data(**kwargs)

        # Get the parameters passed on with the GET or the POST request
        get = self.request.GET if self.request.method == "GET" else self.request.POST
        initial = get.copy()
        self.qd = initial

        self.bHasFormset = (len(self.qd) > 0)

        # Set the title of the application
        context['title'] = "Manuscript"

        # Get the instance
        instance = self.object
        bNew = False

        # Get a form for this manuscript
        if self.request.method == "POST":
            # Do we have an existing object or are we creating?
            if instance == None:
                # Saving a new item
                frm = ManuscriptForm(initial, prefix="manu")
                bNew = True
            else:
                # Editing an existing one
                frm = ManuscriptForm(initial, prefix="manu", instance=instance)

            # Both cases: validation and saving
            if frm.is_valid():
                # The form is valid - do a preliminary saving
                instance = frm.save(commit=False)
                # Check if a new 'Origin' has been added
                if 'origname_ta' in frm.changed_data:

                    # TODO: check if this is not already taken care of...

                    # Get its value
                    sOrigin = frm.cleaned_data['origname_ta']
                    # Check if it is already in the Nicknames
                    origin = Origin.find_or_create(sOrigin)
                    if instance.origin != origin:
                        # Add it
                        instance.origin = origin
                # Now save it for real
                instance.save()
            else:
                # We need to pass on to the user that there are errors
                context['errors'] = frm.errors

            # Check if this is a new one
            if bNew:
                # Put anything here that needs handling if it is a new manuscript instance
                pass
                
        else:
            # Check if this is asking for a new form
            if instance == None:
                # Get the form for the manuscript
                frm = ManuscriptForm(prefix="manu")
            else:
                # Get the form for the manuscript
                frm = ManuscriptForm(instance=instance, prefix="manu")

        # Put the form and the formset in the context
        context['manuForm'] = frm
        
        sermon_list = []
        maxdepth = 0
        if instance != None:
            # Create a well sorted list of sermons
            qs = instance.sermons.filter(order__gte=0).order_by('order')
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
        context['isnew'] = bNew

        # Check this user: is he allowed to UPLOAD data?
        context['authenticated'] = user_is_authenticated(self.request)
        context['is_passim_uploader'] = user_is_ingroup(self.request, 'passim_uploader')
        context['is_passim_editor'] = user_is_ingroup(self.request, 'passim_editor')

        # Return the calculated context
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

    def get_context_data(self, **kwargs):
        # Call the base implementation first to get a context
        context = super(SermonGoldListView, self).get_context_data(**kwargs)

        # Get parameters for the search
        initial = self.request.GET

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
                    lstQ.append(Q(incipit__iregex=val))

                # Check for explicit string
                if 'explicit' in oFields and oFields['explicit'] != "" and oFields['explicit'] != None: 
                    val = adapt_search(oFields['explicit'])
                    lstQ.append(Q(explicit__iregex=val))

                # Check for SermonGold [signature]
                if 'signature' in oFields and oFields['signature'] != "" and oFields['signature'] != None: 
                    val = adapt_search(oFields['signature'])
                    lstQ.append(Q(goldsignatures__code__iregex=val))

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

        # Set the sort order
        #qs = qs.order_by('author__name',
        #                 'signatures',
        #                 'incipit', 
        #                 'explicit')

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
    # One form is attached to this 
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
        source_id = None
        if 'source_id' in self.qd:
            source_id = self.qd['source_id']
        context['source_id'] = source_id
        
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
            if source_id != None:
                qs = qs.exclude(id=source_id)

            # Sort the python way
            qs = sorted(qs, key=lambda x: x.get_sermon_string())
            ## Make sure sorting is done correctly
            #qs = qs.order_by('signature__code', 'author__name', 'incipit', 'explicit')
        # Add the result to the context
        context['results'] = qs
        context['authenticated'] = user_is_authenticated(self.request)
        context['is_passim_uploader'] = user_is_ingroup(self.request, 'passim_uploader')
        context['is_passim_editor'] = user_is_ingroup(self.request, 'passim_editor')

        # Return the updated context
        return context


class SermonDetailsView(DetailView):
    """The details of one sermon"""

    model = SermonDescr
    template_name = 'seeker/sermon_info.html'    # Use this for GET and for POST requests
    template_post = 'seeker/sermon_view.html'

    def get(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            # Do not allow to get a good response
            response = nlogin(request)
        else:
            if not 'pk' in kwargs or kwargs['pk'] == None:
                self.object = None
            else:
                self.object = self.get_object()
            context = self.get_context_data(object=self.object)
            response = self.render_to_response(context)
            #response.content = treat_bom(response.rendered_content)
        return response

    def post(self, request, *args, **kwargs):
        # Initialisation
        data = {'status': 'ok', 'html': '', 'statuscode': ''}
        # Make sure only POSTS get through that are authorized
        if request.user.is_authenticated:
            # Determine the object and the context
            if not 'pk' in kwargs or kwargs['pk'] == None:
                # This is a NEW sermon
                self.object = None
            else:
                self.object = self.get_object()
            context = self.get_context_data(object=self.object)
            # Possibly indicate form errors
            # NOTE: errors is a dictionary itself...
            if 'errors' in context and len(context['errors']) > 0:
                data['status'] = "error"
                data['msg'] = context['errors']
            # response = self.render_to_response(self.template_post, context)
            data['html'] = render_to_string(self.template_post, context, request)
        else:
            data['html'] = "(No authorization)"
            data['status'] = "error"

        # Return the response
        return JsonResponse(data)

    def get_context_data(self, **kwargs):
        # Get the current context
        context = super(SermonDetailsView, self).get_context_data(**kwargs)

        # Get the parameters passed on with the GET or the POST request
        get = self.request.GET if self.request.method == "GET" else self.request.POST
        initial = get.copy()
        self.qd = initial

        self.bHasFormInfo = (len(self.qd) > 0)

        # Set the title of the application
        context['title'] = "Sermon"

        # Get the instance
        instance = self.object
        bNew = False

        # Check if this is a POST or a GET request
        if self.request.method == "POST":
            # Determine what the action is (if specified)
            action = ""
            if 'action' in initial: action = initial['action']
            if action == "delete":
                # The user wants to delete this item
                if 'manuscript_id' in initial:
                    # It is there, so we can add it
                    manuscript = Manuscript.objects.filter(id=initial['manuscript_id']).first()
                    if manuscript != None:
                        # Remove from the SermonMan
                        obj = SermonMan.objects.filter(sermon=instance, manuscript=manuscript).first()
                        if obj != None:
                            obj.delete()
                    # Now remove the sermon itself
                    instance.delete()
                else:
                    # Create an errors object
                    context['errors'] = [ "Trying to remove a sermon that is not tied to a manuscript" ]
                # And return the complied context
                return context
            
            # All other actions just mean: edit or new and send back

            # Do we have an existing object or are we creating?
            if instance == None:
                # Saving a new item
                frm = SermonForm(initial, prefix="sermo")
                bNew = True
            else:
                # Editing an existing one
                frm = SermonForm(initial, prefix="sermo", instance=instance)
            # Both cases: validation and saving
            if frm.is_valid():
                # The form is valid - do a preliminary saving
                instance = frm.save(commit=False)

                # Check what has been added
                if 'nickname_ta' in frm.changed_data:
                    # Get its value
                    sNickname = frm.cleaned_data['nickname_ta']
                    # Check if it is already in the Nicknames
                    nickname = Nickname.find_or_create(sNickname)
                    if instance.nickname != nickname:
                        # Add it
                        instance.nickname = nickname
                # Now save it for real
                instance.save()
            else:
                # We need to pass on to the user that there are errors
                context['errors'] = frm.errors
            # Check if this is a new one
            if bNew:
                # This is a new one, so it should be coupled to the correct manuscript
                if 'manuscript_id' in initial:
                    # It is there, so we can add it
                    manuscript = Manuscript.objects.filter(id=initial['manuscript_id']).first()
                    if manuscript != None:
                        # Add to the SermonMan
                        obj = SermonMan(sermon=instance, manuscript=manuscript)
                        obj.save()
                        # Calculate how many sermons there are
                        sermon_count = manuscript.sermons.all().count()
                        # Make sure the new sermon gets changed
                        instance.order = sermon_count
                        instance.save()
                
        else:
            # Check if this is asking for a new form
            if instance == None:
                # Get the form for the sermon
                frm = SermonForm(prefix="sermo")
            else:
                # Get the form for the sermon
                frm = SermonForm(instance=instance, prefix="sermo")

        # Put the form and the formset in the context
        context['sermoForm'] = frm
        context['msitem'] = instance

        # Check this user: is he allowed to UPLOAD data?
        context['authenticated'] = user_is_authenticated(self.request)
        context['is_passim_uploader'] = user_is_ingroup(self.request, 'passim_uploader')
        context['is_passim_editor'] = user_is_ingroup(self.request, 'passim_editor')

        # Return the calculated context
        return context


class SermonGoldSameDetailsView(BasicPart):
    """The details of one gold-to-gold link"""

    MainModel = SermonGoldSame
    template_name = 'seeker/sermongoldlink_info.html'    # Use this for GET and for POST requests
    title = "SermonGoldLink"
    form_objects = [{'form': SermonGoldSameForm, 'prefix': 'glink', 'readonly': False},
                    {'form': SelectGoldForm, 'prefix': 'gsel', 'readonly': True}]

    def get_instance(self, prefix):
        instance = None
        if prefix == "glink":
            # The instance is the SermonGoldSame instance, the link description
            instance = self.obj
        elif prefix == "gsel":
            # The instance is where the SermonGoldSame instance is pointing to, the dst
            instance = self.obj.dst
        return instance

    def add_to_context(self, context):

        # Check this user: is he allowed to UPLOAD data?
        context['authenticated'] = user_is_authenticated(self.request)
        context['is_passim_uploader'] = user_is_ingroup(self.request, 'passim_uploader')
        context['is_passim_editor'] = user_is_ingroup(self.request, 'passim_editor')
        context['results'] = []

        # Is this a request for deletion?
        if self.action == "delete":
            # Delete the current object
            if self.obj != None:
                self.obj.delete()
                deletestatus = True
            else:
                deletestatus = False
            context['deleted'] = deletestatus

        # Return the adapted context
        return context


class SermonGoldLinkset(BasicPart):
    """The set of links from one gold sermon"""

    MainModel = SermonGold
    template_name = 'seeker/sermongold_linkset.html'
    title = "SermonGoldLinkset"
    GlinkFormSet = inlineformset_factory(SermonGold, SermonGoldSame,
                                         form=SermonGoldSameForm, min_num=0,
                                         fk_name = "src",
                                         extra=0, can_delete=True, can_order=False)
    formset_objects = [{'formsetClass': GlinkFormSet, 'prefix': 'glink', 'readonly': False}]


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

    def after_new(self, instance):
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
        context['is_passim_editor'] = user_is_ingroup(self.request, 'passim_editor')

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

    def after_new(self, instance):
        """Action to be performed after adding a new item"""
        self.afternewurl = reverse('search_gold')
        return True, "" 

    def add_to_context(self, context, instance):
        """Add to the existing context"""

        # This is not longer needed, since it is handled by SermonGoldLinkset

        ## Start a list of related gold sermons
        #lst_related = []
        ## Do we have an instance?
        #if instance != None:
        #    # There is an instance: get the list of SermonGold items to which I link
        #    relations = instance.get_relations()
        #    # Get a form for each of these relations
        #    for instance_rel in relations:
        #        linkprefix = "glink-{}".format(instance_rel.id)
        #        oForm = SermonGoldSameForm(instance=instance_rel, prefix=linkprefix)
        #        lst_related.append(oForm)

        ## Add the list to the context
        #context['relations'] = lst_related

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

    def after_new(self, instance):
        """Action to be performed after adding a new item"""

        self.afternewurl = reverse('author_search')
        return True, "" 

    def add_to_context(self, context, instance):
        context['is_passim_editor'] = user_is_ingroup(self.request, 'passim_editor')
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

    def after_new(self, instance):
        """Action to be performed after adding a new item"""

        self.afternewurl = reverse('author_search')
        return True, "" 

    def add_to_context(self, context, instance):
        context['is_passim_editor'] = user_is_ingroup(self.request, 'passim_editor')
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
        search_form = LibrarySearchForm(initial)

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
        context['title'] = "Passim Libraries"

        # Check if user may upload
        context['is_authenticated'] = user_is_authenticated(self.request)
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
        if country != "": lstQ.append(Q(country__name__iregex=adapt_search(country)))
        if city != "": lstQ.append(Q(city__name__iregex=adapt_search(city)))
        if library != "": lstQ.append(Q(name__iregex=adapt_search(library)))
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
            # Loop
            for lib in self.get_queryset(prefix):
                row = [lib.id, lib.country.name, lib.city.name, lib.name, lib.libtype]
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

