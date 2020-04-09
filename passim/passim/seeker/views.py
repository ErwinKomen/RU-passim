"""
Definition of views for the SEEKER app.
"""

from django.apps import apps
from django.contrib import admin
from django.contrib.auth import login, authenticate
from django.contrib.auth.models import Group
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
from pyzotero import zotero
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

# ======== imports for PDF creation ==========
import io  
from markdown import markdown 
from reportlab.lib.units import inch 
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle 
from reportlab.lib.units import inch 
from reportlab.pdfgen import canvas 
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, ListFlowable, ListItem, Frame, PageBreak   
from reportlab.rl_config import defaultPageSize  

# ======= imports from my own application ======
from passim.settings import APP_PREFIX, MEDIA_DIR
from passim.utils import ErrHandle
from passim.seeker.forms import SearchCollectionForm, SearchManuscriptForm, SearchManuForm, SearchSermonForm, LibrarySearchForm, SignUpForm, \
                                AuthorSearchForm, UploadFileForm, UploadFilesForm, ManuscriptForm, SermonForm, SermonGoldForm, \
                                SelectGoldForm, SermonGoldSameForm, SermonGoldSignatureForm, AuthorEditForm, \
                                SermonGoldEditionForm, SermonGoldFtextlinkForm, SermonDescrGoldForm, SearchUrlForm, \
                                SermonDescrSignatureForm, SermonGoldKeywordForm, SermonGoldLitrefForm, EqualGoldLinkForm, EqualGoldForm, \
                                ReportEditForm, SourceEditForm, ManuscriptProvForm, LocationForm, LocationRelForm, OriginForm, \
                                LibraryForm, ManuscriptExtForm, ManuscriptLitrefForm, SermonDescrKeywordForm, KeywordForm, \
                                ManuscriptKeywordForm, DaterangeForm, ProjectForm, SermonDescrCollectionForm, CollectionForm, \
                                SuperSermonGoldForm, SermonGoldCollectionForm, ManuscriptCollectionForm, \
                                SuperSermonGoldCollectionForm
from passim.seeker.models import get_crpp_date, get_current_datetime, process_lib_entries, adapt_search, get_searchable, get_now_time, \
    add_gold2equal, add_equal2equal, add_ssg_equal2equal, Information, Country, City, Author, Manuscript, \
    User, Group, Origin, SermonDescr, SermonGold, SermonDescrKeyword, Nickname, NewsItem, SourceInfo, SermonGoldSame, SermonGoldKeyword, Signature, Ftextlink, ManuscriptExt, \
    ManuscriptKeyword, Action, EqualGold, EqualGoldLink, Location, LocationName, LocationIdentifier, LocationRelation, LocationType, ProvenanceMan, Provenance, Daterange, \
    Project, Basket, BasketMan, BasketGold, BasketSuper, Litref, LitrefMan, LitrefSG, EdirefSG, Report, SermonDescrGold, Visit, Profile, Keyword, SermonSignature, Status, Library, Collection, CollectionSerm, \
    CollectionMan, CollectionSuper, CollectionGold, LINK_EQUAL, LINK_PRT
from passim.reader.views import reader_uploads

# ======= from RU-Basic ========================
from passim.basic.views import BasicList, BasicDetails


# Some constants that can be used
paginateSize = 20
paginateSelect = 15
paginateValues = (100, 50, 20, 10, 5, 2, 1, )

# Global debugging 
bDebug = False

cnrs_url = "http://medium-avance.irht.cnrs.fr"

def get_application_name():
    """Try to get the name of this application"""

    # Walk through all the installed apps
    for app in apps.get_app_configs():
        # Check if this is a site-package
        if "site-package" not in app.path:
            # Get the name of this app
            name = app.name
            # Take the first part before the dot
            project_name = name.split(".")[0]
            return project_name
    return "unknown"
# Provide application-specific information
PROJECT_NAME = get_application_name()
app_uploader = "{}_uploader".format(PROJECT_NAME.lower())
app_editor = "{}_editor".format(PROJECT_NAME.lower())


def treat_bom(sHtml):
    """REmove the BOM marker except at the beginning of the string"""

    # Check if it is in the beginning
    bStartsWithBom = sHtml.startswith(u'\ufeff')
    # Remove everywhere
    sHtml = sHtml.replace(u'\ufeff', '')
    # Return what we have
    return sHtml

def adapt_m2m(cls, instance, field1, qs, field2, extra = [], related_is_through = False):
    """Adapt the 'field' of 'instance' to contain only the items in 'qs'"""

    errHandle = ErrHandle()
    try:
        # Get current associations
        lstQ = [Q(**{field1: instance})]
        through_qs = cls.objects.filter(*lstQ)
        if related_is_through:
            related_qs = through_qs
        else:
            related_qs = [getattr(x, field2) for x in through_qs]
        # make sure all items in [qs] are associated
        for obj in qs:
            if obj not in related_qs:
                # Add the association
                args = {field1: instance}
                if related_is_through:
                    args[field2] = getattr(obj, field2)
                else:
                    args[field2] = obj
                for item in extra:
                    # Copy the field with this name from [obj] to 
                    args[item] = getattr(obj, item)
                # cls.objects.create(**{field1: instance, field2: obj})
                cls.objects.create(**args)
        # Remove from [cls] all associations that are not in [qs]
        for item in through_qs:
            if related_is_through:
                obj = item
            else:
                obj = getattr(item, field2)
            if obj not in qs:
                # Remove this item
                item.delete()
        # Return okay
        return True
    except:
        msg = errHandle.get_error_message()
        return False

def adapt_m2o(cls, instance, field, qs, link_to_obj = None, **kwargs):
    """Adapt the instances of [cls] pointing to [instance] with [field] to only include [qs] """

    errHandle = ErrHandle()
    try:
        # Get all the [cls] items currently linking to [instance]
        lstQ = [Q(**{field: instance})]
        linked_qs = cls.objects.filter(*lstQ)
        if link_to_obj != None:
            linked_through = [getattr(x, link_to_obj) for x in linked_qs]
        # make sure all items in [qs] are linked to [instance]
        for obj in qs:
            if (obj not in linked_qs) and (link_to_obj == None or obj not in linked_through):
                # Create new object
                oNew = cls()
                setattr(oNew, field, instance)
                # Copy the local fields
                for lfield in obj._meta.local_fields:
                    fname = lfield.name
                    if fname != "id" and fname != field:
                        # Copy the field value
                        setattr(oNew, fname, getattr(obj, fname))
                for k, v in kwargs.items():
                    setattr(oNew, k, v)
                # Need to add an object link?
                if link_to_obj != None:
                    setattr(oNew, link_to_obj, obj)
                oNew.save()
        # Remove links that are not in [qs]
        for obj in linked_qs:
            if obj not in qs:
                # Remove this item
                obj.delete()
        # Return okay
        return True
    except:
        msg = errHandle.get_error_message()
        return False

def adapt_m2o_sig(instance, qs):
    """Adapt the instances of [SermonSignature] pointing to [instance] to only include [qs] 
    
    Note: convert SermonSignature into (Gold) Signature
    """

    errHandle = ErrHandle()
    try:
        # Get all the [SermonSignature] items currently linking to [instance]
        linked_qs = SermonSignature.objects.filter(sermon=instance)
        # make sure all items in [qs] are linked to [instance]
        bRedo = False
        for obj in qs:
            # Get the SermonSignature equivalent for Gold signature [obj]
            sermsig = instance.get_sermonsig(obj)
            if sermsig not in linked_qs:
                # Indicate that we need to re-query
                bRedo = True
        # Do we need to re-query?
        if bRedo: 
            # Yes we do...
            linked_qs = SermonSignature.objects.filter(sermon=instance)
        # Remove links that are not in [qs]
        for obj in linked_qs:
            # Get the gold-signature equivalent of this sermon signature
            gsig = obj.get_goldsig()
            # Check if the gold-sermon equivalent is in [qs]
            if gsig not in qs:
                # Remove this item
                obj.delete()
        # Return okay
        return True
    except:
        msg = errHandle.get_error_message()
        return False

def is_empty_form(form):
    """Check if the indicated form has any cleaned_data"""

    if "cleaned_data" not in form:
        form.is_valid()
    cleaned = form.cleaned_data
    return (len(cleaned) == 0)

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
    response = False if user == None else user.is_authenticated()
    return response

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

def action_model_changes(form, instance):
    field_values = model_to_dict(instance)
    changed_fields = form.changed_data
    changes = {}
    for item in changed_fields: 
        if item in field_values:
            changes[item] = field_values[item]
        else:
            # It is a form field
            try:
                representation = form.cleaned_data[item]
                if isinstance(representation, QuerySet):
                    # This is a list
                    rep_list = []
                    for rep in representation:
                        rep_str = str(rep)
                        rep_list.append(rep_str)
                    representation = json.dumps(rep_list)
                elif isinstance(representation, object):
                    representation = [ representation.id ]
                changes[item] = representation
            except:
                changes[item] = "(unavailable)"
    return changes

def has_string_value(field, obj):
    response = (field != None and field in obj and obj[field] != None and obj[field] != "")
    return response

def has_list_value(field, obj):
    response = (field != None and field in obj and obj[field] != None and len(obj[field]) > 0)
    return response

def has_obj_value(field, obj):
    response = (field != None and field in obj and obj[field] != None)
    return response

def make_search_list(filters, oFields, search_list, qd):
    """Using the information in oFields and search_list, produce a revised filters array and a lstQ for a Queryset"""

    def enable_filter(filter_id, head_id=None):
        for item in filters:
            if filter_id in item['id']:
                item['enabled'] = True
                # Break from my loop
                break
        # Check if this one has a head
        if head_id != None and head_id != "":
            for item in filters:
                if head_id in item['id']:
                    item['enabled'] = True
                    # Break from this sub-loop
                    break
        return True

    def get_value(obj, field, default=None):
        if field in obj:
            sBack = obj[field]
        else:
            sBack = default
        return sBack

    oErr = ErrHandle()

    try:
        # (1) Create default lstQ
        lstQ = []

        # (2) Reset the filters in the list we get
        for item in filters: item['enabled'] = False
    
        # (3) Walk all sections
        for part in search_list:
            head_id = get_value(part, 'section')

            # (4) Walk the list of defined searches
            for search_item in part['filterlist']:
                keyS = get_value(search_item, "keyS")
                keyId = get_value(search_item, "keyId")
                keyFk = get_value(search_item, "keyFk")
                keyList = get_value(search_item, "keyList")
                infield = get_value(search_item, "infield")
                dbfield = get_value(search_item, "dbfield")
                fkfield = get_value(search_item, "fkfield")
                keyType = get_value(search_item, "keyType")
                filter_type = get_value(search_item, "filter")
                s_q = ""
                arFkField = []
                if fkfield != None:
                    arFkField = fkfield.split("|")
               
                # Main differentiation: fkfield or dbfield
                if fkfield:
                    # Check for keyS
                    if has_string_value(keyS, oFields):
                        # Check for ID field
                        if has_string_value(keyId, oFields):
                            val = oFields[keyId]
                            if not isinstance(val, int): 
                                try:
                                    val = val.id
                                except:
                                    pass
                            enable_filter(filter_type, head_id)
                            s_q = Q(**{"{}__id".format(fkfield): val})
                        elif has_obj_value(fkfield, oFields):
                            val = oFields[fkfield]
                            enable_filter(filter_type, head_id)
                            s_q = Q(**{fkfield: val})
                        else:
                            val = oFields[keyS]
                            enable_filter(filter_type, head_id)
                            # We are dealing with a foreign key (or multiple)
                            if len(arFkField) > 1:
                                iStop = 1
                            # we are dealing with a foreign key, so we should use keyFk
                            s_q = None
                            for fkfield in arFkField:
                                if "*" in val:
                                    val = adapt_search(val)
                                    s_q_add = Q(**{"{}__{}__iregex".format(fkfield, keyFk): val})
                                else:
                                    s_q_add = Q(**{"{}__{}__iexact".format(fkfield, keyFk): val})
                                if s_q == None:
                                    s_q = s_q_add
                                else:
                                    s_q |= s_q_add
                    elif has_obj_value(fkfield, oFields):
                        val = oFields[fkfield]
                        enable_filter(filter_type, head_id)
                        s_q = Q(**{fkfield: val})
                        external = get_value(search_item, "external")
                        if has_string_value(external, oFields):
                            qd[external] = getattr(val, "name")
                elif dbfield:
                    # We are dealing with a plain direct field for the model
                    # OR: it is also possible we are dealing with a m2m field -- that gets the same treatment
                    # Check for keyS
                    if has_string_value(keyS, oFields):
                        # Check for ID field
                        if has_string_value(keyId, oFields):
                            val = oFields[keyId]
                            enable_filter(filter_type, head_id)
                            s_q = Q(**{"{}__id".format(dbfield): val})
                        elif has_obj_value(keyFk, oFields):
                            val = oFields[keyFk]
                            enable_filter(filter_type, head_id)
                            s_q = Q(**{dbfield: val})
                        else:
                            val = oFields[keyS]
                            enable_filter(filter_type, head_id)
                            if isinstance(val, int):
                                s_q = Q(**{"{}".format(dbfield): val})
                            elif "*" in val:
                                val = adapt_search(val)
                                s_q = Q(**{"{}__iregex".format(dbfield): val})
                            else:
                                s_q = Q(**{"{}__iexact".format(dbfield): val})
                    elif keyType == "has":
                        # Check the count for the db field
                        val = oFields[filter_type]
                        if val == "yes" or val == "no":
                            enable_filter(filter_type, head_id)
                            if val == "yes":
                                s_q = Q(**{"{}__gt".format(dbfield): 0})
                            else:
                                s_q = Q(**{"{}".format(dbfield): 0})

                # Check for list of specific signatures
                if has_list_value(keyList, oFields):
                    s_q_lst = ""
                    enable_filter(filter_type, head_id)
                    code_list = [getattr(x, infield) for x in oFields[keyList]]
                    if fkfield:
                        # Now we need to look at the id's
                        if len(arFkField) > 1:
                            # THere are more foreign keys: combine in logical or
                            s_q_lst = ""
                            for fkfield in arFkField:
                                if s_q_lst == "":
                                    s_q_lst = Q(**{"{}__{}__in".format(fkfield, infield): code_list})
                                else:
                                    s_q_lst |= Q(**{"{}__{}__in".format(fkfield, infield): code_list})
                        else:
                            # Just one foreign key
                            s_q_lst = Q(**{"{}__{}__in".format(fkfield, infield): code_list})
                    elif dbfield:
                        s_q_lst = Q(**{"{}__in".format(infield): code_list})
                    s_q = s_q_lst if s_q == "" else s_q | s_q_lst

                # Possibly add the result to the list
                if s_q != "": lstQ.append(s_q)
    except:
        msg = oErr.get_error_message()
        oErr.DoError("make_search_list")
        lstQ = []

    # Return what we have created
    return filters, lstQ, qd

def make_ordering(qs, qd, order_default, order_cols, order_heads):

    oErr = ErrHandle()

    try:
        bAscending = True
        sType = 'str'
        order = []
        colnum = ""
        # reset 'used' feature for all heads
        for item in order_heads: item['used'] = None
        if 'o' in qd and qd['o'] != "":
            colnum = qd['o']
            if '=' in colnum:
                colnum = colnum.split('=')[1]
            if colnum != "":
                order = []
                iOrderCol = int(colnum)
                bAscending = (iOrderCol>0)
                iOrderCol = abs(iOrderCol)

                # Set the column that it is in use
                order_heads[iOrderCol-1]['used'] = 1
                # Get the type
                sType = order_heads[iOrderCol-1]['type']
                for order_item in order_cols[iOrderCol-1].split(";"):
                    if order_item != "":
                        if sType == 'str':
                            order.append(Lower(order_item).asc(nulls_last=True))
                        else:
                            order.append(F(order_item).asc(nulls_last=True))
                if bAscending:
                    order_heads[iOrderCol-1]['order'] = 'o=-{}'.format(iOrderCol)
                else:
                    # order = "-" + order
                    order_heads[iOrderCol-1]['order'] = 'o={}'.format(iOrderCol)

                # Reset the sort order to ascending for all others
                for idx, item in enumerate(order_heads):
                    if idx != iOrderCol - 1:
                        # Reset this sort order
                        order_heads[idx]['order'] = order_heads[idx]['order'].replace("-", "")
        else:
            for order_item in order_default[0].split(";"):
                if order_item != "":
                    order.append(Lower(order_item))
           #  order.append(Lower(order_cols[0]))
        if sType == 'str':
            if len(order) > 0:
                qs = qs.order_by(*order)
        else:
            qs = qs.order_by(*order)
        # Possibly reverse the order
        if not bAscending:
            qs = qs.reverse()
    except:
        msg = oErr.get_error_message()
        oErr.DoError("make_ordering")
        lstQ = []

    return qs, order_heads, colnum

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

def get_breadcrumbs(request, name, is_menu, lst_crumb=[], **kwargs):
    """Process one visit and return updated breadcrumbs"""

    # Initialisations
    p_list = []
    p_list.append({'name': 'Home', 'url': reverse('home')})
    # Find out who this is
    username = "anonymous" if request.user == None else request.user.username
    if username != "anonymous" and request.user.username != "":
        # Add the visit
        currenturl = request.get_full_path()
        Visit.add(username, name, currenturl, is_menu, **kwargs)
        # Set the full path, dependent on the arguments we get
        for crumb in lst_crumb:
            if len(crumb) == 2:
                p_list.append(dict(name=crumb[0], url=crumb[1]))
            else:
                pass
        # Also add the final one
        p_list.append(dict(name=name, url=currenturl))
    # Return the breadcrumbs
    return p_list

def get_previous_page(request, top=False):
    """Find the previous page for this user"""

    username = "anonymous" if request.user == None else request.user.username
    if username != "anonymous" and request.user.username != "":
        # Get the current path list
        p_list = Profile.get_stack(username)
        p_item = []
        if len(p_list) < 2:
            prevpage = request.META.get('HTTP_REFERER') 
        elif top:
            p_item = p_list[len(p_list)-1]
            prevpage = p_item['url']
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
    context['is_app_uploader'] = user_is_ingroup(request, app_uploader)
    context['is_app_editor'] = user_is_ingroup(request, app_editor)

    # Process this visit
    context['breadcrumbs'] = get_breadcrumbs(request, "Home", True)

    # Check the newsitems for validity
    NewsItem.check_until()

    # Create the list of news-items
    lstQ = []
    lstQ.append(Q(status='val'))
    newsitem_list = NewsItem.objects.filter(*lstQ).order_by('-created', '-saved')
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
    context['is_app_uploader'] = user_is_ingroup(request, app_uploader)

    # Process this visit
    context['breadcrumbs'] = get_breadcrumbs(request, "Contact", True)

    return render(request,'contact.html', context)

def more(request):
    """Renders the more page."""
    assert isinstance(request, HttpRequest)
    context =  {'title':'More',
                'year':get_current_datetime().year,
                'pfx': APP_PREFIX,
                'site_url': admin.site.site_url}
    context['is_app_uploader'] = user_is_ingroup(request, app_uploader)

    # Process this visit
    context['breadcrumbs'] = get_breadcrumbs(request, "More", True)

    return render(request,'more.html', context)

def technical(request):
    """Renders the technical-information page."""
    assert isinstance(request, HttpRequest)
    context =  {'title':'Technical',
                'year':get_current_datetime().year,
                'pfx': APP_PREFIX,
                'site_url': admin.site.site_url}
    context['is_app_uploader'] = user_is_ingroup(request, app_uploader)

    # Process this visit
    context['breadcrumbs'] = get_breadcrumbs(request, "Technical", True)

    return render(request,'technical.html', context)

def bibliography(request):
    """Renders the more page."""
    assert isinstance(request, HttpRequest)
    context =  {'title':'Bibliography',
                'year':datetime.now().year,
                'pfx': APP_PREFIX,
                'site_url': admin.site.site_url}
    context['is_app_uploader'] = user_is_ingroup(request, app_uploader)

    # Add the edition references (abreviated and full)



    # Create empty list for the editions
    edition_list = []
    
    # Retrieve all records from the Zotero database (user for now)
    zot = zotero.Zotero('5802673', 'user', 'oVBhIJH5elqA8zxrJGwInwWd')
    
    # Store only the records from the Edition collection (key: from URL 7HQU3AY8)
    zot_editions = zot.collection_items('7HQU3AY8')
   
    for item in zot_editions:
        creators_ed = item['data']['creators']
        creator_list_ed = []
        for creator in creators_ed:
            first_name = creator['firstName']
            last_name = creator['lastName']
            creator_list_ed.append(first_name + " " + last_name)
        edition_list.append({'abbr': item['data']['extra'] + ", " + item['data']['pages'], 'full': item['data']['title'], 'creators': ", ".join(creator_list_ed)})
   
    context['edition_list'] = edition_list    
    
    # Add the literature references from zotero, data extra 
        
    # Create empty list for the literature
    
    reference_list = [] 
    
    # Retrieve all records from the Zotero database (user for now)
    zot = zotero.Zotero('5802673', 'user', 'oVBhIJH5elqA8zxrJGwInwWd')
    
    # Store only the records in the Literature collection,  (key: from URL FEPVSGVX)
    zot_literature = zot.collection_items('FEPVSGVX')
        
    
    for item in zot_literature:
        creators = item['data']['creators']
        creator_list = []
        for creator in creators:
            first_name = creator['firstName']
            last_name = creator['lastName']
            creator_list.append(first_name + " " + last_name)
        reference_list.append({'abbr':creator['lastName'] + ", " + item['data']['extra'] + " " + item['data']['volume'] + " (" + item['data']['date']+ ")"+", "+item['data']['pages'], 'full': item['data']['title'], 'creators': ", ".join(creator_list)})
    context['reference_list'] = reference_list

    # Process this visit
    context['breadcrumbs'] = get_breadcrumbs(request, "Bibliography", True)

    return render(request,'bibliography.html', context)

def about(request):
    """Renders the about page."""
    assert isinstance(request, HttpRequest)
    context =  {'title':'About',
                'message':'Radboud University passim utility.',
                'year':get_current_datetime().year,
                'pfx': APP_PREFIX,
                'site_url': admin.site.site_url}
    context['is_app_uploader'] = user_is_ingroup(request, app_uploader)

    # Process this visit
    context['breadcrumbs'] = get_breadcrumbs(request, "About", True)

    return render(request,'about.html', context)

def short(request):
    """Renders the page with the short instructions."""

    assert isinstance(request, HttpRequest)
    template = 'short.html'
    context = {'title': 'Short overview',
               'message': 'Radboud University passim short intro',
               'year': get_current_datetime().year}
    context['is_app_uploader'] = user_is_ingroup(request, app_uploader)
    return render(request, template, context)

def nlogin(request):
    """Renders the not-logged-in page."""
    assert isinstance(request, HttpRequest)
    context =  {    'title':'Not logged in', 
                    'message':'Radboud University passim utility.',
                    'year':get_current_datetime().year,}
    context['is_app_uploader'] = user_is_ingroup(request, app_uploader)
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

def search_generic(s_view, cls, form, qd):
    """Generic queryset generation for searching"""

    qs = None
    oErr = ErrHandle()
    bFilter = False
    genForm = None
    try:
        bHasFormset = (len(qd) > 0)

        if bHasFormset:
            # Get the formset from the input
            lstQ = []
            prefix = s_view.prefix
            filters = s_view.filters
            searches = s_view.searches

            genForm = form(qd, prefix=prefix)

            if genForm.is_valid():

                # Process the criteria from this form 
                oFields = genForm.cleaned_data

                # Create the search based on the specification in searches
                filters, lstQ, qd = make_search_list(filters, oFields, searches, qd)

                # Calculate the final qs
                if len(lstQ) == 0:
                    # No filter: Just show everything
                    qs = cls.objects.all()
                else:
                    # There is a filter: apply it
                    qs = cls.objects.filter(*lstQ).distinct()
                    bFilter = True
            else:
                # TODO: communicate the error to the user???

                # Just show everything
                qs = cls.objects.all().distinct()

        else:
            # Just show everything
            qs = cls.objects.all().distinct()
    except:
        msg = oErr.get_error_message()
        oErr.DoError("search_generic")
        qs = None
        bFilter = False
    # Return the resulting filtered and sorted queryset
    return filters, bFilter, qs, qd, oFields

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
    context['is_app_uploader'] = user_is_ingroup(request, app_uploader)

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

def redo_zotero(request):
    oErr = ErrHandle()
    data = {'status': 'preparing'}

    try:
        if request.method == 'GET':
            Litref.sync_zotero(True)
        data['status'] = 'ok'
    except:
        oErr.DoError("redo_zotero error")
        data = {'status': 'error'}

    # Return this response
    return JsonResponse(data)

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
                    obj.code = "CPPM I {}".format(code)
                    obj.save()
                else:
                    # Break it up into spaced items
                    arCode = code.split(" ")
                    if len(arCode) > 1:
                        if arCode[1] != "I":
                            if len(arCode) > 2:
                                iStop = True
                            arCode[0] = arCode[0] + " I"
                            obj.code = " ".join(arCode)
                            obj.save()
                    
    # Walk the whole gold-signature list
    with transaction.atomic():
        for obj in SermonSignature.objects.all():
            # Check the type
            if obj.editype == "cl":
                # This is clavis -- get the code
                code = obj.code
                if r_number.match(code):
                    # This is only a number
                    obj.code = "CPPM I {}".format(code)
                    obj.save()
                else:
                    # Break it up into spaced items
                    arCode = code.split(" ")
                    if len(arCode) > 1:
                        if arCode[1] != "I":
                            if len(arCode) > 2:
                                iStop = True
                            arCode[0] = arCode[0] + " I"
                            obj.code = " ".join(arCode)
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
        context['is_app_uploader'] = user_is_ingroup(request, app_uploader)
        context['is_app_editor'] = user_is_ingroup(request, app_editor)

        # Only passim uploaders can do this
        if not context['is_app_uploader']: return reverse('home')

        # Indicate the necessary tools sub-part
        context['tools_part'] = "Repair Stype definitions"

        # Process this visit
        context['breadcrumbs'] = get_breadcrumbs(request, "Stype", True)

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
        context['is_app_uploader'] = user_is_ingroup(request, app_uploader)
        context['is_app_editor'] = user_is_ingroup(request, app_editor)

        # Only passim uploaders can do this
        if not context['is_app_uploader']: return reverse('home')

        # Indicate the necessary tools sub-part
        context['tools_part'] = "Establish location definitions"

        # Process this visit
        context['breadcrumbs'] = get_breadcrumbs(request, "Locations", True)

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

def do_provenance(request):
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
        context['is_app_uploader'] = user_is_ingroup(request, app_uploader)
        context['is_app_editor'] = user_is_ingroup(request, app_editor)

        # Only passim uploaders can do this
        if not context['is_app_uploader']: return reverse('home')

        # Indicate the necessary tools sub-part
        context['tools_part'] = "Tweak Manuscript-Provenance connections"

        # Process this visit
        context['breadcrumbs'] = get_breadcrumbs(request, "Provenance", True)

        # Create list to be returned
        result_list = []

        # Get a list of all Manuscript-Provenance links
        qs = ProvenanceMan.objects.all().order_by('manuscript', 'provenance')
        lst_del = []
        man_id = -1
        prov_id = -1
        for item in qs:
            if item.manuscript.id != man_id:
                # This is a new manuscript
                prov_id = -1
                man_id = item.manuscript.id
            if item.provenance.id == prov_id or item.provenance.id == 1:
                # Set for removal
                lst_del.append(item.id)
            # Take over the prov id
            prov_id = item.provenance.id
        # Remove them
        ProvenanceMan.objects.filter(id__in=lst_del).delete()


        # Wrapping it up
        context['result_list'] = lst_del

        # Render and return the page
        return render(request, template_name, context)
    except:
        msg = oErr.get_error_message()
        oErr.DoError("do_provenance")
        return reverse('home')

def do_daterange(request):
    """Copy data ranges from manuscripts to separate tables - if not already there"""

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
        context['is_app_uploader'] = user_is_ingroup(request, app_uploader)
        context['is_app_editor'] = user_is_ingroup(request, app_editor)

        # Only passim uploaders can do this
        if not context['is_app_uploader']: return reverse('home')

        # Indicate the necessary tools sub-part
        context['tools_part'] = "Update from Manuscript to Daterange table"

        # Process this visit
        context['breadcrumbs'] = get_breadcrumbs(request, "Dateranges", True)

        # Create list to be returned
        result_list = []

        # Visit all Manuscripts
        qs = Manuscript.objects.all()
        lst_add = []
        for obj in qs:
            # Check if there are any associated Dateranges
            if obj.manuscript_dateranges.all().count() == 0:
                # There are no date ranges yet: create just ONE
                obj_dr = Daterange.objects.create(yearstart=obj.yearstart, yearfinish=obj.yearfinish, manuscript=obj)
                # Show that we added it
                # oAdded = dict(manuscript=obj.idno, yearstart=obj.yearstart, yearfinish=obj.yearfinish)
                sAdd = "{}: {}-{}".format(obj.idno, obj.yearstart, obj.yearfinish)
                lst_add.append(sAdd)

        # Wrapping it up
        result_list.append(dict(part="Added", result= lst_add))
        context['result_list'] = result_list

        # Render and return the page
        return render(request, template_name, context)
    except:
        msg = oErr.get_error_message()
        oErr.DoError("do_daterange")
        return reverse('home')

def do_mext(request):
    """Copy all 'url' fields from Manuscript instances to separate ManuscriptExt instances and link them to the Manuscript"""

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
        context['is_app_uploader'] = user_is_ingroup(request, app_uploader)
        context['is_app_editor'] = user_is_ingroup(request, app_editor)

        # Only passim uploaders can do this
        if not context['is_app_uploader']: return reverse('home')

        # Indicate the necessary tools sub-part
        context['tools_part'] = "Copy Manuscript links to externals"

        # Process this visit
        context['breadcrumbs'] = get_breadcrumbs(request, "Mext", True)

        # Create list to be returned
        result_list = []
        added_list = []

        # Get a list of all Manuscripts that are not referred to via a ManuscriptExt
        man_ids = [x.manuscript.id for x in ManuscriptExt.objects.all() ]

        qs = Manuscript.objects.exclude(id__in=man_ids)
        with transaction.atomic():
            for item in qs:
                # Get any possible URL here
                url = item.url
                if url != None:
                    # There is an actual URL: Create a new ManuscriptExt instance
                    mext = ManuscriptExt(url=url, manuscript=item)
                    mext.save()
                    added_list.append(mext.id)

        # Wrapping it up
        result_list.append({'part': 'All additions', 'result': json.dumps(added_list)})
        context['result_list'] = result_list

        # Render and return the page
        return render(request, template_name, context)
    except:
        msg = oErr.get_error_message()
        oErr.DoError("do_mext")
        return reverse('home')

