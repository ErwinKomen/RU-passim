"""
Definition of views for the SEEKER app.
"""

from django.contrib import admin
from django.contrib.auth import login, authenticate
from django.contrib.auth.models import Group
from django.core.urlresolvers import reverse
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
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
                                AuthorSearchForm, UploadFileForm, UploadFilesForm, ManuscriptForm, SermonForm
from passim.seeker.models import process_lib_entries, Status, Library, get_now_time, Country, City, Author, Manuscript, User, Group, Origin, SermonMan, SermonDescr

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
    # First trim
    val = val.strip()
    val = '^' + fnmatch.translate(val) + '$'
    return val

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

    ## Create the list of news-items
    #lstQ = []
    #lstQ.append(Q(status='val'))
    #newsitem_list = NewsItem.objects.filter(*lstQ).order_by('-saved', '-created')
    #context['newsitem_list'] = newsitem_list

    # Render and return the page
    return render(request, template_name, context)

def contact(request):
    """Renders the contact page."""
    assert isinstance(request, HttpRequest)
    return render(
        request,
        'contact.html',
        {
            'title':'Contact',
            'message':'Shari Boodts',
            'year':datetime.now().year,
        }
    )

def more(request):
    """Renders the more page."""
    assert isinstance(request, HttpRequest)
    return render(
        request,
        'more.html',
        {
            'title':'More',
            'year':datetime.now().year,
        }
    )

def about(request):
    """Renders the about page."""
    assert isinstance(request, HttpRequest)
    return render(
        request,
        'about.html',
        {
            'title':'About',
            'message':'Radboud University passim utility.',
            'year':datetime.now().year,
        }
    )

def short(request):
    """Renders the page with the short instructions."""

    assert isinstance(request, HttpRequest)
    template = 'short.html'
    context = {'title': 'Short overview',
               'message': 'Radboud University passim short intro',
               'year': datetime.now().year}
    return render(request, template, context)

def nlogin(request):
    """Renders the not-logged-in page."""
    assert isinstance(request, HttpRequest)
    context =  {    'title':'Not logged in', 
                    'message':'Radboud University passim utility.',
                    'year':datetime.now().year,}
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
        city = request.GET.get("city", "")
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
        city = request.GET.get("city", "")
        lib = request.GET.get("library", "")

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
    if request.user.is_authenticated and request.method == 'POST':

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
            # Get the contents of the imported file
            files = request.FILES.getlist('files_field')
            if files != None:
                for data_file in files:
                    filename = data_file.name

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
                            oResult = Manuscript.read_ecodex(username, data_file, filename, arErr)

                        # Determine a status code
                        statuscode = "error" if oResult == None or oResult['status'] == "error" else "completed"
                        if oResult == None:
                            arErr.append("There was an error. No manuscripts have been added")
                        else:
                            lResults.append(oResult)
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
        data['html'] = 'Only use POST and make sure you are logged in'
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
            self.object = self.get_object()
            context = self.get_context_data(object=self.object)
            # Possibly indicate form errors
            if 'errors' in context:
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

        # Get a form for this manuscript
        if self.request.method == "POST":
            # Do we have an existing object or are we creating?
            if instance == None:
                # Saving a new item
                frm = ManuscriptForm(initial, prefix="manu")
                # self_formset = self.SermoFormset(initial, prefix="sermo")
            else:
                # Editing an existing one
                frm = ManuscriptForm(initial, prefix="manu", instance=instance)
                # self_formset = self.SermoFormset(initial, prefix="sermo", instance=instance)
            # Both cases: validation and saving
            if frm.is_valid():
                # The form is valid - do a preliminary saving
                instance = frm.save(commit=False)
                # Now save it for real
                instance.save()
                ## Only now continue with the formset
                #if self_formset.is_valid():
                #    # The formset is valid: walk all the forms
                #    for fSermo in self_formset:
                #        # Check if the sermon form is valid
                #        if fSermo.is_valid():
                #            # Save it and get the instance
                #            sermon = fSermo.save()
                #            # Check link between the sermon and the manuscript
                #            link = SermonMan.objects.filter(sermon=sermon, manuscript=instance).first()
                #            if link == None:
                #                # Add this link
                #                link = SermonMan(sermon=sermon, manuscript=instance)
                #                link.save()
            else:
                # We need to pass on to the user that there are errors
                context['errors'] = frm.errors
                
        else:
            # Get the form for the manuscript
            frm = ManuscriptForm(instance=instance, prefix="manu")
            ## Get all the sermondescr object belonging to this Manuscript
            #qs = instance.sermons.all()
            ##qs_link = instance.sermons.all().values_list('sermon', flat=True)
            ##qs = SermonDescr.objects.filter(id__in=qs_link)
            ## Get the formset for the sermons of this manuscript
            #if qs == None:
            #    # Need to provide an EMPTY formset. Is this the way??
            #    sermo_formset = self.SermoFormset(prefix='sermo')
            #else:
            #    sermo_formset = self.SermoFormset(prefix='sermo', queryset=qs)

        # Put the form and the formset in the context
        context['manuForm'] = frm
        # context['sermo_formset'] = sermo_formset

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

        self.bHasFormset = (len(self.qd) > 0)

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
                        if 'signature' in oFields and oFields['signature'] != "": 
                            val = adapt_search(oFields['signature'])
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
                qs = Manuscript.objects.all().order_by('name')
            elif len(lstQ) == 1:
                # criteria = reduce(operator.or_, lstQ)
                qs = Manuscript.objects.filter(*lstQ).order_by('name').distinct()
            else:
                criteria = reduce(operator.or_, lstQ)
                qs = Manuscript.objects.filter(criteria).order_by('name').distinct()
        else:
            # Just show everything
            qs = Manuscript.objects.all().order_by('name')

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

        # Get a form for this manuscript
        if self.request.method == "POST":
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
                
        else:
            # Check if this is asking for a new form
            if instance == None:
                # Get the form for the manuscript
                frm = SermonForm(prefix="sermo")
            else:
                # Get the form for the manuscript
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
            lstQ.append(Q(name__iregex=val))

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