def do_goldsearch(request):
    """Re-calculate the srchincipit and srchexplicit fields for gold sermons"""

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
        context['is_app_uploader'] = user_is_ingroup(request, app_uploader)
        context['is_app_editor'] = user_is_ingroup(request, app_editor)

        # Only passim uploaders can do this
        if not context['is_app_uploader']: return reverse('home')

        # Indicate the necessary tools sub-part
        context['tools_part'] = "Re-create Gold sermon searching (incipit/explicit)"

        # Process this visit
        context['breadcrumbs'] = get_breadcrumbs(request, "Sermons", True)

        # Start up processing
        added = 0
        with transaction.atomic():
            for item in SermonGold.objects.all():
                srchincipit = item.srchincipit
                srchexplicit = item.srchexplicit
                # Double check the equal field
                if item.equal == None:
                    geq = EqualGold.objects.create()
                    item.equal = geq
                item.save()
                if item.srchincipit != srchincipit or item.srchexplicit != srchexplicit:
                    added += 1
   
        # Create list to be returned
        result_list = []
        result_list.append({'part': 'Number of changed gold-sermons', 'result': added})

        context['result_list'] = result_list
    
        # Render and return the page
        return render(request, template_name, context)
    except:
        msg = oErr.get_error_message()
        oErr.DoError("do_goldsearch")
        return reverse('home')

def do_sermons(request):
    """Remove duplicate sermons from manuscripts and/or do other SermonDescr initialisations"""

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
        context['is_app_uploader'] = user_is_ingroup(request, app_uploader)
        context['is_app_editor'] = user_is_ingroup(request, app_editor)

        # Only passim uploaders can do this
        if not context['is_app_uploader']: return reverse('home')

        # Indicate the necessary tools sub-part
        context['tools_part'] = "Repair manuscript-sermons"

        # Process this visit
        context['breadcrumbs'] = get_breadcrumbs(request, "Sermons", True)
    
        # Start up processing
        added = 0
        lst_total = []
        lst_total.append("<table><thead><tr><th>Manuscript</th><th>Sermon</th></tr>")
        lst_total.append("<tbody>")

        # Step #1: walk all manuscripts
        qs_m = Manuscript.objects.all().order_by('id')
        for manu in qs_m:
            # Get all the sermons for this manuscript in appropriate order (reverse ID)
            sermon_lst = SermonDescr.objects.filter(manu=manu).order_by('-id').values('id', 'title', 'author', 'nickname', 'locus', 'incipit', 'explicit', 'note', 'additional', 'order')
            remove_lst = []
            if manu.id == 1245:
                iStop = 1
            for idx, sermon_obj in enumerate(sermon_lst):
                # Check if duplicates are there, and if so put them in the remove list
                start = idx + 1
                for check in sermon_lst[start:]:
                    # compare all relevant elements
                    bEqual = True
                    for attr in check:
                        if attr != 'id':
                            if check[attr] != sermon_obj[attr]:
                                bEqual = False
                                break
                    if bEqual:
                        id = check['id']
                        if id not in remove_lst:
                            remove_lst.append(id)
                            lst_total.append("<tr><td>{}</td><td>{}</td></tr>".format(manu.id, check['id']))
                            added += 1
            # Remove duplicates for this manuscript
            if len(remove_lst) > 0:
                SermonDescr.objects.filter(id__in=remove_lst).delete()

        # Step #2: tidy up sermon fields
        qs_s = SermonDescr.objects.all().order_by('id')
        with transaction.atomic():
            for sermo in qs_s:
                bChange = False
                # Check if the sub title equals the title
                if sermo.subtitle != None and sermo.title != None and sermo.subtitle == sermo.title:
                    sermo.subtitle = ""
                    bChange = True
                # Save if needed
                if bChange:
                    sermo.save()

        # Step #3: init latin
        SermonDescr.init_latin()


        lst_total.append("</tbody></table>")

        # Create list to be returned
        result_list = []
        result_list.append({'part': 'Number of removed sermons', 'result': added})
        result_list.append({'part': 'All changes', 'result': "\n".join(lst_total)})

        context['result_list'] = result_list
    
        # Render and return the page
        return render(request, template_name, context)
    except:
        msg = oErr.get_error_message()
        oErr.DoError("do_sermons")
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
        context['is_app_uploader'] = user_is_ingroup(request, app_uploader)
        context['is_app_editor'] = user_is_ingroup(request, app_editor)

        # Only passim uploaders can do this
        if not context['is_app_uploader']: return reverse('home')

        # Indicate the necessary tools sub-part
        context['tools_part'] = "Repair gold-to-gold links"

        # Process this visit
        context['breadcrumbs'] = get_breadcrumbs(request, "GoldToGold", True)

        added = 0
        lst_total = []
        lst_total.append("<table><thead><tr><th>item</th><th>src</th><th>dst</th><th>linktype</th><th>addtype</th><th>Path</th></tr>")
        lst_total.append("<tbody>")

        method = "goldspread" 

        # Step #1: remove all unnecessary links
        oErr.Status("{} step #1".format(method))
        qs = EqualGoldLink.objects.all()
        lst_delete = []
        for relation in qs:
            if relation.src == relation.dst:
                lst_delete.append(relation.id)
        oErr.Status("Step 1: removing {} links".format(len(lst_delete)))
        if len(lst_delete) > 0:
            EqualGoldLink.objects.filter(Q(id__in=lst_delete)).delete()

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
                            added += 1

        # Step #3: add individual equals
        oErr.Status("{} step #3".format(method))
        # Visit all SermonGold instances and create eqg's for those that don't have one yet
        for gold in SermonGold.objects.all():
            if gold.equal == None:
                eqg = EqualGold()
                eqg.save()
                gold.equal = eqg
                gold.save()
                added += 1

        # -- or can a SermonGold be left without an equality group, if he is not equal to anything (yet)?

        # Step #4 (new): copy 'partial' and other near links to linke between groups
        oErr.Status("{} step #4a".format(method))
        for linktype in LINK_PRT:
            lst_prt_add = []    # List of partially equals relations to be added
            # Get all links of the indicated type
            qs_prt = EqualGoldLink.objects.filter(linktype=linktype).order_by('src__id')
            # Walk these links
            for obj_prt in qs_prt:
                # Get the equal groups of the link
                src_eqg = obj_prt.src
                dst_eqg = obj_prt.dst
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
                        added += 1
                        lst_total.append("<tr><td>{}</td><td>{}</td><td>{}</td><td>{}</td><td>{}</td><td>{}</td></tr>".format( 
                            (idx+1), item['src'].id, item['dst'].id, linktype, "add", "" ))
        # y = [o for o in lst_prt_add if o['src'].id == 708]
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

def do_ssgmigrate(request):
    """Migration of super sermon gold"""

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
        context['is_app_uploader'] = user_is_ingroup(request, app_uploader)
        context['is_app_editor'] = user_is_ingroup(request, app_editor)

        # Only passim uploaders can do this
        if not context['is_app_uploader']: return reverse('home')

        # Indicate the necessary tools sub-part
        context['tools_part'] = "Migrate SSG"

        added = 0
        lst_total = []

        # Walk all the EqualGold items
        qs = EqualGold.objects.all()
        number = qs.count()
        for idx, obj in enumerate(qs):
            print("SSG migration item {} of {}".format(idx+1, number))
            # Need treatment?
            if not obj.author or not obj.number:
                # Check how many SG items there are within this EqualGold (=ssg)
                qs_sg = obj.equal_goldsermons.all()
                if qs_sg.count() == 1:
                    # There is just ONE (1) GS in the set
                    sg = qs_sg.first()
                    # (1) Get the author
                    author = sg.author
                    if author != None:
                        # There is an author!!
                        auth_num = author.get_number()
                        if auth_num > 0:
                            # Check the highest sermon number for this author
                            iNumber = EqualGold.sermon_number(author)
                            # Now we have both an author and a number...
                            obj.author = author
                            obj.number = iNumber
                            obj.code = EqualGold.passim_code(auth_num, iNumber)
                            obj.incipit = sg.incipit
                            obj.srchincipit = sg.srchincipit
                            obj.explicit = sg.explicit
                            obj.srchexplicit = sg.srchexplicit
                            obj.save()
                            added += 1
                            lst_total.append(obj.code)

                # Double check on author
                if obj.author == None:
                    # Set the author to 'undecided'
                    author = Author.get_undecided()
                    obj.author = author

            # Double check to see if something has changed
            if obj.code == "DETERMINE":
                obj.code = "ZZZ_DETERMINE"
                obj.save()

        # Create list to be returned
        result_list = []
        result_list.append({'part': 'Number of added SSGs', 'result': added})
        # result_list.append({'part': 'All additions', 'result': json.dumps(lst_total)})
        result_list.append({'part': 'All additions', 'result': "\n".join(lst_total)})

        context['result_list'] = result_list
    
        # Render and return the page
        return render(request, template_name, context)
    except:
        msg = oErr.get_error_message()
        oErr.DoError("ssgmigrate")
        return reverse('home')

def get_old_edi(edi):
    """Split pages and year from edition, keep stripped edition and the pages
    The number of matches increase when the year in the name of the edition
    and in the short reference from Zotero is not used.
    """
 
    pages = None
    result = None
    status = "ok"
    # Split up edition and pages part
    arResult = edi.name.split(",")
    # In case of no pages, split string to get rid of year 
    if len(arResult) ==  1:
        result_tmp1 = arResult[0].split("(")
        result = result_tmp1[0].strip()
    # In case there are pages
    elif len(arResult) > 1: 
        # Split string to get rid of year 
        result_tmp1 = arResult[0].split("(")
        result = result_tmp1[0].strip()
        pages = arResult[1].strip()
        if not re.match(r'^[\d\-]+$', pages): 
            status = pages
            pages = None

    return result, pages, status

def get_short_edit(short):
    # Strip off the year of the short reference in Litref, keep only first part (abbr and seriesnumber)

    result = None
    arResult = short.split("(")
    if len(arResult) > 1:
        result = arResult[0].strip()
    elif len(arResult) == 1:
        result = arResult[0].strip()
    return result

def do_create_pdf_edi(request):
    """This definition creates the input for the pdf with all all used edition (full) references."""
        
    # Store title, and pageinfo (for at the bottom of the page) 
    Title = "Edition references used in PASSIM:"
    pageinfo = "Editions PASSIM"
             
    # Store name of the pdf file 
    filename = "Edi_ref_PASSIM.pdf"
            
    # Calculate the final qs for the edition litrefs
    ediref_ids = [x['reference'] for x in EdirefSG.objects.all().values('reference')]
       
    # Sort and filter all editions
    qs = Litref.objects.filter(id__in=ediref_ids).order_by('short')

    # Create a list of objects
    pdf_list = []
    for obj in qs:
        item = {}
        item = obj.full
        pdf_list.append(item)
    
    # Call create_pdf_passim function with arguments  
    response = create_pdf_passim(Title, pageinfo, filename, pdf_list)
  
    # And return the pdf
    return response

def do_create_pdf_lit(request):
    """"This definition creates the input for the pdf with all used literature (full) references."""
         
    # Store title, and pageinfo (for at the bottom of the page) 
    Title = "Literature references used in PASSIM:"
    pageinfo = "Literature PASSIM"
       
    # Store name of the file    
    filename = "Lit_ref_PASSIM.pdf"
    
    # Calculate the final qs for the manuscript litrefs
    litref_ids_man = [x['reference'] for x in LitrefMan.objects.all().values('reference')]
    
    # Calculate the final qs for the Gold sermon litrefs
    litref_ids_sg = [x['reference'] for x in LitrefSG.objects.all().values('reference')]

    # Combine the two qs into one and filter
    litref_ids = chain(litref_ids_man, litref_ids_sg)
    
    # Hier worden short en full opgehaald?
    qs = Litref.objects.filter(id__in=litref_ids).order_by('short') 
    
    # Create a list of objects 
    pdf_list = []
    for obj in qs:
        item = {}
        item = obj.full
        pdf_list.append(item)
        
    # Call create_pdf_passim function with arguments  
    response  = create_pdf_passim(Title, pageinfo, filename, pdf_list)
       
    # And return the pdf
    return response

def create_pdf_passim(Title, pageinfo, filename, pdf_list):
    """This definition creates a pdf for all passim requests."""
     
    # Define sizes of the pages in the pdf
    PAGE_HEIGHT=defaultPageSize[1]; PAGE_WIDTH=defaultPageSize[0]
    
    # Store text and current date for information on date of the download
    today = datetime.today()
    today.strftime('%Y-%m-%d')
       
    # Set buffer   
    buffer = io.BytesIO()

    # Set the first page
    def myFirstPage(canvas, doc):
        canvas.saveState()
        canvas.setFont('Helvetica-Bold',22)
        canvas.drawCentredString(PAGE_WIDTH/2.0, PAGE_HEIGHT-80, Title)
        canvas.setFont('Helvetica',10)
        canvas.drawString(75,730, "Downloaded on: ")
        canvas.drawString(150,730, today.strftime('%d-%m-%Y'))
        canvas.setFont('Helvetica',9)
        canvas.drawString(inch, 0.75 * inch, "Page 1 / %s" % pageinfo)
        canvas.restoreState()
    
    # Set the second and later pages
    def myLaterPages(canvas, doc):
        canvas.saveState()
        canvas.setFont('Helvetica',9)
        canvas.drawString(inch, 0.75 * inch, "Page %d %s" % (doc.page, pageinfo))
        canvas.restoreState()

    # Create the HttpResponse object with the appropriate PDF headers. 
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename="{}"'.format(filename)
               
    # Define style of the pdf
    styles = getSampleStyleSheet()
        
    doc = SimpleDocTemplate(buffer)
    Story = [Spacer(1,1.05*inch)]
    style = styles["Normal"]
    # Dit tzt afhankelijk maken van lit en edi, niet van manuscript TH: hier nog met Erwin over hebben

    for line in pdf_list:
        line_2 = markdown(line)
        line_3 = line_2.replace("<em>", "<i>")
        line_4 = line_3.replace("</em>", "</i>")
        line_5 = markdown(line_4)
          
        lit_ref = (line_5) *1 
        p = Paragraph(lit_ref, style, '-')
        Story.append(p)
        Story.append(Spacer(1,0.2*inch))
    doc.build(Story, onFirstPage=myFirstPage, onLaterPages=myLaterPages)
    
    # Write the buffer to the PDF
    response.write(buffer.getvalue())
    # Close the buffer cleanly, and we're done.
    buffer.close()
       
    # And return the pdf
    return response

def do_create_pdf_manu(request):
    """This definition creates the input for the pdf with all manuscripts in the passim database."""
  
    # Store title, and pageinfo (for at the bottom of each page) 
    Title = "Manuscripts listed in PASSIM:"
    pageinfo = "Manuscripts PASSIM"
             
    # Store name of the pdf file 
    filename = "Manu_list_PASSIM.pdf"

    # Calculate the qs for the manuscripts       
    qs = Manuscript.objects.all()
    
    # Create temporary list and add relevant fields to the list
    pdf_list_temp = []
    for obj in qs:
        # Count all items for each manuscript
        count = obj.manusermons.all().count() # 
        
        # Handle empty origin fields
        origin = None if obj.origin == None else obj.origin.name
        
        # Retrieve all provenances for each manuscript
        qs_prov = obj.manuscripts_provenances.all()
        
        # Iterate through the queryset, place name and location 
        # for each provenance together 
        prov_texts = []
        for prov in qs_prov:
            prov = prov.provenance
            prov_text = prov.name
            if prov.location:
                prov_text = "{} ({})".format(prov_text, prov.location.name)
            prov_texts.append(prov_text)
        # Join all provenances together
        provenance = ", ".join(prov_texts)
        
        # Store all relevant items in a dictionary and append to the list TH: let op, link lib and city
        name = "" if obj.name == None else obj.name         
        idno = "" if obj.idno == None else obj.idno
        yearstart = "" if obj.yearstart == None else obj.yearstart
        yearfinish = "" if obj.yearfinish == None else obj.yearfinish
        libname = "" if obj.library == None else obj.library.name
        city = "" if obj.library == None or obj.library.city == None else obj.library.city.name
        
        item = dict(name=name, idno=idno, yearstart=yearstart, yearfinish=yearfinish,
                stype=obj.get_stype_display(), libname=libname, city=city, origin=origin, provenance=provenance,
                count=count)
        pdf_list_temp.append(item)
             
    # Sort the list on city and yearstart
    pdf_list_sorted = sorted(pdf_list_temp, key=itemgetter('city', 'yearstart')) 
        
    # Create five strings and add to pdf_list (to be processed in create_pdf_passim)
    pdf_list=[]
    for dict_item in pdf_list_sorted:
       
       # The first string contains the name of the city, library and id code of the manuscript     
       string_1 = dict_item['city'] + ", "+ dict_item['libname'] + ", "+ dict_item['idno']
       
       # The second string contains the start and end year of the manuscript and the number of items of the manuscript
       string_2 = 'Date: ' + str(dict_item['yearstart']) + "-" + str(dict_item['yearfinish']) + ', items: ' + str(dict_item['count'])
       
       # The third string contains the status of the manuscript: manual, imported or edited
       string_3 = 'Status: ' + dict_item['stype']
       
       # The fourth string contains the origin of the manuscript
       if dict_item['origin'] == None:
          origin = ""
       else:
          origin = dict_item['origin']
              
       string_4 = 'Origin: ' + origin
        
       # The fifth string contains the provenances of the manuscript
       if dict_item['provenance'] == None:
          provenance = ""
       else:
          provenance = dict_item['provenance']

       string_5 = 'Provenances: '+ provenance
       
       # The strings are combined into one with markddown line breaks so that each string is placed on a new line in the pdf
       combined = string_1 + "<br />" + string_2 + "<br />" + string_3 + "<br />" + string_4 + "<br />" + string_5
       
       # The new combined strings are placed in a new list, to be used in the create_pdf_passim function.        
       pdf_list.append(combined)

    # Call create_pdf_passim function with arguments  
    response = create_pdf_passim(Title, pageinfo, filename, pdf_list)
  
    # And return the pdf
    return response

# ============== NOTE: superseded by the READER app ===================
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
    if request.user.is_authenticated and request.method == 'POST' and user_is_ingroup(request, app_uploader):
    
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
    if request.user.is_authenticated and request.method == 'POST' and user_is_ingroup(request, app_uploader):

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

def search_ecodex(request):
    arErr = []
    error_list = []
    data = {'status': 'ok', 'html': ''}
    username = request.user.username
    errHandle = ErrHandle()

    # Check if the user is authenticated and if it is POST
    if request.user.is_authenticated and request.method == 'POST' and user_is_ingroup(request, app_editor):
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

# ============== NOTE: end of READER app superseded material ==========

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

    if request.user.is_authenticated and request.method == 'POST' and user_is_ingroup(request, app_uploader):

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
def get_countries(request):
    """Get a list of countries for autocomplete"""

    data = 'fail'
    method = "useLocation"
    if request.is_ajax():
        oErr = ErrHandle()
        try:
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
        except:
            msg = oErr.get_error_message()
            oErr.DoError("get_countries")
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
        oErr = ErrHandle()
        try:
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
        except:
            msg = oErr.get_error_message()
            oErr.DoError("get_cities")
    else:
        data = "Request is not ajax"
    mimetype = "application/json"
    return HttpResponse(data, mimetype)
    
@csrf_exempt
def get_libraries(request):
    """Get a list of libraries for autocomplete"""

    data = 'fail'
    if request.is_ajax():
        oErr = ErrHandle()
        try:
            # Get the user-specified 'country' and 'city' strings
            country = request.GET.get('country', "")
            if country == "": country = request.GET.get('country_ta', "")
            city = request.GET.get("city", "")
            if city == "": city = request.GET.get('city_ta', "")
            lib = request.GET.get("library", "")
            if lib == "": lib = request.GET.get('libname_ta', "")

            # build the query
            lstQ = []
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
            libraries = Library.objects.filter(*lstQ).order_by('name').values('name','id') 
            results = []
            for co in libraries:
                co_json = {'name': co['name'], 'id': co['id'] }
                results.append(co_json)
            data = json.dumps(results)
        except:
            msg = oErr.get_error_message()
            oErr.DoError("get_libraries")
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

@csrf_exempt
def get_locations(request):
    """Get a list of location names for autocomplete"""

    data = 'fail'
    if request.is_ajax():
        oErr = ErrHandle()
        try:
            sName = request.GET.get('name', '')
            lstQ = []
            lstQ.append(Q(name__icontains=sName))
            locations = Location.objects.filter(*lstQ).order_by('name').values('name', 'loctype__name', 'id')
            results = []
            for co in locations:
                # name = "{} ({})".format(co['name'], co['loctype__name'])
                name = co['name']
                co_json = {'name': name, 'id': co['id'], 'loctype': co['loctype__name'] }
                results.append(co_json)
            data = json.dumps(results)
        except:
            msg = oErr.get_error_message()
            oErr.DoError("get_locations")
    else:
        data = "Request is not ajax"
    mimetype = "application/json"
    return HttpResponse(data, mimetype)

@csrf_exempt
def get_litref(request):
    """Get ONE particular short representation of a litref"""
    
    data = 'fail'
    if request.is_ajax():
        oErr = ErrHandle()
        try:
            sId = request.GET.get('id', '')
            co_json = {'id': sId}
            lstQ = []
            lstQ.append(Q(id=sId))
            litref = Litref.objects.filter(Q(id=sId)).first()
            if litref:
                short = litref.get_short()
                co_json['name'] = short
            data = json.dumps(co_json)
        except:
            msg = oErr.get_error_message()
            oErr.DoError("get_litref")
    else:
        data = "Request is not ajax"
    mimetype = "application/json"
    return HttpResponse(data, mimetype)

@csrf_exempt
def get_litrefs(request):
    """Get a list of literature references for autocomplete"""
    
    data = 'fail'
    if request.is_ajax():
        oErr = ErrHandle()
        try:
            sName = request.GET.get('name', '')
            lstQ = []
            lstQ.append(Q(full__icontains=sName)|Q(short__icontains=sName))
            litrefs = Litref.objects.filter(*lstQ).order_by('short').values('full', 'short', 'id')
            results = [] 
            for co in litrefs:
                name = "{} {}".format(co['full'], co['short'])
                co_json = {'name': name, 'id': co['id'] }
                results.append(co_json)
            data = json.dumps(results)
        except:
            msg = oErr.get_error_message()
            oErr.DoError("get_litrefs")
    else:
        data = "Request is not ajax"
    mimetype = "application/json"
    return HttpResponse(data, mimetype)

@csrf_exempt
def get_sg(request):
    """Get ONE particular short representation of a SG"""
    
    data = 'fail'
    if request.is_ajax():
        oErr = ErrHandle()
        try:
            sId = request.GET.get('id', '')
            co_json = {'id': sId}
            lstQ = []
            lstQ.append(Q(id=sId))
            sg = SermonGold.objects.filter(Q(id=sId)).first()
            if sg:
                short = sg.get_label()
                co_json['name'] = short
            data = json.dumps(co_json)
        except:
            msg = oErr.get_error_message()
            oErr.DoError("get_sg")
    else:
        data = "Request is not ajax"
    mimetype = "application/json"
    return HttpResponse(data, mimetype)

@csrf_exempt
def get_sglink(request):
    """Get ONE particular short representation of a *link* to a SG"""
    
    data = 'fail'
    if request.is_ajax():
        oErr = ErrHandle()
        try:
            sId = request.GET.get('id', '')
            co_json = {'id': sId}
            lstQ = []
            lstQ.append(Q(id=sId))
            sg = SermonDescrGold.objects.filter(Q(id=sId)).first()
            if sg:
                short = sg.get_label()
                co_json['name'] = short
            data = json.dumps(co_json)
        except:
            msg = oErr.get_error_message()
            oErr.DoError("get_sglink")
    else:
        data = "Request is not ajax"
    mimetype = "application/json"
    return HttpResponse(data, mimetype)

@csrf_exempt
def get_ssg(request):
    """Get ONE particular short representation of a SSG"""
    
    data = 'fail'
    if request.is_ajax():
        oErr = ErrHandle()
        try:
            sId = request.GET.get('id', '')
            co_json = {'id': sId}
            lstQ = []
            lstQ.append(Q(id=sId))
            ssg = EqualGold.objects.filter(Q(id=sId)).first()
            if ssg:
                short = ssg.get_short()
                co_json['name'] = short
            data = json.dumps(co_json)
        except:
            msg = oErr.get_error_message()
            oErr.DoError("get_ssg")
    else:
        data = "Request is not ajax"
    mimetype = "application/json"
    return HttpResponse(data, mimetype)

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
            items = list(items.values("code", "id"))

            # OLD METHOD items = items.values_list('code', "id")
            results = []
            for co in items:
                # OLD METHOD co_json = {'name': co.code, 'id': co.id }
                co_json = {'name': co["code"], 'id': co["id"] }
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
def get_sermosig(request):
    """Get the correct GOLD signature, given a SERMON signature"""
    
    data = 'fail'
    if request.is_ajax():
        oErr = ErrHandle()
        try:
            sId = request.GET.get('id', '')
            co_json = {'id': sId}
            sermosig = SermonSignature.objects.filter(Q(id=sId)).first()
            if sermosig:
                short = sermosig.gsig.code
                co_json['name'] = short
            data = json.dumps(co_json)
        except:
            msg = oErr.get_error_message()
            oErr.DoError("get_sermosig")
    else:
        data = "Request is not ajax"
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

@csrf_exempt
def get_collections(request):
    """Get a list of collections for autocomplete"""

    oErr = ErrHandle()
    try:
        data = 'fail'
        if request.is_ajax():
            # Get the complete code line, which could use semicolon-separation
            coll_line = request.GET.get("name", "")
            coll_list = coll_line.split(";")
            col = "" if len(coll_list) == 0 else coll_list[-1].strip()
            lstQ = []
            lstQ.append(Q(name__icontains=col))
            items = Collection.objects.filter(*lstQ).order_by("name").distinct()
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
def get_gold(request, pk=None):
    """Get details of one particular gold sermon"""

    oErr = ErrHandle()
    data = {'status': 'fail'}
    fields = ['author', 'incipit', 'explicit', 'critlinks', 'bibliography' ]
    try:
        if request.is_ajax() and user_is_authenticated(request):
            # Get the id of the gold sermon
            qd = request.GET if request.method == "GET" else request.POST
            goldid = qd.get("goldid", "")
            bFound = False
            if goldid == "" and pk != None:
                obj = SermonGold.objects.filter(id=pk).first()
                bFound = True
            else:
                signature = Signature.objects.filter(id=goldid).first()
                if signature==None:
                    data['msg'] = "Signature not found"
                    data['status'] = "error"
                else:
                    obj = signature.gold
                    bFound = True
            if obj == None:
                data['msg'] = "Gold not found"
                data['status'] = "error"
            elif bFound:
                # Copy all relevant information
                info = {}
                d = model_to_dict(obj)
                for field in fields:
                    info[field] = d[field]  
                # Add the authorname
                authorname = ""
                if obj.author != None:
                    authorname = obj.author.name                  
                info['authorname'] = authorname

                # Copy keywords
                info['keywords'] = [x['id'] for x in obj.keywords.all().values('id')]

                # Copy signatures
                info['signatures'] = [x['id'] for x in obj.goldsignatures.all().values('id')]

                data['data'] = info

                data['status'] = "ok"
        else:
            data['msg'] = "Request is not ajax"
            data['status'] = "error"
    except: 
        msg = oErr.get_error_message()
        data['msg'] = msg
        data['status'] = "error"
    mimetype = "application/json"
    return HttpResponse(json.dumps(data), mimetype)

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
    previous = None         # Return to this
    bDebug = False          # Debugging information
    redirectpage = ""       # Where to redirect to
    data = {'status': 'ok', 'html': ''}       # Create data to be returned    
    
    def post(self, request, pk=None):
        # A POST request means we are trying to SAVE something
        self.initializations(request, pk)
        # Initialize typeahead list
        lst_typeahead = []

        # Explicitly set the status to OK
        self.data['status'] = "ok"
        
        if self.checkAuthentication(request):
            # Build the context
            context = dict(object_id = pk, savedate=None)
            context['authenticated'] = user_is_authenticated(request)
            context['is_app_uploader'] = user_is_ingroup(request, app_uploader)
            context['is_app_editor'] = user_is_ingroup(request, app_editor)

            # Action depends on 'action' value
            if self.action == "":
                if self.bDebug: self.oErr.Status("ResearchPart: action=(empty)")
                # Walk all the forms for preparation of the formObj contents
                for formObj in self.form_objects:
                    # Are we SAVING a NEW item?
                    if self.add:
                        # We are saving a NEW item
                        formObj['forminstance'] = formObj['form'](request.POST, prefix=formObj['prefix'])
                        formObj['action'] = "new"
                    else:
                        # We are saving an EXISTING item
                        # Determine the instance to be passed on
                        instance = self.get_instance(formObj['prefix'])
                        # Make the instance available in the form-object
                        formObj['instance'] = instance
                        # Get an instance of the form
                        formObj['forminstance'] = formObj['form'](request.POST, prefix=formObj['prefix'], instance=instance)
                        formObj['action'] = "change"

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
                                # Log the SAVE action
                                details = {'id': instance.id}
                                if formObj['forminstance'].changed_data != None:
                                    details['changes'] = action_model_changes(formObj['forminstance'], instance)
                                if 'action' in formObj: details['savetype'] = formObj['action']
                                Action.add(request.user.username, self.MainModel.__name__, "save", json.dumps(details))
                                # Set the context
                                context['savedate']="saved at {}".format(get_current_datetime().strftime("%X"))
                                # Put the instance in the form object
                                formObj['instance'] = instance
                                # Store the instance id in the data
                                self.data[prefix + '_instanceid'] = instance.id
                                # Any action after saving this form
                                self.after_save(prefix, instance=instance, form=formObj['forminstance'])
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

                            # x = json.dumps(sorted(self.qd.items(), key=lambda kv: kv[0]), indent=2)
                    # Add instance to the context object
                    context[prefix + "Form"] = formObj['forminstance']
                    # Get any possible typeahead parameters
                    lst_form_ta = getattr(formObj['forminstance'], "typeaheads", None)
                    if lst_form_ta != None:
                        for item in lst_form_ta:
                            lst_typeahead.append(item)
                # Walk all the formset objects
                for formsetObj in self.formset_objects:
                    prefix  = formsetObj['prefix']
                    if self.can_process_formset(prefix):
                        formsetClass = formsetObj['formsetClass']
                        form_kwargs = self.get_form_kwargs(prefix)
                        if self.add:
                            # Saving a NEW item
                            if 'initial' in formsetObj:
                                formset = formsetClass(request.POST, request.FILES, prefix=prefix, initial=formsetObj['initial'], form_kwargs = form_kwargs)
                            else:
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
                        # Make sure we know what we are dealing with
                        itemtype = "form_{}".format(prefix)
                        # Adapt the formset contents only, when it is NOT READONLY
                        if not formsetObj['readonly']:
                            # Is the formset valid?
                            if formset.is_valid():
                                # Possibly handle the clean() for this formset
                                if 'clean' in formsetObj:
                                    # Call the clean function
                                    self.clean(formset, prefix)
                                has_deletions = False
                                if len(self.arErr) == 0:
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
                                                        # Log the delete action
                                                        details = {'id': form.instance.id}
                                                        Action.add(request.user.username, itemtype, "delete", json.dumps(details))
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
                                                    if has_changed and len(self.arErr) == 0: 
                                                        # Save the instance
                                                        sub_instance.save()
                                                        # Adapt the last save time
                                                        context['savedate']="saved at {}".format(get_current_datetime().strftime("%X"))
                                                        # Log the delete action
                                                        details = {'id': sub_instance.id}
                                                        if form.changed_data != None:
                                                            details['changes'] = action_model_changes(form, sub_instance)
                                                        Action.add(request.user.username, itemtype, "save", json.dumps(details))
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
                    # Get any possible typeahead parameters
                    lst_formset_ta = getattr(formset.form, "typeaheads", None)
                    if lst_formset_ta != None:
                        for item in lst_formset_ta:
                            lst_typeahead.append(item)
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
                    # Log the delete action
                    details = {'id': self.obj.id}
                    Action.add(request.user.username, self.MainModel.__name__, "delete", json.dumps(details))
                    # We have permission to delete the instance
                    self.obj.delete()
                    context['deleted'] = True

            # Allow user to add to the context
            context = self.add_to_context(context)
            
            # Possibly add data from [context.data]
            if 'data' in context:
                for k,v in context['data'].items():
                    self.data[k] = v

            # First look at redirect page
            self.data['redirecturl'] = ""
            if self.redirectpage != "":
                self.data['redirecturl'] = self.redirectpage
            # Check if 'afternewurl' needs adding
            # NOTE: this should only be used after a *NEW* instance has been made -hence the self.add check
            if 'afternewurl' in context and self.add:
                self.data['afternewurl'] = context['afternewurl']
            else:
                self.data['afternewurl'] = ""
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

            # Set any possible typeaheads
            self.data['typeaheads'] = lst_typeahead

            # Get the HTML response
            if len(self.arErr) > 0:
                if self.template_err_view != None:
                     # Create a list of errors
                    self.data['err_view'] = render_to_string(self.template_err_view, context, request)
                else:
                    self.data['error_list'] = error_list
                    self.data['errors'] = self.arErr
                self.data['html'] = ''
                # We may not redirect if there is an error!
                self.data['redirecturl'] = ''
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
        # Initialize typeahead list
        lst_typeahead = []

        # Continue if authorized
        if self.checkAuthentication(request):
            context = dict(object_id = pk, savedate=None)
            context['prevpage'] = self.previous
            context['authenticated'] = user_is_authenticated(request)
            context['is_app_uploader'] = user_is_ingroup(request, app_uploader)
            context['is_app_editor'] = user_is_ingroup(request, app_editor)
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
                # Get any possible typeahead parameters
                lst_form_ta = getattr(formObj['forminstance'], "typeaheads", None)
                if lst_form_ta != None:
                    for item in lst_form_ta:
                        lst_typeahead.append(item)
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
                    # Possibly initial (default) values
                    if 'initial' in formsetObj:
                        initial = formsetObj['initial']
                    else:
                        initial = None
                    # show the data belonging to the current [obj]
                    instance = self.get_instance(prefix)
                    qs = self.get_queryset(prefix)
                    if qs == None:
                        formset = formsetClass(prefix=prefix, instance=instance, form_kwargs=form_kwargs)
                    else:
                        formset = formsetClass(prefix=prefix, instance=instance, queryset=qs, initial=initial, form_kwargs=form_kwargs)
                # Get any possible typeahead parameters
                lst_formset_ta = getattr(formset.form, "typeaheads", None)
                if lst_formset_ta != None:
                    for item in lst_formset_ta:
                        lst_typeahead.append(item)
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

            # Set any possible typeaheads
            self.data['typeaheads'] = json.dumps(lst_typeahead)
            
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

    def after_save(self, prefix, instance=None, form=None):
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
    form_objects = []       # List of form objects
    afternewurl = ""        # URL to move to after adding a new item
    prefix = ""             # The prefix for the one (!) form we use
    previous = None         # Start with empty previous page
    title = ""              # The title to be passed on with the context
    titlesg = None          # Alternative title in singular
    rtype = "json"          # JSON response (alternative: html)
    prefix_type = ""        # Whether the adapt the prefix or not ('simple')
    mForm = None            # Model form
    basic_name = None
    basic_name_prefix = ""
    do_not_save = False
    newRedirect = False     # Redirect the page name to a correct one after creating
    redirectpage = ""       # Where to redirect to
    add = False             # Are we adding a new record or editing an existing one?
    is_basic = False        # Is this a basic details/edit view?
    lst_typeahead = []

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

                # Set any possible typeaheads
                data['typeaheads'] = self.lst_typeahead

                response = JsonResponse(data)
            else:
                response = reverse('nlogin')
        else:
            context = self.get_context_data(object=self.object)

            if self.is_basic and self.template_name == "":
                if self.rtype == "json":
                    self.template_name = "seeker/generic_edit.html"
                else:
                    self.template_name = "seeker/generic_details.html"
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
                # Set any possible typeaheads
                data['typeaheads'] = self.lst_typeahead
                response = JsonResponse(data)
            elif self.redirectpage != "":
                return redirect(self.redirectpage)
            else:
                # Set any possible typeaheads
                context['typeaheads'] = json.dumps(self.lst_typeahead)
                # This takes self.template_name...
                sHtml = render_to_string(self.template_name, context, request)
                sHtml = sHtml.replace("\ufeff", "")
                response = HttpResponse(sHtml)
                # response = self.render_to_response(context)

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

            if self.is_basic and self.template_name == "":
                if self.rtype == "json":
                    self.template_name = "seeker/generic_edit.html"
                else:
                    self.template_name = "seeker/generic_details.html"

            if self.rtype == "json":
                if self.template_post == "": self.template_post = self.template_name
                response = render_to_string(self.template_post, context, request)
                response = response.replace("\ufeff", "")
                data['html'] = response
                # Set any possible typeaheads
                data['typeaheads'] = self.lst_typeahead
                response = JsonResponse(data)
            elif self.newRedirect and self.redirectpage != "":
                # Redirect to this page
                return redirect(self.redirectpage)
            else:
                # Set any possible typeaheads
                context['typeaheads'] = json.dumps(self.lst_typeahead)
                # This takes self.template_name...
                response = self.render_to_response(context)
        else:
            data['html'] = "(No authorization)"
            data['status'] = "error"
            response = JsonResponse(data)

        # Return the response
        return response

    def initializations(self, request, pk):
        # Store the previous page
        # self.previous = get_previous_page(request)

        self.lst_typeahead = []

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
        
        # Possibly perform custom initializations
        self.custom_init(self.object)
        
    def custom_init(self, instance):
        pass

    def before_delete(self, instance):
        """Anything that needs doing before deleting [instance] """
        return True, "" 

    def after_new(self, form, instance):
        """Action to be performed after adding a new item"""
        return True, "" 

    def before_save(self, form, instance):
        """Action to be performed after saving an item preliminarily, and before saving completely"""
        return True, "" 

    def after_save(self, form, instance):
        """Actions to be performed after saving"""
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
        context['is_app_uploader'] = user_is_ingroup(self.request, app_uploader)
        context['is_app_editor'] = user_is_ingroup(self.request, app_editor)
        # context['prevpage'] = get_previous_page(self.request) # self.previous
        context['afternewurl'] = ""

        # Possibly define where a listview is
        classname = self.model._meta.model_name
        if self.basic_name == None or self.basic_name == "":
            if self.basic_name_prefix == "":
                self.basic_name = classname
            else:
                self.basic_name = "{}{}".format(self.basic_name_prefix, self.prefix)
        basic_name = self.basic_name
        listviewname = "{}_list".format(basic_name)
        try:
            context['listview'] = reverse(listviewname)
        except:
            context['listview'] = reverse('home')

        if self.is_basic:
            context['afterdelurl'] = context['listview']

        # Get the parameters passed on with the GET or the POST request
        get = self.request.GET if self.request.method == "GET" else self.request.POST
        initial = get.copy()
        self.qd = initial

        self.bHasFormInfo = (len(self.qd) > 0)

        # Set the title of the application
        context['title'] = self.title

        # Get the instance
        instance = self.object

        frm = self.prepare_form(instance, context, initial)

        if frm:

            if instance == None:
                instance = frm.instance
                self.object = instance

            # Walk all the formset objects
            bFormsetChanged = False
            for formsetObj in self.formset_objects:
                formsetClass = formsetObj['formsetClass']
                prefix  = formsetObj['prefix']
                formset = None
                form_kwargs = self.get_form_kwargs(prefix)
                if 'noinit' in formsetObj and formsetObj['noinit'] and not self.add:
                    # Only process actual changes!!
                    if self.request.method == "POST" and self.request.POST:

                        #if self.add:
                        #    # Saving a NEW item
                        #    if 'initial' in formsetObj:
                        #        formset = formsetClass(self.request.POST, self.request.FILES, prefix=prefix, initial=formsetObj['initial'], form_kwargs = form_kwargs)
                        #    else:
                        #        formset = formsetClass(self.request.POST, self.request.FILES, prefix=prefix, form_kwargs = form_kwargs)
                        #else:
                        #    # Get a formset including any stuff from POST
                        #    formset = formsetClass(self.request.POST, prefix=prefix, instance=instance)

                        # Get a formset including any stuff from POST
                        formset = formsetClass(self.request.POST, prefix=prefix, instance=instance)
                        # Process this formset
                        self.process_formset(prefix, self.request, formset)
                        
                        # Process all the correct forms in the formset
                        for subform in formset:
                            if subform.is_valid():
                                subform.save()
                                # Signal that the *FORM* needs refreshing, because the formset changed
                                bFormsetChanged = True

                        if formset.is_valid():
                            # Load an explicitly empty formset
                            formset = formsetClass(initial=[], prefix=prefix, form_kwargs=form_kwargs)
                        else:
                            # Retain the original formset, that now contains the error specifications per form
                            # But: do *NOT* add an additional form to it
                            pass

                    else:
                        # All other cases: Load an explicitly empty formset
                        formset = formsetClass(initial=[], prefix=prefix, form_kwargs=form_kwargs)
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
                # Get any possible typeahead parameters
                lst_formset_ta = getattr(formset.form, "typeaheads", None)
                if lst_formset_ta != None:
                    for item in lst_formset_ta:
                        self.lst_typeahead.append(item)

            # Essential formset information
            for formsetObj in self.formset_objects:
                prefix = formsetObj['prefix']
                if 'fields' in formsetObj: context["{}_fields".format(prefix)] = formsetObj['fields']
                if 'linkfield' in formsetObj: context["{}_linkfield".format(prefix)] = formsetObj['linkfield']

            # Check if the formset made any changes to the form
            if bFormsetChanged:
                # OLD: 
                frm = self.prepare_form(instance, context)

            # Put the form and the formset in the context
            context['{}Form'.format(self.prefix)] = frm
            context['basic_form'] = frm
            context['instance'] = instance
            context['options'] = json.dumps({"isnew": (instance == None)})

            # Possibly define the admin detailsview
            if instance:
                admindetails = "admin:seeker_{}_change".format(classname)
                try:
                    context['admindetails'] = reverse(admindetails, args=[instance.id])
                except:
                    pass
            context['modelname'] = self.model._meta.object_name
            context['titlesg'] = self.titlesg if self.titlesg else self.title if self.title != "" else basic_name.capitalize()

            # Make sure we have a url for editing
            if instance and instance.id:
                # There is a details and edit url
                context['editview'] = reverse("{}_edit".format(basic_name), kwargs={'pk': instance.id})
                context['detailsview'] = reverse("{}_details".format(basic_name), kwargs={'pk': instance.id})
            # Make sure we have an url for new
            context['addview'] = reverse("{}_details".format(basic_name))

        # Determine breadcrumbs and previous page
        if self.is_basic:
            title = self.title if self.title != "" else basic_name
            if self.rtype == "json":
                # This is the EditView
                context['breadcrumbs'] = get_breadcrumbs(self.request, "{} edit".format(title), False)
                prevpage = reverse('home')
                context['prevpage'] = prevpage
            else:
                # This is DetailsView
                # Process this visit and get the new breadcrumbs object
                prevpage = context['listview']
                context['prevpage'] = prevpage
                crumbs = []
                crumbs.append([title, prevpage])
                current_name = title if instance else "{} (new)".format(title)
                context['breadcrumbs'] = get_breadcrumbs(self.request, current_name, True, crumbs)

        # Possibly add to context by the calling function
        context = self.add_to_context(context, instance)

        # fill in the form values
        if frm and 'mainitems' in context:
            for mobj in context['mainitems']:
                # Check for possible form field information
                if 'field_key' in mobj: mobj['field_key'] = frm[mobj['field_key']]
                if 'field_ta' in mobj: mobj['field_ta'] = frm[mobj['field_ta']]
                if 'field_list' in mobj: mobj['field_list'] = frm[mobj['field_list']]

        # Define where to go to after deletion
        if 'afterdelurl' not in context or context['afterdelurl'] == "":
            context['afterdelurl'] = get_previous_page(self.request)

        # Return the calculated context
        return context

    def prepare_form(self, instance, context, initial=[]):
        # Initialisations
        bNew = False
        mForm = self.mForm
        oErr = ErrHandle()

        # Determine the prefix
        if self.prefix_type == "":
            # Old approach:
            #id = "n" if instance == None else instance.id
            #prefix = "{}-{}".format(self.prefix, id)

            # new approach
            if instance == None:
                prefix = self.prefix
            else:
                prefix = "{}-{}".format(self.prefix, instance.id)
        else:
            prefix = self.prefix

        # Check if this is a POST or a GET request
        if self.request.method == "POST" and not self.do_not_save:
            # Determine what the action is (if specified)
            action = ""
            if 'action' in initial: action = initial['action']
            if action == "delete":
                # The user wants to delete this item
                try:
                    bResult, msg = self.before_delete(instance)
                    if bResult:
                        # Log the DELETE action
                        details = {'id': instance.id}
                        Action.add(self.request.user.username, instance.__class__.__name__, "delete", json.dumps(details))
                        # Remove this sermongold instance
                        instance.delete()
                    else:
                        # Removing is not possible
                        context['errors'] = {'delete': msg }
                except:
                    msg = oErr.get_error_message()
                    # Create an errors object
                    context['errors'] = {'delete':  msg }

                if 'afterdelurl' not in context or context['afterdelurl'] == "":
                    context['afterdelurl'] = get_previous_page(self.request, True)

                # Make sure we are returning JSON
                self.rtype = "json"

                # Possibly add to context by the calling function
                context = self.add_to_context(context, instance)

                # No need to retern a form anymore - we have been deleting
                return None
            
            # All other actions just mean: edit or new and send back
            # Make instance available
            context['object'] = instance
            self.object = instance
            
            # Do we have an existing object or are we creating?
            if instance == None:
                # Saving a new item
                frm = mForm(initial, prefix=prefix)
                bNew = True
                self.add = True
            elif len(initial) == 0:
                # Create a completely new form, on the basis of the [instance] only
                frm = mForm(prefix=prefix, instance=instance)
            else:
                # Editing an existing one
                frm = mForm(initial, prefix=prefix, instance=instance)
            # Both cases: validation and saving
            if frm.is_valid():
                # The form is valid - do a preliminary saving
                obj = frm.save(commit=False)
                # Any checks go here...
                bResult, msg = self.before_save(form=frm, instance=obj)
                if bResult:
                    # Now save it for real
                    obj.save()
                    # Log the SAVE action
                    details = {'id': obj.id}
                    details["savetype"] = "new" if bNew else "change"
                    if frm.changed_data != None and len(frm.changed_data) > 0:
                        details['changes'] = action_model_changes(frm, obj)
                    Action.add(self.request.user.username, obj.__class__.__name__, "save", json.dumps(details))

                    # Make sure the form is actually saved completely
                    frm.save()
                    instance = obj

                    # Any action(s) after saving
                    bResult, msg = self.after_save(frm, obj)
                else:
                    context['errors'] = {'save': msg }
            else:
                # We need to pass on to the user that there are errors
                context['errors'] = frm.errors

            # Check if this is a new one
            if bNew:
                if self.is_basic:
                    self.afternewurl = context['listview']
                    if self.rtype == "html":
                        # Make sure we do a page redirect
                        self.newRedirect = True
                        self.redirectpage = reverse("{}_details".format(self.basic_name), kwargs={'pk': instance.id})
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
            if frm.is_valid():
                iOkay = 1
            # Walk all the form objects
            for formObj in self.form_objects:
                formClass = formObj['form']
                prefix = formObj['prefix']
                # This is only for *NEW* forms (right now)
                form = formClass(prefix=prefix)
                context[prefix + "Form"] = form
                # Get any possible typeahead parameters
                lst_form_ta = getattr(formObj['forminstance'], "typeaheads", None)
                if lst_form_ta != None:
                    for item in lst_form_ta:
                        self.lst_typeahead.append(item)

        # Get any possible typeahead parameters
        if frm != None:
            lst_form_ta = getattr(frm, "typeaheads", None)
            if lst_form_ta != None:
                for item in lst_form_ta:
                    self.lst_typeahead.append(item)
        # Return the form we made
        return frm
    

class BasicListView(ListView):
    """Basic listview
    
    This listview inherits the standard listview and adds a few automatic matters
    """

    paginate_by = 15
    entrycount = 0
    qd = None
    bFilter = False
    basketview = False
    template_name = 'seeker/basic_list.html'
    bHasParameters = False
    bUseFilter = False
    new_button = True
    initial = None
    listform = None
    has_select2 = False
    plural_name = ""
    sg_name = ""
    basic_name = ""
    basic_name_prefix = ""
    basic_edit = ""
    basic_details = ""
    prefix = ""
    order_default = []
    order_cols = []
    order_heads = []
    filters = []
    searches = []
    downloads = []
    custombuttons = []
    list_fields = []
    uploads = []
    delete_line = False
    lst_typeaheads = []
    sort_order = ""
    page_function = None

    def initializations(self):
        return None

    def get_context_data(self, **kwargs):
        # Call the base implementation first to get a context
        context = super(BasicListView, self).get_context_data(**kwargs)

        oErr = ErrHandle()

        # Allo user to specify alterations to the class instance
        self.initializations()

        # Get parameters for the search
        if self.initial == None:
            initial = self.request.POST if self.request.POST else self.request.GET
        else:
            initial = self.initial

        # Need to load the correct form
        if self.listform:
            frm = self.listform(initial, prefix=self.prefix)
            if frm.is_valid():
                context['{}Form'.format(self.prefix)] = frm
                # Get any possible typeahead parameters
                lst_form_ta = getattr(frm, "typeaheads", None)
                if lst_form_ta != None:
                    for item in lst_form_ta:
                        self.lst_typeaheads.append(item)

            if self.has_select2:
                context['has_select2'] = True
            context['listForm'] = frm

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
        if self.page_function:
            context['page_function'] = self.page_function

        # Set the page number if needed
        if 'page_obj' in context and 'page' in initial and initial['page'] != "":
            # context['page_obj'].number = initial['page']
            page_num = int(initial['page'])
            context['page_obj'] = context['paginator'].page( page_num)
            # Make sure to adapt the object_list
            context['object_list'] = context['page_obj']

        # Set the title of the application
        if self.plural_name =="":
            self.plural_name = str(self.model._meta.verbose_name_plural)
        context['title'] = self.plural_name
        if self.basic_name == "":
            if self.basic_name_prefix == "":
                self.basic_name = str(self.model._meta.model_name)
            else:
                self.basic_name = "{}{}".format(self.basic_name_prefix, self.prefix)
        context['titlesg'] = self.sg_name if self.sg_name != "" else self.basic_name.capitalize()
        context['basic_name'] = self.basic_name
        context['basic_add'] = reverse("{}_details".format(self.basic_name))
        context['basic_list'] = reverse("{}_list".format(self.basic_name))
        context['basic_edit'] = self.basic_edit if self.basic_edit != "" else "{}_edit".format(self.basic_name)
        context['basic_details'] = self.basic_details if self.basic_details != "" else "{}_details".format(self.basic_name)

        # Make sure to transform the 'object_list' into a 'result_list'
        context['result_list'] = self.get_result_list(context['object_list'])

        context['sortOrder'] = self.sort_order

        context['new_button'] = self.new_button

        # Adapt possible downloads
        if len(self.downloads) > 0:
            for item in self.downloads:
                if 'url' in item and item['url'] != "" and "/" not in item['url']:
                    item['url'] = reverse(item['url'])
            context['downloads'] = self.downloads

        # Specify possible upload
        if len(self.uploads) > 0:
            for item in self.uploads:
                if 'url' in item and item['url'] != "" and "/" not in item['url']:
                    item['url'] = reverse(item['url'])
            context['uploads'] = self.uploads

        # Custom buttons
        if len(self.custombuttons) > 0:
            for item in self.custombuttons:
                if 'template_name' in item:
                    # get the code of the template
                    pass
            context['custombuttons'] = self.custombuttons

        # Delete button per line?
        if self.delete_line:
            context['delete_line'] = True

        # Make sure we pass on the ordered heads
        context['order_heads'] = self.order_heads
        context['has_filter'] = self.bFilter
        fsections = []
        # Adapt filters with the information from searches
        for section in self.searches:
            oFsection = {}
            bHasValue = False
            # Add filter section name
            section_name = section['section']
            if section_name != "" and section_name not in fsections:
                oFsection = dict(name=section_name, has_value=False)
                # fsections.append(dict(name=section_name))
            # Copy the relevant search filter
            for item in section['filterlist']:
                # Find the corresponding item in the filters
                id = "filter_{}".format(item['filter'])
                for fitem in self.filters:
                    if id == fitem['id']:
                        try:
                            fitem['search'] = item
                            # Add possible fields
                            if 'keyS' in item and item['keyS'] in frm.cleaned_data: 
                                fitem['keyS'] = frm[item['keyS']]
                                if fitem['keyS'].value(): bHasValue = True
                            if 'keyList' in item and item['keyS'] in frm.cleaned_data: 
                                fitem['keyList'] = frm[item['keyList']]
                                if fitem['keyList'].value(): bHasValue = True
                            if 'keyS' in item and item['keyS'] in frm.cleaned_data: 
                                if 'dbfield' in item and item['dbfield'] in frm.cleaned_data:
                                    fitem['dbfield'] = frm[item['dbfield']]
                                    if fitem['dbfield'].value(): bHasValue = True
                                elif 'fkfield' in item and item['fkfield'] in frm.cleaned_data:
                                    fitem['fkfield'] = frm[item['fkfield']]                                    
                                    if fitem['fkfield'].value(): bHasValue = True
                                else:
                                    # There is a keyS without corresponding fkfield or dbfield
                                    pass
                            break
                        except:
                            sMsg = oErr.get_error_message()
                            break
            if bHasValue: oFsection['has_value'] = True
            if oFsection != None: fsections.append(oFsection)

        # Make it available
        context['filters'] = self.filters
        context['fsections'] = fsections
        context['list_fields'] = self.list_fields

        # Add any typeaheads that should be initialized
        context['typeaheads'] = json.dumps( self.lst_typeaheads)

        # Check if user may upload
        context['is_authenticated'] = user_is_authenticated(self.request)
        context['authenticated'] = context['is_authenticated'] 
        context['is_app_uploader'] = user_is_ingroup(self.request, app_uploader)
        context['is_app_editor'] = user_is_ingroup(self.request, app_editor)

        # Process this visit and get the new breadcrumbs object
        prevpage = reverse('home')
        context['prevpage'] = prevpage
        context['breadcrumbs'] = get_breadcrumbs(self.request, self.plural_name, True)

        context['usebasket'] = self.basketview

        # Allow others to add to context
        context = self.add_to_context(context, initial)

        # Return the calculated context
        return context

    def add_to_context(self, context, initial):
        return context

    def get_result_list(self, obj_list):
        result_list = []
        # Walk all items in the object list
        for obj in obj_list:
            # Transform this object into a list of objects that can be shown
            result = dict(id=obj.id)
            fields = []
            for head in self.order_heads:
                fobj = dict(value="")
                fname = None
                if 'field' in head:
                    # This is a field that can be shown
                    fname = head['field']
                    default = "" if 'default' not in head else head['default']
                    value = getattr(obj, fname, default)
                    if not value is None:
                        fobj['value'] = value
                elif 'custom' in head:
                    # The user should provide a way to determine the value for this field
                    fvalue, ftitle = self.get_field_value(obj, head['custom'])
                    if not fvalue is None:
                        fobj['value']= fvalue
                    if ftitle != None:
                        fobj['title'] = ftitle
                    fname = head['custom']
                classes = []
                if fname != None: classes.append("{}-{}".format(self.basic_name, fname))
                if 'linkdetails' in head and head['linkdetails']: fobj['linkdetails'] = True
                if 'main' in head and head['main']:
                    fobj['styles'] = "width: 100%;"
                    fobj['main'] = True
                    if self.delete_line:
                        classes.append("ms editable")
                elif 'options' in head and len(head['options']) > 0:
                    options = head['options']
                    if 'delete' in options:
                        fobj['delete'] = True
                    fobj['styles'] = "width: {}px;".format(50 * len(options))
                    classes.append("tdnowrap")
                else:
                    fobj['styles'] = "width: 100px;"
                    classes.append("tdnowrap")
                if 'align' in head and head['align'] != "":
                    fobj['align'] = head['align'] 
                fobj['classes'] = " ".join(classes)
                fields.append(fobj)
            # Make the list of field-values available
            result['fields'] = fields
            # Add to the list of results
            result_list.append(result)
        return result_list

    def get_field_value(self, instance, custom):
        return "", ""

    def get_paginate_by(self, queryset):
        """
        Paginate by specified value in default class property value.
        """
        return self.paginate_by

    def get_basketqueryset(self):
        """User-specific function to get a queryset based on a basket"""
        return None

    def adapt_search(self, fields):
        return fields
  
    def get_queryset(self):
        # Get the parameters passed on with the GET or the POST request
        get = self.request.GET if self.request.method == "GET" else self.request.POST
        get = get.copy()
        self.qd = get

        self.bHasParameters = (len(get) > 0)
        bHasListFilters = False
        if self.bHasParameters:
            # y = [x for x in get ]
            bHasListFilters = len([x for x in get if self.prefix in x and get[x] != ""]) > 0
            if not bHasListFilters:
                self.basketview = ("usebasket" in get and get['usebasket'] == "True")

        # Get the queryset and the filters
        if self.basketview:
            self.basketview = True
            # We should show the contents of the basket
            # (1) Reset the filters
            for item in self.filters: item['enabled'] = False
            # (2) Indicate we have no filters
            self.bFilter = False
            # (3) Set the queryset -- this is listview-specific
            qs = self.get_basketqueryset()

            # Do the ordering of the results
            order = self.order_default
            qs, self.order_heads, colnum = make_ordering(qs, self.qd, order, self.order_cols, self.order_heads)
        elif self.bHasParameters or self.bUseFilter:
            self.basketview = False
            lstQ = []
            # Indicate we have no filters
            self.bFilter = False

            # Read the form with the information
            thisForm = self.listform(self.qd, prefix=self.prefix)

            if thisForm.is_valid():
                # Process the criteria for this form
                oFields = thisForm.cleaned_data

                # Allow user to adapt the list of search fields
                oFields = self.adapt_search(oFields)

                self.filters, lstQ, self.initial = make_search_list(self.filters, oFields, self.searches, self.qd)
                # Calculate the final qs
                if len(lstQ) == 0:
                    # Just show everything
                    qs = self.model.objects.all()
                else:
                    # There is a filter, so apply it
                    qs = self.model.objects.filter(*lstQ).distinct()
                    # Only set the [bFilter] value if there is an overt specified filter
                    for filter in self.filters:
                        if filter['enabled']:
                            self.bFilter = True
                            break
                    # OLD self.bFilter = True
            else:
                # Just show everything
                qs = self.model.objects.all().distinct()

            # Do the ordering of the results
            order = self.order_default
            qs, self.order_heads, colnum = make_ordering(qs, self.qd, order, self.order_cols, self.order_heads)
        else:
            self.basketview = False
            qs = self.model.objects.all().distinct()
            order = self.order_default
            qs, tmp_heads, colnum = make_ordering(qs, self.qd, order, self.order_cols, self.order_heads)
        self.sort_order = colnum

        # Determine the length
        self.entrycount = len(qs)

        # Return the resulting filtered and sorted queryset
        return qs

    def post(self, request, *args, **kwargs):
        return self.get(request, *args, **kwargs)
    

class LocationListView(ListView):
    """Listview of locations"""

    model = Location
    paginate_by = 15
    template_name = 'seeker/location_list.html'
    entrycount = 0

    def get_context_data(self, **kwargs):
        # Call the base implementation first to get a context
        context = super(LocationListView, self).get_context_data(**kwargs)

        # Get parameters
        initial = self.request.GET

        # Determine the count 
        context['entrycount'] = self.entrycount # self.get_queryset().count()

        # Set the prefix
        context['app_prefix'] = APP_PREFIX

        # Get parameters for the search
        initial = self.request.GET
        # The searchform is just a list form, but filled with the 'initial' parameters
        context['searchform'] = LocationForm(initial)

        # Make sure the paginate-values are available
        context['paginateValues'] = paginateValues

        if 'paginate_by' in initial:
            context['paginateSize'] = int(initial['paginate_by'])
        else:
            context['paginateSize'] = paginateSize

        # Set the title of the application
        context['title'] = "Passim location info"

        # Check if user may upload
        context['is_authenticated'] = user_is_authenticated(self.request)
        context['is_app_uploader'] = user_is_ingroup(self.request, app_uploader)
        context['is_app_editor'] = user_is_ingroup(self.request, app_editor)

        # Process this visit and get the new breadcrumbs object
        prevpage = reverse('home')
        context['prevpage'] = prevpage
        context['breadcrumbs'] = get_breadcrumbs(self.request, "Locations", True)

        # Return the calculated context
        return context

    def get_paginate_by(self, queryset):
        """
        Paginate by specified value in default class property value.
        """
        return self.paginate_by
  
    def get_queryset(self):
        # Get the parameters passed on with the GET or the POST request
        get = self.request.GET if self.request.method == "GET" else self.request.POST
        get = get.copy()
        self.get = get

        lstQ = []

        # Check for author [name]
        if 'name' in get and get['name'] != '':
            val = adapt_search(get['name'])
            # Search in both the name field
            lstQ.append(Q(name__iregex=val))

        # Check for location type
        if 'loctype' in get and get['loctype'] != '':
            val = get['loctype']
            # Search in both the name field
            lstQ.append(Q(loctype=val))

        # Calculate the final qs
        qs = Location.objects.filter(*lstQ).order_by('name').distinct()

        # Determine the length
        self.entrycount = len(qs)

        # Return the resulting filtered and sorted queryset
        return qs