class BasicPart(View):
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
    
    def post(self, request, object_id=None):
        # A POST request means we are trying to SAVE something
        self.initializations(request, object_id)

        # Explicitly set the status to OK
        self.data['status'] = "ok"

        if self.checkAuthentication(request):
            # Build the context
            context = dict(object_id = object_id, savedate=None)
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
                        else:
                            self.arErr.append(formObj['forminstance'].errors)
                            self.form_validated = False

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
                                # Make sure all changes are saved in one database-go
                                with transaction.atomic():
                                    # Walk all the forms in the formset
                                    for form in formset:
                                        # At least check for validity
                                        if form.is_valid() and self.is_custom_valid(prefix, form):
                                            # Should we delete?
                                            if form.cleaned_data['DELETE']:
                                                # Delete this one
                                                form.instance.delete()
                                                # NOTE: the template knows this one is deleted by looking at form.DELETE
                                                # form.delete()
                                            else:
                                                # Check if anything has changed so far
                                                has_changed = form.has_changed()
                                                # Save it preliminarily
                                                instance = form.save(commit=False)
                                                # Any actions before saving
                                                if self.before_save(prefix, request, instance, form):
                                                    has_changed = True
                                                # Save this construction
                                                if has_changed: 
                                                    # Save the instance
                                                    instance.save()
                                                    # Adapt the last save time
                                                    context['savedate']="saved at {}".format(datetime.now().strftime("%X"))
                                                    # Store the instance id in the data
                                                    self.data[prefix + '_instanceid'] = instance.id
                                        else:
                                            if len(form.errors) > 0:
                                                self.arErr.append(form.errors)
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
            else:
                # In this case reset the errors - they should be shown within the template
                self.data['html'] = render_to_string(self.template_name, context, request)
            # At any rate: empty the error basket
            self.arErr = []
            error_list = []

        else:
            self.data['html'] = "Please log in before continuing"

        # Return the information
        return JsonResponse(self.data)
        
    def get(self, request, object_id=None): 
        self.data['status'] = 'ok'
        # Perform the initializations that need to be made anyway
        self.initializations(request, object_id)
        if self.checkAuthentication(request):
            context = dict(object_id = object_id, savedate=None)
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