class LocationDetailsView(PassimDetails):
    model = Location
    mForm = LocationForm
    template_name = 'seeker/location_details.html'
    prefix = 'loc'
    prefix_type = "simple"
    title = "LocationDetails"
    rtype = "html"

    def after_new(self, form, instance):
        """Action to be performed after adding a new item"""

        self.afternewurl = reverse('location_list')
        return True, "" 

    def add_to_context(self, context, instance):
        # Add the list of relations in which I am contained
        contained_locations = []
        if instance != None:
            contained_locations = instance.hierarchy(include_self=False)
        context['contained_locations'] = contained_locations

        # The standard information
        context['is_app_editor'] = user_is_ingroup(self.request, app_editor)
        # Process this visit and get the new breadcrumbs object
        prevpage = reverse('location_list')
        crumbs = []
        crumbs.append(['Locations', prevpage])
        current_name = "Location details"
        if instance:
            current_name = "Location [{}]".format(instance.name)
        context['prevpage'] = prevpage
        context['breadcrumbs'] = get_breadcrumbs(self.request, current_name, True, crumbs)
        return context


class LocationEdit(BasicPart):
    """The details of one location"""

    MainModel = Location
    template_name = 'seeker/location_edit.html'  
    title = "Location" 
    afternewurl = ""
    # One form is attached to this 
    prefix = "loc"
    form_objects = [{'form': LocationForm, 'prefix': prefix, 'readonly': False}]

    def before_save(self, prefix, request, instance = None, form = None):
        bNeedSaving = False
        if prefix == "loc":
            pass

        return bNeedSaving

    def after_save(self, prefix, instance = None, form = None):
        bStatus = True
        if prefix == "loc":
            # Check if there is a locationlist
            if 'locationlist' in form.cleaned_data:
                locationlist = form.cleaned_data['locationlist']

                # Get all the containers inside which [instance] is contained
                current_qs = Location.objects.filter(container_locrelations__contained=instance)
                # Walk the new list
                for item in locationlist:
                    #if item.id not in current_ids:
                    if item not in current_qs:
                        # Add it to the containers
                        LocationRelation.objects.create(contained=instance, container=item)
                # Update the current list
                current_qs = Location.objects.filter(container_locrelations__contained=instance)
                # Walk the current list
                remove_list = []
                for item in current_qs:
                    if item not in locationlist:
                        # Add it to the list of to-be-fremoved
                        remove_list.append(item.id)
                # Remove them from the container
                if len(remove_list) > 0:
                    LocationRelation.objects.filter(contained=instance, container__id__in=remove_list).delete()

        return bStatus

    def add_to_context(self, context):

        # Get the instance
        instance = self.obj

        if instance != None:
            pass

        afternew =  reverse('location_list')
        if 'afternewurl' in self.qd:
            afternew = self.qd['afternewurl']
        context['afternewurl'] = afternew

        return context


class LocationRelset(BasicPart):
    """The set of provenances from one manuscript"""

    MainModel = Location
    template_name = 'seeker/location_relset.html'
    title = "LocationRelations"
    LrelFormSet = inlineformset_factory(Location, LocationRelation,
                                         form=LocationRelForm, min_num=0,
                                         fk_name = "contained",
                                         extra=0, can_delete=True, can_order=False)
    formset_objects = [{'formsetClass': LrelFormSet, 'prefix': 'lrel', 'readonly': False}]

    def get_queryset(self, prefix):
        qs = None
        if prefix == "lrel":
            # List the parent locations for this location correctly
            qs = LocationRelation.objects.filter(contained=self.obj).order_by('container__name')
        return qs

    def before_save(self, prefix, request, instance = None, form = None):
        has_changed = False
        if prefix == "lrel":
            # Get any selected partof location id
            loc_id = form.cleaned_data['partof']
            if loc_id != "":
                # Check if a new relation should be made or an existing one should be changed
                if instance.id == None:
                    # Set the correct container
                    location = Location.objects.filter(id=loc_id).first()
                    instance.container = location
                    has_changed = True
                elif instance.container == None or instance.container.id == None or instance.container.id != int(loc_id):
                    location = Location.objects.filter(id=loc_id).first()
                    # Set the correct container
                    instance.container = location
                    has_changed = True
 
        return has_changed


class OriginListView(BasicList):
    """Listview of origins"""

    model = Origin
    listform = OriginForm
    prefix = "prj"
    has_select2 = True
    paginate_by = 15
    page_function = "ru.passim.seeker.search_paged_start"
    order_cols = ['name', 'location', 'note', '']
    order_default = order_cols
    order_heads = [{'name': 'Name', 'order': 'o=1', 'type': 'str', 'custom': 'origin', 'main': True, 'linkdetails': True},
                   {'name': 'Location', 'order': 'o=2', 'type': 'str', 'custom': 'location'},
                   {'name': 'Note', 'order': 'o=3', 'type': 'str', 'custom': 'note'},
                   {'name': '', 'order': '', 'type': 'str', 'custom': 'manulink' }]
    filters = [ {"name": "Location",         "id": "filter_location",     "enabled": False},
                {"name": "Shelfmark",       "id": "filter_manuid",      "enabled": False, "head_id": "filter_other"},
               ]
    searches = [
        {'section': '', 'filterlist': [
            {'filter': 'location', 'dbfield': 'name', 'keyS': 'location_ta', 'keyList': 'locationlist', 'infield': 'name' }]}
        ]

    def get_field_value(self, instance, custom):
        sBack = ""
        sTitle = ""
        html = []
        if custom == "manulink":
            # Link to manuscripts in this project
            count = instance.origin_manuscripts.all().count()
            url = reverse('search_manuscript')
            if count > 0:
                html.append("<a href='{}?manu-prjlist={}'><span class='badge jumbo-3 clickable' title='{} manuscripts with this origin'>{}</span></a>".format(
                    url, instance.id, count, count))
        elif custom == "location":
            sLocation = ""
            if instance.location:
                sLocation = instance.location.name
            html.append(sLocation)
        elif custom == "note":
            sNote = "" if not instance.note else instance.note
            html.append(sNote)
        elif custom == "origin":
            sName = instance.name
            if sName == "": sName = "<i>(unnamed)</i>"
            html.append(sName)
        # Combine the HTML code
        sBack = "\n".join(html)
        return sBack, sTitle


class OriginDetailsView(PassimDetails):
    model = Origin
    mForm = OriginForm
    template_name = 'seeker/origin_details.html'
    prefix = 'org'
    prefix_type = "simple"
    title = "OriginDetails"
    rtype = "html"

    def after_new(self, form, instance):
        """Action to be performed after adding a new item"""

        self.afternewurl = reverse('origin_list')
        if instance != None:
            # Make sure we do a page redirect
            self.newRedirect = True
            self.redirectpage = reverse('origin_details', kwargs={'pk': instance.id})
        return True, "" 

    def add_to_context(self, context, instance):
        context['is_app_editor'] = user_is_ingroup(self.request, app_editor)
        # Process this visit and get the new breadcrumbs object
        prevpage = reverse('origin_list')
        crumbs = []
        crumbs.append(['Origins', prevpage])
        current_name = "Origin details"
        if instance:
            current_name = "Origin [{}]".format(instance.name)
        context['prevpage'] = prevpage
        context['breadcrumbs'] = get_breadcrumbs(self.request, current_name, True, crumbs)
        return context


class OriginEdit(BasicPart):
    """The details of one origin"""

    MainModel = Origin
    template_name = 'seeker/origin_edit.html'  
    title = "Origin" 
    afternewurl = ""
    # One form is attached to this 
    prefix = "org"
    form_objects = [{'form': OriginForm, 'prefix': prefix, 'readonly': False}]

    def before_save(self, prefix, request, instance = None, form = None):
        bNeedSaving = False
        if prefix == "org":
            pass

        return bNeedSaving

    def add_to_context(self, context):

        # Get the instance
        instance = self.obj

        if instance != None:
            pass

        afternew =  reverse('origin_list')
        if 'afternewurl' in self.qd:
            afternew = self.qd['afternewurl']
        context['afternewurl'] = afternew
        context['afterdelurl'] = reverse('origin_list')

        return context


class SermonEdit(BasicDetails):
    """The editable part of one sermon description (manifestation)"""
    
    model = SermonDescr
    mForm = SermonForm
    prefix = "sermo"
    title = "Sermon" 
    rtype = "json"
    mainitems = []
    basic_name = "sermon"

    StogFormSet = inlineformset_factory(SermonDescr, SermonDescrGold,
                                         form=SermonDescrGoldForm, min_num=0,
                                         fk_name = "sermon",
                                         extra=0, can_delete=True, can_order=False)
    SDkwFormSet = inlineformset_factory(SermonDescr, SermonDescrKeyword,
                                       form=SermonDescrKeywordForm, min_num=0,
                                       fk_name="sermon", extra=0)
    SDcolFormSet = inlineformset_factory(SermonDescr, CollectionSerm,
                                       form=SermonDescrCollectionForm, min_num=0,
                                       fk_name="sermon", extra=0)
    SDsignFormSet = inlineformset_factory(SermonDescr, SermonSignature,
                                         form=SermonDescrSignatureForm, min_num=0,
                                         fk_name = "sermon",
                                         extra=0, can_delete=True, can_order=False)

    formset_objects = [{'formsetClass': StogFormSet,   'prefix': 'stog',   'readonly': False, 'noinit': True, 'linkfield': 'sermon'},
                       {'formsetClass': SDkwFormSet,   'prefix': 'sdkw',   'readonly': False, 'noinit': True, 'linkfield': 'sermon'},                       
                       {'formsetClass': SDcolFormSet,  'prefix': 'sdcol',  'readonly': False, 'noinit': True, 'linkfield': 'sermo'},
                       {'formsetClass': SDsignFormSet, 'prefix': 'sdsig',  'readonly': False, 'noinit': True, 'linkfield': 'sermon'}] 
       
    def add_to_context(self, context, instance):
        """Add to the existing context"""

        # Define the main items to show and edit
        iStop = 1
        context['mainitems'] = [
            {'type': 'plain', 'label': "Status:",               'value': instance.get_stype_display,'field_key': 'stype'},
            {'type': 'plain', 'label': "Manuscript id",         'value': instance.manu.id,          'field_key': "manu", 'empty': 'idonly'},
            {'type': 'plain', 'label': "Locus:",                'value': instance.locus,            'field_key': "locus"}, 
            {'type': 'plain', 'label': "Attributed author:",    'value': instance.get_author,       'field_key': 'author'},
            {'type': 'plain', 'label': "Title:",                'value': instance.title,            'field_key': 'title'},
            {'type': 'plain', 'label': "Sub title:",            'value': instance.subtitle,         'field_key': 'subtitle'},
            {'type': 'safe',  'label': "Incipit:",              'value': instance.get_incipit_markdown, 
             'field_key': 'incipit',  'key_ta': 'srmincipit-key'}, 
            {'type': 'safe',  'label': "Explicit:",             'value': instance.get_explicit_markdown,
             'field_key': 'explicit', 'key_ta': 'srmexplicit-key'}, 
            {'type': 'safe',  'label': "Quote:",                'value': instance.get_quote_markdown,'field_key': 'quote'}, 
            {'type': 'plain', 'label': "Bibliographic notes:",  'value': instance.bibnotes,         'field_key': 'bibnotes'},
            {'type': 'plain', 'label': "Feast:",                'value': instance.feast,            'field_key': 'feast'},
            {'type': 'plain', 'label': "Bible reference(s):",   'value': instance.bibleref,         'field_key': 'bibleref'},
            {'type': 'plain', 'label': "Additional:",           'value': instance.additional,       'field_key': 'additional'},
            {'type': 'plain', 'label': "Note:",                 'value': instance.note,             'field_key': 'note'},
            {'type': 'line',  'label': "Keywords:",             'value': instance.get_keywords_markdown(), 
             'multiple': True,  'field_list': 'kwlist',         'fso': self.formset_objects[1]},
            {'type': 'line',    'label': "Gryson/Clavis (auto):",'value': instance.get_eqsetsignatures_markdown(),
             'title': "Gryson/Clavis codes of the Sermons Gold that are part of the same equality set"}, 
            {'type': 'line',    'label': "Gryson/Clavis (manual):",'value': instance.get_sermonsignatures_markdown(),
             'title': "Gryson/Clavis codes manually linked to this manifestation Sermon", 'unique': True,
             'field_list': 'siglist',        'fso': self.formset_objects[3], 'template_selection': 'ru.passim.sigs_template'},
            {'type': 'plain',   'label': "Collections:",        'value': instance.get_collections_markdown(), 
             'multiple': True,  'field_list': 'collist_s',      'fso': self.formset_objects[2] },
            {'type': 'line',    'label': "Editions:",           'value': instance.get_editions_markdown()},
            {'type': 'line',    'label': "Literature:",         'value': instance.get_litrefs_markdown()},
            {'type': 'line',    'label': "Gold Sermon links:",  'value': instance.get_goldlinks_markdown(), 
             'multiple': True,  'field_list': 'goldlist',       'fso': self.formset_objects[0], 
             'inline_selection': 'ru.passim.sglink_template',   'template_selection': 'ru.passim.sg_template'}
            ]
        # Notes:
        # Collections: provide a link to the Sermon-listview, filtering on those Sermons that are part of one particular collection

        # Add a button back to the Manuscript
        topleftlist = []
        if instance.manu:
            buttonspecs = {'label': "M", 
                 'title': "Go to manuscript {}".format(instance.manu.idno), 
                 'url': reverse('manuscript_details', kwargs={'pk': instance.manu.id})}
            topleftlist.append(buttonspecs)
        context['topleftbuttons'] = topleftlist
        # Add something right to the SermonDetails title
        context['title_addition'] = instance.get_eqsetsignatures_markdown('first')
        # Add the manuscript's IDNO completely right
        context['title_right'] = "<span class='manuscript-idno'>{}</span>".format(instance.manu.idno)

        # Signal that we have select2
        context['has_select2'] = True

        # Return the context we have made
        return context

    def after_new(self, form, instance):
        """Action to be performed after adding a new item"""

        ## Set the 'afternew' URL
        #self.afternewurl = reverse('sermon_list')

        # Return positively
        return True, "" 

    def process_formset(self, prefix, request, formset):
        """This is for processing *NEWLY* added items (using the '+' sign)"""

        bAllowNewSignatureManually = False
        errors = []
        bResult = True
        instance = formset.instance
        for form in formset:
            if form.is_valid():
                cleaned = form.cleaned_data
                # Action depends on prefix
                if prefix == "sdsign" and bAllowNewSignatureManually:
                    # Signature processing
                    # NOTE: this should never be reached, because we do not allow adding *new* signatures manually here
                    editype = ""
                    code = ""
                    if 'newgr' in cleaned and cleaned['newgr'] != "":
                        # Add gryson
                        editype = "gr"
                        code = cleaned['newgr']
                    elif 'newcl' in cleaned and cleaned['newcl'] != "":
                        # Add gryson
                        editype = "cl"
                        code = cleaned['newcl']
                    elif 'newot' in cleaned and cleaned['newot'] != "":
                        # Add gryson
                        editype = "ot"
                        code = cleaned['newot']
                    if editype != "":
                        # Find this item in the Gold Signatures
                        gsig = Signature.objects.filter(editype=editype, code=code).first()
                        if gsig != None:
                            form.instance.gsig = gsig
                        # Set the correct parameters
                        form.instance.code = code
                        form.instance.editype = editype
                        # Note: it will get saved with formset.save()
                elif prefix == "sdkw":
                    # Keyword processing
                    if 'newkw' in cleaned and cleaned['newkw'] != "":
                        newkw = cleaned['newkw']
                        # Is the KW already existing?
                        obj = Keyword.objects.filter(name=newkw).first()
                        if obj == None:
                            obj = Keyword.objects.create(name=newkw)
                        # Make sure we set the keyword
                        form.instance.keyword = obj
                        # Note: it will get saved with formset.save()
                elif prefix == "sdcol":
                    # Collection processing
                    if 'newcol' in cleaned and cleaned['newcol'] != "":
                        newcol = cleaned['newcol']
                        # Is the COL already existing?
                        obj = Collection.objects.filter(name=newcol).first()
                        if obj == None:
                            # TODO: add profile here
                            profile = Profile.get_user_profile(request.user.username)
                            obj = Collection.objects.create(name=newcol, type='sermo', owner=profile)
                        # Make sure we set the keyword
                        form.instance.collection = obj
                        # Note: it will get saved with formset.save()
                elif prefix == "stog":
                    # SermonDescr-To-SermonGold processing
                    if 'newgold' in cleaned and cleaned['newgold'] != "":
                        newgold = cleaned['newgold']
                        # There also must be a linktype
                        if 'newlinktype' in cleaned and cleaned['newlinktype'] != "":
                            linktype = cleaned['newlinktype']
                            # Check existence
                            obj = SermonDescrGold.objects.filter(sermon=instance, gold=newgold, linktype=linktype).first()
                            if obj == None:
                                gold = SermonGold.objects.filter(id=newgold).first()
                                if gold != None:
                                    # Set the right parameters for creation later on
                                    form.instance.linktype = linktype
                                    form.instance.gold = gold
                    # Note: it will get saved with form.save()
            else:
                errors.append(form.errors)
                bResult = False
        return None

    def after_save(self, form, instance):
        """This is for processing items from the list of available ones"""

        msg = ""
        bResult = True
        oErr = ErrHandle()
        
        try:
            # Process many-to-many changes: Add and remove relations in accordance with the new set passed on by the user
            # (1) 'keywords'
            kwlist = form.cleaned_data['kwlist']
            adapt_m2m(SermonDescrKeyword, instance, "sermon", kwlist, "keyword")

            # (2) 'Links to Gold Signatures'
            siglist = form.cleaned_data['siglist']
            adapt_m2m(SermonSignature, instance, "sermon", siglist, "gsig", extra = ['editype', 'code'])

            # (3) 'Links to Gold Sermons'
            goldlist = form.cleaned_data['goldlist']
            adapt_m2m(SermonDescrGold, instance, "sermon", goldlist, "gold", extra = ['linktype'], related_is_through=True)

            # (4) 'collections'
            collist_s = form.cleaned_data['collist_s']
            adapt_m2m(CollectionSerm, instance, "sermo", collist_s, "collection")

        except:
            msg = oErr.get_error_message()
            bResult = False
        return bResult, msg


class SermonDetails(SermonEdit):
    """The details of one sermon manifestation (SermonDescr)"""

    rtype = "html"

    def add_to_context(self, context, instance):
        """Add to the existing context"""

        # Start by executing the standard handling
        super(SermonDetails, self).add_to_context(context, instance)

        context['sections'] = []

        # List of post-load objects
        context['postload_objects'] = []

        # Lists of related objects
        context['related_objects'] = []

        # Return the context we have made
        return context

    def before_save(self, form, instance):
        return True, ""

    def process_formset(self, prefix, request, formset):
        return None

    def after_save(self, form, instance):
        return True, ""


class SermonEdit_ORIGINAL(PassimDetails):
    """The details of one sermon description"""
    
    model = SermonDescr
    mForm = SermonForm
    template_name = 'seeker/sermon_edit.html'   
    prefix = "sermo"
    title = "Sermon" 
    basic_name = "sermon"
    afternewurl = ""
    StogFormSet = inlineformset_factory(SermonDescr, SermonDescrGold,
                                         form=SermonDescrGoldForm, min_num=0,
                                         fk_name = "sermon",
                                         extra=0, can_delete=True, can_order=False)
    SDkwFormSet = inlineformset_factory(SermonDescr, SermonDescrKeyword,
                                       form=SermonDescrKeywordForm, min_num=0,
                                       fk_name="sermon", extra=0)
    SDcolFormSet = inlineformset_factory(SermonDescr, CollectionSerm,
                                       form=SermonDescrCollectionForm, min_num=0,
                                       fk_name="sermon", extra=0)

    formset_objects = [{'formsetClass': StogFormSet,   'prefix': 'stog',   'readonly': False},
                       {'formsetClass': SDkwFormSet,   'prefix': 'sdkw',   'readonly': False, 'noinit': True, 'linkfield': 'sermon'},                       
                       {'formsetClass': SDcolFormSet,  'prefix': 'sdcol',  'readonly': False, 'noinit': True, 'linkfield': 'sermo'}]    

    def after_new(self, form, instance):
        """Action to be performed after adding a new item"""

        # Set the 'afternew' URL...
        self.afternewurl = reverse('sermon_details', kwargs={'pk': instance.id})

        # Return positively
        return True, "" 

    def before_delete(self, instance):
        # All is well
        return True, "" 

    def process_formset(self, prefix, request, formset):

        errors = []
        bResult = True
        instance = formset.instance
        for form in formset:
            if form.is_valid():
                cleaned = form.cleaned_data
                # Action depends on prefix
                if prefix == "sdkw":
                    # Keyword processing
                    if 'newkw' in cleaned and cleaned['newkw'] != "":
                        newkw = cleaned['newkw']
                        # Is the KW already existing?
                        obj = Keyword.objects.filter(name=newkw).first()
                        if obj == None:
                            obj = Keyword.objects.create(name=newkw)
                        # Make sure we set the keyword
                        form.instance.keyword = obj
                        # Note: it will get saved with formset.save()
                elif prefix == "sdcol":
                    # Keyword processing
                    if 'newcol' in cleaned and cleaned['newcol'] != "":
                        newcol = cleaned['newcol']
                        # Is the COL already existing?
                        obj = Collection.objects.filter(name=newcol).first()
                        if obj == None:
                            # TODO: add profile here
                            profile = Profile.get_user_profile(request.user.username)
                            obj = Collection.objects.create(name=newcol, type='sermo', owner=profile)
                        # Make sure we set the keyword
                        form.instance.collection = obj
                        # Note: it will get saved with formset.save()
                elif prefix == "stog":
                    # Which sermon-gold instances are linked to this sermon-descr
                    iStop = 1
                    pass                
            else:
                errors.append(form.errors)
                bResult = False
        return None
    
    def before_save(self, form, instance):
        form.fields['kwlist'].initial = instance.keywords.all().order_by('name')
        form.fields['siglist'].initial = instance.sermonsignatures.all().order_by('editype', 'code')
        return True, ""
    
    def after_save(self, form, instance):
        msg = ""
        bResult = True
        oErr = ErrHandle()
        
        try:
            # Sermon-specific matters - if this is a new one
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
            elif instance and instance.order <= 0:
                # Calculate how many sermons there are
                sermon_count = manuscript.manusermons.all().count()
                # Make sure the new sermon gets changed
                instance.order = sermon_count
                instance.save()
                
            # Process many-to-many changes: Add and remove relations in accordance with the new set passed on by the user
            # (1) 'keywords'
            kwlist = form.cleaned_data['kwlist']
            adapt_m2m(SermonDescrKeyword, instance, "sermon", kwlist, "keyword")
            # (2) 'collections' - but *only* the *sermon* collection
            collist = form.cleaned_data['collist_s']
            adapt_m2m(CollectionSerm, instance, "sermon", collist, "collection")

            # Process many-to-one changes
            # (1) 'sermonsignatures'
            siglist = form.cleaned_data['siglist']
            # What we get is a list of 'gold' Signature ids -- this must be changed into a list of [SermonSignature] ids
            adapt_m2o_sig(instance, siglist)
        except:
            msg = oErr.get_error_message()
            bResult = False
        return bResult, msg

    def add_to_context(self, context, instance):

        # Not sure if this is still needed
        context['msitem'] = instance

        # Make sure to pass on the manuscript_id
        # context['afternewurl'] = ""
        manuscript_id = None
        if 'manuscript_id' in self.qd:
            manuscript_id = self.qd['manuscript_id']
            # Set the URL to be taken after saving
            # context['afternewurl'] = reverse('manuscript_details', kwargs={'pk': manuscript_id})
        context['manuscript_id'] = manuscript_id

        # Define where to go to after deletion
        # context['afterdelurl'] = reverse("sermon_list")
        if manuscript_id:
            context['afterdelurl'] = reverse('manuscript_details', kwargs={'pk': manuscript_id})
        else:
            context['afterdelurl'] = get_previous_page(self.request)

        return context


class SermonDetails_ORIGINAL(SermonEdit_ORIGINAL):
    """The details of one sermon"""

    template_name = 'seeker/sermon_details.html'    # Use this for GET and for POST requests
    rtype = "html"

    def after_new(self, form, instance):
        """Action to be performed after adding a new item"""

        # Calculate how many sermons there are
        manuscript = instance.manu
        if manuscript != None:
            sermon_count = manuscript.manusermons.all().count()
            # Make sure the new sermon gets changed
            instance.order = sermon_count
            instance.save()
        if instance != None:
            # Make sure we do a page redirect
            self.newRedirect = True
            self.redirectpage = reverse('sermon_details', kwargs={'pk': instance.id})
        return True, "" 

    def add_to_context(self, context, instance):
        """Add to the existing context"""

        # Process this visit and get the new breadcrumbs object
        #   Static breadcrumbs should be:
        #       Manuscripts >> Manuscript [idno] >> Manuscript sermons >> Sermon [author/title]
        prevpage = reverse('sermon_list')
        context['prevpage'] = prevpage
        # Start creating a list of breadcrumbs
        crumbs = []
        crumbs.append(['Manuscripts', reverse('search_manuscript')])
        manu_sermons = prevpage
        if instance:
            # Which manuscript do we belong to?
            manu = instance.manu
            if manu:
                manu_id = manu.idno
                if manu_id == None: manu_id = "(unknown ms)"
                manu_url = reverse('manuscript_details', kwargs={'pk': manu.id})
                crumbs.append(['{}'.format(manu_id), manu_url])
               #  manu_sermons = "{}?sermo-manu={}".format(reverse('sermon_list'), manu.id )
                manu_sermons = "{}?sermo-manuidlist={}".format(reverse('sermon_list'), manu.id )
        crumbs.append(['Manuscript sermons', manu_sermons])
        # Figure out what the sermon details are
        current_name = "Sermon details"
        if instance:
            lDetails = []
            if instance.author: lDetails.append(instance.author.name)
            if instance.title: 
                title = instance.title[:10]
                dots = "" if len(instance.title) < 10 else "..."
                lDetails.append("{}{}".format(title,dots))
            if len(lDetails) > 0:
                current_name = "Sermon [{}]".format(", ".join(lDetails))
        context['breadcrumbs'] = get_breadcrumbs(self.request, current_name, True, crumbs)

        # New:
        if instance == None:
            # We are creating a new sermon
            man_id = None
            # What is the manuscript id?
            if 'manuscript_id' in self.qd:
                man_id = self.qd['manuscript_id']
            context['manuscript_id'] = man_id
        elif 'sermo-manu' in self.qd:
            context['manuscript_id'] = self.qd['sermo-manu']
            manuscript_id = context['manuscript_id']
            self.afternewurl = reverse('manuscript_details', kwargs={'pk': manuscript_id})
            context['afternewurl'] = self.afternewurl
        elif instance.manu == None:
            context['manuscript_id'] = None
        else:
            context['manuscript_id'] = instance.manu.id

        # Are we copying information??
        if 'goldcopy' in self.qd:
            # Get the ID of the gold sermon from which we are copying
            goldid = self.qd['goldcopy']
            gold = SermonGold.objects.filter(id=goldid).first()

            include_keyword_copy = False

            if gold != None:
                # Copy all relevant information to obj
                obj = self.object
                # (1) copy author
                if gold.author != None: obj.author = gold.author
                # (2) copy incipit
                if gold.incipit != None and gold.incipit != "": obj.incipit = gold.incipit ; obj.srchincipit = gold.srchincipit
                # (3) copy explicit
                if gold.explicit != None and gold.explicit != "": obj.explicit = gold.explicit ; obj.srchexplicit = gold.srchexplicit

                if include_keyword_copy:
                    # (4) copy keywords
                    kwlist = [x['id'] for x in obj.keywords.all().values('id')]
                    for kw in gold.keywords.all():
                        # Check if it is already there
                        if kw.id not in kwlist:
                            # Add it in the proper way
                            srm_kw = SermonDescrKeyword(sermon=obj, keyword=kw)
                            srm_kw.save()

                # (5) copy signatures from *all* gold sermons in the equality set
                # [5.a] get my gold equality set
                geq = gold.equal
                # [5.b] get all gold sermons in this equality set (i.e. part of SSG)
                qs_geq = SermonGold.objects.filter(equal=geq)
                # [5.c] Walk all gold sermons in the equality set (i.e. part of SSG)
                for obj_geq in qs_geq:
                    for gold_sig in obj_geq.goldsignatures.all():
                        # Check if it is already there
                        srm_sig = SermonSignature.objects.filter(code=gold_sig.code, editype=gold_sig.editype, sermon=obj).first()
                        if srm_sig == None:
                            srm_sig = SermonSignature(gsig=gold_sig, code=gold_sig.code, editype=gold_sig.editype, sermon=obj)
                            srm_sig.save()
                # Now save the adapted sermon
                obj.save()
            # And in all cases: make sure we redirect to the 'clean' GET page
            self.redirectpage = reverse('sermon_details', kwargs={'pk': self.object.id})
        else:
            # Pass on all the linked-gold editions + get all authors from the linked-gold stuff
            goldauthors = []
            # Visit all linked gold sermons
            for linked in SermonDescrGold.objects.filter(sermon=self.object, linktype=LINK_EQUAL):
                # Access the gold sermon
                gold = linked.gold
                # Does this one have an author?
                if gold.author != None:
                    goldauthors.append(gold.author)
            # Why is this needed?
            context['goldauthors'] = goldauthors

        return context
    
    def before_save(self, form, instance):
        # Make sure the SermonEdit behaviour is not copied here
        return True, ""

    def process_formset(self, prefix, request, formset):
        # Make sure the SermonEdit behaviour is not copied here
        return None

    def after_save(self, form, instance):
        # Make sure the SermonEdit behaviour is not copied here
        return True, ""


class SermonListView(BasicList):
    """Search and list sermons"""
    
    model = SermonDescr
    listform = SermonForm
    prefix = "sermo"
    paginate_by = 20
    new_button = False      # Don't show the [Add new sermon] button here. It is shown under the Manuscript Details view.
    basketview = False
    plural_name = "Sermons"
    basic_name = "sermon"
    has_select2 = True
    page_function = "ru.passim.seeker.search_paged_start"
    order_cols = ['author__name;nickname__name', 'siglist', 'srchincipit;srchexplicit', 'manu__idno', '','']
    order_default = order_cols
    order_heads = [{'name': 'Author', 'order': 'o=1', 'type': 'str', 'custom': 'author', 'linkdetails': True}, 
                   {'name': 'Signature', 'order': 'o=2', 'type': 'str', 'custom': 'signature'}, 
                   {'name': 'Incipit ... Explicit', 'order': 'o=3', 'type': 'str', 'custom': 'incexpl', 'main': True, 'linkdetails': True},
                   {'name': 'Manuscript', 'order': 'o=4', 'type': 'str', 'custom': 'manuscript'},
                   {'name': 'Locus', 'order': '', 'type': 'str', 'field': 'locus' },
                   {'name': 'Links', 'order': '', 'type': 'str', 'custom': 'links'},
                   {'name': 'Status', 'order': '', 'type': 'str', 'custom': 'status'}]

    filters = [ {"name": "Gryson or Clavis", "id": "filter_signature",      "enabled": False},
                {"name": "Author",           "id": "filter_author",         "enabled": False},
                {"name": "Incipit",          "id": "filter_incipit",        "enabled": False},
                {"name": "Explicit",         "id": "filter_explicit",       "enabled": False},
                {"name": "Keyword",          "id": "filter_keyword",        "enabled": False}, 
                {"name": "Feast",            "id": "filter_feast",          "enabled": False},
                {"name": "Manuscript...",    "id": "filter_manuscript",     "enabled": False, "head_id": "none"},
                {"name": "Collection...",    "id": "filter_collection",     "enabled": False, "head_id": "none"},
                {"name": "Sermon",           "id": "filter_collsermo",      "enabled": False, "head_id": "filter_collection"},
                {"name": "Sermon Gold",      "id": "filter_collgold",       "enabled": False, "head_id": "filter_collection"},
                {"name": "Super sermon gold","id": "filter_collsuper",      "enabled": False, "head_id": "filter_collection"},
                {"name": "Manuscript",       "id": "filter_collmanu",       "enabled": False, "head_id": "filter_collection"},
                {"name": "Shelfmark",        "id": "filter_manuid",         "enabled": False, "head_id": "filter_manuscript"},
                {"name": "Country",          "id": "filter_country",        "enabled": False, "head_id": "filter_manuscript"},
                {"name": "City",             "id": "filter_city",           "enabled": False, "head_id": "filter_manuscript"},
                {"name": "Library",          "id": "filter_library",        "enabled": False, "head_id": "filter_manuscript"},
                {"name": "Origin",           "id": "filter_origin",         "enabled": False, "head_id": "filter_manuscript"},
                {"name": "Provenance",       "id": "filter_provenance",     "enabled": False, "head_id": "filter_manuscript"},
                {"name": "Date from",        "id": "filter_datestart",      "enabled": False, "head_id": "filter_manuscript"},
                {"name": "Date until",       "id": "filter_datefinish",     "enabled": False, "head_id": "filter_manuscript"},
                ]

    searches = [
        {'section': '', 'filterlist': [
            {'filter': 'incipit',       'dbfield': 'srchincipit',       'keyS': 'incipit'},
            {'filter': 'explicit',      'dbfield': 'srchexplicit',      'keyS': 'explicit'},
            {'filter': 'title',         'dbfield': 'title',             'keyS': 'title'},
            {'filter': 'feast',         'dbfield': 'feast',             'keyS': 'feast'},
            {'filter': 'author',        'fkfield': 'author',            'keyS': 'authorname',
                                        'keyFk': 'name', 'keyList': 'authorlist', 'infield': 'id', 'external': 'sermo-authorname' },
            {'filter': 'signature',     'fkfield': 'signatures|goldsermons__goldsignatures',        
                                        'keyS': 'signature', 'keyFk': 'code', 'keyId': 'signatureid', 'keyList': 'siglist', 'infield': 'code' },
            {'filter': 'keyword',       'fkfield': 'keywords',          'keyS': 'keyword',   
                                        'keyFk': 'name', 'keyList': 'kwlist', 'infield': 'name' }, 
            ]},
        {'section': 'collection', 'filterlist': [
            {'filter': 'collmanu',      'fkfield': 'manu__collections',              'keyFk': 'name', 'keyList': 'collist_m',  'infield': 'name' }, 
            {'filter': 'collsermo',     'fkfield': 'collections',                    'keyFk': 'name', 'keyList': 'collist_s',  'infield': 'name' }, 
            {'filter': 'collgold',      'fkfield': 'goldsermons__collections',       'keyFk': 'name', 'keyList': 'collist_sg', 'infield': 'name' }, 
            {'filter': 'collsuper',     'fkfield': 'equal_goldsermons__collections', 'keyFk': 'name', 'keyList': 'collist_ssg','infield': 'name' }
            ]},
        {'section': 'manuscript', 'filterlist': [
            {'filter': 'manuid',        'fkfield': 'manu',                    'keyS': 'manuidno',     'keyList': 'manuidlist', 'keyFk': 'idno', 'infield': 'id'},
            {'filter': 'country',       'fkfield': 'manu__library__lcountry', 'keyS': 'country_ta',   'keyId': 'country',     'keyFk': "name"},
            {'filter': 'city',          'fkfield': 'manu__library__lcity',    'keyS': 'city_ta',      'keyId': 'city',        'keyFk': "name"},
            {'filter': 'library',       'fkfield': 'manu__library',           'keyS': 'libname_ta',   'keyId': 'library',     'keyFk': "name"},
            {'filter': 'origin',        'fkfield': 'manu__origin',            'keyS': 'origin_ta',    'keyId': 'origin',      'keyFk': "name"},
            {'filter': 'provenance',    'fkfield': 'manu__provenances',       'keyS': 'prov_ta',      'keyId': 'prov',        'keyFk': "name"},
            {'filter': 'datestart',     'dbfield': 'manu__yearstart__gte',    'keyS': 'date_from'},
            {'filter': 'datefinish',    'dbfield': 'manu__yearfinish__lte',   'keyS': 'date_until'},
            ]}
         ]

    def add_to_context(self, context, initial):
        # Find out who the user is
        profile = Profile.get_user_profile(self.request.user.username)
        context['basketsize'] = 0 if profile == None else profile.basketsize
        context['basket_show'] = reverse('basket_show')
        context['basket_update'] = reverse('basket_update')
        return context

    def get_basketqueryset(self):
        if self.basketview:
            profile = Profile.get_user_profile(self.request.user.username)
            qs = profile.basketitems.all()
        else:
            qs = SermonDescr.objects.all()
        return qs

    def get_field_value(self, instance, custom):
        sBack = ""
        sTitle = ""
        html = []
        if custom == "author":
            if instance.author:
                html.append("<span style='color: darkgreen; font-size: small;'>{}</span>".format(instance.author.name[:20]))
                sTitle = instance.author.name
            elif instance.nickname:
                html.append("<span style='color: darkred; font-size: small;'>{}</span>".format(instance.nickname.name[:20]))
                sTitle = instance.nickname.name
            else:
                html.append("<span><i>(unknown)</i></span>")
        elif custom == "signature":
            html.append("<span>{}</span>".format(instance.signature_string()[:20]))
            sTitle = instance.signature_string()
        elif custom == "incexpl":
            html.append("<span>{}</span>".format(instance.get_incipit_markdown()))
            dots = "..." if instance.incipit else ""
            html.append("<span style='color: blue;'>{}</span>".format(dots))
            html.append("<span>{}</span>".format(instance.get_explicit_markdown()))
        elif custom == "manuscript":
                          #<a href="{% url 'manuscript_details' sermon.manu.id %}" class="nostyle">
                          #  <span  style="font-size: small;">{{sermon.manu.idno|truncatechars:20}}</span>
                          #</a>
            html.append("<a href='{}' class='nostyle'><span style='font-size: small;'>{}</span></a>".format(
                reverse('manuscript_details', kwargs={'pk': instance.manu.id}),
                instance.manu.idno[:20]))
            sTitle = instance.manu.idno
        elif custom == "links":
            for gold in instance.goldsermons.all():
                for link_def in gold.link_oview():
                    if link_def['count'] > 0:
                        html.append("<span class='badge {}' title='{}'>{}</span>".format(link_def['class'], link_def['title'], link_def['count']))
        elif custom == "status":
            # Provide that status badge
            html.append("<span class='badge' title='{}'>{}</span>".format(instance.get_stype_display(), instance.stype[:1]))
        # Combine the HTML code
        sBack = "\n".join(html)
        return sBack, sTitle


class KeywordEdit(BasicDetails):
    """The details of one keyword"""

    model = Keyword
    mForm = KeywordForm
    prefix = 'kw'
    title = "KeywordEdit"
    rtype = "json"
    mainitems = []
    
    def add_to_context(self, context, instance):
        """Add to the existing context"""

        # Define the main items to show and edit
        context['mainitems'] = [
            {'type': 'plain', 'label': "Name:",      'value': instance.name, 'field_key': 'name'}
            ]
        # Return the context we have made
        return context


class KeywordDetails(KeywordEdit):
    """Like Keyword Edit, but then html output"""
    rtype = "html"
    

class KeywordListView(BasicList):
    """Search and list keywords"""

    model = Keyword
    listform = KeywordForm
    prefix = "kw"
    paginate_by = 20
    # template_name = 'seeker/keyword_list.html'
    has_select2 = True
    page_function = "ru.passim.seeker.search_paged_start"
    order_cols = ['name', '']
    order_default = order_cols
    order_heads = [{'name': 'Keyword', 'order': 'o=1', 'type': 'str', 'field': 'name', 'default': "(unnamed)", 'main': True, 'linkdetails': True},
                   {'name': 'Frequency', 'order': '', 'type': 'str', 'custom': 'links'}]
    filters = [ {"name": "Keyword",         "id": "filter_keyword",     "enabled": False}]
    searches = [
        {'section': '', 'filterlist': [
            {'filter': 'keyword',   'dbfield': 'name',          'keyS': 'keyword_ta', 'keyList': 'kwlist', 'infield': 'name' }]}
        ]

    def get_field_value(self, instance, custom):
        sBack = ""
        sTitle = ""
        if custom == "links":
            html = []
            # Get the HTML code for the links of this instance
            number = instance.freqsermo()
            if number > 0:
                url = reverse('sermon_list')
                html.append("<a href='{}?sermo-keyword={}'>".format(url, instance.name))
                html.append("<span class='badge jumbo-1 clickable' title='Frequency in manifestation sermons'>{}</span></a>".format(number))
            number = instance.freqgold()
            if number > 0:
                url = reverse('search_gold')
                html.append("<a href='{}?gold-keyword={}'>".format(url, instance.name))
                html.append("<span class='badge jumbo-2 clickable' title='Frequency in gold sermons'>{}</span></a>".format(number))
            number = instance.freqmanu()
            if number > 0:
                url = reverse('search_manuscript')
                html.append("<a href='{}?manu-kwlist={}'>".format(url, instance.id))
                html.append("<span class='badge jumbo-3 clickable' title='Frequency in manuscripts'>{}</span></a>".format(number))
            # Combine the HTML code
            sBack = "\n".join(html)
        return sBack, sTitle


class ProjectEdit(PassimDetails):
    """The details of one project"""

    model = Project
    mForm = ProjectForm
    template_name = 'seeker/project_edit.html'
    template_post = 'seeker/project_edit.html'
    prefix = 'prj'
    title = "ProjectEdit"
    afternewurl = ""
    rtype = "json"

    def after_new(self, form, instance):
        """Action to be performed after adding a new item"""

        self.afternewurl = reverse('project_list')
        return True, "" 

    def add_to_context(self, context, instance):
        context['is_app_editor'] = user_is_ingroup(self.request, app_editor)
        # Process this visit and get the new breadcrumbs object
        prevpage = reverse('project_list')
        context['prevpage'] = prevpage
        crumbs = []
        crumbs.append(['Projects', reverse('project_list')])
        context['breadcrumbs'] = get_breadcrumbs(self.request, "Project details", True, crumbs)
        context['afterdelurl'] = reverse('project_list')
        
        return context


class ProjectDetails(ProjectEdit):
    """The details of one project"""

    template_name = 'seeker/project_details.html'
    template_post = 'seeker/project_details.html'
    title = "ProjectDetails"
    rtype = "html"  # GET provides a HTML form straight away

    def after_new(self, form, instance):
        """Action to be performed after adding a new item"""

        self.afternewurl = reverse('project_list')
        if instance != None:
            # Make sure we do a page redirect
            self.newRedirect = True
            self.redirectpage = reverse('project_details', kwargs={'pk': instance.id})
        return True, "" 


class ProjectListView(BasicList):
    """Search and list projects"""

    model = Project
    listform = ProjectForm
    prefix = "prj"
    has_select2 = True
    paginate_by = 20
    # template_name = 'seeker/project_list.html'
    page_function = "ru.passim.seeker.search_paged_start"
    order_cols = ['name', '']
    order_default = order_cols
    order_heads = [{'name': 'Project', 'order': 'o=1', 'type': 'str', 'custom': 'project', 'main': True, 'linkdetails': True},
                   {'name': '', 'order': '', 'type': 'str', 'custom': 'manulink' }]
    filters = [ {"name": "Project",         "id": "filter_project",     "enabled": False},
                {"name": "Shelfmark",       "id": "filter_manuid",      "enabled": False, "head_id": "filter_other"},
               ]
    searches = [
        {'section': '', 'filterlist': [
            {'filter': 'project',   'dbfield': 'name',          'keyS': 'project_ta', 'keyList': 'prjlist', 'infield': 'name' }]}
        ]

    def get_field_value(self, instance, custom):
        sBack = ""
        sTitle = ""
        html = []
        if custom == "manulink":
            # Link to manuscripts in this project
            count = instance.project_manuscripts.all().count()
            url = reverse('search_manuscript')
            if count > 0:
                html.append("<a href='{}?manu-prjlist={}'><span class='badge jumbo-3 clickable' title='{} manuscripts in this project'>{}</span></a>".format(
                    url, instance.id, count, count))
        elif custom == "project":
            sName = instance.name
            if sName == "": sName = "<i>(unnamed)</i>"
            html.append(sName)
        # Combine the HTML code
        sBack = "\n".join(html)
        return sBack, sTitle


class CollAnyEdit(BasicDetails):
    """Manu: Manuscript collections"""

    model = Collection
    mForm = CollectionForm
    prefix = "any"
    basic_name_prefix = "coll"
    rtype = "json"
    title = "Any collection"
    mainitems = []

    def add_to_context(self, context, instance):
          """Add to the existing context"""

          # Define the main items to show and edit
          context['mainitems'] = [
             {'type': 'plain', 'label': "Name:",        'value': instance.name, 'field_key': 'name'},
             {'type': 'plain', 'label': "Description:", 'value': instance.descrip, 'field_key': 'descrip'},
             {'type': 'plain', 'label': "URL:",         'value': instance.url, 'field_key': 'url'},
             {'type': 'plain', 'label': "Scope:",       'value': instance.get_scope_display, 'field_key': 'scope'},
             {'type': 'plain', 'label': "Type:",        'value': instance.get_type_display},
             {'type': 'plain', 'label': "Readonly:",    'value': instance.readonly, 'field_key': 'readonly'},
             {'type': 'plain', 'label': "Created:",     'value': instance.get_created},
             {'type': 'line',  'label': "Size:",        'value': instance.get_size_markdown}
             ]
          
          # Return the context we have made
          return context    
    
    def before_save(self, form, instance):
        if form != None:
            # Search the user profile
            profile = Profile.get_user_profile(self.request.user.username)
            form.instance.owner = profile
            # The collection type is now a parameter
            form.instance.type = self.prefix
        return True, ""


class CollManuEdit(CollAnyEdit):
    """Manu: Manuscript collections"""

    prefix = "manu"
    title = "Manuscript collection"


class CollSermoEdit(CollAnyEdit):
    """Sermo: SermonDescr collections """

    prefix = "sermo"
    title = "Sermon collection"


class CollGoldEdit(CollAnyEdit):
    """Gold: SermonGold collections """

    prefix = "gold"
    title = "Gold collection"


class CollSuperEdit(CollAnyEdit):
    """Super: EqualGold collections = super sermon gold """

    prefix = "super"
    title = "Super collection"


class CollAnyDetails(CollAnyEdit):
    """Like CollAnyEdit, but then with html"""
    rtype = "html"


class CollManuDetails(CollManuEdit):
    """Like CollManuEdit, but then with html"""
    rtype = "html"


class CollSermoDetails(CollSermoEdit):
    """Like CollSermoEdit, but then with html"""
    rtype = "html"


class CollGoldDetails(CollGoldEdit):
    """Like CollGoldEdit, but then with html"""
    rtype = "html"


class CollSuperDetails(CollSuperEdit):
    """Like CollSuperEdit, but then with html"""
    rtype = "html"


class CollGoldEditORG(BasicDetails):
    """Gold: SermonGold collections """

    model = Collection
    mForm = CollectionForm
    prefix = "gold"
    basic_name_prefix = "coll"
    rtype = "json"
    title = "Gold collection"
    mainitems = []

    def add_to_context(self, context, instance):
          """Add to the existing context"""

          # Define the main items to show and edit
          context['mainitems'] = [
             {'type': 'plain', 'label': "Name:",        'value': instance.name,             'field_key': 'name'},
             {'type': 'plain', 'label': "Description:", 'value': instance.descrip,          'field_key': 'descrip'},
             {'type': 'plain', 'label': "URL:",         'value': instance.url,              'field_key': 'url'},
             {'type': 'plain', 'label': "Scope:",       'value': instance.get_scope_display, 'field_key': 'scope'},
             {'type': 'plain', 'label': "Readonly:",    'value': instance.readonly,         'field_key': 'readonly'},
             {'type': 'plain', 'label': "Type:",        'value': instance.get_type_display, 'field_key': 'type'},
             {'type': 'plain', 'label': "Created:",     'value': instance.get_created}
             ]
          # Return the context we have made
          return context    
    
    def before_save(self, form, instance):
        if form != None:
            # Search the user profile
            profile = Profile.get_user_profile(self.request.user.username)
            form.instance.owner = profile
            # Also make sure that the correct type (=prefix) gets established
            form.instance.type = self.prefix
        return True, ""


class CollSuperEditORG(BasicDetails):
    """Super: EqualGold collections = super sermon gold """

    model = Collection
    mForm = CollectionForm
    prefix = "super"
    basic_name_prefix = "coll"
    rtype = "json"
    title = "Super collection"
    mainitems = []

    def add_to_context(self, context, instance):
          """Add to the existing context"""

          # Define the main items to show and edit
          context['mainitems'] = [
             {'type': 'plain', 'label': "Name:",        'value': instance.name, 'field_key': 'name'},
             {'type': 'plain', 'label': "Description:", 'value': instance.descrip, 'field_key': 'descrip'},
             {'type': 'plain', 'label': "URL:",         'value': instance.url, 'field_key': 'url'},
             {'type': 'plain', 'label': "Scope:",       'value': instance.get_scope_display, 'field_key': 'scope'},
             {'type': 'plain', 'label': "Readonly:",    'value': instance.readonly, 'field_key': 'readonly'},
             {'type': 'plain', 'label': "Type:",        'value': instance.get_type_display},
             {'type': 'plain', 'label': "Created:",     'value': instance.get_created}
             ]
          # Return the context we have made
          return context    
    
    def before_save(self, form, instance):
        if form != None:
            # Search the user profile
            profile = Profile.get_user_profile(self.request.user.username)
            form.instance.owner = profile
            # Also make sure that the correct type (=prefix) gets established
            form.instance.type = self.prefix
        return True, ""


class CollectionListView(BasicList):
    """Search and list collections"""

    model = Collection
    listform = CollectionForm
    prefix = "any"
    paginate_by = 20
    bUseFilter = True
    has_select2 = True
    basic_name_prefix = "coll"
    plural_name = ""
    order_cols = ['scope', 'name', 'created', '']
    order_default = order_cols
    order_heads = [{'name': 'Scope',        'order': 'o=1', 'type': 'str', 'custom': 'scope'},
                   {'name': 'Collection',   'order': 'o=2', 'type': 'str', 'field': 'name', 'linkdetails': True, 'main': True},
                   {'name': 'Created',      'order': 'o=3', 'type': 'str', 'custom': 'created'},
                   {'name': 'Frequency',    'order': '',    'type': 'str', 'custom': 'links'}
                   ]
    filters = [ {"name": "Collection", "id": "filter_collection", "enabled": False}]
    searches = [
        {'section': '', 'filterlist': [
            {'filter': 'collection', 'dbfield': 'name', 'keyS': 'collection_ta', 'keyList': 'collist', 'infield': 'name'}]},
        {'section': 'other', 'filterlist': [
            {'filter': 'owner',   'fkfield': 'owner',  'keyS': 'owner', 'keyFk': 'id', 'keyList': 'ownlist', 'infield': 'id' },
            {'filter': 'coltype', 'dbfield': 'type',   'keyS': 'type',  'keyList': 'typelist' }]}
        ]

    def initializations(self):
        if self.prefix == "sermo":
            self.plural_name = "Sermon collections"
            self.sg_name = "Sermon collection"
        elif self.prefix == "manu":
            self.plural_name = "Manuscript Collections"
            self.sg_name = "Manuscript collection"
        elif self.prefix == "gold":
            self.plural_name = "Gold sermons Collections"
            self.sg_name = "Sermon gold collection"
        elif self.prefix == "super":
            self.plural_name = "Super sermons gold Collections"
            self.sg_name = "Super sermon gold collection"        
        elif self.prefix == "any":
            self.new_button = False
            self.plural_name = "All types Collections"
            self.sg_name = "Collection"  
            self.order_cols = ['type', 'scope', 'name', 'created', '']
            self.order_default = self.order_cols
            self.order_heads  = [
                {'name': 'Type',        'order': 'o=1', 'type': 'str', 'custom': 'type'},
                {'name': 'Scope',       'order': 'o=2', 'type': 'str', 'custom': 'scope'},
                {'name': 'Collection',  'order': 'o=3', 'type': 'str', 'field': 'name', 'linkdetails': True, 'main': True},
                {'name': 'Created',     'order': 'o=4', 'type': 'str', 'custom': 'created'},
                {'name': 'Frequency',   'order': '',    'type': 'str', 'custom': 'links'}
            ]  
        return None

    def adapt_search(self, fields):
        # Check if the collist is identified
        if fields['ownlist'] == None or len(fields['ownlist']) == 0:
            # Get the user
            user = User.objects.filter(username=self.request.user.username).first()
            # Get to the profile of this user
            qs = Profile.objects.filter(user=user)
            fields['ownlist'] = qs

            # Also make sure that we add the collection type, which is specified in "prefix"
            if self.prefix != "any":
                fields['type'] = self.prefix
        return fields

    def get_field_value(self, instance, custom):
        sBack = ""
        sTitle = ""
        if custom == "links":
            html = []
            # Get the HTML code for the links of this instance
            number = instance.freqsermo()
            if number > 0:
                url = reverse('sermon_list')
                html.append("<a href='{}?sermo-collist_s={}'>".format(url, instance.id))
                html.append("<span class='badge jumbo-1 clickable' title='Frequency in manifestation sermons'>{}</span></a>".format(number))
            number = instance.freqgold()
            if number > 0:
                url = reverse('search_gold')
                html.append("<a href='{}?gold-collist_sg={}'>".format(url, instance.id))
                html.append("<span class='badge jumbo-2 clickable' title='Frequency in gold sermons'>{}</span></a>".format(number))
            number = instance.freqmanu()
            if number > 0:
                url = reverse('search_manuscript')
                html.append("<a href='{}?manu-collist_m={}'>".format(url, instance.id))
                html.append("<span class='badge jumbo-3 clickable' title='Frequency in manuscripts'>{}</span></a>".format(number))
            number = instance.freqsuper()
            if number > 0:
                url = reverse('equalgold_list')
                html.append("<a href='{}?ssg-collist_ssg={}'>".format(url, instance.id))
                html.append("<span class='badge jumbo-3 clickable' title='Frequency in manuscripts'>{}</span></a>".format(number))
            # Combine the HTML code
            sBack = "\n".join(html)
        elif custom == "type":
            sBack = instance.get_type_display()
        elif custom == "scope":
            sBack = instance.get_scope_display()
        elif custom == "created":
            sBack = get_crpp_date(instance.created)
        return sBack, sTitle


class CollectionEdit(PassimDetails):
    """The details of one collection"""
 
    model = Collection
    mForm = CollectionForm
    template_name = 'seeker/collection_edit.html'
    template_post = 'seeker/collection_edit.html'
    prefix = 'col'
    title = "CollectionEdit"
    afternewurl = ""
    rtype = "json"

    def after_new(self, form, instance):
        """Action to be performed after adding a new item"""

        self.afternewurl = reverse('collection_list')
        return True, "" 
        
    def add_to_context(self, context, instance):
        context['is_app_editor'] = user_is_ingroup(self.request, app_editor)
        # Process this visit and get the new breadcrumbs object
        prevpage = reverse('collection_list')
        context['prevpage'] = prevpage
        crumbs = []
        crumbs.append(['Collections', reverse('collection_list')])
        context['breadcrumbs'] = get_breadcrumbs(self.request, "Collection details", True, crumbs)
        context['afterdelurl'] = reverse('collection_list')
       
        return context

    def before_save(self, form, instance):
        if form != None:
            # Search the user profile
            profile = Profile.get_user_profile(self.request.user.username)
            form.instance.owner = profile
        return True, ""


class CollectionDetails(CollectionEdit):
    """The editing of one collection"""

    template_name = 'seeker/collection_details.html'
    template_post = 'seeker/collection_details.html'
    title = "CollectionDetails"
    rtype = "html"  # GET provides a HTML form straight away

    def after_new(self, form, instance):
        """Action to be performed after adding a new item"""

        self.afternewurl = reverse('collection_list')
        if instance != None:
            # Make sure we do a page redirect
            self.newRedirect = True
            self.redirectpage = reverse('collection_details', kwargs={'pk': instance.id})
        return True, "" 


class CollectionSermset(BasicPart):
    """The set of sermons from the collection"""

    MainModel = Collection
    template_name = 'seeker/collection_sermset.html'
    title = "CollectionsSermons"

    def add_to_context(self, context):
        
        # Pass on all the sermons from each Collection
        col = self.obj.id #??
        scol_list = []
        for item in Collection.objects.filter(collection_id=col):
            oAdd = {}
            oAdd['title'] = item.title.id
            # oAdd['title'] = item.reference.title

            scol_list.append(oAdd)

        context['scol_list'] = scol_list

        return context


class SermonLinkset(BasicPart):
    """The set of links from one gold sermon"""

    MainModel = SermonDescr
    template_name = 'seeker/sermon_linkset.html'
    title = "SermonLinkset"
    StogFormSet = inlineformset_factory(SermonDescr, SermonDescrGold,
                                         form=SermonDescrGoldForm, min_num=0,
                                         fk_name = "sermon",
                                         extra=0, can_delete=True, can_order=False)
    formset_objects = [{'formsetClass': StogFormSet, 'prefix': 'stog', 'readonly': False, 'initial': [{'linktype': LINK_EQUAL }]}]

    def add_to_context(self, context):
        x = 1
        #for fs in context['stog_formset']:
        #    for form in fs:
        #        gold = form['gold']
        #        geq = gold.equal_goldsermons.all()
        #        qs = geq
        return context


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
    
    
class SermonColset(BasicPart):
    """The set of collections that the sermon is a part of"""
    MainModel = SermonDescr
    template_name = 'seeker/sermon_colset.html'
    title = "SermonDescrCollections"
    ScolFormSet = inlineformset_factory(SermonDescr, CollectionSerm,  
                                        form = SermonDescrCollectionForm, min_num=0,
                                        fk_name = "sermon", extra=0, can_delete=True, can_order=False)
    formset_objects = [{'formsetClass': ScolFormSet, 'prefix': 'scol', 'readonly': False}]

    def before_save(self, prefix, request, instance = None, form = None):
        has_changed = False
        if prefix == "scol":
            # Get the chosen collection
            obj = form.cleaned_data['collection']
            if obj == None:
                # Get the value entered for the collection
                col = form['name'].data
                # Check if this is an existing collection
                obj = Collection.objects.filter(name__iexact=col).first() # gaat dit goed
                # Now set the instance value correctly
                instance.collection = obj
                has_changed = True

        return has_changed


class SermonKwset(BasicPart):
    """The set of keywords from one sermon"""

    MainModel = SermonDescr
    template_name = 'seeker/sermon_kwset.html'
    title = "SermonDescrKeywords"
    SkwFormSet = inlineformset_factory(SermonDescr, SermonDescrKeyword,
                                         form=SermonDescrKeywordForm, min_num=0,
                                         fk_name = "sermon",
                                         extra=0, can_delete=True, can_order=False)
    formset_objects = [{'formsetClass': SkwFormSet, 'prefix': 'skw', 'readonly': False}]

    def before_save(self, prefix, request, instance = None, form = None):
        has_changed = False
        if prefix == "skw":
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
    

class SermonEdiset(BasicPart):
    """The set of editions from the gold-sermons related to me"""

    MainModel = SermonDescr
    template_name = 'seeker/sermon_ediset.html'
    title = "SermonDescrEditions"

    def add_to_context(self, context):

        # Pass on all the linked-gold editions to the sermons
        sedi_list = []
        # Visit all linked gold sermons
        for linked in SermonDescrGold.objects.filter(sermon=self.obj, linktype=LINK_EQUAL):
            # Access the gold sermon
            gold = linked.gold
            
            # Get all the editions references of this gold sermon 
            for item in EdirefSG.objects.filter(sermon_gold_id = gold):
                
                oAdd = {}
                oAdd['reference_id'] = item.reference.id
                oAdd['short'] = item.reference.short
                oAdd['reference'] = item.reference
                oAdd['pages'] = item.pages
                sedi_list.append(oAdd)
       
        context['sedi_list'] = sedi_list

        return context


class SermonLitset(BasicPart):
    """The set of literature references from SermonGold(s) and Manuscript passed over to each Sermon"""

    MainModel = SermonDescr
    template_name = 'seeker/sermon_litset.html'
    title = "SermonDescrLiterature"
    
    def add_to_context(self, context):
        
        # Pass on all the literature from Manuscript to each of the Sermons of that Manuscript
               
        # First the litrefs from the manuscript: 
        manu = self.obj.manu
        lref_list = []
        for item in LitrefMan.objects.filter(manuscript=manu):
            oAdd = {}
            oAdd['reference_id'] = item.reference.id
            oAdd['short'] = item.reference.short
            oAdd['reference'] = item.reference
            oAdd['pages'] = item.pages
            lref_list.append(oAdd)
       
        # Second the litrefs from the linked Gold sermons: 

        for linked in SermonDescrGold.objects.filter(sermon=self.obj, linktype=LINK_EQUAL):
            # Access the gold sermon
            gold = linked.gold
            # Get all the literature references of this gold sermon 
            for item in LitrefSG.objects.filter(sermon_gold_id = gold):
                
                oAdd = {}
                oAdd['reference_id'] = item.reference.id
                oAdd['short'] = item.reference.short
                oAdd['reference'] = item.reference
                oAdd['pages'] = item.pages
                lref_list.append(oAdd)
                
        # Set the sort order TH: werkt
        lref_list = sorted(lref_list, key=lambda x: "{}_{}".format(x['short'].lower(), x['pages']))
                
        # Remove duplicates 
        unique_litref_list=[]
                
        previous = None
        for item in lref_list:
            # Keep the first
            if previous == None:
                unique_litref_list.append(item)
            # Try to compare current item to previous
            elif previous != None:
                # Are they the same?
                if item['reference_id'] == previous['reference_id'] and \
                    item['pages'] == previous['pages']:
                    # They are the same, no need to copy
                    pass
                            
                # elif previous == None: 
                #    unique_litref_list.append(item)
                else:
                    # Add this item to the new list
                    unique_litref_list.append(item)

            # assign previous
            previous = item
                
        litref_list = unique_litref_list
        
        context['lref_list'] = litref_list
       
        return context


class ManuscriptEdit(PassimDetails):
    """The details of one manuscript"""

    model = Manuscript  
    mForm = ManuscriptForm
    template_name = 'seeker/manuscript_edit.html'  
    title = "Manuscript" 
    afternewurl = ""
    prefix = "manu"
    MdrFormSet = inlineformset_factory(Manuscript, Daterange,
                                         form=DaterangeForm, min_num=1,
                                         fk_name = "manuscript",
                                         extra=0, can_delete=True, can_order=False)
    McolFormSet = inlineformset_factory(Manuscript, CollectionMan,
                                       form=ManuscriptCollectionForm, min_num=0,
                                       fk_name="manuscript", extra=0)
    MlitFormSet = inlineformset_factory(Manuscript, LitrefMan,
                                         form = ManuscriptLitrefForm, min_num=0,
                                         fk_name = "manuscript",
                                         extra=0, can_delete=True, can_order=False)

    formset_objects = [{'formsetClass': MdrFormSet, 'prefix': 'mdr', 'readonly': False},
                       {'formsetClass': McolFormSet,  'prefix': 'mcol',  'readonly': False, 'noinit': True, 'linkfield': 'manu'},
                       {'formsetClass': MlitFormSet,  'prefix': 'mlit',  'readonly': False, 'noinit': True, 'linkfield': 'manuscript'}]

    def add_to_context(self, context, instance):

        # context['afternewurl'] = reverse('search_manuscript')
        context['afterdelurl'] = reverse('search_manuscript')

        # All us wellL return the adapted context
        return context
    
    def process_formset(self, prefix, request, formset):

        errors = []
        bResult = True
        instance = formset.instance
        for form in formset:
            if form.is_valid():
                cleaned = form.cleaned_data
                # Action depends on prefix
                if prefix == "mcol":
                    # Keyword processing
                    if 'newcol' in cleaned and cleaned['newcol'] != "":
                        newcol = cleaned['newcol']
                        # Is the COL already existing?
                        obj = Collection.objects.filter(name=newcol).first()
                        if obj == None:
                            # TODO: add profile here
                            profile = Profile.get_user_profile(request.user.username)
                            obj = Collection.objects.create(name=newcol, type='manu', owner=profile)
                        # Make sure we set the keyword
                        form.instance.collection = obj
                        # Note: it will get saved with formset.save()
                elif prefix == "mlit":
                    # Literature reference processing
                    newpages = ""
                    if 'newpages' in cleaned and cleaned['newpages'] != "":
                        newpages = cleaned['newpages']
                    # Also get the litref
                    if 'oneref' in cleaned:
                        litref = cleaned['oneref']
                        # Check if all is in order
                        if litref:
                            form.instance.reference = litref
                            if newpages:
                                form.instance.pages = newpages
                    # Note: it will get saved with form.save()
                
            else:
                errors.append(form.errors)
                bResult = False
        return None

    def before_save(self, form, instance = None):
        bOkay = True
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

        return bOkay, ""
    
    def after_save(self, form, instance):
        msg = ""
        bResult = True
        oErr = ErrHandle()
        
        try:
            # Process many-to-many changes: Add and remove relations in accordance with the new set passed on by the user
            collist = form.cleaned_data['collist']
            adapt_m2m(CollectionMan, instance, "manuscript", collist, "collection")
            litlist = form.cleaned_data['litlist']
            adapt_m2m(LitrefMan, instance, "manuscript", litlist, "reference", extra=['pages'], related_is_through = True)
                    
        except:
            msg = oErr.get_error_message()
            bResult = False
        
        return bResult, msg


class ManuscriptDetails(ManuscriptEdit):
    """Editable manuscript details"""

    template_name = 'seeker/manuscript_details.html'    # Use this for GET requests
    afternewurl = ""
    rtype = "html"      # Load this as straight forward html

    def after_new(self, form, instance):
        """Action to be performed after adding a new item"""

        # Set a redirect page
        if instance != None:
            # Make sure we do a page redirect
            self.newRedirect = True
            self.redirectpage = reverse('manuscript_details', kwargs={'pk': instance.id})
        return True, "" 

    def before_save(self, form, instance):
        bNeedSaving = False
        if instance:
            if not instance.project:
                # Set the default project: Passim
                passim = Project.objects.filter(Q(name__iexact="passim")).first()
                instance.project = passim
                bNeedSaving = True
            if instance.source == None:
                # Create a source info element
                source = SourceInfo(collector=self.request.user.username, code="Manually added") # TH: aanpassen, klopt niet, ccfr
                source.save()
                instance.source = source
                bNeedSaving = True
        return bNeedSaving, ""

    def add_to_context(self, context, instance):
        template_sermon = 'seeker/sermon_view.html'

        def sermon_object(obj ):
            # Calculate the HTML for this sermon
            context = dict(msitem=obj)
            html = treat_bom( render_to_string(template_sermon, context))
            # Determine what the label is going to be
            label = obj.locus
            # Determine the parent, if any
            parent = 1 if obj.parent == None else obj.parent.order + 1
            id = obj.order + 1
            # Create a sermon representation
            oSermon = dict(id=id, parent=parent, pos=label, child=[], f = dict(order=obj.order, html=html))
            return oSermon

        # Construct the hierarchical list
        sermon_list = []
        maxdepth = 0
        build_htable = False

        if instance != None:
            # Create a well sorted list of sermons
            qs = instance.manusermons.filter(order__gte=0).order_by('order')
            prev_level = 0
            for sermon in qs:
                # Need this first, because it also REPAIRS possible parent errors
                level = sermon.getdepth()

                # Only then continue!
                oSermon = {}
                oSermon['obj'] = sermon
                oSermon['nodeid'] = sermon.order + 1
                oSermon['childof'] = 1 if sermon.parent == None else sermon.parent.order + 1
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

            # Alternative method: create a hierarchical object of sermons
            if build_htable:
                lSermon = []
                for sermon in qs:
                    # Create sermon object
                    oSermon = sermon_object(sermon)
                    # Add it to the list
                    lSermon.append(oSermon)
                    # Immediately attach it to the correct parent
                    parent_id = oSermon['parent']
                    if parent_id:
                        oParent = next((x for x in lSermon if x['id'] == oSermon['parent'] ), None)
                        if oParent:
                            oParent['child'].append(oSermon)
                # Retain the top sermon
                oSermon = lSermon[0]
                # Remove the list
                lSermon = []

                # DEBUGGING: show what we have
                sSermon = json.dumps(oSermon)
                context['sermon_htable'] = sSermon

        # Add instances to the list, noting their childof and order
        context['sermon_list'] = sermon_list
        context['sermon_count'] = len(sermon_list)
        context['maxdepth'] = maxdepth
        #context['isnew'] = bNew

        # Figure out what the identity of this manuscript is
        manu_name = "Manuscript details"
        if instance == "None":
            manu_name = "New manuscript"
        else:
            if instance.idno:
                manu_name = "{}".format(instance.idno)
            elif instance.name:
                manu_name = "Manuscript [{}]".format(instance.name)
            elif instance.library:
                manu_name = "Manuscript from: [{}]".format(instance.library.name)
            else:
                manu_name = "Manuscript (unidentified)"

        # Process this visit and get the new breadcrumbs object
        prevpage = reverse('search_manuscript')
        context['prevpage'] = prevpage
        crumbs = []
        crumbs.append(['Manuscripts', prevpage])
        context['breadcrumbs'] = get_breadcrumbs(self.request, manu_name, False, crumbs)

        context['afternewurl'] = reverse('search_manuscript')

        return context


class ManuscriptHierarchy(ManuscriptDetails):
    newRedirect = True

    def custom_init(self, instance):
        errHandle = ErrHandle()

        try:
            # Make sure to set the correct redirect page
            if instance:
                self.redirectpage = reverse("manuscript_details", kwargs={'pk': instance.id})
            # Make sure we are not saving
            self.do_not_save = True
            # Get the [hlist] value
            if 'manu-hlist' in self.qd:
                # Interpret the list of information that we receive
                hlist = json.loads(self.qd['manu-hlist'])
                with transaction.atomic():
                    for item in hlist:
                        bNeedSaving = False
                        # Get the sermon of this item
                        sermon = SermonDescr.objects.filter(id=item['id']).first()
                        order = int(item['nodeid']) -1
                        parent_order = int(item['childof']) - 1
                        parent = None if parent_order == 0 else SermonDescr.objects.filter(manu=instance, order=parent_order).first()
                        # Check if anytyhing changed
                        if sermon.order != order:
                            sermon.order = order
                            bNeedSaving =True
                        if sermon.parent is not parent:
                            sermon.parent = parent
                            # Sanity check...
                            if sermon.parent.id == parent.id:
                                sermon.parent = None
                            bNeedSaving = True
                        # Do we need to save this one?
                        if bNeedSaving:
                            sermon.save()

            return True
        except:
            msg = errHandle.get_error_message()
            errHandle.DoError("ManuscriptHierarchy")
            return False


class ManuscriptListView(BasicList):
    """Search and list manuscripts"""
    
    model = Manuscript
    listform = SearchManuForm
    has_select2 = True
    paginate_by = 20
    bUseFilter = True
    prefix = "manu"
    order_cols = ['library__lcity__name', 'library__name', 'idno;name', '', 'yearstart','yearfinish', 'stype','']
    order_default = order_cols
    order_heads = [{'name': 'City',     'order': 'o=1', 'type': 'str', 'custom': 'city'},
                   {'name': 'Library',  'order': 'o=2', 'type': 'str', 'custom': 'library'},
                   {'name': 'Name',     'order': 'o=3', 'type': 'str', 'custom': 'name', 'main': True, 'linkdetails': True},
                   {'name': 'Items',    'order': '',    'type': 'int', 'custom': 'count',   'align': 'right'},
                   {'name': 'From',     'order': 'o=5', 'type': 'int', 'custom': 'from',    'align': 'right'},
                   {'name': 'Until',    'order': 'o=6', 'type': 'int', 'custom': 'until',   'align': 'right'},
                   {'name': 'Status',   'order': 'o=7', 'type': 'str', 'custom': 'status'},
                   {'name': '',         'order': '',    'type': 'str', 'custom': 'links'}]
    filters = [ 
        {"name": "Shelfmark",       "id": "filter_manuid",           "enabled": False},
        {"name": "Country",         "id": "filter_country",          "enabled": False},
        {"name": "City",            "id": "filter_city",             "enabled": False},
        {"name": "Library",         "id": "filter_library",          "enabled": False},
        {"name": "Origin",          "id": "filter_origin",           "enabled": False},
        {"name": "Provenance",      "id": "filter_provenance",       "enabled": False},
        {"name": "Date range",      "id": "filter_daterange",        "enabled": False},
        {"name": "Keyword",         "id": "filter_keyword",          "enabled": False},
        {"name": "Sermon...",       "id": "filter_sermon",           "enabled": False, "head_id": "none"},
        {"name": "Collection...",   "id": "filter_collection",       "enabled": False, "head_id": "none"},
        {"name": "Gryson or Clavis","id": "filter_signature",        "enabled": False, "head_id": "filter_sermon"},
        {"name": "Manuscript",      "id": "filter_collection_manu",  "enabled": False, "head_id": "filter_collection"},
        {"name": "Sermon",          "id": "filter_collection_sermo", "enabled": False, "head_id": "filter_collection"},
        {"name": "Sermon Gold",     "id": "filter_collection_gold",  "enabled": False, "head_id": "filter_collection"},
        {"name": "Super sermon gold","id": "filter_collection_super","enabled": False, "head_id": "filter_collection"},
        {"name": "Project",         "id": "filter_project",          "enabled": False, "head_id": "filter_other"},
      ]

    searches = [
        {'section': '', 'filterlist': [
            {'filter': 'manuid',           'dbfield': 'idno',                                   'keyS': 'idno',          'keyList': 'manuidlist', 'infield': 'id'},
            {'filter': 'country',          'fkfield': 'library__lcountry',                      'keyS': 'country_ta',    'keyId': 'country',     'keyFk': "name"},
            {'filter': 'city',             'fkfield': 'library__lcity',                         'keyS': 'city_ta',       'keyId': 'city',        'keyFk': "name"},
            {'filter': 'library',          'fkfield': 'library',                                'keyS': 'libname_ta',    'keyId': 'library',     'keyFk': "name"},
            {'filter': 'provenance',       'fkfield': 'provenances__location',                  'keyS': 'prov_ta',       'keyId': 'prov',        'keyFk': "name"},
            {'filter': 'origin',           'fkfield': 'origin',                                 'keyS': 'origin_ta',     'keyId': 'origin',      'keyFk': "name"},
            {'filter': 'keyword',          'fkfield': 'keywords',                               'keyS': 'keyword',       'keyFk': 'name', 'keyList': 'kwlist', 'infield': 'name' },
            {'filter': 'daterange',        'dbfield': 'yearstart__gte',                         'keyS': 'date_from'},
            {'filter': 'daterange',        'dbfield': 'yearfinish__lte',                        'keyS': 'date_until'},
            ]},
        {'section': 'collection', 'filterlist': [
            {'filter': 'collection_manu',  'fkfield': 'collections',                            'keyS': 'collection',    'keyFk': 'name', 'keyList': 'collist_m', 'infield': 'name' },
            {'filter': 'collection_sermo', 'fkfield': 'manusermons__collections',               'keyS': 'collection_s',  'keyFk': 'name', 'keyList': 'collist_s', 'infield': 'name' },
            {'filter': 'collection_gold',  'fkfield': 'manusermons__goldsermons__collections',  'keyS': 'collection_sg', 'keyFk': 'name', 'keyList': 'collist_sg', 'infield': 'name' },
            {'filter': 'collection_super', 'fkfield': 'manusermons__goldsermons__equal__collections', 'keyS': 'collection_ssg','keyFk': 'name', 'keyList': 'collist_ssg', 'infield': 'name' },
            ]},
        {'section': 'sermon', 'filterlist': [
            {'filter': 'signature', 'fkfield': 'manusermons__sermonsignatures',  'keyS': 'signature', 'keyFk': 'code', 'keyId': 'signatureid', 'keyList': 'siglist', 'infield': 'code' },
            ]},
        {'section': 'other', 'filterlist': [
            {'filter': 'project',   'fkfield': 'project',  'keyS': 'project', 'keyFk': 'id', 'keyList': 'prjlist', 'infield': 'name' },
            ]}
         ]
    #uploads = [{"title": "ecodex", "label": "e-codices", "url": "import_ecodex", "msg": "Upload e-codices XML files"},
    #           {"title": "ead",    "label": "EAD",       "url": "import_ead",    "msg": "Upload 'archives et manuscripts' XML files"}]
    uploads = reader_uploads
    custombuttons = [{"name": "search_ecodex", "title": "Convert e-codices search results into a list", "icon": "music", "template_name": "seeker/search_ecodices.html" }]

    def add_to_context(self, context, initial):
        # Add a files upload form
        context['uploadform'] = UploadFilesForm()

        # Add a form to enter a URL
        context['searchurlform'] = SearchUrlForm()
        
        # Find out who the user is
        profile = Profile.get_user_profile(self.request.user.username)
        context['basketsize'] = 0 if profile == None else profile.basketsize_manu
        context['basket_show'] = reverse('basket_show_manu')
        context['basket_update'] = reverse('basket_update_manu')

        return context

    def get_basketqueryset(self):
        if self.basketview:
            profile = Profile.get_user_profile(self.request.user.username)
            qs = profile.basketitems_manu.all()
        else:
            qs = Manuscript.objects.all()
        return qs

    def adapt_search(self, fields):
        # Check if the prjlist is identified
        if fields['prjlist'] == None or len(fields['prjlist']) == 0:
            # Get the default project
            qs = Project.objects.all()
            if qs.count() > 0:
                prj_default = qs.first()
                qs = Project.objects.filter(id=prj_default.id)
                fields['prjlist'] = qs
        return fields

    def get_field_value(self, instance, custom):
        sBack = ""
        sTitle = ""
        html = []
        if custom == "city":
            if instance.library and instance.library.lcity:
                city = instance.library.lcity.name
                html.append("<span>{}</span>".format(city[:12]))        
                sTitle = city
        elif custom == "library":
            if instance.library:
                lib = instance.library.name
                html.append("<span>{}</span>".format(lib[:12]))  
                sTitle = lib      
        elif custom == "name":
            html.append("<span class='manuscript-idno'>{}</span>".format(instance.idno))
            if instance.name:
                html.append("<span class='manuscript-title'>| {}</span>".format(instance.name[:100]))
                sTitle = instance.name
        elif custom == "count":
            html.append("{}".format(instance.manusermons.count()))
        elif custom == "from":
            for item in instance.manuscript_dateranges.all():
                html.append("<div>{}</div".format(item.yearstart))
        elif custom == "until":
            for item in instance.manuscript_dateranges.all():
                html.append("<div>{}</div".format(item.yearfinish))
        elif custom == "status":
            html.append("<span class='badge'>{}</span>".format(instance.stype[:1]))
            sTitle = instance.get_stype_display()
        elif custom == "links":
            sLinks = ""
            if instance.url:
                sLinks = "<a role='button' class='btn btn-xs jumbo-1' href='{}'><span class='glyphicon glyphicon-link'><span></a>".format(instance.url)
                sTitle = "External link"
            html.append(sLinks)
        # Combine the HTML code
        sBack = "\n".join(html)
        return sBack, sTitle
  

class ManuscriptProvset(BasicPart):
    """The set of provenances from one manuscript"""

    MainModel = Manuscript
    template_name = 'seeker/manuscript_provset.html'
    title = "ManuscriptProvenances"
    MprovFormSet = inlineformset_factory(Manuscript, ProvenanceMan,
                                         form=ManuscriptProvForm, min_num=0,
                                         fk_name = "manuscript",
                                         extra=0, can_delete=True, can_order=False)
    formset_objects = [{'formsetClass': MprovFormSet, 'prefix': 'mprov', 'readonly': False}]

    def get_queryset(self, prefix):
        qs = None
        if prefix == "mprov":
            # List the provenances for this manuscript correctly
            qs = ProvenanceMan.objects.filter(manuscript=self.obj).order_by('provenance__name')
        return qs

    def before_save(self, prefix, request, instance = None, form = None):
        has_changed = False
        if prefix == "mprov":
            # First need to get a possible ID of the (new) location 
            loc_id = form.cleaned_data['location']
            # Check if a new provenance should be made
            if instance.id == None or instance.provenance == None or instance.provenance.id == None or \
               instance.provenance.location != None and instance.provenance.location.id != int(loc_id):
                # Need to create a new provenance
                name = form.cleaned_data['name']
                note = form.cleaned_data['note']
                # Create the new provenance
                provenance = Provenance(name=name, note=note)

                bCanSave = True
                # Possibly add location
                loc_name = form.cleaned_data['location_ta']
                if loc_id != "":
                    location = Location.objects.filter(id=loc_id).first()
                    provenance.location = location
                elif loc_name != "":
                    # The user specified a new location, but we are not able to process it here
                    # TODO: how do we signal to the user that he has to add a location elsewhere??
                    bCanSave = False
                    self.arErr.append("You are using a new location [{}]. Add it first, and then select it.".format(loc_name))

                if bCanSave:
                    # Save the new provenance
                    provenance.save()
                    instance.provenance = provenance

                    # Make a new ProvenanceMan
                    instance.manuscript = self.obj

                    # Indicate that changes have been made
                    has_changed = True
            elif instance and instance.id and instance.provenance:
                # Check for any other changes in existing stuff
                provenance = instance.provenance
                name = form.cleaned_data['name']
                note = form.cleaned_data['note']
                if provenance.name != name:
                    # Change in name
                    instance.provenance.name = name
                    instance.provenance.save()
                    has_changed = True
                if provenance.note != note:
                    # Change in note
                    instance.provenance.note = note
                    instance.provenance.save()
                    has_changed = True

        return has_changed
    

class SermonGoldEdiset(BasicPart):
    """The set of critical text editions from one gold sermon""" 

    MainModel = SermonGold
    template_name = 'seeker/sermongold_ediset.html'
    title = "SermonGoldEditions"
    GediFormSet = inlineformset_factory(SermonGold, EdirefSG,
                                         form = SermonGoldEditionForm, min_num=0,
                                         fk_name = "sermon_gold",
                                         extra=0, can_delete=True, can_order=False)
    formset_objects = [{'formsetClass': GediFormSet, 'prefix': 'gedi', 'readonly': False}]

    def get_queryset(self, prefix):
        qs = None
        if prefix == "gedi":
            # List the editions for this SermonGold correctly
            qs = EdirefSG.objects.filter(sermon_gold=self.obj).order_by('reference__short')
        return qs
   
    def before_save(self, prefix, request, instance = None, form = None):
        has_changed = False
        # Check if a new litref should be processed
        litref_id = form.cleaned_data['litref']
        if litref_id != "":
            if instance.id == None or instance.reference == None or instance.reference.id == None or \
                instance.reference.id != int(litref_id):
                # Find the correct litref
                litref = Litref.objects.filter(id=litref_id).first()
                if litref != None:
                    # Adapt the value of the instance 
                    instance.reference = litref
                    has_changed = True
            
        return has_changed  
    

class ManuscriptLitset(BasicPart):
    """The set of literature references from one manuscript"""

    MainModel = Manuscript
    template_name = 'seeker/manuscript_litset.html'
    title = "ManuscriptLiterature"
    MlitFormSet = inlineformset_factory(Manuscript, LitrefMan,
                                         form = ManuscriptLitrefForm, min_num=0,
                                         fk_name = "manuscript",
                                         extra=0, can_delete=True, can_order=False)
    formset_objects = [{'formsetClass': MlitFormSet, 'prefix': 'mlit', 'readonly': False}]

    def get_queryset(self, prefix):
        qs = None
        if prefix == "mlit":
            # List the litrefs for this manuscript correctly
            qs = LitrefMan.objects.filter(manuscript=self.obj).order_by('reference__short')
        return qs

    def before_save(self, prefix, request, instance = None, form = None):
        has_changed = False
        # Check if a new reference should be processed
        litref_id = form.cleaned_data['litref']
        if litref_id != "":
            if instance.id == None or instance.reference == None or instance.reference.id == None or \
                instance.reference.id != int(litref_id):
                # Find the correct litref
                litref = Litref.objects.filter(id=litref_id).first()
                if litref != None:
                    # Adapt the value of the instance 
                    instance.reference = litref
                    has_changed = True
            
        return has_changed


class ManuscriptExtset(BasicPart):
    """The set of provenances from one manuscript"""

    MainModel = Manuscript
    template_name = 'seeker/manuscript_extset.html'
    title = "ManuscriptExternalLinks"
    MextFormSet = inlineformset_factory(Manuscript, ManuscriptExt,
                                         form=ManuscriptExtForm, min_num=0,
                                         fk_name = "manuscript",
                                         extra=0, can_delete=True, can_order=False)
    formset_objects = [{'formsetClass': MextFormSet, 'prefix': 'mext', 'readonly': False}]

    def get_queryset(self, prefix):
        qs = None
        if prefix == "mext":
            # List the external links for this manuscript correctly
            qs = ManuscriptExt.objects.filter(manuscript=self.obj).order_by('url')
        return qs

    def before_save(self, prefix, request, instance = None, form = None):
        has_changed = False
        # NOTE: no drastic things here yet
        return has_changed

    
class ManuscriptKwset(BasicPart):
    """The set of keywords from one manuscript"""

    MainModel = Manuscript
    template_name = 'seeker/manuscript_kwset.html'
    title = "ManuscriptKeywords"
    MkwFormSet = inlineformset_factory(Manuscript, ManuscriptKeyword,
                                         form=ManuscriptKeywordForm, min_num=0,
                                         fk_name = "manuscript",
                                         extra=0, can_delete=True, can_order=False)
    formset_objects = [{'formsetClass': MkwFormSet, 'prefix': 'mkw', 'readonly': False}]

    def before_save(self, prefix, request, instance = None, form = None):
        has_changed = False
        if prefix == "mkw":
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


class SermonGoldListView(BasicList):
    """Search and list manuscripts"""
    
    model = SermonGold
    listform = SermonGoldForm
    prefix = "gold"
    basic_name = "gold"
    plural_name = "Gold sermons"
    sg_name = "Gold sermon"
    new_button = False      # Don't show the [Add a new Gold Sermon] button here. 
                            # Issue #173: creating Gold Sermons may only happen from SuperSermonGold list view
    has_select2 = True
    paginate_by = 20
    order_default = ['author__name', 'siglist', 'equal__code', 'srchincipit;srchexplicit', '', '', '']
    order_cols = order_default
    order_heads = [{'name': 'Author', 'order': 'o=1', 'type': 'str', 'custom': 'author'}, 
                   {'name': 'Signature', 'order': 'o=2', 'type': 'str', 'custom': 'signature'}, 
                   {'name': 'Passim Code', 'order': 'o=3', 'type': 'str', 'custom': 'code'}, 
                   {'name': 'Incipit ... Explicit', 'order': 'o=4', 'type': 'str', 'custom': 'incexpl', 'main': True, 'linkdetails': True},
                   {'name': 'Editions', 'order': '', 'type': 'str', 'custom': 'edition'},
                   {'name': 'Links', 'order': '', 'type': 'str', 'custom': 'links'},
                   {'name': 'Status', 'order': '', 'type': 'str', 'custom': 'status'}]
    filters = [
        {"name": "Gryson or Clavis","id": "filter_signature",   "enabled": False},
        {"name": "Passim code",     "id": "filter_code",        "enabled": False},
        {"name": "Author",          "id": "filter_author",      "enabled": False},
        {"name": "Incipit",         "id": "filter_incipit",     "enabled": False},
        {"name": "Explicit",        "id": "filter_explicit",    "enabled": False},
        {"name": "Keyword",         "id": "filter_keyword",     "enabled": False},
        {"name": "Collection...",   "id": "filter_collection",  "enabled": False, "head_id": "none"},
        {"name": "Manuscript",      "id": "filter_collmanu",    "enabled": False, "head_id": "filter_collection"},
        {"name": "Sermon",          "id": "filter_collsermo",   "enabled": False, "head_id": "filter_collection"},
        {"name": "Sermon Gold",     "id": "filter_collgold",    "enabled": False, "head_id": "filter_collection"},
        {"name": "Super sermon gold","id": "filter_collsuper",  "enabled": False, "head_id": "filter_collection"},
        ]       
    searches = [
        {'section': '', 'filterlist': [
            {'filter': 'incipit',   'dbfield': 'srchincipit',       'keyS': 'incipit'},
            {'filter': 'explicit',  'dbfield': 'srchexplicit',      'keyS': 'explicit'},
            {'filter': 'author',    'fkfield': 'author',            'keyS': 'authorname', 'keyFk': 'name', 'keyList': 'authorlist', 'infield': 'id', 'external': 'gold-authorname' },
            {'filter': 'signature', 'fkfield': 'goldsignatures',    'keyS': 'signature', 'keyFk': 'code', 'keyId': 'signatureid', 'keyList': 'siglist', 'infield': 'code' },
            {'filter': 'code',      'fkfield': 'equal',             'keyFk': 'code',     'keyList': 'codelist', 'infield': 'code'},
            {'filter': 'keyword',   'fkfield': 'keywords',          'keyS': 'keyword',   'keyFk': 'name', 'keyList': 'kwlist', 'infield': 'name' } ]},
        {'section': 'collection', 'filterlist': [
            {'filter': 'collmanu',  'fkfield': 'sermondescr__manu__collections','keyS': 'collection','keyFk': 'name', 'keyList': 'collist_m', 'infield': 'name' }, 
            {'filter': 'collsermo', 'fkfield': 'sermondescr__collections',      'keyS': 'collection','keyFk': 'name', 'keyList': 'collist_s', 'infield': 'name' }, 
            {'filter': 'collgold',  'fkfield': 'collections',                   'keyS': 'collection','keyFk': 'name', 'keyList': 'collist_sg', 'infield': 'name' }, 
            {'filter': 'collsuper', 'fkfield': 'equal__collections',            'keyS': 'collection','keyFk': 'name', 'keyList': 'collist_ssg', 'infield': 'name' } 
            ]}
        ]
    uploads = [{"title": "gold", "label": "Gold", "url": "import_gold", "msg": "Upload Excel files"}]

    def add_to_context(self, context, initial):
        # Find out who the user is
        profile = Profile.get_user_profile(self.request.user.username)
        context['basketsize'] = 0 if profile == None else profile.basketsize_gold
        context['basket_show'] = reverse('basket_show_gold')
        context['basket_update'] = reverse('basket_update_gold')
        return context

    def get_basketqueryset(self):
        if self.basketview:
            profile = Profile.get_user_profile(self.request.user.username)
            # TODO: chck the below -- is that SG??
            qs = profile.basketitems_gold.all()
        else:
            qs = SermonGold.objects.all()
        return qs

    def get_field_value(self, instance, custom):
        sBack = ""
        sTitle = ""
        html = []
        if custom == "author":
            if instance.author:
                html.append("<span style='color: darkgreen; font-size: small;'>{}</span>".format(instance.author.name[:20]))
                sTitle = instance.author.name
            else:
                html.append("<span><i>(unknown)</i></span>")
        elif custom == "signature":
            for sig in instance.goldsignatures.all():
                editype = sig.editype
                url = "{}?gold-siglist={}".format(reverse("gold_list"), sig.id)
                short = sig.short()
                html.append("<span class='badge signature {}' title='{}'><a class='nostyle' href='{}'>{}</a></span>".format(editype, short, url, short[:20]))
        elif custom == "code":
            equal = instance.equal
            if equal:
                code = "(undetermined)" if equal.code == None else equal.code
                url = reverse('equalgold_details', kwargs={'pk': equal.id})
            else:
                code = "(not specified)"
                url = "#"
            html.append("<span class='passimcode'><a class='nostyle' href='{}'>{}</a></span>".format(url, code))
        elif custom == "edition":
            html.append("<span>{}</span>".format(instance.editions()[:20]))
            sTitle = instance.editions()
        elif custom == "incexpl":
            if instance.incipit == "" and instance.explicit == "":
                url = reverse('gold_details', kwargs={'pk': instance.id})
                html.append("<span><a href='{}'><i>(not specified)</i></a></span>".format(url))
            else:
                html.append("<span>{}</span>".format(instance.get_incipit_markdown()))
                dots = "..." if instance.incipit else ""
                html.append("<span style='color: blue;'>{}</span>".format(dots))
                html.append("<span>{}</span>".format(instance.get_explicit_markdown()))
        elif custom == "links":
            for link_def in instance.link_oview():
                if link_def['count'] > 0:
                    html.append("<span class='badge {}' title='{}'>{}</span>".format(link_def['class'], link_def['title'], link_def['count']))
        elif custom == "status":
            # Provide that status badge
            html.append("<span class='badge' title='{}'>{}</span>".format(instance.get_stype_display(), instance.stype[:1]))
        # Combine the HTML code
        sBack = "\n".join(html)
        return sBack, sTitle

    def initializations(self):
        # Check if signature adaptation is needed
        gsig_done = Information.get_kvalue("sermon_gsig")
        if gsig_done == None or gsig_done == "":
            # Perform adaptations
            if SermonSignature.adapt_gsig():
                # Success
                Information.set_kvalue("sermon_gsig", "done")

        return None


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
        context['is_app_uploader'] = user_is_ingroup(self.request, app_uploader)
        context['is_app_editor'] = user_is_ingroup(self.request, app_editor)

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
                    lstQ.append(Q(srchincipit__iregex=val))

                # (3) Process explicit
                if 'explicit' in oFields and oFields['explicit'] != "" and oFields['explicit'] != None: 
                    val = adapt_search(oFields['explicit'])
                    lstQ.append(Q(srchexplicit__iregex=val))

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

    def after_save(self, prefix, instance = None, form = None):
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
    formset_objects = [{'formsetClass': GlinkFormSet, 'prefix': 'glink', 'readonly': False, 'initial': [{'linktype': LINK_EQUAL }]}]

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

    def after_save(self, prefix, instance = None, form = None):
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


class SermonGoldEdit(BasicDetails):
    """The details of one sermon"""

    model = SermonGold
    mForm = SermonGoldForm
    prefix = 'gold'
    title = "Sermon Gold"
    rtype = "json"
    mainitems = []
    basic_name = "gold"

    GkwFormSet = inlineformset_factory(SermonGold, SermonGoldKeyword,
                                       form=SermonGoldKeywordForm, min_num=0,
                                       fk_name="gold", extra=0)
    GsignFormSet = inlineformset_factory(SermonGold, Signature,
                                         form=SermonGoldSignatureForm, min_num=0,
                                         fk_name = "gold",
                                         extra=0, can_delete=True, can_order=False)
    GediFormSet = inlineformset_factory(SermonGold, EdirefSG,
                                         form = SermonGoldEditionForm, min_num=0,
                                         fk_name = "sermon_gold",
                                         extra=0, can_delete=True, can_order=False)
    GcolFormSet = inlineformset_factory(SermonGold, CollectionGold,
                                       form=SermonGoldCollectionForm, min_num=0,
                                       fk_name="gold", extra=0)
    GlitFormSet = inlineformset_factory(SermonGold, LitrefSG,
                                         form = SermonGoldLitrefForm, min_num=0,
                                         fk_name = "sermon_gold",
                                         extra=0, can_delete=True, can_order=False)
    GftxtFormSet = inlineformset_factory(SermonGold, Ftextlink,
                                         form=SermonGoldFtextlinkForm, min_num=0,
                                         fk_name = "gold",
                                         extra=0, can_delete=True, can_order=False)
    
    formset_objects = [{'formsetClass': GsignFormSet, 'prefix': 'gsign', 'readonly': False, 'noinit': True, 'linkfield': 'gold'},
                       {'formsetClass': GkwFormSet,   'prefix': 'gkw',   'readonly': False, 'noinit': True, 'linkfield': 'gold'},
                       {'formsetClass': GediFormSet,  'prefix': 'gedi',  'readonly': False, 'noinit': True, 'linkfield': 'sermon_gold'}, 
                       {'formsetClass': GcolFormSet,  'prefix': 'gcol',  'readonly': False, 'noinit': True, 'linkfield': 'gold'},
                       {'formsetClass': GlitFormSet,  'prefix': 'glit',  'readonly': False, 'noinit': True, 'linkfield': 'sermon_gold'},
                       {'formsetClass': GftxtFormSet, 'prefix': 'gftxt', 'readonly': False, 'noinit': True, 'linkfield': 'gold'}]

    def add_to_context(self, context, instance):
        """Add to the existing context"""

        # Define the main items to show and edit
        context['mainitems'] = [
            {'type': 'safe', 'label': "Belongs to:",            'value': instance.get_ssg_markdown,   
             'title': 'Belongs to the equality set of Super Sermon Gold...', 'field_key': "equal"}, 
            {'type': 'safe',  'label': "Together with:",        'value': instance.get_eqset,
             'title': 'Other Sermons Gold members of the same equality set'},
            {'type': 'plain', 'label': "Status:",               'value': instance.get_stype_display, 'field_key': 'stype', 'hidenew': True},
            {'type': 'plain', 'label': "Attributed author:",    'value': instance.get_author, 'field_key': 'author'},
            {'type': 'safe',  'label': "Incipit:",              'value': instance.get_incipit_markdown, 
             'field_key': 'incipit',  'key_ta': 'gldincipit-key'}, 
            {'type': 'safe',  'label': "Explicit:",             'value': instance.get_explicit_markdown,
             'field_key': 'explicit', 'key_ta': 'gldexplicit-key'}, 
            {'type': 'plain', 'label': "Bibliography:",         'value': instance.bibliography, 'field_key': 'bibliography'},
            {'type': 'line',  'label': "Keywords:",             'value': instance.get_keywords_markdown(), 
             'multiple': True, 'field_list': 'kwlist', 'fso': self.formset_objects[1]},
            {'type': 'line', 'label': "Gryson/Clavis codes:",   'value': instance.get_signatures_markdown(),  'unique': True, 
             'multiple': True, 'field_list': 'siglist', 'fso': self.formset_objects[0]},
            {'type': 'plain', 'label': "Collections:",          'value': instance.get_collections_markdown(), 
             'multiple': True, 'field_list': 'collist_sg', 'fso': self.formset_objects[3] },
            {'type': 'line', 'label': "Editions:",              'value': instance.get_editions_markdown(), 
             'multiple': True, 'field_list': 'edilist', 'fso': self.formset_objects[2], 'template_selection': 'ru.passim.litref_template'},
            {'type': 'line', 'label': "Literature:",            'value': instance.get_litrefs_markdown(), 
             'multiple': True, 'field_list': 'litlist', 'fso': self.formset_objects[4], 'template_selection': 'ru.passim.litref_template'},
            {'type': 'line', 'label': "Full text links:",       'value': instance.get_ftxtlinks_markdown(), 
             'multiple': True, 'field_list': 'ftxtlist', 'fso': self.formset_objects[5]},
            ]
        # Notes:
        # Collections: provide a link to the SSG-listview, filtering on those SSGs that are part of one particular collection


        # TODO: add [sermongold_litset] unobtrusively

        # Signal that we have select2
        context['has_select2'] = True

        # Return the context we have made
        return context

    def after_new(self, form, instance):
        """Action to be performed after adding a new item"""

        # Set the 'afternew' URL
        self.afternewurl = reverse('search_gold')

        # Create a new equality set to which we add this Gold sermon
        if instance.equal == None:
            geq = EqualGold.create_empty()
            instance.equal = geq
            instance.save()

        # Return positively
        return True, "" 

    def process_formset(self, prefix, request, formset):

        errors = []
        bResult = True
        instance = formset.instance
        for form in formset:
            if form.is_valid():
                cleaned = form.cleaned_data
                # Action depends on prefix
                if prefix == "gsign":
                    # Signature processing
                    editype = ""
                    code = ""
                    if 'newgr' in cleaned and cleaned['newgr'] != "":
                        # Add gryson
                        editype = "gr"
                        code = cleaned['newgr']
                    elif 'newcl' in cleaned and cleaned['newcl'] != "":
                        # Add gryson
                        editype = "cl"
                        code = cleaned['newcl']
                    elif 'newot' in cleaned and cleaned['newot'] != "":
                        # Add gryson
                        editype = "ot"
                        code = cleaned['newot']
                    if editype != "":
                        # Set the correct parameters
                        form.instance.code = code
                        form.instance.editype = editype
                        # Note: it will get saved with formset.save()
                elif prefix == "gkw":
                    # Keyword processing
                    if 'newkw' in cleaned and cleaned['newkw'] != "":
                        newkw = cleaned['newkw']
                        # Is the KW already existing?
                        obj = Keyword.objects.filter(name=newkw).first()
                        if obj == None:
                            obj = Keyword.objects.create(name=newkw)
                        # Make sure we set the keyword
                        form.instance.keyword = obj
                        # Note: it will get saved with formset.save()
                elif prefix == "gcol":
                    # Collection processing
                    if 'newcol' in cleaned and cleaned['newcol'] != "":
                        newcol = cleaned['newcol']
                        # Is the COL already existing?
                        obj = Collection.objects.filter(name=newcol).first()
                        if obj == None:
                            # TODO: add profile here
                            profile = Profile.get_user_profile(request.user.username)
                            obj = Collection.objects.create(name=newcol, type='gold', owner=profile)
                        # Make sure we set the keyword
                        form.instance.collection = obj
                        # Note: it will get saved with formset.save()
                elif prefix == "gedi":
                    # Edition processing
                    newpages = ""
                    if 'newpages' in cleaned and cleaned['newpages'] != "":
                        newpages = cleaned['newpages']
                    # Also get the litref
                    if 'oneref' in cleaned:
                        litref = cleaned['oneref']
                        # Check if all is in order
                        if litref:
                            form.instance.reference = litref
                            if newpages:
                                form.instance.pages = newpages
                    # Note: it will get saved with form.save()
                elif prefix == "glit":
                    # Literature reference processing
                    newpages = ""
                    if 'newpages' in cleaned and cleaned['newpages'] != "":
                        newpages = cleaned['newpages']
                    # Also get the litref
                    if 'oneref' in cleaned:
                        litref = cleaned['oneref']
                        # Check if all is in order
                        if litref:
                            form.instance.reference = litref
                            if newpages:
                                form.instance.pages = newpages
                    # Note: it will get saved with form.save()
                elif prefix == "gftxt":
                    # Process many-to-ONE full-text links
                    if 'newurl' in cleaned and cleaned['newurl'] != "":
                        form.instance.url = cleaned['newurl']
                        # Note: it will get saved with formset.save()
            else:
                errors.append(form.errors)
                bResult = False
        return None

    def after_save(self, form, instance):
        msg = ""
        bResult = True
        oErr = ErrHandle()
        
        try:
            # Process many-to-many changes: Add and remove relations in accordance with the new set passed on by the user
            # (1) 'keywords'
            kwlist = form.cleaned_data['kwlist']
            adapt_m2m(SermonGoldKeyword, instance, "gold", kwlist, "keyword")

            # (2) 'editions'
            edilist = form.cleaned_data['edilist']
            adapt_m2m(EdirefSG, instance, "sermon_gold", edilist, "reference", extra=['pages'], related_is_through = True)

            # (3) 'collections'
            collist_sg = form.cleaned_data['collist_sg']
            adapt_m2m(CollectionGold, instance, "gold", collist_sg, "collection")

            # (5) 'literature'
            litlist = form.cleaned_data['litlist']
            adapt_m2m(LitrefSG, instance, "sermon_gold", litlist, "reference", extra=['pages'], related_is_through = True)

            # Process many-to-ONE changes
            # (1) 'goldsignatures'
            siglist = form.cleaned_data['siglist']
            adapt_m2o(Signature, instance, "gold", siglist)

            # (2) 'full text links'
            ftxtlist = form.cleaned_data['ftxtlist']
            adapt_m2o(Ftextlink, instance, "gold", ftxtlist)
        except:
            msg = oErr.get_error_message()
            bResult = False
        return bResult, msg


class SermonGoldDetails(SermonGoldEdit):
    """The details of one sermon"""

    rtype = "html"

    def add_to_context(self, context, instance):
        """Add to the existing context"""

        # Start by executing the standard handling
        super(SermonGoldDetails, self).add_to_context(context, instance)

        # Are we copying information?? (only allowed if we are the app_editor)
        if 'goldcopy' in self.qd and context['is_app_editor']:
            # Get the ID of the gold sermon from which information is to be copied to the SSG
            goldid = self.qd['goldcopy']
        else:
            context['sections'] = []

            # List of post-load objects
            postload_objects = []
            ## (1) postload: full-text
            #ftxt_obj = dict(prefix="gftxt", url=reverse('gold_ftxtset', kwargs={'pk': instance.id}))
            #postload_objects.append(ftxt_obj)

            ## (2) postload: literature
            #lit_obj = dict(prefix="lit", url=reverse('gold_litset', kwargs={'pk': instance.id}))
            #postload_objects.append(lit_obj)

            context['postload_objects'] = postload_objects

            # Lists of related objects
            related_objects = []
            context['related_objects'] = related_objects

        # Return the context we have made
        return context

    def before_save(self, form, instance):
        return True, ""

    def process_formset(self, prefix, request, formset):
        return None

    def after_save(self, form, instance):
        return True, ""


class SermonGoldEdit_ORIGINAL(PassimDetails):
    """The details of one sermon"""

    model = SermonGold
    mForm = SermonGoldForm
    template_name = 'seeker/sermongold_edit.html'   
    prefix = "gold"
    title = "SermonGold" 
    basic_name = "gold"
    afternewurl = ""
    GkwFormSet = inlineformset_factory(SermonGold, SermonGoldKeyword,
                                       form=SermonGoldKeywordForm, min_num=0,
                                       fk_name="gold", extra=0)
    GsignFormSet = inlineformset_factory(SermonGold, Signature,
                                         form=SermonGoldSignatureForm, min_num=0,
                                         fk_name = "gold",
                                         extra=0, can_delete=True, can_order=False)
    GediFormSet = inlineformset_factory(SermonGold, EdirefSG,
                                         form = SermonGoldEditionForm, min_num=0,
                                         fk_name = "sermon_gold",
                                         extra=0, can_delete=True, can_order=False)
    GcolFormSet = inlineformset_factory(SermonGold, CollectionGold,
                                       form=SermonGoldCollectionForm, min_num=0,
                                       fk_name="gold", extra=0)
    
    formset_objects = [{'formsetClass': GsignFormSet, 'prefix': 'gsign', 'readonly': False, 'noinit': True, 'linkfield': 'gold'},
                       {'formsetClass': GkwFormSet,   'prefix': 'gkw',   'readonly': False, 'noinit': True, 'linkfield': 'gold'},
                       {'formsetClass': GediFormSet,  'prefix': 'gedi',  'readonly': False, 'noinit': True, 'linkfield': 'sermon_gold'}, 
                       {'formsetClass': GcolFormSet,  'prefix': 'gcol',  'readonly': False, 'noinit': True, 'linkfield': 'gold'}]

    def after_new(self, form, instance):
        """Action to be performed after adding a new item"""

        # Set the 'afternew' URL
        self.afternewurl = reverse('search_gold')

        # Create a new equality set to which we add this Gold sermon
        if instance.equal == None:
            geq = EqualGold.objects.create()
            instance.equal = geq
            instance.save()

        # Return positively
        return True, "" 

    def before_delete(self, instance):
        # All is well
        return True, "" 

    def process_formset(self, prefix, request, formset):

        errors = []
        bResult = True
        instance = formset.instance
        for form in formset:
            if form.is_valid():
                cleaned = form.cleaned_data
                # Action depends on prefix
                if prefix == "gsign":
                    # Signature processing
                    editype = ""
                    code = ""
                    if 'newgr' in cleaned and cleaned['newgr'] != "":
                        # Add gryson
                        editype = "gr"
                        code = cleaned['newgr']
                    elif 'newcl' in cleaned and cleaned['newcl'] != "":
                        # Add gryson
                        editype = "cl"
                        code = cleaned['newcl']
                    elif 'newot' in cleaned and cleaned['newot'] != "":
                        # Add gryson
                        editype = "ot"
                        code = cleaned['newot']
                    if editype != "":
                        # Set the correct parameters
                        form.instance.code = code
                        form.instance.editype = editype
                        # Note: it will get saved with formset.save()
                elif prefix == "gkw":
                    # Keyword processing
                    if 'newkw' in cleaned and cleaned['newkw'] != "":
                        newkw = cleaned['newkw']
                        # Is the KW already existing?
                        obj = Keyword.objects.filter(name=newkw).first()
                        if obj == None:
                            obj = Keyword.objects.create(name=newkw)
                        # Make sure we set the keyword
                        form.instance.keyword = obj
                        # Note: it will get saved with formset.save()
                elif prefix == "gcol":
                    # Keyword processing
                    if 'newcol' in cleaned and cleaned['newcol'] != "":
                        newcol = cleaned['newcol']
                        # Is the COL already existing?
                        obj = Collection.objects.filter(name=newcol).first()
                        if obj == None:
                            # TODO: add profile here
                            profile = Profile.get_user_profile(request.user.username)
                            obj = Collection.objects.create(name=newcol, type='gold', owner=profile)
                        # Make sure we set the keyword
                        form.instance.collection = obj
                        # Note: it will get saved with formset.save()
                elif prefix == "gedi":
                    # Edition processing
                    newpages = ""
                    if 'newpages' in cleaned and cleaned['newpages'] != "":
                        newpages = cleaned['newpages']
                    # Also get the litref
                    litref = cleaned['oneref']
                    # Check if all is in order
                    if litref:
                        form.instance.reference = litref
                        if newpages:
                            form.instance.pages = newpages
                    # Note: it will get saved with form.save()
            else:
                errors.append(form.errors)
                bResult = False
        return None

    def before_save(self, form, instance):
        form.fields['kwlist'].initial = instance.keywords.all().order_by('name')
        form.fields['siglist'].initial = instance.goldsignatures.all().order_by('editype', 'code')
        return True, ""

    def after_save(self, form, instance):
        msg = ""
        bResult = True
        oErr = ErrHandle()
        
        try:
            # Process many-to-many changes: Add and remove relations in accordance with the new set passed on by the user
            # (1) 'keywords'
            kwlist = form.cleaned_data['kwlist']
            adapt_m2m(SermonGoldKeyword, instance, "gold", kwlist, "keyword")
            edilist = form.cleaned_data['edilist']
            adapt_m2m(EdirefSG, instance, "sermon_gold", edilist, "reference", extra=['pages'], related_is_through = True)
            collist_sg = form.cleaned_data['collist_sg']
            adapt_m2m(CollectionGold, instance, "gold", collist_sg, "collection")

            # Process many-to-one changes
            # (1) 'goldsignatures'
            siglist = form.cleaned_data['siglist']
            adapt_m2o(Signature, instance, "gold", siglist)
        except:
            msg = oErr.get_error_message()
            bResult = False
        return bResult, msg

    def add_to_context(self, context, instance):
        """Add to the existing context"""

        # Check if editions have been added

        # Process this visit and get the new breadcrumbs object
        context['breadcrumbs'] = get_breadcrumbs(self.request, "Gold-Sermon edit", False)
        # context['prevpage'] = get_previous_page(self.request)
        prevpage = reverse('home')
        context['prevpage'] = prevpage

        context['afterdelurl'] = reverse('search_gold')

        return context


class SermonGoldDetails_ORIGINAL(SermonGoldEdit_ORIGINAL):
    """The details of one sermon"""

    template_name = 'seeker/sermongold_details.html'  
    rtype = "html"

    def after_new(self, form, instance):
        """Action to be performed after adding a new item"""
        # self.afternewurl = reverse('search_gold')

        if instance.equal == None:
            # Create a new equality set to which we add this Gold sermon
            geq = EqualGold.objects.create()
            instance.equal = geq
            instance.save()


        # Make sure we do a page redirect
        self.newRedirect = True
        self.redirectpage = reverse('gold_details', kwargs={'pk': instance.id})

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
        prevpage = reverse('search_gold')
        context['prevpage'] = prevpage
        crumbs = []
        crumbs.append(['Gold Sermons', prevpage])
        if instance:
            qs = instance.goldsignatures.all()
            if qs.count() == 0:
                current_name = "Gold-sermon (no id)"
            else:
                current_name = "Gold-sermon [{}]".format(qs[0].code)
        else:
            current_name = "Gold-sermon (new)"
        context['breadcrumbs'] = get_breadcrumbs(self.request, current_name, True, crumbs)

        return context

    def before_save(self, form, instance):
        return True, ""

    def process_formset(self, prefix, request, formset):
        return None

    def after_save(self, form, instance):
        return True, ""


class SermonGoldLitset(BasicPart):
    """The set of literature references from one SermonGold"""

    MainModel = SermonGold
    template_name = 'seeker/sermongold_litset.html'
    title = "SermonGoldLiterature"
    SGlitFormSet = inlineformset_factory(SermonGold, LitrefSG, form=SermonGoldLitrefForm, 
                                         min_num=0, fk_name = "sermon_gold",
                                         extra=0, can_delete=True, can_order=False)
    formset_objects = [{'formsetClass': SGlitFormSet, 'prefix': 'sglit', 'readonly': False}]

    def get_queryset(self, prefix):
        qs = LitrefSG.objects.none()
        if prefix == "sglit":
            # List the litrefs for this SermonGold correctly
            qs = LitrefSG.objects.filter(sermon_gold=self.obj).order_by('reference__short')
        return qs

    def before_save(self, prefix, request, instance = None, form = None):
        has_changed = False
        # Check if a new reference should be processed
        litref_id = form.cleaned_data['litref']
        if litref_id != "":
            if instance.id == None or instance.reference == None or instance.reference.id == None or \
                instance.reference.id != int(litref_id):
                # Find the correct litref
                litref = Litref.objects.filter(id=litref_id).first()
                if litref != None:
                    # Adapt the value of the instance 
                    instance.reference = litref
                    has_changed = True
            
        return has_changed


class EqualGoldEdit(BasicDetails):
    model = EqualGold
    mForm = SuperSermonGoldForm
    prefix = 'ssg'
    title = "Super Sermon Gold"
    rtype = "json"
    new_button = True
    mainitems = []
    
    EqgcolFormSet = inlineformset_factory(EqualGold, CollectionSuper,
                                       form=SuperSermonGoldCollectionForm, min_num=0,
                                       fk_name="super", extra=0)
    GeqFormSet = inlineformset_factory(EqualGold, SermonGold, 
                                         form=EqualGoldForm, min_num=0,
                                         fk_name = "equal",
                                         extra=0, can_delete=True, can_order=False)
    
    formset_objects = [{'formsetClass': EqgcolFormSet, 'prefix': 'eqgcol', 'readonly': False, 'noinit': True, 'linkfield': 'super'},
                       {'formsetClass': GeqFormSet, 'prefix': 'geq', 'readonly': False}]

    def add_to_context(self, context, instance):
        """Add to the existing context"""

        # Define the main items to show and edit
        context['mainitems'] = [
            {'type': 'plain', 'label': "Author:",        'value': instance.author, 'field_key': 'author'},
            {'type': 'plain', 'label': "Sermon number:", 'value': instance.number, 'field_view': 'number', 
             'title': 'This is the automatically assigned sermon number for this particular author' },
            {'type': 'plain', 'label': "Passim Code:",   'value': instance.code,   'title': 'The Passim Code is automatically determined'}, 
            {'type': 'safe',  'label': "Incipit:",       'value': instance.get_incipit_markdown, 'field_key': 'incipit',  'key_ta': 'gldincipit-key'}, 
            {'type': 'safe',  'label': "Explicit:",      'value': instance.get_explicit_markdown,'field_key': 'explicit', 'key_ta': 'gldexplicit-key'}, 
            {'type': 'bold',  'label': "Moved to:",      'value': instance.get_moved_code, 'empty': 'hide', 'link': instance.get_moved_url},
            {'type': 'bold',  'label': "Previous:",      'value': instance.get_previous_code, 'empty': 'hide', 'link': instance.get_previous_url},
            {'type': 'line',  'label': "Collections:",   'value': instance.get_collections_markdown(), 
                'multiple': True, 'field_list': 'collist_ssg', 'fso': self.formset_objects[0] }
            #{'type': 'plain', 'label': "Collections:",   'value': instance.collections.all().order_by('name'), 
            #    'multiple': True, 'field_list': 'collist_ssg', 'qlist': 'collist_ssg', 'link': reverse('equalgold_list'), 'fso': self.formset_objects[0] }
            ]
        # Notes:
        # Collections: provide a link to the SSG-listview, filtering on those SSGs that are part of one particular collection

        # Signal that we have select2
        context['has_select2'] = True

        # SPecification of the new button
        context['new_button_title'] = "Sermon Gold"
        context['new_button_name'] = "gold"
        context['new_button_url'] = reverse("gold_details")
        context['new_button_params'] = [
            {'name': 'gold-n-equal', 'value': instance.id}
            ]

        # Return the context we have made
        return context

    def process_formset(self, prefix, request, formset):
        errors = []
        bResult = True
        instance = formset.instance
        for form in formset:
            if form.is_valid():
                cleaned = form.cleaned_data
                # Action depends on prefix
                
                if prefix == "eqgcol":
                    # Keyword processing
                    if 'newcol' in cleaned and cleaned['newcol'] != "":
                        newcol = cleaned['newcol']
                        # Is the COL already existing?
                        obj = Collection.objects.filter(name=newcol).first()
                        if obj == None:
                            # TODO: add profile here
                            profile = Profile.get_user_profile(request.user.username)
                            obj = Collection.objects.create(name=newcol, type='super', owner=profile)
                        # Make sure we set the keyword
                        form.instance.collection = obj
                        # Note: it will get saved with formset.save()
            else:
                errors.append(form.errors)
                bResult = False
        return None

    def before_save(self, form, instance):
        # Check for author
        if instance.author == None:
            # Set to "undecided" author if possible
            author = Author.get_undecided()
            instance.author = author
        return True, ""

    def after_save(self, form, instance):
        msg = ""
        bResult = True
        oErr = ErrHandle()
        
        try:
            # Process many-to-many changes: Add and remove relations in accordance with the new set passed on by the user
            collist_ssg = form.cleaned_data['collist_ssg']
            adapt_m2m(CollectionSuper, instance, "super", collist_ssg, "collection")

        except:
            msg = oErr.get_error_message()
            bResult = False
        return bResult, msg


class EqualGoldDetails(EqualGoldEdit):
    rtype = "html"

    def add_to_context(self, context, instance):
        """Add to the existing context"""

        # Start by executing the standard handling
        super(EqualGoldDetails, self).add_to_context(context, instance)

        # Are we copying information?? (only allowed if we are the app_editor)
        if 'goldcopy' in self.qd and context['is_app_editor']:
            # Get the ID of the gold sermon from which information is to be copied to the SSG
            goldid = self.qd['goldcopy']
            # Get the GOLD SERMON instance
            gold = SermonGold.objects.filter(id=goldid).first()

            if gold != None:
                # Copy all relevant information to the EqualGold obj (which as a SSG)
                obj = self.object
                # (1) copy author
                if gold.author != None: obj.author = gold.author
                # (2) copy incipit
                if gold.incipit != None and gold.incipit != "": obj.incipit = gold.incipit ; obj.srchincipit = gold.srchincipit
                # (3) copy explicit
                if gold.explicit != None and gold.explicit != "": obj.explicit = gold.explicit ; obj.srchexplicit = gold.srchexplicit

                # Now save the adapted EqualGold obj
                obj.save()
            # And in all cases: make sure we redirect to the 'clean' GET page
            self.redirectpage = reverse('equalgold_details', kwargs={'pk': self.object.id})
        else:
            context['sections'] = []

            # List of post-load objects
            postload_objects = []
            # (1) postload: gold equality
            geq_obj = dict(prefix="ssgeq", url=reverse('equalgold_eqset', kwargs={'pk': instance.id}))
            postload_objects.append(geq_obj)

            # (2) postload: relation to other
            glink_obj = dict(prefix="ssglink", url=reverse('equalgold_linkset', kwargs={'pk': instance.id}))
            postload_objects.append(glink_obj)

            context['postload_objects'] = postload_objects

            # Lists of related objects
            related_objects = []

            # List of manuscripts related to the SSG via sermon descriptions
            manuscripts = dict(title="Manuscripts", prefix="manu")
            # Get all ID's of sermondescr instances linking to the correct eqg instance
            # manu_ids = SermonDescr.goldsermons.filter(equal=instance).distinct().values('manu__id')
            manu_ids = SermonDescr.objects.filter(goldsermons__equal=instance).distinct().values('manu__id')
            qs = Manuscript.objects.filter(id__in=manu_ids).order_by('idno')
            rel_list =[]
            for item in qs:
                manu_name = "<span class='signature'>{}</span> {}".format(item.idno, item.name)
                rel_item = []
                rel_item.append({'value': item.library.lcity.name})
                rel_item.append({'value': item.library.name})
                rel_item.append({'value': manu_name, 'title': item.idno, 'main': True,
                                 'link': reverse('manuscript_details', kwargs={'pk': item.id})})
                rel_item.append({'value': item.manusermons.all().count(), 'align': "right"})
                rel_item.append({'value': item.yearstart, 'align': "right"})
                rel_item.append({'value': item.yearfinish, 'align': "right"})
                rel_list.append(rel_item)
            manuscripts['rel_list'] = rel_list
            manuscripts['columns'] = ['City', 'Library', 'Name', 'Items', 'From', 'Until']
            related_objects.append(manuscripts)

            context['related_objects'] = related_objects

        # Return the context we have made
        return context

    def before_save(self, form, instance):
        return True, ""

    def process_formset(self, prefix, request, formset):
        return None

    def after_save(self, form, instance):
        return True, ""


class EqualGoldListView(BasicList):
    """List super sermon gold instances"""

    model = EqualGold
    listform = SuperSermonGoldForm
    has_select2 = True  # Check
    prefix = "ssg"
    plural_name = "Super sermons gold"
    sg_name = "Super sermon gold"
    order_cols = ['code', 'author', 'number', '', 'srchincipit', '' ]
    order_default= order_cols
    order_heads = [
        {'name': 'Author',                  'order': 'o=1', 'type': 'str', 'custom': 'author', 'linkdetails': True},
        {'name': 'Number',                  'order': 'o=2', 'type': 'int', 'custom': 'number', 'linkdetails': True},
        {'name': 'Code',                    'order': 'o=3', 'type': 'str', 'custom': 'code',   'linkdetails': True},
        {'name': 'Gryson/Clavis',           'order': ''   , 'type': 'str', 'custom': 'sig',
         'title': "The Gryson/Clavis codes of all the Sermons Gold in this equality set"},
        {'name': 'Incipit ... Explicit',    'order': 'o=5', 'type': 'str', 'custom': 'incexpl', 'main': True, 'linkdetails': True,
         'title': "The incipit...explicit that has been chosen for this Super Sermon Gold"},
        {'name': 'Size',                    'order': ''   , 'type': 'int', 'custom': 'size',
         'title': "Number of Sermons Gold that are part of the equality set of this Super Sermon Gold"}
        ]
    filters = [
        {"name": "Author",          "id": "filter_author",            "enabled": False},
        {"name": "Incipit",         "id": "filter_incipit",           "enabled": False},
        {"name": "Explicit",        "id": "filter_explicit",          "enabled": False},
        {"name": "Passim code",     "id": "filter_code",              "enabled": False},
        {"name": "Number",          "id": "filter_number",            "enabled": False},
        {"name": "Gryson/Clavis",   "id": "filter_signature",         "enabled": False},
        {"name": "Collection...",   "id": "filter_collection",        "enabled": False, "head_id": "none"},
        {"name": "Manuscript",      "id": "filter_collmanu",          "enabled": False, "head_id": "filter_collection"},
        {"name": "Sermon",          "id": "filter_collsermo",         "enabled": False, "head_id": "filter_collection"},
        {"name": "Sermon Gold",     "id": "filter_collgold",          "enabled": False, "head_id": "filter_collection"},
        {"name": "Super sermon gold","id": "filter_collsuper",        "enabled": False, "head_id": "filter_collection"},
               ]
    searches = [
        {'section': '', 'filterlist': [
            {'filter': 'incipit',   'dbfield': 'srchincipit',       'keyS': 'incipit'},
            {'filter': 'explicit',  'dbfield': 'srchexplicit',      'keyS': 'explicit'},
            {'filter': 'code',      'dbfield': 'code',              'keyS': 'code'},
            {'filter': 'number',    'dbfield': 'number',            'keyS': 'number'},
            {'filter': 'author',    'fkfield': 'author',            'keyS': 'authorname', 'keyFk': 'name', 'keyList': 'authorlist', 'infield': 'id', 'external': 'gold-authorname' },
            {'filter': 'signature', 'fkfield': 'equal_goldsermons__goldsignatures', 'keyS': 'signature', 'keyFk': 'code', 'keyId': 'signatureid', 'keyList': 'siglist', 'infield': 'code' }
            ]},
        {'section': 'collection', 'filterlist': [
            {'filter': 'collmanu',  'fkfield': 'equal_goldsermons__sermondescr__manu__collections',  'keyS': 'collection','keyFk': 'name', 'keyList': 'collist_m', 'infield': 'name' }, 
            {'filter': 'collsermo', 'fkfield': 'equal_goldsermons__sermondescr__collections',        'keyS': 'collection','keyFk': 'name', 'keyList': 'collist_s', 'infield': 'name' }, 
            {'filter': 'collgold',  'fkfield': 'equal_goldsermons__collections',                     'keyS': 'collection','keyFk': 'name', 'keyList': 'collist_sg', 'infield': 'name' }, 
            {'filter': 'collsuper', 'fkfield': 'collections',                                        'keyS': 'collection','keyFk': 'name', 'keyList': 'collist_ssg', 'infield': 'name' }
            ]}
        ]
    
    def add_to_context(self, context, initial):
        # Find out who the user is
        profile = Profile.get_user_profile(self.request.user.username)
        context['basketsize'] = 0 if profile == None else profile.basketsize_super
        context['basket_show'] = reverse('basket_show_super')
        context['basket_update'] = reverse('basket_update_super')
        return context
        
    def get_basketqueryset(self):
        if self.basketview:
            profile = Profile.get_user_profile(self.request.user.username)
            qs = profile.basketitems_super.all()
        else:
            qs = EqualGold.objects.all()
        return qs

    def get_field_value(self, instance, custom):
        sBack = ""
        sTitle = ""
        html = []
        if custom == "author":
            # Get a good name for the author
            if instance.author:
                html.append(instance.author.name)
            else:
                html.append("<i>(not specified)</i>")
        elif custom == "number":
            sNumber = "-" if instance.number  == None else instance.number
            html.append("{}".format(sNumber))
        elif custom == "size":
            iSize = instance.equal_goldsermons.all().count()
            html.append("{}".format(iSize))
        elif custom == "code":
            sCode = "-" if instance.code  == None else instance.code
            html.append("{}".format(sCode))
        elif custom == "incexpl":
            html.append("<span>{}</span>".format(instance.get_incipit_markdown()))
            dots = "..." if instance.incipit else ""
            html.append("<span style='color: blue;'>{}</span>".format(dots))
            html.append("<span>{}</span>".format(instance.get_explicit_markdown()))
        elif custom == "sig":
            # Get all the associated signatures
            qs = Signature.objects.filter(gold__equal=instance).order_by('editype', 'code')
            for sig in qs:
                editype = sig.editype
                url = "{}?gold-siglist={}".format(reverse("gold_list"), sig.id)
                short = sig.short()
                html.append("<span class='badge signature {}' title='{}'><a class='nostyle' href='{}'>{}</a></span>".format(editype, short, url, short[:20]))
        # Combine the HTML code
        sBack = "\n".join(html)
        return sBack, sTitle


class EqualGoldEqualset(BasicPart):
    """The set of gold sermons that are part of one SSG = EqualGold object"""

    MainModel = EqualGold
    template_name = 'seeker/super_eqset.html'
    title = "SuperSermonGoldEqualset"
    SSGeqFormSet = inlineformset_factory(EqualGold, SermonGold, 
                                         form=EqualGoldForm, min_num=0,
                                         fk_name = "equal",
                                         extra=0, can_delete=True, can_order=False)
    formset_objects = [{'formsetClass': SSGeqFormSet, 'prefix': 'ssgeq', 'readonly': False}]

    def get_queryset(self, prefix):
        qs = None
        if prefix == "ssgeq":
            # Get all SermonGold instances with the same EqualGold
            #  (those are all SermonGold instances that have a FK linking to me)
            qs = self.obj.equal_goldsermons.all()
        return qs

    def get_instance(self, prefix):
        if prefix == "ssgeq" or "ssgeq" in prefix:
            return self.obj
        else:
            return self.obj

    def process_formset(self, prefix, request, formset):
        if prefix == "ssgeq":
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
        geq = instance.equal.create_new()
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
        if prefix != None and prefix == "ssgeq" and instance != None:
            # No actual deletion of anything should take place...
            bDoDelete = False
            # Perform the operation
            self.remove_from_eqset(instance)
        return bDoDelete

    def before_save(self, prefix, request, instance = None, form = None):
        # Use [self.gold] to communicate with [after_save()]

        bNeedSaving = False
        if prefix == "ssgeq":
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

    def after_save(self, prefix, instance = None, form = None):
        # The instance here is the geq-instance, so an instance of SermonGold
        # Now make sure all related material is updated

        if self.gold == None:
            # Add this gold sermon to the equality group of the target
            added, lst_res = add_gold2equal(instance, self.obj)
        else:
            # The user wants to change the gold-sermon inside the equality set: 
            # (1) Keep track of the current equality set
            eqset = self.obj
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
        context['associations'] = self.obj.equalgold_src.all()

        return context

    
class EqualGoldLinkset(BasicPart):
    """The set of EqualGold instances that link to an EqualGold one, but that are not 'equal' """

    MainModel = EqualGold
    template_name = 'seeker/super_linkset.html'
    title = "SermonGoldLinkset"
    SSGlinkFormSet = inlineformset_factory(EqualGold, EqualGoldLink,
                                         form=EqualGoldLinkForm, min_num=0,
                                         fk_name = "src",
                                         extra=0, can_delete=True, can_order=False)
    formset_objects = [{'formsetClass': SSGlinkFormSet, 'prefix': 'ssglink', 'readonly': False, 'initial': [{'linktype': LINK_EQUAL }], 'clean': True}]

    def clean(self, formset, prefix):
        # Clean method
        if prefix == "ssglink":
            # Iterate over all forms and get the destinations
            lDstList = []
            for form in formset.forms:
                dst = form.cleaned_data['dst']
                if dst == None:
                    dst = form.cleaned_data['target_list']
                # Check if we have a destination
                if dst != None:
                    # Check if it is already in the list
                    if dst in lDstList:
                        # Something is wrong: double desination
                        self.arErr.append("A target Super Sermon Gold can only be used once")
                        return False
                    # Add it to the list
                    lDstList.append(dst)
        return True

    def process_formset(self, prefix, request, formset):
        if prefix == "ssglink":
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
                # end if
        # No need to return a value
        return True

    def before_delete(self, prefix = None, instance = None):
        id = instance.id
        return True

    def before_save(self, prefix, request, instance = None, form = None):
        bNeedSaving = False
        if prefix == "ssglink":
            if 'target_list' in form.cleaned_data:
                # Get the one single destination id number
                dst = form.cleaned_data['target_list']
                if dst != None:
                    # Fill in the destination
                    instance.dst = dst
                    bNeedSaving = True
        return bNeedSaving

    def after_save(self, prefix, instance = None, form = None):
        # The instance here is the glink-instance, so an instance of EqualGoldLink
        # Now make sure all related material is updated

        added, lst_res = add_ssg_equal2equal(self.obj, instance.dst, instance.linktype)
        return True


class AuthorEdit(PassimDetails):
    """The details of one author"""

    model = Author
    mForm = AuthorEditForm
    template_name = 'seeker/author_edit.html'
    template_post = 'seeker/author_edit.html'
    prefix = 'author'
    title = "Author"
    afternewurl = ""
    rtype = "json"

    def after_new(self, form, instance):
        """Action to be performed after adding a new item"""

        self.afternewurl = reverse('author_search')
        return True, "" 

    def add_to_context(self, context, instance):
        context['is_app_editor'] = user_is_ingroup(self.request, app_editor)
        # Process this visit and get the new breadcrumbs object
        context['breadcrumbs'] = get_breadcrumbs(self.request, "Author edit", False)

        context['afterdelurl'] = reverse('author_search')
        return context


class AuthorDetails(AuthorEdit):
    """The details of one author"""

    template_name = 'seeker/author_details.html'
    template_post = 'seeker/author_details.html'
    rtype = "html"  # GET provides a HTML form straight away

    def after_new(self, form, instance):
        """Action to be performed after adding a new item"""

        self.afternewurl = reverse('author_search')
        if instance != None:
            # Make sure we do a page redirect
            self.newRedirect = True
            self.redirectpage = reverse('author_details', kwargs={'pk': instance.id})
        return True, "" 

    def add_to_context(self, context, instance):
        context['is_app_editor'] = user_is_ingroup(self.request, app_editor)

        context['afterdelurl'] = ""
        # Process this visit and get the new breadcrumbs object
        prevpage = reverse('author_search')
        context['prevpage'] = prevpage
        crumbs = []
        crumbs.append(['Authors', prevpage])
        if instance:
            current_name = instance.name
        else:
            current_name = "Author details"
        context['breadcrumbs'] = get_breadcrumbs(self.request, current_name, True, crumbs)
        return context


class AuthorListView(BasicList):
    """Search and list authors"""

    model = Author
    listform = AuthorSearchForm
    has_select2 = True
    prefix = "auth"
    paginate_by = 20
    delete_line = True
    page_function = "ru.passim.seeker.search_paged_start"
    order_cols = ['abbr', 'number', 'name', '', '']
    order_default = ['name', 'abbr', 'number', '', '']
    order_heads = [{'name': 'Abbr',        'order': 'o=1', 'type': 'str', 'title': 'Abbreviation of this name (used in standard literature)', 'field': 'abbr', 'default': ""},
                   {'name': 'Number',      'order': 'o=2', 'type': 'int', 'title': 'Passim author number', 'field': 'number', 'default': 10000, 'align': 'right'},
                   {'name': 'Author name', 'order': 'o=3', 'type': 'str', 'field': "name", "default": "", 'main': True, 'linkdetails': True},
                   {'name': 'Links',       'order': '',    'type': 'str', 'title': 'Number of links from Sermon Descriptions and Gold Sermons', 'custom': 'links' },
                   {'name': '',            'order': '',    'type': 'str', 'options': ['delete']}]
    filters = [ {"name": "Author",         "id": "filter_author",     "enabled": False}]
    searches = [
        {'section': '', 'filterlist': [
            {'filter': 'author', 'dbfield': 'name', 'keyS': 'author_ta', 'keyList': 'authlist', 'infield': 'name' }]}
        ]
    downloads = [{"label": "Excel", "dtype": "xlsx", "url": 'author_results'},
                 {"label": "csv (tab-separated)", "dtype": "csv", "url": 'author_results'},
                 {"label": None},
                 {"label": "json", "dtype": "json", "url": 'author_results'}]
    uploads = [{"url": "import_authors", "label": "Authors (csv/json)", "msg": "Specify the CSV file (or the JSON file) that contains the PASSIM authors"}]

    def get_field_value(self, instance, custom):
        sBack = ""
        sTitle = ""
        if custom == "links":
            html = []
            # Get the HTML code for the links of this instance
            number = instance.author_goldsermons.count()
            if number > 0:
                url = reverse('search_gold')
                html.append("<span class='badge jumbo-2' title='linked gold sermons'>")
                html.append(" <a class='nostyle' href='{}?gold-author={}'>{}</a></span>".format(url, instance.id, number))
            number = instance.author_sermons.count()
            if number > 0:
                url = reverse('sermon_list')
                html.append("<span class='badge jumbo-1' title='linked sermon descriptions'>")
                html.append(" <a href='{}?sermo-author={}'>{}</a></span>".format(url, instance.id, number))
            # Combine the HTML code
            sBack = "\n".join(html)
        return sBack, sTitle


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
        context['is_app_uploader'] = user_is_ingroup(self.request, app_uploader)
        context['is_app_editor'] = user_is_ingroup(self.request, app_editor)

         # Process this visit and get the new breadcrumbs object
        prevpage = reverse('home')
        context['prevpage'] = prevpage
        context['breadcrumbs'] = get_breadcrumbs(self.request, "Libraries", True)

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
                row = {"id": lib.id, "country": lib.get_country_name(), "city": lib.get_city_name(), "library": lib.name, "libtype": lib.libtype}
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


class LibraryDetailsView(PassimDetails):
    model = Library
    mForm = LibraryForm
    template_name = 'seeker/library_details.html'
    prefix = 'lib'
    prefix_type = "simple"
    title = "LibraryDetails"
    rtype = "html"

    def after_new(self, form, instance):
        """Action to be performed after adding a new item"""

        self.afternewurl = reverse('library_list')
        return True, "" 

    def add_to_context(self, context, instance):
        context['is_app_editor'] = user_is_ingroup(self.request, app_editor)
        # Process this visit and get the new breadcrumbs object
        prevpage = reverse('library_list')
        context['prevpage'] = prevpage
        crumbs = []
        crumbs.append(['Libraries', prevpage])
        if instance:
            if instance.name:
                current_name = instance.name
            else:
                current_name = "Library (unnamed)"
        else:
            current_name = "Library details"
        context['breadcrumbs'] = get_breadcrumbs(self.request, current_name, True, crumbs)
        return context


class LibraryEdit(BasicPart):
    """The details of one library"""

    MainModel = Library
    template_name = 'seeker/library_edit.html'  
    title = "Library" 
    afternewurl = ""
    # One form is attached to this 
    prefix = "lib"
    form_objects = [{'form': LibraryForm, 'prefix': prefix, 'readonly': False}]

    def before_save(self, prefix, request, instance = None, form = None):
        bNeedSaving = False
        if prefix == "lib":
            # Check whether the location has changed
            if 'location' in form.changed_data:
                # Get the new location
                location = form.cleaned_data['location']
                if location != None:
                    # Get the hierarchy including myself
                    hierarchy = location.hierarchy()
                    for item in hierarchy:
                        if item.loctype.name == "city":
                            instance.lcity = item
                            bNeedSaving = True
                        elif item.loctype.name == "country":
                            instance.lcountry = item
                            bNeedSaving = True
            pass

        return bNeedSaving

    def add_to_context(self, context):

        # Get the instance
        instance = self.obj

        if instance != None:
            pass

        afternew =  reverse('library_list')
        if 'afternewurl' in self.qd:
            afternew = self.qd['afternewurl']
        context['afternewurl'] = afternew

        return context


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
        context['is_app_uploader'] = user_is_ingroup(self.request, app_uploader)
        context['is_app_editor'] = user_is_ingroup(self.request, app_editor)

        # Process this visit and get the new breadcrumbs object
        prevpage = reverse('home')
        context['prevpage'] = prevpage
        context['breadcrumbs'] = get_breadcrumbs(self.request, "Upload reports", True)

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
        context['is_app_editor'] = user_is_ingroup(self.request, app_editor)
        # Process this visit and get the new breadcrumbs object
        prevpage = reverse('report_list')
        context['prevpage'] = prevpage
        crumbs = []
        crumbs.append(['Reports', prevpage])
        current_name = "Report details"
        if instance:
            current_name = "Report {} {}".format(instance.get_reptype_display(), get_crpp_date(instance.created))
        context['breadcrumbs'] = get_breadcrumbs(self.request, current_name, True, crumbs)
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


class SourceListView(BasicList):
    """Listview of sources"""

    model = SourceInfo
    listform = SourceEditForm
    has_select2 = True
    bUseFilter = True
    page_function = "ru.passim.seeker.search_paged_start"
    prefix = "src"
    basic_name = "source"
    order_cols = ['created', 'collector', 'url']
    order_default = order_cols
    order_heads = [{'name': 'Date',           'order': 'o=1', 'type': 'str', 'custom': 'date', 'align': 'right', 'linkdetails': True},
                   {'name': 'Collector',      'order': 'o=2', 'type': 'str', 'field': 'collector'},
                   {'name': 'Collected from', 'order': 'o=3', 'type': 'str', 'custom': 'from', 'main': True}]
    filters = [ {"name": "Collector",       "id": "filter_collector",      "enabled": False} ]
    searches = [
        {'section': '', 'filterlist': [
            {'filter': 'collector', 'fkfield': 'profile', 'keyS': 'profile_ta', 'keyFk': 'user__username', 'keyList': 'profilelist', 'infield': 'id'}
            ]}
         ]

    def get_field_value(self, instance, custom):
        sBack = ""
        sTitle = ""
        if custom == "date":
            sBack = instance.created.strftime("%d/%b/%Y %H:%M")
        elif custom == "from":
            if instance.url != None:
                sBack = instance.url
        return sBack, sTitle

    def add_to_context(self, context, initial):
        SourceInfo.init_profile()
        return context
    

class SourceDetailsView(PassimDetails):
    model = SourceInfo
    mForm = SourceEditForm
    template_name = 'seeker/source_details.html'
    prefix = 'source'
    prefix_type = "simple"
    title = "SourceDetails"
    rtype = "html"

    def after_new(self, form, instance):
        """Action to be performed after adding a new item"""

        self.afternewurl = reverse('source_list')
        if instance != None:
            # Make sure we do a page redirect
            self.newRedirect = True
            self.redirectpage = reverse('source_details', kwargs={'pk': instance.id})
        return True, "" 

    def add_to_context(self, context, instance):
        context['is_app_editor'] = user_is_ingroup(self.request, app_editor)
        # Process this visit and get the new breadcrumbs object
        prevpage = reverse('source_list')
        context['prevpage'] = prevpage
        crumbs = []
        crumbs.append(['Sources', prevpage])
        current_name = "Source details"
        if instance:
            current_name = "Source {} {}".format(instance.collector, get_crpp_date(instance.created))
        context['breadcrumbs'] = get_breadcrumbs(self.request, current_name, True, crumbs)
        return context

    def before_save(self, form, instance):
        if form != None:
            # Search the user profile
            profile = Profile.get_user_profile(self.request.user.username)
            form.instance.profile = profile
        return True, ""


class SourceEdit(BasicPart):
    """The details of one manuscript"""

    MainModel = SourceInfo
    template_name = 'seeker/source_edit.html'
    title = "SourceInfo" 
    afternewurl = ""
    # One form is attached to this 
    prefix = "source"
    form_objects = [{'form': SourceEditForm, 'prefix': prefix, 'readonly': False}]

    def custom_init(self):
        """Adapt the prefix for [sermo] to fit the kind of prefix provided by PassimDetails"""

        return True

    def add_to_context(self, context):

        # Get the instance
        instance = self.obj

        # Not sure if this is still needed
        context['msitem'] = instance

        afternew =  reverse('source_list')
        if 'afternewurl' in self.qd:
            afternew = self.qd['afternewurl']
        context['afternewurl'] = afternew
        # Define where to go to after deletion
        context['afterdelurl'] = reverse('source_list')

        return context

    def after_save(self, prefix, instance = None, form = None):

        # There's is no real return value needed here 
        return True


class LitRefListView(ListView):
    """Listview of edition and literature references"""
       
    model = Litref
    paginate_by = 2000
    template_name = 'seeker/literature_list.html'
    entrycount = 0

    def get_context_data(self, **kwargs):
        # Call the base implementation first to get a context
        context = super(LitRefListView, self).get_context_data(**kwargs)

        # Get parameters
        initial = self.request.GET

        # Determine the count for literature references
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
        context['title'] = "Passim literature info"

        # Change name of the qs for edition references 
        context['edition_list'] = self.get_editionset() 

        # Determine the count for edition references
        context['entrycount_edition'] = self.entrycount_edition

        # Check if user may upload
        context['is_authenticated'] = user_is_authenticated(self.request)
        context['is_app_uploader'] = user_is_ingroup(self.request, app_uploader)
        context['is_app_editor'] = user_is_ingroup(self.request, app_editor)

        # Process this visit and get the new breadcrumbs object
        prevpage = reverse('home')
        context['prevpage'] = prevpage
        context['breadcrumbs'] = get_breadcrumbs(self.request, "Literature references", True)

        # Return the calculated context
        return context
    
    def get_paginate_by(self, queryset):
        """
        Paginate by specified value in default class property value.
        """
        return self.paginate_by
    
    # Queryset literature references
    def get_queryset(self):
        # Get the parameters passed on with the GET or the POST request
        get = self.request.GET if self.request.method == "GET" else self.request.POST
        get = get.copy()
        self.get = get

        # Calculate the final qs for the manuscript litrefs
        litref_ids_man = [x['reference'] for x in LitrefMan.objects.all().values('reference')]
        # Calculate the final qs for the Gold sermon litrefs
        litref_ids_sg = [x['reference'] for x in LitrefSG.objects.all().values('reference')]

        # Combine the two qs into one and filter
        litref_ids = chain(litref_ids_man, litref_ids_sg)
        qs = Litref.objects.filter(id__in=litref_ids).order_by('short')

        # Determine the length
        self.entrycount = len(qs)

        # Return the resulting filtered and sorted queryset
        return qs

    # Queryset edition references
    def get_editionset(self):
        # Get the parameters passed on with the GET or the POST request
        get = self.request.GET if self.request.method == "GET" else self.request.POST
        get = get.copy()
        self.get = get

        # Calculate the final qs for the manuscript litrefs
        ediref_ids = [x['reference'] for x in EdirefSG.objects.all().values('reference')]
       
        # Sort and filter all editions
        qs = Litref.objects.filter(id__in=ediref_ids).order_by('short')

        # Determine the length
        self.entrycount_edition = len(qs)

        # Return the resulting filtered and sorted queryset
        return qs


class BasketView(SermonListView):
    """Like SermonListView, but then with the basket set true"""
    basketview = True


class BasketViewManu(ManuscriptListView):
    """Like ManuscriptListView, but then with the basket set true"""
    basketview = True


class BasketViewGold(SermonGoldListView):
    """Like SermonGoldListView, but then with the basket set true"""
    basketview = True


class BasketViewSuper(EqualGoldListView):
    """Like EqualGoldListView, but then with the basket set true"""
    basketview = True


class BasketUpdate(BasicPart):
    """Update contents of the sermondescr basket"""

    MainModel = SermonDescr
    clsBasket = Basket
    template_name = "seeker/basket_choices.html"
    entrycount = 0
    bFilter = False
    s_view = SermonListView
    s_form = SermonForm
    s_field = "sermon"
    colltype = "sermo"
    form_objects = [{'form': CollectionForm, 'prefix': colltype, 'readonly': False}]

    def add_to_context(self, context):
        # Reset the redirect page
        self.redirectpage = ""

        # Get the operation
        if 'operation' in self.qd:
            operation = self.qd['operation']
        else:
            return context

        # Get our profile
        profile = Profile.get_user_profile(self.request.user.username)
        if profile != None:

            # Get the queryset
            self.filters, self.bFilter, qs, ini, oFields = search_generic(self.s_view, self.MainModel, self.s_form, self.qd)

            kwargs = {'profile': profile}

            # Action depends on the operation specified
            if qs and operation == "create":
                # Remove anything there
                self.clsBasket.objects.filter(profile=profile).delete()
                # Add
                with transaction.atomic():
                    for item in qs:
                        kwargs[self.s_field] = item
                        self.clsBasket.objects.create(**kwargs)
                # Process history
                profile.history(operation, self.colltype, oFields)
            elif qs and operation == "add":
                # Add
                with transaction.atomic():
                    for item in qs:
                        kwargs[self.s_field] = item
                        self.clsBasket.objects.create(**kwargs)
                # Process history
                profile.history(operation, self.colltype, oFields)
            elif qs and operation == "remove":
                # Add
                with transaction.atomic():
                    for item in qs:
                        kwargs[self.s_field] = item
                        self.clsBasket.objects.filter(**kwargs).delete()
                # Process history
                profile.history(operation, self.colltype, oFields)
            elif operation == "reset":
                # Remove everything from our basket
                self.clsBasket.objects.filter(profile=profile).delete()
                # Reset the history for this one
                profile.history(operation, self.colltype)
            elif qs and (operation == "collcreate" or operation == "colladd"):
                # Queryset: the basket contents
                qs = self.clsBasket.objects.filter(profile=profile)

                # Get the history string
                history = getattr(profile, "history{}".format(self.colltype))

                # New collection or existing one?
                coll = None
                bChanged = False
                if operation == "collcreate":
                    # Save the current basket as a collection that needs to receive a name
                    coll = Collection.objects.create(name="PROVIDE_SHORT_NAME", path=history, 
                                                     descrip="Created from a {} listview basket".format(self.colltype), 
                                                     owner=profile, type=self.colltype)
                elif oFields['collone']:
                    coll = oFields['collone']
                if coll == None:
                    # TODO: provide some kind of error??
                    pass
                else:
                    # Link the collection with the correct model
                    kwargs = {'collection': coll}
                    if self.colltype == "sermo":
                        clsColl = CollectionSerm
                        field = "sermon"
                    elif self.colltype == "gold":
                        clsColl = CollectionGold
                        field = "gold"
                    elif self.colltype == "manu":
                        clsColl = CollectionMan
                        field = "manuscript"
                    elif self.colltype == "super":
                        clsColl = CollectionSuper
                        field = "super"
                    with transaction.atomic():
                        for item in qs:
                            kwargs[field] = getattr( item, self.s_field)
                            # Check if it doesn't exist yet
                            obj = clsColl.objects.filter(**kwargs).first()
                            if obj == None:
                                clsColl.objects.create(**kwargs)
                                # Note that some changes have been made
                                bChanged = True
                    # Make sure to redirect to this instance -- but only for COLLCREATE
                    if operation == "collcreate":
                        self.redirectpage = reverse('coll{}_details'.format(self.colltype), kwargs={'pk': coll.id})
                    else:
                        # We are adding
                        collurl = reverse('coll{}_details'.format(self.colltype), kwargs={'pk': coll.id})
                        collname = coll.name
                        context['data'] = dict(collurl=collurl, collname=collname)
                        # Have changes been made?
                        if bChanged:
                            # Add the current basket history to the collection's path
                            lst_history_basket = json.loads(history)
                            lst_history_coll = json.loads(coll.path)
                            for item in lst_history_basket:
                                lst_history_coll.append(item)
                            coll.path = json.dumps(lst_history_coll)
                            coll.save()

            # Adapt the basket size
            context['basketsize'] = self.get_basketsize(profile)

            # Set the other context parameters
            if self.colltype == "sermo":
                context['basket_show'] = reverse('basket_show' )
                context['basket_update'] = reverse('basket_update')
            else:
                context['basket_show'] = reverse('basket_show_{}'.format(self.colltype))
                context['basket_update'] = reverse('basket_update_{}'.format(self.colltype))

        # Return the updated context
        return context

    def get_basketsize(self, profile):
        # Adapt the basket size
        basketsize = profile.basketitems.count()
        profile.basketsize = basketsize
        profile.save()
        # Return the basketsize
        return basketsize

 
class BasketUpdateManu(BasketUpdate):
    """Update contents of the manuscript basket"""

    MainModel = Manuscript
    clsBasket = BasketMan 
    s_view = ManuscriptListView
    s_form = SearchManuForm
    s_field = "manu"
    colltype = "manu"
    form_objects = [{'form': CollectionForm, 'prefix': colltype, 'readonly': False}]

    def get_basketsize(self, profile):
        # Adapt the basket size
        basketsize = profile.basketitems_manu.count()
        profile.basketsize_manu = basketsize
        profile.save()
        # Return the basketsize
        return basketsize


class BasketUpdateGold(BasketUpdate):
    """Update contents of the sermondescr basket"""

    MainModel = SermonGold
    clsBasket = BasketGold
    s_view = SermonGoldListView
    s_form = SermonGoldForm
    s_field = "gold"
    colltype = "gold"
    form_objects = [{'form': CollectionForm, 'prefix': colltype, 'readonly': False}]

    def get_basketsize(self, profile):
        # Adapt the basket size
        basketsize = profile.basketitems_gold.count()
        profile.basketsize_gold = basketsize
        profile.save()
        # Return the basketsize
        return basketsize
    

class BasketUpdateSuper(BasketUpdate):
    """Update contents of the sermondescr basket"""

    MainModel = EqualGold
    clsBasket = BasketSuper
    s_view = EqualGoldListView
    s_form = SuperSermonGoldForm
    s_field = "super"
    colltype = "super"
    form_objects = [{'form': CollectionForm, 'prefix': colltype, 'readonly': False}]

    def get_basketsize(self, profile):
        # Adapt the basket size
        basketsize = profile.basketitems_super.count()
        profile.basketsize_super = basketsize
        profile.save()
        # Return the basketsize
        return basketsize


