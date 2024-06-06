"""
Definition of DCT-related views and procedures for the SEEKER app.

DCT = Dynamic Comparative Table
"""

# View imports
# from re import X
from django.apps import apps
from django.contrib import admin
from django.contrib.auth import login, authenticate
from django.contrib.auth.models import Group, User
from django.db import transaction
from django.db.models import Q, Prefetch, Count, F
from django.urls import reverse
from django.http import HttpRequest, HttpResponse, HttpResponseRedirect, JsonResponse, FileResponse
from django.middleware.csrf import get_token
from django.shortcuts import get_object_or_404, render, redirect
from django.template.loader import render_to_string
from django.template import Context
from io import StringIO
import copy
import json
import csv
import openpyxl

# ======= imports from my own application ======
from passim.settings import APP_PREFIX, MEDIA_DIR, WRITABLE_DIR
from passim.utils import ErrHandle
from passim.basic.views import BasicList, BasicDetails, BasicPart
from passim.seeker.views import get_application_context, get_breadcrumbs, user_is_ingroup, nlogin, user_is_authenticated, \
    user_is_superuser, get_selectitem_info, adapt_m2m
from passim.seeker.models import SermonDescr, EqualGold, Manuscript, Signature, Profile, CollectionSuper, Collection, Project2, \
    Basket, BasketMan, BasketSuper, BasketGold
from passim.seeker.models import get_crpp_date, get_current_datetime, process_lib_entries, get_searchable, get_now_time
from passim.dct.models import ImportSetProject, ResearchSet, SetList, SetDef, get_passimcode, get_goldsig_dct, \
    SavedItem, SavedSearch, SelectItem, SavedVis, SaveGroup, ImportSet, ImportReview
from passim.dct.forms import ResearchSetForm, SetDefForm, RsetSelForm, SaveGroupForm, SgroupSelForm, \
    ImportSetForm, ImportReviewForm
from passim.approve.models import EqualChange, EqualApproval
from passim.stemma.models import StemmaItem, StemmaSet

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
app_user = "{}_user".format(PROJECT_NAME.lower())
app_editor = "{}_editor".format(PROJECT_NAME.lower())
app_userplus = "{}_userplus".format(PROJECT_NAME.lower())
app_developer = "{}_developer".format(PROJECT_NAME.lower())
app_moderator = "{}_moderator".format(PROJECT_NAME.lower())

def sermones_reset(request):
    """Reset SERMONES"""

    oErr = ErrHandle()
    stype = "imp"
    mtype = "man"
    try:
        # Make sure this is a HTTP request
        assert isinstance(request, HttpRequest)

        # Double check who this is
        if user_is_superuser(request):

            # Find the project that we need to 'cancel'
            project = Project2.objects.filter(name__icontains="luc de coninck").first()
            if not project is None:
                # Find all the manuscripts that need removing
                qs = Manuscript.objects.filter(manuscript_proj__project=project, stype=stype, mtype=mtype)

                # Remove them
                qs.delete()

        # Render and return the page
        return redirect('mypassim_details')
    except:
        msg = oErr.get_error_message()
        oErr.DoError("sermones_reset")
        return redirect('home')

def manuscript_ssgs(manu, bDebug = False):
    """Get the ordered list of SSGs related to a manuscript"""

    oErr = ErrHandle()
    lBack = None
    try:
        # Get a list of SSGs to which the sermons in this manuscript point
        qs = manu.sermondescr_super.all().order_by('sermon__msitem__order').values(
            'sermon__msitem__order', 'super', 'super__code')
        lBack = []
        with transaction.atomic():
            for obj in qs:
                # Get the order number
                order = obj['sermon__msitem__order']
                # Get the SSG
                super = obj['super']
                code = obj['super__code']
                # Treat signatures for this SSG
                sigbest = get_goldsig_dct(super)
                if sigbest == "":
                    sigbest = "ssg_{}".format(super)
                # Put into object
                oItem = dict(super=super, sig=sigbest, order=order, code=code)
                # Add to list
                lBack.append(oItem)

        # Debugging: print the list
        if bDebug:
            print("Manuscript id={}".format(manu.id))
            for oItem in lBack:
                order = oItem.get("order")
                super = oItem.get("super")
                sig = oItem.get("sig")
                code = get_passimcode(super, code)
                print("sermon {}: ssg={} sig=[{}]".format(order, code, sig))

    except:
        msg = oErr.get_error_message()
        oErr.DoError("manuscript_ssgs")
    return lBack

def collection_ssgs(coll, bDebug = False):
    """Get the ordered list of SSGs in the [super] type collection"""

    oErr = ErrHandle()
    lBack = None
    try:
        # Get the list of SSGs inside this collection
        qs = CollectionSuper.objects.filter(collection=coll).order_by('order').values(
            'order', 'super', 'super__code')
        lBack = []
        with transaction.atomic():
            for obj in qs:
                # Get the order number
                order = obj['order']
                # Get the SSG
                super = obj['super']
                code = obj['super__code']
                # Treat signatures for this SSG
                sigbest = get_goldsig_dct(super)
                if sigbest == "":
                    sigbest = "ssg_{}".format(super)
                # Put into object
                oItem = dict(super=super, sig=sigbest, order=order, code=code)
                # Add to list
                lBack.append(oItem)

        # Debugging: print the list
        if bDebug:
            print("Collection id={}".format(coll.id))
            for oItem in lBack:
                order = oItem.get("order")
                super = oItem.get("super")
                sig = oItem.get("sig")
                code = get_passimcode(super, code)
                print("sermon {}: ssg={} sig=[{}]".format(order, code, sig))

    except:
        msg = oErr.get_error_message()
        oErr.DoError("collection_ssgs")
    return lBack

def dct_manulist(lst_manu, bDebug=False):
    """Create a DCT based on the manuscripts in the list"""

    oErr = ErrHandle()
    lBack = None
    try:
        # Check the number of manuscripts
        if lst_manu == None or len(lst_manu) < 2:
            oErr.Status("Not enough manuscripts to compare")
            return None
        # We have enough manuscripts: Get the lists of SSGs
        lst_ssglists = []
        for manu in lst_manu:
            oSsgList = dict(manu=manu, ssglist=manuscript_ssgs(manu))
            lst_ssglists.append(oSsgList)
        # Prepare and create an appropriate table = list of rows
        rows = []
        # Create header row
        oRow = []
        oRow.append('Gr/Cl/Ot')
        for oSsgList in lst_ssglists:
            manu_name = oSsgList['manu'].get_full_name_html()
            oRow.append(manu_name)
        rows.append(oRow)
        lst_pivot = lst_ssglists[0]
        for oPivot in lst_pivot['ssglist']:
            # Create a row based on this pivot
            oRow = []
            # (1) row header
            oRow.append(oPivot['sig'])
            # (2) pivot SSG number
            oRow.append(oPivot['order'])
            # (3) SSG number in all other manuscripts
            ssg_id = oPivot['super']
            for lst_this in lst_ssglists[1:]:
                bFound = False
                order = ""
                for oItem in lst_this['ssglist']:
                    if ssg_id == oItem['super']:
                        # Found it!
                        order = oItem['order']
                        bFound = True
                        break
                oRow.append(order)
            # (4) add the row to the list
            rows.append(oRow)
        # Make sure we return the right information
        lBack = rows

    except:
        msg = oErr.get_error_message()
        oErr.DoError("dct_manulist")
    return lBack




# =================== MyPassim as model view attempt ======
class MyPassimEdit(BasicDetails):
    model = Profile
    mform = None
    prefix = "pre"  # Personal Research Environment
    prefix_type = "simple"
    title = "MY PASSIM"
    sel_button = "svdi"
    template_name = "dct/mypassim.html"
    has_select2 = True
    mainitems = []

    form_list = [
        {"prefix": "svdi", "formclass": RsetSelForm, "forminstance": None},
        {"prefix": "sgrp", "formclass": SgroupSelForm, "forminstance": None},
        ]

    selectbuttons = [
        {'title': 'Add to DCT',         'mode': 'show_dct',      'button': 'jumbo-1', 'glyphicon': 'glyphicon-wrench'},
        ]

    def custom_init(self, instance):
        if user_is_authenticated(self.request):
            # Get the profile id of this user
            profile = Profile.get_user_profile(self.request.user.username)
            self.object = profile
        else:
            pass
        return None

    def add_to_context(self, context, instance):

        def get_project_list(qs):
            sBack = "(none)"
            oErr = ErrHandle()
            try:
                if qs.count() > 0:
                    html = []
                    for obj in qs:
                        if obj.__class__.__name__ == "Project2":
                            project = obj
                        else:
                            project = obj.project
                        url = reverse('project2_details', kwargs={'pk': project.id})
                        html.append("<span class='project'><a href='{}'>{}</a></span>".format(url, project.name))
                    sBack = ",".join(html)
            except:
                msg = oErr.get_error_message()
                oErr.DoError("get_project_list")

            return sBack

        oErr = ErrHandle()
        bAllowSermonesReset = False
        try:
            profile = self.object
            context['profile'] = profile
            context['rset_count'] = ResearchSet.objects.filter(profile=profile).count()
            context['dct_count'] = SetDef.objects.filter(researchset__profile=profile).count()
            context['count_datasets'] = Collection.objects.filter(settype="pd", owner=profile).count()
            context['sermones_allow'] = bAllowSermonesReset

            # Special treatment: we have select2 and we have at least one form 
            initial = {}
            user= self.request.user
            for oItem in self.form_list:
                frmcls = oItem['formclass']
                prefix = oItem['prefix']
                frm = frmcls(initial, prefix=prefix, user=user)
                oItem['forminstance'] = frm
                # Possibly set the basic_form
                if context.get("basic_form") is None:
                    context['basic_form'] = frm

            # COunting table sizes for the super user
            if user_is_superuser(self.request):
                table_infos = []
                tables = [
                    {'app': 'seeker',
                     'models': ['Collection', 'Profile', 'Manuscript', 'SermonDescr', 'SermonHead', 'SermonGold', 
                          'Codico', 'MsItem', 'Author', 'Keyword', 'Library', 'Origin', 'Provenance', 'SourceInfo', 'Signature',
                          'SermonDescrEqual']},
                    {'app': 'dct', 
                     'models': ['ResearchSet', 'SetList', 'SetDef'] }
                          ]
                for oApp in tables:
                    app_name = oApp['app']
                    models = oApp['models']
                    models.sort()
                    for model in models:
                        cls = apps.app_configs[app_name].get_model(model)
                        count = cls.objects.count()
                        oInfo = dict(app_name=app_name, model_name=model, count=count)
                        table_infos.append(oInfo)
                context['table_infos'] = table_infos

            # Figure out which projects this editor may handle
            if context['is_app_editor']:
                # Figure out any editing rights
                context['edit_projects'] = get_project_list(profile.get_editor_projects())

                # Approver for project(s)
                context['approve_projects'] = get_project_list(profile.project_approver.all())

                # Default project(s)
                context['default_projects'] = get_project_list(profile.project_approver.filter(status="incl"))

            # Make sure to check (and possibly create) EqualApprove items for this user
            iCount = EqualChange.check_projects(profile)

            # What about the field changes that I have suggested?
            context['count_fchange_all'] = profile.profileproposals.count()
            context['count_fchange_open'] = profile.profileproposals.filter(atype="def").count()

            # How many do I need to approve?    
            context['count_approve_all'] = profile.profileapprovals.count()
            context['count_approve_task'] = profile.profileapprovals.filter(atype="def").count()

            # What about the SSG/AFs that I have suggested?
            context['count_afadd_all'] = profile.profileaddings.count()
            context['count_afadd_open'] = profile.profileaddings.filter(atype="def").count()

            # How many SSG/AFs do I need to approve?    
            context['count_afaddapprove_all'] = profile.profileaddapprovals.count()
            context['count_afaddapprove_task'] = profile.profileaddapprovals.filter(atype="def").count()

            # Add any related objects
            context['related_objects'] = self.get_related_objects(profile, context)

        except:
            msg = oErr.get_error_message()
            oErr.DoError("mypassimedit/add_to_context")

        return context

    def get_related_objects(self, instance, context):
        """Calculate and add related objects:

        Currently:
            - Saved items
            - Saved searches
            - Saved visualizations
            - DCTs
            - Stemmatizer research sets
            # To be extended: 
            - Imports
        """

        def add_one_item(rel_item, value, resizable=False, title=None, align=None, link=None, main=None, draggable=None):
            oAdd = dict(value=value)
            if resizable: oAdd['initial'] = 'small'
            if title != None: oAdd['title'] = title
            if align != None: oAdd['align'] = align
            if link != None: oAdd['link'] = link
            if main != None: oAdd['main'] = main
            if draggable != None: oAdd['draggable'] = draggable
            rel_item.append(oAdd)
            return True

        def check_order(qs):
            with transaction.atomic():
                for idx, obj in enumerate(qs):
                    if obj.order <= 0:
                        obj.order = idx + 1
                        obj.save()

        username = self.request.user.username
        team_group = app_editor

        # Authorization: only app-editors may edit!
        bMayEdit = user_is_ingroup(self.request, team_group)
        # FOr MyPassim the user may be in the group app_user
        if not bMayEdit:
            bMayEdit = user_is_ingroup(self.request, app_user)
            
        related_objects = []
        lstQ = []
        rel_list =[]
        resizable = True
        index = 1
        sort_start = ""
        sort_start_int = ""
        sort_end = ""
        if bMayEdit:
            sort_start = '<span class="sortable"><span class="fa fa-sort sortshow"></span>&nbsp;'
            sort_start_int = '<span class="sortable integer"><span class="fa fa-sort sortshow"></span>&nbsp;'
            sort_end = '</span>'

        oErr = ErrHandle()
        try:
            # Make sure to work with the current user's profile
            profile = self.object

            # [1] =============================================================
            # Get all 'SavedItem' objects that belong to the current user (=profile)
            sitemset = dict(title="Saved items", prefix="svitem")  
            if resizable: sitemset['gridclass'] = "resizable dragdrop sel-table"
            sitemset['savebuttons'] = bMayEdit
            sitemset['saveasbutton'] = False
            sitemset['selbutton'] = True
            sitemset['selitemtype'] = "svdi"
            sitemset['selitemForm'] = self.form_list[0]['forminstance']

            # Create custombuttons
            lCustom = []
            lCustom.append("<span>")
            lCustom.append('<a class="btn btn-xs jumbo-1" role="button" data-toggle="collapse" data-target="#sgroup-add" ')
            lCustom.append('title="Add/remove/edit saved-item Group Names">')
            lCustom.append('<span class="glyphicon glyphicon-th-large"></span></a>')
            lCustom.append("</span>")
            custombuttons = "\n".join(lCustom)
            sitemset['custombutton'] = custombuttons

            # Create what is needed for the custom context
            sgroupForm = self.form_list[1]['forminstance']
            # context = dict(profile=profile, sgroupForm=sgroupForm)
            context['profile'] = profile
            context['sgroupForm'] = sgroupForm
            sitemset['customshow'] = render_to_string("dct/sgroup_add.html", context, self.request)

            rel_list =[]

            qs_sgrouplist = [x.id for x in instance.profile_savegroups.all().order_by('name')]
            qs_sgrouplist.insert(0, None)
            qs_sitemlist = instance.profile_saveditems.all().order_by('group__name', 'order', 'sitemtype')

            # Look into selections
            qs_sitemids = [x.id for x in qs_sitemlist]
            sitemset['sel_count'] = instance.profile_selectitems.filter(saveditem_id__in=qs_sitemids).count()

            # Also store the count
            sitemset['count'] = qs_sitemlist.count()
            sitemset['instance'] = instance
            sitemset['detailsview'] = reverse('mypassim_details') #, kwargs={'pk': instance.id})
            # These elements have an 'order' attribute, so they  may be corrected
            check_order(qs_sitemlist)

            # at the top-level: walk the group list
            for group_id in qs_sgrouplist:
                # Look for all [saved items] in this group
                if group_id is None:
                    qs_sitemlist = instance.profile_saveditems.filter(group__isnull=True).order_by('order', 'sitemtype')
                else:
                    # Select the items in this group
                    qs_sitemlist = instance.profile_saveditems.filter(group__id=group_id).order_by('order', 'sitemtype')
                    # Add an item for the name of the group
                    rel_item = []
                    sGroupName = SaveGroup.objects.filter(id=group_id).first().name
                    iGroupSize = qs_sitemlist.count()
                    url = reverse('savegroup_details', kwargs={'pk': group_id})
                    rel_list.append(dict(isgroup=True, id=group_id, name=sGroupName, count=iGroupSize, url=url))

                    #if bMayEdit:
                    #    # Actions that can be performed on this item
                    #    add_one_item(rel_item, self.get_field_value("savegroup", obj, "buttons"), False)

                # Walk these sitemlist
                for obj in qs_sitemlist:
                    # The [obj] is of type `SavedItem`

                    rel_item = []

                    # The [item] depends on the sitemtype
                    item = None
                    itemset = dict(manu="manuscript", serm="sermon", ssg="equal", hc="collection", pd="collection")
                    if obj.sitemtype in itemset:
                        item = getattr(obj, itemset[obj.sitemtype])

                    # SavedItem: Order within the set of SavedItems
                    add_one_item(rel_item, obj.order, False, align="right", draggable=True)

                    # SavedItem: Type
                    add_one_item(rel_item, obj.get_sitemtype_display(), False)

                    # SavedItem: title of the manu/serm/ssg/coll
                    kwargs = None
                    #if obj.name != None and obj.name != "":
                    #    kwargs = dict(name=obj.name)
                    add_one_item(rel_item, self.get_field_value(obj.sitemtype, item, "title", kwargs=kwargs), False, main=True)

                    # SavedItem: Size (number of SSG in this manu/serm/ssg/coll)
                    add_one_item(rel_item, self.get_field_value(obj.sitemtype, item, "size"), False, align="right")

                    if bMayEdit:
                        # Actions that can be performed on this item
                        add_one_item(rel_item, self.get_field_value("saveditem", obj, "buttons"), False)

                    sel_info = get_selectitem_info(self.request, obj, self.object, self.sel_button)

                    # Add this line to the list
                    group_id = "0" if group_id is None else group_id
                    rel_list.append(dict(isgroup=False, id=obj.id, cols=rel_item, sel_info=sel_info, group_id=group_id))
            
            sitemset['rel_list'] = rel_list
            sitemset['columns'] = [
                '{}<span title="Default order">Order<span>{}'.format(sort_start_int, sort_end),
                '{}<span title="Type of saved item">Item</span>{}'.format(sort_start, sort_end), 
                '{}<span title="The title of the manuscript/sermon/authority-file/dataset/collection">Title</span>{}'.format(sort_start, sort_end), 
                '{}<span title="Number of SSGs part of this item">Size</span>{}'.format(sort_start_int, sort_end)
                ]
            if bMayEdit:
                sitemset['columns'].append("")
            related_objects.append(copy.copy(sitemset))

            # [2] ===============================================================
            # Get all 'SavedSearch' objects that belong to the current user (=profile)
            svsearchset = dict(title="Saved searches", prefix="svsearch")  
            if resizable: svsearchset['gridclass'] = "resizable dragdrop"
            svsearchset['savebuttons'] = bMayEdit
            svsearchset['saveasbutton'] = False
            rel_list =[]

            qs_svsearchlist = instance.profile_savedsearches.all().order_by('order', 'name')
            # Also store the count
            svsearchset['count'] = qs_svsearchlist.count()
            svsearchset['instance'] = instance
            svsearchset['detailsview'] = reverse('mypassim_details') #, kwargs={'pk': instance.id})
            # These elements have an 'order' attribute, so they  may be corrected
            check_order(qs_svsearchlist)

            # Walk these svsearchlist
            for obj in qs_svsearchlist:
                # The [obj] is of type `SavedSearch`

                rel_item = []

                # TODO:
                # Relevant columns for the saved searches are:
                # 1 - order
                # 2 - name for the saved search
                # 3 - listview name (e.g. Manifestation, Manuscript, Authority File and so on)
                #     or an icon for this listview, or a 3-letter abbr for this listview

                # SavedSearch: Order within the set of SavedSearches
                add_one_item(rel_item, obj.order, False, align="right", draggable=True)

                # SavedSearch: Name
                add_one_item(rel_item, obj.name, False, main=True)

                # SavedSearch: Listview name + link
                add_one_item(rel_item, obj.get_view_link(), False)

                if bMayEdit:
                    # Actions that can be performed on this item
                    add_one_item(rel_item, self.get_field_value("savedsearch", obj, "buttons"), False)

                # Add this line to the list
                rel_list.append(dict(id=obj.id, cols=rel_item))
            
            svsearchset['rel_list'] = rel_list
            svsearchset['columns'] = [
                '{}<span title="Default order">Order<span>{}'.format(sort_start_int, sort_end),
                '{}<span title="Name of saved search">Name</span>{}'.format(sort_start, sort_end), 
                '{}<span title="Kind of listview">View</span>{}'.format(sort_start, sort_end), 
                ]
            if bMayEdit:
                svsearchset['columns'].append("")
            related_objects.append(copy.copy(svsearchset))

            # [3] ===============================================================
            # Get all 'SavedVis' objects that belong to the current user (=profile)
            svdvisset = dict(title="Saved visualizations", prefix="svdvis")  
            if resizable: svdvisset['gridclass'] = "resizable dragdrop"
            svdvisset['savebuttons'] = bMayEdit
            svdvisset['saveasbutton'] = False
            rel_list =[]

            qs_svdvislist = instance.profile_savedvisualizations.all().order_by('order', 'name')
            # Also store the count
            svdvisset['count'] = qs_svdvislist.count()
            svdvisset['instance'] = instance
            svdvisset['detailsview'] = reverse('mypassim_details') #, kwargs={'pk': instance.id})
            # These elements have an 'order' attribute, so they  may be corrected
            check_order(qs_svdvislist)

            # Walk these svdvislist
            for obj in qs_svdvislist:
                # The [obj] is of type `SavedVis`

                rel_item = []

                # TODO:
                # Relevant columns for the Saved visualisations are:
                # 1 - order
                # 2 - name for the saved search
                # 3 - visualization name (e.g. AF Overlap, AF transmission, DCT and so on)
                #     or: an icon for this visualization
                #     or: a 3-letter abbr for this visualization

                # SavedVis: Order within the set of Saved visualizations
                add_one_item(rel_item, obj.order, False, align="right", draggable=True)

                # SavedVis: Name
                add_one_item(rel_item, obj.name, False, main=True)

                # SavedVis: visualization type + link to open/execute it
                add_one_item(rel_item, obj.get_view_link(), False)

                if bMayEdit:
                    # Actions that can be performed on this item
                    add_one_item(rel_item, self.get_field_value("savedvis", obj, "buttons"), False)

                # Add this line to the list
                rel_list.append(dict(id=obj.id, cols=rel_item))
            
            svdvisset['rel_list'] = rel_list
            svdvisset['columns'] = [
                '{}<span title="Default order">Order<span>{}'.format(sort_start_int, sort_end),
                '{}<span title="Name of saved visualization">Name</span>{}'.format(sort_start, sort_end), 
                '{}<span title="Kind of visualization">Type</span>{}'.format(sort_start, sort_end), 
                ]
            if bMayEdit:
                svdvisset['columns'].append("")
            related_objects.append(copy.copy(svdvisset))

            # [3] ===============================================================
            # Get all 'SetDef' objects that belong to the current user (=profile)
            dctdefset = dict(title="Dynamic comparitive tables", prefix="dctdef")  
            if resizable: dctdefset['gridclass'] = "resizable dragdrop"
            dctdefset['savebuttons'] = bMayEdit
            dctdefset['saveasbutton'] = False
            rel_list =[]

            # qs_dctdeflist = instance.profile_mydctualizations.all().order_by('order', 'name')
            qs_dctdeflist = SetDef.objects.filter(researchset__profile=instance).order_by('order', 'name')
            # Also store the count
            dctdefset['count'] = qs_dctdeflist.count()
            dctdefset['instance'] = instance
            dctdefset['detailsview'] = reverse('mypassim_details') #, kwargs={'pk': instance.id})

            # And store an introduction
            lIntro = []
            lIntro.append('View and work with research sets on the <em>development version</em> of ')
            lIntro.append('the <a role="button" class="btn btn-xs jumbo-1" ')
            lIntro.append('href="{}">DCT tool</a> page.'.format(reverse('researchset_list')))
            sIntro = " ".join(lIntro)
            dctdefset['introduction'] = sIntro

            # These elements have an 'order' attribute, but...
            #   ... but that order may *NOT be corrected here
            # check_order(qs_dctdeflist)

            # Walk these dctdeflist
            for obj in qs_dctdeflist:
                # The [obj] is of type `SetDef`

                rel_item = []

                # TODO:
                # Relevant columns for the Your visualisations are:
                # 1 - order
                # 2 - name of the ResearchSet
                # 3 - name of the DCT

                # SetDef: Order within the set of Your visualizations
                add_one_item(rel_item, obj.order, False, align="right", draggable=True)

                # SetDef: researchSet name
                add_one_item(rel_item, obj.researchset.name, False, main=True)

                # SetDef: DCT name
                add_one_item(rel_item, obj.get_view_link(), False)

                if bMayEdit:
                    # Actions that can be performed on this item
                    add_one_item(rel_item, self.get_field_value("mydct", obj, "buttons"), False)

                # Add this line to the list
                rel_list.append(dict(id=obj.id, cols=rel_item))
            
            dctdefset['rel_list'] = rel_list
            dctdefset['columns'] = [
                '{}<span title="Default order">Order<span>{}'.format(sort_start_int, sort_end),
                '{}<span title="Research set">Research set</span>{}'.format(sort_start, sort_end), 
                '{}<span title="Dynamic Comparative Table">DCT</span>{}'.format(sort_start, sort_end), 
                ]
            if bMayEdit:
                dctdefset['columns'].append("")
            related_objects.append(copy.copy(dctdefset))

            # [3] ===============================================================
            # Get all 'StemmaSet' objects that belong to the current user (=profile)
            stemmaset = dict(title="Stemmatizer research sets", prefix="stemma")  
            if resizable: stemmaset['gridclass'] = "resizable dragdrop"
            stemmaset['savebuttons'] = bMayEdit
            stemmaset['saveasbutton'] = False
            rel_list =[]

            qs_stemmalist = StemmaSet.objects.filter(profile=instance).order_by('name')
            # Also store the count
            stemmaset['count'] = qs_stemmalist.count()
            stemmaset['instance'] = instance
            stemmaset['detailsview'] = reverse('mypassim_details') #, kwargs={'pk': instance.id})

            # And store an introduction
            lIntro = []
            lIntro.append('View and work with stemmatizer research sets on the <em>development version</em> of ')
            lIntro.append('the <a role="button" class="btn btn-xs jumbo-1" ')
            lIntro.append('href="{}">Stemmatizer tool</a> page.'.format(reverse('stemmaset_list')))
            sIntro = " ".join(lIntro)
            stemmaset['introduction'] = sIntro

            # These elements have an 'order' attribute, but...
            #   ... but that order may *NOT be corrected here
            # check_order(qs_stemmalist)

            # Walk these stemmalist
            order = 0
            for obj in qs_stemmalist:
                # The [obj] is of type `StemmaSet`

                rel_item = []
                order += 1

                # TODO:
                # Relevant columns for the Your visualisations are:
                # 1 - name of the StemmaSet
                # 2 - scope of the Stemma research set (priv/team/publ)
                # 3 - size in terms of number of SSGs part of this set
                # 4 - analyze button

                # SetDef: Order within the set of Your visualizations
                add_one_item(rel_item, order, False, align="right", draggable=True)

                # Name: the name of this Stemmaset
                add_one_item(rel_item, obj.get_name_markdown(), False, main=True)

                # Analyze: button to analyze this one
                add_one_item(rel_item, obj.get_analyze_markdown(), False, main=True)

                # Scope: private, team or global
                add_one_item(rel_item, obj.get_scope_display(), False)

                # Size: number of StemmaItems part of this StemmaSet
                size = "{}".format(obj.stemmaset_stemmaitems.count())
                add_one_item(rel_item, size, False, align="right")

                if bMayEdit:
                    # Actions that can be performed on this item
                    add_one_item(rel_item, self.get_field_value("stemma", obj, "buttons"), False)

                # Add this line to the list
                rel_list.append(dict(id=obj.id, cols=rel_item))
            
            stemmaset['rel_list'] = rel_list
            stemmaset['columns'] = [
                '{}<span title="Default order">Order<span>{}'.format(sort_start_int, sort_end),
                '{}<span title="Name of the stemmatizer research set">Name</span>{}'.format(sort_start, sort_end), 
                '{}<span title="Analyze the stemmatological research set">Analyze</span>{}'.format(sort_start, sort_end), 
                '{}<span title="Scope">Scope</span>{}'.format(sort_start, sort_end), 
                '{}<span title="Number of items in this research set">Size</span>{}'.format(sort_start, sort_end), 
                ]
            if bMayEdit:
                stemmaset['columns'].append("")
            related_objects.append(copy.copy(stemmaset))

            # [4] ===============================================================
            if context['is_app_editor']:
                # Get all 'ImportSet' objects that belong to the current user (=profile)
                importset = dict(title="Excel import sets", prefix="xlsimp")  
                if resizable: importset['gridclass'] = "resizable dragdrop"
                importset['savebuttons'] = bMayEdit
                importset['saveasbutton'] = False
                rel_list =[]

                qs_imports = ImportSet.objects.filter(profile=instance).order_by('excel')
                # Also store the count
                importset['count'] = qs_imports.count()
                importset['instance'] = instance
                importset['detailsview'] = reverse('mypassim_details') #, kwargs={'pk': instance.id})

                # And store an introduction
                lIntro = []
                lIntro.append('View and work with <a role="button" class="btn btn-xs jumbo-1" ')
                lIntro.append('href="{}">Excel import submissions</a>.'.format(reverse('importset_list')))
                sIntro = " ".join(lIntro)
                importset['introduction'] = sIntro

                # These elements have an 'order' attribute, but...
                #   ... but that order may *NOT be corrected here
                # check_order(qs_imports)

                # Walk these imports
                order = 0
                for obj in qs_imports:
                    # The [obj] is of type `ImportSet`

                    rel_item = []
                    order += 1

                    # TODO:
                    # Relevant columns for the Your visualisations are:
                    # 1 - filename of the ImportSet submission
                    # 2 - type (manuscript or authority file)
                    # 3 - status
                    # 4 - date

                    # SetDef: Order within the set of Your visualizations
                    add_one_item(rel_item, order, False, align="right", draggable=True)

                    # Name: the filename of the import submission
                    sName = obj.get_name()
                    url = reverse('importset_details', kwargs={'pk': obj.id})
                    add_one_item(rel_item, sName, False, main=True, link=url)

                    # Type: what the import submission describes (M/SSG)
                    sType = obj.get_type()
                    add_one_item(rel_item, sType, False, main=False)

                    # Status: status of the submission
                    sStatus = obj.get_status()
                    add_one_item(rel_item, sStatus, False)

                    # Date: last save date of submission
                    sDate = obj.get_saved()
                    add_one_item(rel_item, sDate, False) # , align="right")

                    if bMayEdit:
                        # Actions that can be performed on this item
                        add_one_item(rel_item, self.get_field_value("stemma", obj, "buttons"), False)

                    # Add this line to the list
                    rel_list.append(dict(id=obj.id, cols=rel_item))
            
                importset['rel_list'] = rel_list
                importset['columns'] = [
                    '{}<span title="Default order">Order<span>{}'.format(sort_start_int, sort_end),
                    '{}<span title="Name of the Excel file submitted">Name</span>{}'.format(sort_start, sort_end), 
                    '{}<span title="Type of submission">Type</span>{}'.format(sort_start, sort_end), 
                    '{}<span title="Status of the submission">Status</span>{}'.format(sort_start, sort_end), 
                    '{}<span title="Date last saved">Date</span>{}'.format(sort_start, sort_end), 
                    ]
                if bMayEdit:
                    importset['columns'].append("")
                related_objects.append(copy.copy(importset))

            # [5] ===============================================================
            if context['is_app_moderator']:
                # Get all 'ImportReview' objects that belong to the current user (=profile)
                importreview = dict(title="Excel import reviews", prefix="xlsrev")  
                if resizable: importreview['gridclass'] = "resizable dragdrop"
                importreview['savebuttons'] = bMayEdit
                importreview['saveasbutton'] = False
                rel_list =[]

                qs_reviews = ImportReview.objects.all().order_by('moderator__user__username', 'order')
                # Also store the count
                importreview['count'] = qs_reviews.count()
                importreview['instance'] = instance
                importreview['detailsview'] = reverse('mypassim_details') #, kwargs={'pk': instance.id})

                # And store an introduction
                lIntro = []
                lIntro.append('View and work with <a role="button" class="btn btn-xs jumbo-1" ')
                lIntro.append('href="{}">Excel import reviews</a>.'.format(reverse('importreview_list')))
                sIntro = " ".join(lIntro)
                importreview['introduction'] = sIntro

                # These elements have an 'order' attribute, but...
                #   ... but that order may *NOT be corrected here
                # check_order(qs_reviews)

                # Walk these imports
                order = 0
                for obj in qs_reviews:
                    # The [obj] is of type `ImportReview`

                    rel_item = []
                    order += 1

                    importset = obj.importset

                    # TODO:
                    # Relevant columns for the Your visualisations are:
                    # 1 - filename of the ImportReview submission
                    # 2 - user
                    # 3 - type (manuscript or authority file)
                    # 4 - status
                    # 5 - date

                    # SetDef: Order within the set of Your visualizations
                    add_one_item(rel_item, order, False, align="right", draggable=True)

                    # The user who has submitted this
                    sUser = obj.get_owner()
                    add_one_item(rel_item, sUser, False, main=False)

                    # Name: the filename of the import submission
                    sName = importset.get_name()
                    url = reverse('importreview_details', kwargs={'pk': obj.id})
                    add_one_item(rel_item, sName, False, main=True, link=url)

                    # Type: what the import submission describes (M/SSG)
                    sType = importset.get_type()
                    add_one_item(rel_item, sType, False, main=False)

                    # Status: status of the review
                    sStatus = obj.get_status()
                    add_one_item(rel_item, sStatus, False)

                    # Date: last save date of review
                    sDate = obj.get_saved()
                    add_one_item(rel_item, sDate, False) # , align="right")

                    if bMayEdit:
                        # Actions that can be performed on this item
                        add_one_item(rel_item, self.get_field_value("stemma", obj, "buttons"), False)

                    # Add this line to the list
                    rel_list.append(dict(id=obj.id, cols=rel_item))
            
                importreview['rel_list'] = rel_list
                importreview['columns'] = [
                    '{}<span title="Default order">Order<span>{}'.format(sort_start_int, sort_end),
                    '{}<span title="User who submitted this Excel">User</span>{}'.format(sort_start, sort_end), 
                    '{}<span title="Name of the Excel file submitted">Name</span>{}'.format(sort_start, sort_end), 
                    '{}<span title="Type of submission">Type</span>{}'.format(sort_start, sort_end), 
                    '{}<span title="Status of the review">Review</span>{}'.format(sort_start, sort_end), 
                    '{}<span title="Date last saved">Date</span>{}'.format(sort_start, sort_end), 
                    ]
                if bMayEdit:
                    importreview['columns'].append("")
                related_objects.append(copy.copy(importreview))

        except:
            msg = oErr.get_error_message()
            oErr.DoError("mypassimedit/get_related_objects")

        # Return the adapted context
        return related_objects

    def get_field_value(self, type, instance, custom, kwargs=None):
        sBack = ""
        collection_types = ['hc', 'pd' ]
        sRemove = "<a class='btn btn-xs jumbo-1'><span class='glyphicon glyphicon-remove related-remove' title='Delete this item'></span></a>"

        oErr = ErrHandle()
        try:

            if type == "manu":
                # This is a Manuscript
                if custom == "title":
                    url = reverse("manuscript_details", kwargs={'pk': instance.id})
                    sBack = "<span class='clickable'><a href='{}' class='nostyle'>{}, {}, <span class='signature'>{}</span></a><span>".format(
                        url, instance.get_city(), instance.get_library(), instance.idno)
                elif custom == "size":
                    # Get the number of SSGs related to items in this manuscript
                    count = EqualGold.objects.filter(sermondescr_super__sermon__msitem__codico__manuscript=instance).order_by('id').distinct().count()
                    sBack = "{}".format(count)

            elif type == "serm":
                # This is a sermon description
                if custom == "title":
                    url = reverse("sermon_details", kwargs = {'pk': instance.id})
                    sBack = "<span class='clickable'><a href='{}' class='nostyle'><span class='signature'>{}</span>: {}</a><span>".format(
                        url, instance.msitem.codico.manuscript.idno, instance.get_locus())
                elif custom == "size":
                    # Get the number of SSGs to which this Sermon points
                    count = instance.equalgolds.count()
                    sBack = "{}".format(count)

            elif type == "ssg":
                # This is an Authority File (=SSG)
                if custom == "title":
                    sBack = instance.get_passimcode_markdown()
                elif custom == "size":
                    count = 1   # There is just 1 authority file
                    sBack = "{}".format(count)


            elif type in collection_types:
                if custom == "title":
                    sTitle = "none"
                    if instance is None:
                        sBack = sTitle
                    else:
                        if type == "hc":
                            # Historical collection
                            url = reverse("collhist_details", kwargs={'pk': instance.id})
                        else:
                            # Private or Public dataset
                            if instance.scope == "publ":
                                url = reverse("collpubl_details", kwargs={'pk': instance.id})
                            else:
                                url = reverse("collpriv_details", kwargs={'pk': instance.id})
                        if kwargs != None and 'name' in kwargs:
                            title = "{} (dataset name: {})".format( kwargs['name'], instance.name)
                        else:
                            title = instance.name
                        sBack = "<span class='clickable'><a href='{}' class='nostyle'>{}</a></span>".format(url, title)
                elif custom == "size":
                    # Get the number of SSGs related to items in this collection
                    #count = "-1" if instance is None else instance.super_col.count()
                    #sBack = "{}".format(count)
                    sBack = instance.get_size_markdown()

            elif type == "saveditem":
                # A saved item should get the button 'Delete'
                if custom == "buttons":
                    # Create the remove button
                    # sBack = "<a class='btn btn-xs jumbo-2'><span class='related-remove'>Delete</span></a>"
                    sBack = sRemove

            elif type == "savedsearch":
                # A saved item should get the button 'Delete'
                if custom == "buttons":
                    # Create the remove button
                    # sBack = "<a class='btn btn-xs jumbo-2'><span class='related-remove'>Delete</span></a>"
                    sBack = sRemove

            elif type == "savedvis":
                # A saved item should get the button 'Delete'
                if custom == "buttons":
                    # Create the remove button
                    # sBack = "<a class='btn btn-xs jumbo-2'><span class='related-remove'>Delete</span></a>"
                    sBack = sRemove

            elif type == "mydct":
                # A DCT should get the button 'Delete'
                if custom == "buttons":
                    # Create the remove button
                    # sBack = "<a class='btn btn-xs jumbo-2'><span class='related-remove'>Delete</span></a>"
                    sBack = sRemove

            elif type == "stemma":
                # A Stemma research set should get the button 'Delete'
                if custom == "buttons":
                    # Create the remove button
                    # sBack = "<a class='btn btn-xs jumbo-2'><span class='related-remove'>Delete</span></a>"
                    sBack = sRemove


        except:
            msg = oErr.get_error_message()
            oErr.DoError("MyPassimEdit/get_field_value")

        return sBack

    def check_hlist(self, instance):
        """Check if a hlist parameter is given, and hlist saving is called for"""

        oErr = ErrHandle()
        bChanges = False
        bDebug = True
        hlist_objects = [
            {"prefix": "svitem",    "cls": SavedItem, "grp": SaveGroup},
            {"prefix": "svsearch",  "cls": SavedSearch},
            {"prefix": "svdvis",    "cls": SavedVis},
            {"prefix": "dctdef",    "cls": SetDef},
            {"prefix": "stemma",    "cls": StemmaSet},
            {"prefix": "xlsimp",    "cls": ImportSet},
            {"prefix": "xlsrev",    "cls": ImportReview},
            ]

        try:
            # Walk all hlist objects
            for oHlist in hlist_objects:
                prefix = oHlist.get("prefix")
                cls = oHlist.get("cls")
                grp = oHlist.get("grp")
                arg_hlist = "{}-hlist".format(prefix)
                arg_glist = "{}-glist".format(prefix)
                arg_savenew = "{}-savenew".format(prefix)

                # NOTE: it is either [hlist] or [glist], not both of them
                if arg_glist in self.qd and not grp is None:
                    glist = json.loads(self.qd[arg_glist])

                    # Make sure we are not saving
                    self.do_not_save = True
                    # But that we do a new redirect
                    self.newRedirect = True

                    # Change the redirect URL
                    if self.redirectpage == "":
                        self.redirectpage = reverse('mypassim_details')

                    # We also need to create a [hlist] to check existing
                    hlist = []
                    # What we have is the ordered list of SavedItem id's plus a possible SaveGroup id
                    with transaction.atomic():
                        # Make sure the orders are correct
                        for idx, oItem in enumerate(glist):
                            order = idx + 1
                            groupid = oItem.get("groupid")
                            item_id = oItem.get("rowid")

                            # Keep track of the actually used items, in the mean time
                            hlist.append(item_id)

                            if prefix == "dctdef":
                                lstQ = [Q(researchset__profile=instance)]
                            else:
                                lstQ = [Q(profile=instance)]
                            lstQ.append(Q(**{"id": item_id}))
                            obj = cls.objects.filter(*lstQ).first()

                            if isinstance(groupid, str): groupid = int(groupid)
                            if groupid == 0:
                                group = None
                            else:
                                if prefix == "dctdef":
                                    lstQ = [Q(researchset__profile=instance)]
                                else:
                                    lstQ = [Q(profile=instance)]
                                lstQ.append(Q(**{"id": groupid}))
                                group = grp.objects.filter(*lstQ).first()

                            if obj != None:
                                # The order should be correct
                                if obj.order != order:
                                    obj.order = order
                                    obj.save()
                                    bChanges = True
                                # The group adherence should also be correct
                                current_group_id = 0 if obj.group is None else obj.group.id
                                if current_group_id != groupid:
                                    # Assign the new group
                                    obj.group = group
                                    obj.save()
                                    bChanges = True

                    # See if any need to be removed
                    if prefix == "dctdef":
                        existing_item_id = [str(x.id) for x in cls.objects.filter(researchset__profile=instance)]
                    else:
                        existing_item_id = [str(x.id) for x in cls.objects.filter(profile=instance)]
                    delete_id = []
                    for item_id in existing_item_id:
                        if not item_id in hlist:
                            delete_id.append(item_id)
                    if len(delete_id)>0:
                        if prefix == "dctdef":
                            lstQ = [Q(researchset__profile=instance)]
                        else:
                            lstQ = [Q(profile=instance)]
                        lstQ.append(Q(**{"id__in": delete_id}))
                        cls.objects.filter(*lstQ).delete()
                        bChanges = True

                    if bChanges:
                        # (6) Re-calculate the order
                        cls.update_order(instance)

                elif arg_hlist in self.qd and arg_savenew in self.qd:
                    # Interpret the list of information that we receive
                    hlist = json.loads(self.qd[arg_hlist])
                    # Interpret the savenew parameter
                    savenew = self.qd[arg_savenew]

                    # Make sure we are not saving
                    self.do_not_save = True
                    # But that we do a new redirect
                    self.newRedirect = True

                    # Change the redirect URL
                    if self.redirectpage == "":
                        self.redirectpage = reverse('mypassim_details')

                    # What we have is the ordered list of SavedItem id's that are part of this collection
                    with transaction.atomic():
                        # Make sure the orders are correct
                        for idx, item_id in enumerate(hlist):
                            order = idx + 1
                            if prefix == "dctdef":
                                lstQ = [Q(researchset__profile=instance)]
                            else:
                                lstQ = [Q(profile=instance)]
                            lstQ.append(Q(**{"id": item_id}))
                            obj = cls.objects.filter(*lstQ).first()
                            if obj != None:
                                if obj.order != order:
                                    obj.order = order
                                    obj.save()
                                    bChanges = True
                    # See if any need to be removed
                    if prefix == "dctdef":
                        existing_item_id = [str(x.id) for x in cls.objects.filter(researchset__profile=instance)]
                    else:
                        existing_item_id = [str(x.id) for x in cls.objects.filter(profile=instance)]
                    delete_id = []
                    for item_id in existing_item_id:
                        if not item_id in hlist:
                            delete_id.append(item_id)
                    if len(delete_id)>0:
                        if prefix == "dctdef":
                            lstQ = [Q(researchset__profile=instance)]
                        else:
                            lstQ = [Q(profile=instance)]
                        lstQ.append(Q(**{"id__in": delete_id}))
                        cls.objects.filter(*lstQ).delete()
                        bChanges = True

                    if bChanges:
                        # (6) Re-calculate the order
                        cls.update_order(instance)

            return True
        except:
            msg = oErr.get_error_message()
            oErr.DoError("MyPassimEdit/check_hlist")
            return False


class MyPassimDetails(MyPassimEdit):
    """The HTML variant of [ResearchSetEdit]"""

    rtype = "html"

    def custom_init(self, instance):
        # First process what needs to be done anyway
        custom_result = super(MyPassimDetails, self).custom_init(instance)

        # Now continue
        profile = instance if not instance is None else self.object
        if not profile is None:
            # Check for hlist saving
            self.check_hlist(profile)
        return None


# ================= Views for SavedSearch ==========================

class SavedSearchApply(BasicPart):
    """Add a named saved search item"""

    MainModel = User

    def add_to_context(self, context):

        oErr = ErrHandle()
        data = dict(status="ok")
       
        try:

            # We already know who we are
            profile = self.obj.user_profiles.first()
            # Retrieve necessary parameters
            usersearch_id = self.qd.get("svd-usersearch_id")
            searchname = ""
            for k,v in self.qd.items():
                if "-searchname" in k:
                    if isinstance(v,str) and "<script" in v:
                        searchname = "--script--"
                    else:
                        searchname = v
                    break
            if searchname == "--script--":
                # The name contains a script
                data['action'] = "script"
            elif searchname == "":
                # User did not supply a name
                data['action'] = "empty"
            else:
                # Create a saved search
                obj = SavedSearch.objects.filter(name=searchname, profile=profile).first()
                if obj is None:
                    obj = SavedSearch.objects.create(name=searchname, profile=profile, usersearch_id=usersearch_id)
                else:
                    # Check and set the usersearch_id
                    searchid = obj.usersearch.id
                    if usersearch_id != searchid:
                        obj.usersearch_id = usersearch_id
                        obj.save()
                # Indicate what happened: adding
                data['action'] = "added"

        except:
            msg = oErr.get_error_message()
            oErr.DoError("SavedSearchApply")
            data['status'] = "error"

        context['data'] = data
        return context


class SavedVisualizationApply(BasicPart):
    """Add a named saved visualization item"""

    MainModel = User

    def add_to_context(self, context):

        oErr = ErrHandle()
        data = dict(status="ok")
       
        try:

            # We already know who we are
            profile = self.obj.user_profiles.first()
            # Retrieve necessary parameters
            options = self.qd.get("options")
            # Unwrap the options
            if not options is None:
                oOptions = json.loads(options)
                # URL to be called to get the visualization
                visurl = oOptions.get("visurl")
                # Type of visualization
                vistype = oOptions.get("vistype")

                searchname = ""
                for k,v in self.qd.items():
                    if "-visname" in k:
                        if isinstance(v,str) and "<script" in v:
                            searchname = "--script--"
                        else:
                            searchname = v
                        break
                if searchname == "--script--":
                    # The name contains a script
                    data['action'] = "script"
                elif searchname == "":
                    # User did not supply a name
                    data['action'] = "empty"
                else:
                    # Create a saved search
                    obj = SavedVis.objects.filter(name=searchname, profile=profile).first()
                    if obj is None:
                        obj = SavedVis.objects.create(name=searchname, profile=profile, visurl=visurl, options=options)
                    else:
                        bNeedSaving = False
                        # Check and set the visurl + options
                        if obj.visurl != visurl: 
                            obj.visurl = visurl 
                            bNeedSaving = True
                        if obj.options != options:
                            obj.options = options
                            bNeedSaving = True

                        if bNeedSaving:
                            obj.save()
                    # Indicate what happened: adding
                    data['action'] = "added"

        except:
            msg = oErr.get_error_message()
            oErr.DoError("SavedVisualizationApply")
            data['status'] = "error"

        context['data'] = data
        return context


# ================= Views for SavedItem, SelectItem ================

class SavedItemApply(BasicPart):
    """Either add or remove an item as saved data"""

    MainModel = Profile

    def add_to_context(self, context):

        oErr = ErrHandle()
        data = dict(status="ok")
       
        try:
            # Check validity and permissions
            # issue #386: non-editors must be able to do this too
            # if not self.userpermissions("w"):
            if not self.userpermissions("r"):
                # Don't do anything
                return context

            # We already know who we are
            profile = self.obj

            # Retrieve necessary parameters
            sitemtype = self.qd.get("sitemtype")
            sitemaction = self.qd.get("sitemaction")
            saveditemid = self.qd.get("saveditemid")
            itemid = self.qd.get("itemid")

            itemset = dict(manu="manuscript", serm="sermon", ssg="equal", hc="collection", pd="collection")
            itemidfield = itemset[sitemtype]

            if sitemaction == "add":
                # We are going to add an item as a saveditem
                lstQ = []
                lstQ.append(Q(profile=profile))
                lstQ.append(Q(sitemtype=sitemtype))
                lstQ.append(Q(**{"{}_id".format(itemidfield): itemid}))
                obj = SavedItem.objects.filter(*lstQ).first()
                # OLD and obsolete: obj = SavedItem.objects.filter(profile=profile, sitemtype=sitemtype).first()
                if obj is None:
                    obj = SavedItem.objects.create(
                        profile=profile, sitemtype=sitemtype)
                    # The particular attribute to set depends on the sitemtype
                    setattr(obj, "{}_id".format(itemidfield), itemid)
                    obj.save()
                data['action'] = "added"
            elif sitemaction == "remove" and not saveditemid is None:
                # We need to remove *ALL* relevant items
                lstQ = []
                lstQ.append(Q(profile=profile))
                lstQ.append(Q(sitemtype=sitemtype))
                lstQ.append(Q(**{"{}_id".format(itemidfield): itemid}))
                delete_id = SavedItem.objects.filter(*lstQ).values("id")
                if len(delete_id) > 0:
                    SavedItem.objects.filter(id__in=delete_id).delete()
                data['action'] = "removed"

            # Possibly adapt the ordering of the saved items for this user
            if 'action' in data:
                # Something has happened
                SavedItem.update_order(profile)
        except:
            msg = oErr.get_error_message()
            oErr.DoError("SavedItemApply")
            data['status'] = "error"

        context['data'] = data
        return context


class SelectItemApply(BasicPart):
    """Either add or remove an item as selected data"""

    MainModel = Profile

    def add_to_context(self, context):

        oErr = ErrHandle()
        data = dict(status="ok")
        oSelBasket = dict(
            serm=dict(model=Basket, field_b="sermon", field_s="sermon", field_p="basketsize"),
            manu=dict(model=BasketMan, field_b="manu", field_s="manuscript", field_p="basketsize_manu"),
            ssg=dict(model=BasketSuper, field_b="super", field_s="equal", field_p="basketsize_super"),
            gold=dict(model=BasketGold, field_b="gold", field_s="gold", field_p="basketsize_gold")
            )
        oSelDct = dict(
            manu=dict(setlisttype="manu", field_s="manuscript"),
            hc=dict(setlisttype="ssgd", field_s="collection"),
            pd=dict(setlisttype="ssgd", field_s="collection")
            )
       
        try:
            # We already know who we are
            profile = self.obj

            # Check validity and permissions
            # issue #386: non-editors must be able to do this too
            # if not self.userpermissions("w"):
            if not self.userpermissions("r"):
                # Don't do anything
                return context

            # Retrieve necessary parameters
            selitemtype = self.qd.get("selitemtype")
            selitemaction = self.qd.get("selitemaction")
            mode = self.qd.get("mode")
            selitemid = self.qd.get("selitemid")
            itemid = self.qd.get("itemid")
            rsetoneid = None
            for k,v in self.qd.items():
                if "rsetone" in k:
                    rsetoneid = v
                    break

            itemset = dict(manu="manuscript", serm="sermon", ssg="equal", 
                           hc="collection", pd="collection", svdi="saveditem")
            itemidfield = itemset[selitemtype]

            if selitemaction == "-" and not mode is None:
                selitemaction = mode

            if selitemaction == "add":
                # We are going to add an item as a selitem
                lstQ = []
                lstQ.append(Q(profile=profile))
                lstQ.append(Q(selitemtype=selitemtype))
                lstQ.append(Q(**{"{}_id".format(itemidfield): itemid}))
                obj = SelectItem.objects.filter(*lstQ).first()
                if obj is None:
                    obj = SelectItem.objects.create(profile=profile, selitemtype=selitemtype)
                    # The particular attribute to set depends on the selitemtype
                    setattr(obj, "{}_id".format(itemidfield), itemid)
                    obj.save()
                data['action'] = "added"
            elif selitemaction == "remove" and not selitemid is None:
                # We need to remove *ALL* relevant items
                lstQ = []
                lstQ.append(Q(profile=profile))
                lstQ.append(Q(selitemtype=selitemtype))
                lstQ.append(Q(**{"{}_id".format(itemidfield): itemid}))
                delete_id = SelectItem.objects.filter(*lstQ).values("id")
                if len(delete_id) > 0:
                    SelectItem.objects.filter(id__in=delete_id).delete()
                data['action'] = "removed"

            elif selitemaction == "clear_sel":
                # Remove all selections for this item type
                delete_id = SelectItem.objects.filter(profile=profile, selitemtype=selitemtype).values("id")
                if len(delete_id) > 0:
                    SelectItem.objects.filter(id__in=delete_id).delete()
                # Indicate that the JS also needs to do some clearing
                data['action'] = "clear_sel"

            elif selitemaction == "del_items":
                # The associated items should be removed + selection removed
                # (1) First remove the associated items
                for obj in SelectItem.objects.filter(profile=profile, selitemtype=selitemtype):
                    # For the moment restrict this to PD only
                    if selitemtype == "pd":
                        # Remove collection, provided this is the owner
                        if obj.collection.owner.id == profile.id:
                            obj.collection.delete()
                    #if selitemtype == "manu":
                    #    # Remove manuscript
                    #    obj.manuscript.delete()
                    #elif selitemtype == "serm":
                    #    # Remove manuscript
                    #    obj.sermon.delete()
                    #elif selitemtype == "ssg":
                    #    # Remove manuscript
                    #    obj.equal.delete()
                    #elif selitemtype in ["hist", "pd"]:
                    #    # Remove manuscript
                    #    obj.collection.delete()
                    #elif selitemtype == "svdi":
                    #    # Remove manuscript
                    #    obj.saveditem.delete()

                # (2) In all situations: clear the selection
                delete_id = SelectItem.objects.filter(profile=profile, selitemtype=selitemtype).values("id")
                if len(delete_id) > 0:
                    SelectItem.objects.filter(id__in=delete_id).delete()
                # Indicate that the JS also needs to do some clearing
                data['action'] = "del_items"

            elif selitemaction == "add_saveitem":
                # Add all selected items to the Saved Items
                qs = SelectItem.objects.filter(profile=profile, selitemtype=selitemtype)
                for obj_sel in qs:
                    # Check if we have this already as SavedItem
                    obj_sav = SavedItem.objects.filter(profile=profile, sitemtype=selitemtype,
                            manuscript=obj_sel.manuscript, sermon=obj_sel.sermon,
                            equal=obj_sel.equal, collection=obj_sel.collection).first()
                    if obj_sav is None:
                        # Create it
                        obj_sav = SavedItem.objects.create(profile=profile, sitemtype=selitemtype,
                                manuscript=obj_sel.manuscript, sermon=obj_sel.sermon,
                                equal=obj_sel.equal, collection=obj_sel.collection)

                # Remove the selection
                qs.delete()

                # Indicate that the JS also needs to do some clearing
                data['action'] = "update_sav"

            elif selitemaction == "add_basket":
                # Double check: this functionality only exists for S, SG, SSG, M
                if selitemtype in oSelBasket:
                    # Add all selected items to the Basket of the currently selected listview
                    qs = SelectItem.objects.filter(profile=profile, selitemtype=selitemtype)

                    # Figure out which selection object to use
                    selParams = oSelBasket[selitemtype]
                    cls = selParams['model']
                    field_b = selParams['field_b']
                    field_s = selParams['field_s']
                    field_p = selParams['field_p']

                    # Get initial basket size
                    basketsize = cls.objects.filter(profile=profile).count()
                    # If that initial size is zero...
                    if basketsize == 0:
                        # Then we need to supply a targeturl to return to where we came from
                        data['newbasket'] = "#basiclist_filter"

                    # Walk all selected items
                    for obj_sel in qs:  
                        # which object is this?
                        obj = getattr(obj_sel, field_s)
                                              
                        # Check if this item already exists in the basket
                        lstQ = [Q(profile=profile)]
                        lstQ.append(Q(**{"{}".format(field_b): obj.id}))
                        obj_basket = cls.objects.filter(*lstQ).first()
                        if obj_basket is None:
                            # Create a dictionary with the required stuff
                            data_dict = dict(profile=profile)
                            data_dict[field_b] = obj
                            # Add it to the basket
                            cls.objects.create(**data_dict)
                    # Re-calculate the size of the basket
                    basketsize = cls.objects.filter(profile=profile).count()

                    # Adapt the profile's basketsize
                    setattr(profile, field_p, basketsize)
                    profile.save()

                    data['basketsize'] = basketsize

                    # Remove the selection
                    qs.delete()

                    # Indicate that the JS also needs to do some clearing
                    data['action'] = "update_basket"

            elif selitemaction == "add_dct":
                # A research set needs to have been selected
                if not rsetoneid is None:
                    # Get to the research set
                    rset = ResearchSet.objects.filter(id=rsetoneid).first()
                    if not rset is None:
                        # Make a list of items that are to be added to the DCT
                        if selitemtype == "svdi":
                            # Treat special case: 'svdi' = SavedItems from the PRE
                            qs = SelectItem.objects.filter(profile=profile, selitemtype=selitemtype)

                            # List to capture of all id's of SelItem that are used
                            lst_selitem = []

                            # Retrieve each SavedItem and interpret it
                            for selitem in qs:
                                saveditem = selitem.saveditem
                                if not saveditem is None:
                                    selitemtype = saveditem.sitemtype

                                    if selitemtype in oSelDct:
                                        # Figure out which selection object to use
                                        selParams = oSelDct[selitemtype]
                                        setlisttype = selParams['setlisttype']
                                        field_s = selParams['field_s']

                                        # Add what the SavedItem points to the chosen research set
                                        item = getattr(saveditem,field_s)
                                        rset.add_list(item, setlisttype)

                                        # Indicate that this can be 'unselected'
                                        lst_selitem.append(selitem.id)

                            # make sure to add a link to the research set here
                            data['researchset'] = reverse("researchset_details", kwargs={'pk': rsetoneid})

                            # Remove the selection
                            if len(lst_selitem) > 0:
                                SelectItem.objects.filter(id__in=lst_selitem).delete()

                            # Indicate that the JS also needs to do some clearing
                            data['action'] = "update_dct"

                        # Double check: this functionality only exists for M, HC, PD
                        elif selitemtype in oSelDct:
                            # Add all selected items to the DCT
                            qs = SelectItem.objects.filter(profile=profile, selitemtype=selitemtype)

                            # Figure out which selection object to use
                            selParams = oSelDct[selitemtype]
                            setlisttype = selParams['setlisttype']
                            field_s = selParams['field_s']

                            # Walk all the selected items
                            for obj in qs:
                                # Add this item to the chosen research set
                                item = getattr(obj,field_s)
                                rset.add_list(item, setlisttype)
                            # make sure to add a link to the research set here
                            data['researchset'] = reverse("researchset_details", kwargs={'pk': rsetoneid})

                            # Remove the selection
                            qs.delete()

                            # Indicate that the JS also needs to do some clearing
                            data['action'] = "update_dct"

            

            # Has something happened?
            if 'action' in data:
                # Okay, then re-calculate the amount of selected items
                data['selitemcount'] = SelectItem.get_selectcount(profile, selitemtype)

        except:
            msg = oErr.get_error_message()
            oErr.DoError("SelectItemApply")
            data['status'] = "error"

        context['data'] = data
        return context



# ================== Views for the SaveGroup stuff =================


class SaveGroupListView(BasicList):
    """Listview of SaveGroup"""

    model = SaveGroup
    listform = SaveGroupForm
    bUseFilter = True
    prefix = "sgrp"
    plural_name = "SaveGroups"
    new_button = True
    use_team_group = True
    order_cols = ['name', 'saved', '']
    order_default = order_cols
    order_heads = [
        {'name': 'Name',        'order': 'o=1','type': 'str', 'field': 'name',                      'linkdetails': True, 'main': True},
        {'name': 'Date',        'order': 'o=2','type': 'str', 'custom': 'date', 'align': 'right',   'linkdetails': True},
        {'name': 'Saved items', 'order': '',   'type': 'int', 'custom': 'count', 'align': 'right'},
                ]
    filters = [ 
        {"name": "Name",       "id": "filter_name",      "enabled": False},
        ]
    searches = [
        {'section': '', 'filterlist': [
            {'filter': 'name',  'dbfield': 'name',      'keyS': 'name'},
            ]},
        {'section': 'other', 'filterlist': [
            {'filter': 'scope',     'dbfield': 'scope',  'keyS': 'scope'}
            ]}
         ]

    def get_field_value(self, instance, custom):
        sBack = ""
        sTitle = ""

        if custom == "date":
            sBack = instance.saved.strftime("%d/%b/%Y %H:%M")
        elif custom == "owner":
            sBack = instance.profile.user.username
        elif custom == "count":
            iCount = instance.group_saveditems.count()
            sBack = "{}".format(iCount)

        return sBack, sTitle

    def get_own_list(self):
        # Get the user
        username = self.request.user.username
        user = User.objects.filter(username=username).first()
        # Get to the profile of this user
        qs = Profile.objects.filter(user=user)
        return qs

    def adapt_search(self, fields):
        lstExclude=None
        qAlternative = None

        # Show private datasets as well as those with scope "team", provided the person is in the team
        ownlist = self.get_own_list()
        fields['scope'] = Q(profile__in=ownlist)  

        # Return the correct response
        return fields, lstExclude, qAlternative


class SaveGroupEdit(BasicDetails):
    model = SaveGroup
    mForm = SaveGroupForm
    prefix = 'sgrp'
    prefix_type = "simple"
    title = "SaveGroup"
    use_team_group = True
    listview = None
    listviewtitle = "MyPassim"
    mainitems = []

    def custom_init(self, instance):
        # Set the listview target
        self.listview = reverse("mypassim_details")
        # Make sure upon deletion we also return to the same listview target

        return None

    def add_to_context(self, context, instance):
        """Add to the existing context"""

        # Define the main items to show and edit
        context['mainitems'] = [
            {'type': 'line',  'label': "Name:",         'value': instance.name,              'field_key': 'name'  },
            {'type': 'line',  'label': "Size:",         'value': instance.get_size_markdown()   },
            {'type': 'plain', 'label': "Created:",      'value': instance.get_created()         },
            {'type': 'plain', 'label': "Saved:",        'value': instance.get_saved()           },
            ]

        # Signal that we do have select2
        context['has_select2'] = True

        # Determine what the permission level is of this collection for the current user
        # (1) Is this user a different one than the one who created the collection?
        profile_owner = instance.profile
        profile_user = Profile.get_user_profile(self.request.user.username)
        # (2) Set default permission
        permission = "read"
        if profile_owner.id == profile_user.id:
            # (3) Any creator of the SaveGroup may write it
            permission = "write"

        context['permission'] = permission

        context['afterdelurl'] = self.listview

        # Return the context we have made
        return context


class SaveGroupDetails(SaveGroupEdit):
    """The HTML variant of [SaveGroupEdit]"""

    rtype = "html"

    def before_save(self, form, instance):
        bStatus = True
        msg = ""
        # Do we already have an instance?
        if instance == None or instance.id == None:
            # See if we have the profile id
            profile = Profile.get_user_profile(self.request.user.username)
            form.instance.profile = profile

        # Do we have cleaned data?
        if hasattr(form, "cleaned_data"):
            cleaned = form.cleaned_data

        # Return as usual
        return bStatus, msg


class SaveGroupApply(BasicPart):
    """Possibly add a new SaveGroup for this user"""

    MainModel = Profile

    def add_to_context(self, context):

        oErr = ErrHandle()
        data = dict(status="ok")
        bIsNewGroup = False
        sHtml = ""
       
        try:
            # Check validity and permissions
            if not self.userpermissions("w"):
                # Don't do anything
                return context

            # We already know who we are
            profile = self.obj

            # Retrieve necessary parameters
            sgroupadd = self.qd.get("sgrp-sgroupadd")
            sgroupaction = self.qd.get("sgroupaction")

            if sgroupaction == "add":
                # We are going to add a SaveGroup
                lstQ = []
                lstQ.append(Q(profile=profile))
                lstQ.append(Q(name__iexact=sgroupadd))
                obj = SaveGroup.objects.filter(*lstQ).first()
                # OLD and obsolete: obj = SavedItem.objects.filter(profile=profile, sitemtype=sitemtype).first()
                if obj is None:
                    obj = SaveGroup.objects.create(
                        profile=profile, name=sgroupadd)
                    obj.save()
                    bIsNewGroup = True
                data['action'] = "added"

                # Calculate what the savegroup HTML row looks like
                if bIsNewGroup:
                    context = dict(groupid=obj.id, groupname=sgroupadd)
                    sHtml = render_to_string("dct/sgroup_new.html", context, self.request)
                data['sgroupnew'] = sHtml

            ## Possibly adapt the ordering of the saved items for this user
            #if 'action' in data:
            #    # Something has happened
            #    SavedItem.update_order(profile)
        except:
            msg = oErr.get_error_message()
            oErr.DoError("SaveGroupApply")
            data['status'] = "error"

        context['data'] = data
        return context



# =================== Model views for the DCT ========


class ResearchSetListView(BasicList):
    """Listview of ResearchSet"""

    model = ResearchSet
    listform = ResearchSetForm
    has_select2 = True
    bUseFilter = True
    prefix = "rset"
    plural_name = "DCT tool page"
    new_button = True
    use_team_group = True
    order_cols = ['name', 'scope', 'profile__user__username', 'saved', '']
    order_default = order_cols
    order_heads = [
        {'name': 'Name',    'order': 'o=1','type': 'str', 'field': 'name',                      'linkdetails': True, 'main': True},
        {'name': 'Scope',   'order': 'o=2', 'type': 'str', 'custom': 'scope',                   'linkdetails': True},
        {'name': 'Owner',   'order': 'o=3', 'type': 'str', 'custom': 'owner',                   'linkdetails': True},
        {'name': 'Date',    'order': 'o=4','type': 'str', 'custom': 'date', 'align': 'right',   'linkdetails': True},
        {'name': 'DCT',     'order': 'o=5','type': 'str', 'custom': 'dct', 'align': 'right'},
                ]
    filters = [ 
        {"name": "Name",       "id": "filter_name",      "enabled": False},
        {"name": "Owner",      "id": "filter_owner",     "enabled": False} 
        ]
    searches = [
        {'section': '', 'filterlist': [
            {'filter': 'name',  'dbfield': 'name',      'keyS': 'name'},
            {'filter': 'owner', 'fkfield': 'profile',   'keyList': 'ownlist', 'infield': 'id' },
            ]},
        {'section': 'other', 'filterlist': [
            {'filter': 'scope',     'dbfield': 'scope',  'keyS': 'scope'}]}
         ]

    def initializations(self):
        # Some things are needed for initialization
        return None

    def get_own_list(self):
        # Get the user
        username = self.request.user.username
        user = User.objects.filter(username=username).first()
        # Get to the profile of this user
        qs = Profile.objects.filter(user=user)
        return qs

    def get_field_value(self, instance, custom):
        sBack = ""
        sTitle = ""

        if custom == "date":
            sBack = instance.saved.strftime("%d/%b/%Y %H:%M")
        elif custom == "dct":
            html = []
            # Find the first DCT for this research set
            dct = SetDef.objects.filter(researchset=instance).first()
            if dct == None:
                sBack = "-"
            else:
                url = reverse('setdef_details', kwargs={'pk': dct.id})
                html.append("<a href='{}' title='Show the default DCT for this research set'><span class='glyphicon glyphicon-open' style='color: darkblue;'></span></a>".format(url))
                sBack = "\n".join(html)
        elif custom == "scope":
            sBack = instance.get_scope_display()
        elif custom == "owner":
            sBack = instance.profile.user.username

        return sBack, sTitle

    def add_to_context(self, context, initial):

        return context

    def adapt_search(self, fields):
        lstExclude=None
        qAlternative = None

        # Show private datasets as well as those with scope "team", provided the person is in the team
        ownlist = self.get_own_list()
        if user_is_ingroup(self.request, app_editor):
            fields['scope'] = ( ( Q(scope="priv") & Q(profile__in=ownlist)  ) | Q(scope="team") | Q(scope="publ") )
        else:
            fields['scope'] = ( ( Q(scope="priv") & Q(profile__in=ownlist)  ) | Q(scope="publ") )

        return fields, lstExclude, qAlternative


class ResearchSetEdit(BasicDetails):
    model = ResearchSet
    mForm = ResearchSetForm
    prefix = 'rset'
    prefix_type = "simple"
    title = "ResearchSet"
    use_team_group = True
    mainitems = []

    def add_to_context(self, context, instance):
        """Add to the existing context"""

        # Define the main items to show and edit
        context['mainitems'] = [
            {'type': 'line',  'label': "Name:",         'value': instance.name,              'field_key': 'name'  },
            {'type': 'safe',  'label': "Notes:",        'value': instance.get_notes_html(),  'field_key': 'notes' },
            {'type': 'plain', 'label': "Scope:",        'value': instance.get_scope_display, 'field_key': 'scope'},
            {'type': 'plain', 'label': "Owner:",        'value': instance.profile.user.username },
            {'type': 'line',  'label': "Size:",         'value': instance.get_size_markdown()   },
            {'type': 'plain', 'label': "Created:",      'value': instance.get_created()         },
            {'type': 'plain', 'label': "Saved:",        'value': instance.get_saved()           },
            ]

        # Only if the user has permission
        if context['is_app_editor']:
            # Create the html to add an item to the researchset
            add_html = render_to_string("dct/setlist_add.html", context, self.request)
            context['mainitems'].append( {'type': 'line',  'label': "Add:",        'value': add_html})

            # Create the HTML to add a new DCT derived from this researchset
            dct_html = render_to_string("dct/dct_create.html", context, self.request)
            context['mainitems'].append({'type': 'line', 'label': "DCT:", 'value': dct_html})


        # Signal that we do have select2
        context['has_select2'] = True

        # Determine what the permission level is of this collection for the current user
        # (1) Is this user a different one than the one who created the collection?
        profile_owner = instance.profile
        profile_user = Profile.get_user_profile(self.request.user.username)
        # (2) Set default permission
        permission = ""
        if profile_owner.id == profile_user.id:
            # (3) Any creator of the collection may write it
            permission = "write"
        else:
            # (4) permission for different users
            if context['is_app_editor']:
                # (5) what if the user is an app_editor?
                if instance.scope == "publ":
                    # Editors may read/write collections with 'public' scope
                    permission = "write"
                elif instance.scope == "team":
                    # Editors may read collections with 'team' scope
                    permission = "read"
            else:
                # (5) any other users
                if instance.scope == "publ":
                    # All users may read collections with 'public' scope
                    permission = "read"

        context['permission'] = permission

        # Return the context we have made
        return context

    def check_hlist(self, instance):
        """Check if a hlist parameter is given, and hlist saving is called for"""

        oErr = ErrHandle()
        bChanges = False
        bDebug = True

        try:
            arg_hlist = "setlists-hlist"
            arg_savenew = "setlists-savenew"
            if arg_hlist in self.qd and arg_savenew in self.qd:
                # Interpret the list of information that we receive
                hlist = json.loads(self.qd[arg_hlist])
                # Interpret the savenew parameter
                savenew = self.qd[arg_savenew]

                # Make sure we are not saving
                self.do_not_save = True
                # But that we do a new redirect
                self.newRedirect = True

                # Change the redirect URL
                if self.redirectpage == "":
                    self.redirectpage = reverse('researchset_details', kwargs={'pk': instance.id})

                # What we have is the ordered list of Manuscript id's that are part of this collection
                with transaction.atomic():
                    # Make sure the orders are correct
                    for idx, item_id in enumerate(hlist):
                        order = idx + 1
                        lstQ = [Q(researchset=instance)]
                        lstQ.append(Q(**{"id": item_id}))
                        obj = SetList.objects.filter(*lstQ).first()
                        if obj != None:
                            if obj.order != order:
                                obj.order = order
                                obj.save()
                                bChanges = True
                # See if any need to be removed
                existing_item_id = [str(x.id) for x in SetList.objects.filter(researchset=instance)]
                delete_id = []
                for item_id in existing_item_id:
                    if not item_id in hlist:
                        delete_id.append(item_id)
                if len(delete_id)>0:
                    lstQ = [Q(researchset=instance)]
                    lstQ.append(Q(**{"id__in": delete_id}))
                    SetList.objects.filter(*lstQ).delete()
                    bChanges = True

                if bChanges:
                    # (6) Re-calculate the set of setlists
                    force = True if bDebug else False
                    instance.update_ssglists(force)

            return True
        except:
            msg = oErr.get_error_message()
            oErr.DoError("ResearchSetEdit/check_hlist")
            return False
    

class ResearchSetDetails(ResearchSetEdit):
    """The HTML variant of [ResearchSetEdit]"""

    rtype = "html"
    listviewtitle = "DCT tool page"
    
    def custom_init(self, instance):
        if instance != None:
            # Check for hlist saving
            self.check_hlist(instance)
        return None

    def before_save(self, form, instance):
        bStatus = True
        msg = ""
        # Do we already have an instance?
        if instance == None or instance.id == None:
            # See if we have the profile id
            profile = Profile.get_user_profile(self.request.user.username)
            form.instance.profile = profile
        # Do we have cleaned data?
        if hasattr(form, "cleaned_data"):
            cleaned = form.cleaned_data
            # See what is in there...
            manu = cleaned.get("manulist")
            hist = cleaned.get("histlist")
            ssgd = cleaned.get("ssgdlist")
            ssgdname = cleaned.get("ssgdname")
            dctname = cleaned.get("dctname")

            if manu != None or hist != None or ssgd != None:
                 # (1) Preliminary order
                order = 1
                obj = instance.researchset_setlists.all().order_by("-order").first()
                if obj != None:
                    order = obj.order + 1
                # Go for manu
                if manu != None:
                    # We have a manuscript being added
                    setlisttype = "manu"
                    # Check its presence
                    setlist = SetList.objects.filter(researchset=instance, manuscript=manu).first()
                    if setlist == None or len(setlist.contents) < 3:
                        if setlist == None:
                            # (3) Create the new list
                            setlist = SetList.objects.create(
                                researchset=instance, order=order, 
                                setlisttype=setlisttype, manuscript=manu)
                        # Make sure the contents is re-calculated
                        setlist.calculate_contents()
                elif hist!= None:
                    # This is a historical collection
                    setlisttype = "hist"
                    # Check its presence
                    setlist = SetList.objects.filter(researchset=instance, collection=hist).first()
                    if setlist == None or len(setlist.contents) < 3:
                        if setlist == None:
                            # (3) Create the new list
                            setlist = SetList.objects.create(
                                researchset=instance, order=order, 
                                setlisttype=setlisttype, collection=hist)
                        # Make sure the contents is re-calculated
                        setlist.calculate_contents()
                elif ssgd != None:
                    # This is a personal or public dataset of SSGs
                    setlisttype = "ssgd"
                    # Check its presence
                    setlist = SetList.objects.filter(researchset=instance, collection=ssgd).first()
                    if setlist == None or len(setlist.contents) < 3:
                        if setlist == None:
                            # (3) Create the new list
                            setlist = SetList.objects.create(
                                researchset=instance, order=order, 
                                setlisttype=setlisttype, collection=ssgd)
                            # Possibly add the name
                            if ssgdname != None and ssgdname != "":
                                setlist.name = ssgdname
                                setlist.save()
                        # Make sure the contents is re-calculated
                        setlist.calculate_contents()
                # (4) Re-calculate the order
                instance.adapt_order()
                # (6) Re-calculate the set of setlists
                instance.update_ssglists()
            elif not dctname is None and dctname != "":
                # Save as a new item and open that one
                notes = "Default DCT created by request of the user"
                setdef_new = SetDef.objects.create(
                    researchset=instance,
                    name=dctname,
                    notes=notes)
                # (6) Re-calculate the set of setlists
                force = False
                instance.update_ssglists(force)

                # We do a new redirect
                self.newRedirect = True
                # Change the redirect URL
                if self.redirectpage == "":
                    self.redirectpage = reverse('researchset_details', kwargs={'pk': instance.id})

        # Return as usual
        return bStatus, msg

    def add_to_context(self, context, instance):
        # Perform the standard initializations:
        context = super(ResearchSetDetails, self).add_to_context(context, instance)

        def add_one_item(rel_item, value, resizable=False, title=None, align=None, link=None, main=None, draggable=None):
            oAdd = dict(value=value)
            if resizable: oAdd['initial'] = 'small'
            if title != None: oAdd['title'] = title
            if align != None: oAdd['align'] = align
            if link != None: oAdd['link'] = link
            if main != None: oAdd['main'] = main
            if draggable != None: oAdd['draggable'] = draggable
            rel_item.append(oAdd)
            return True

        def check_order(qs):
            with transaction.atomic():
                for idx, obj in enumerate(qs):
                    if obj.order < 0:
                        obj.order = idx + 1
                        obj.save()

        username = self.request.user.username
        team_group = app_editor

        # Authorization: only app-editors may edit!
        bMayEdit = user_is_ingroup(self.request, team_group)
            
        # All PDs: show the content
        related_objects = []
        lstQ = []
        rel_list =[]
        resizable = True
        index = 1
        sort_start = ""
        sort_start_int = ""
        sort_end = ""
        if bMayEdit:
            sort_start = '<span class="sortable"><span class="fa fa-sort sortshow"></span>&nbsp;'
            sort_start_int = '<span class="sortable integer"><span class="fa fa-sort sortshow"></span>&nbsp;'
            sort_end = '</span>'

        oErr = ErrHandle()

        try:

            # [1] =============================================================
            # Get all 'SetList' objects that are part of this 'ResearchSet'
            setlists = dict(title="Lists within this research set", prefix="setlists")  
            if resizable: setlists['gridclass'] = "resizable dragdrop"
            setlists['savebuttons'] = bMayEdit
            setlists['saveasbutton'] = False

            qs_setlist = instance.researchset_setlists.all().order_by(
                    'order', 'setlisttype')
            # These elements have an 'order' attribute, so they  may be corrected
            check_order(qs_setlist)

            # Walk these setlists
            for obj in qs_setlist:
                # The [obj] is of type `SetList`

                rel_item = []

                # The [item] depends on the setlisttype
                item = None
                if obj.setlisttype == "manu":
                    item = obj.manuscript
                else:
                    item = obj.collection

                # SetList: Order within the ResearchSet
                add_one_item(rel_item, obj.order, False, align="right", draggable=True)

                # SetList: Type
                add_one_item(rel_item, obj.get_setlisttype_display(), False)

                # SetList: title of the manu/coll
                kwargs = None
                if obj.name != None and obj.name != "":
                    kwargs = dict(name=obj.name)
                add_one_item(rel_item, self.get_field_value(obj.setlisttype, item, "title", kwargs=kwargs), False, main=True)

                # SetList: Size (number of SSG in this manu/coll)
                add_one_item(rel_item, self.get_field_value(obj.setlisttype, item, "size"), False, align="right")

                if bMayEdit:
                    # Actions that can be performed on this item
                    # Was (see issue #393): add_one_item(rel_item, self.get_actions())
                    add_one_item(rel_item, self.get_field_value("setlist", obj, "buttons"), False)

                # Add this line to the list
                rel_list.append(dict(id=obj.id, cols=rel_item))
            
            setlists['rel_list'] = rel_list
            setlists['columns'] = [
                '{}<span title="Default order">Order<span>{}'.format(sort_start_int, sort_end),
                '{}<span title="Type of setlist">Type of this setlist</span>{}'.format(sort_start, sort_end), 
                '{}<span title="The title of the manuscript/dataset/collection">Title</span>{}'.format(sort_start, sort_end), 
                '{}<span title="Number of SSGs part of this setlist">Size</span>{}'.format(sort_start_int, sort_end)
                ]
            if bMayEdit:
                setlists['columns'].append("")
            related_objects.append(setlists)

            # [2] =============================================================
            # Get all the 'DCT' parameter definitions
            setdefs = dict(title="DCT definitions", prefix="setdefs")
            if resizable: setdefs['gridclass'] = "resizable"
            setdefs['savebuttons'] = False
            setdefs['saveasbutton'] = False
            qs_setdefs = instance.researchset_setdefs.all().order_by(
                'order')

            # Walk these setdefs
            rel_list = []
            order = 1
            for obj in qs_setdefs:
                rel_item = []

                # SetDef: Order within the ResearchSet
                add_one_item(rel_item, order, False, align="right")
                order += 1

                # SetDef: Name
                add_one_item(rel_item, self.get_field_value("setdef", obj, "name"), obj.name, False)

                # SetDef: Notes
                add_one_item(rel_item, obj.notes, False, main=True)

                # SetDef: Date when last saved
                add_one_item(rel_item, obj.get_saved(), False)

                # Button to launch this SetDef as a DCT
                add_one_item(rel_item, self.get_field_value("setdef", obj, "buttons"), False)

                # Add this line to the list
                rel_list.append(dict(id=obj.id, cols=rel_item))
            
            setdefs['rel_list'] = rel_list
            setdefs['columns'] = [                
                '{}<span title="Order">Order<span>{}'.format(sort_start_int, sort_end),
                '{}<span title="Name of this DCT">Name</span>{}'.format(sort_start, sort_end), 
                '{}<span title="Notes on this DCT">Notes</span>{}'.format(sort_start, sort_end), 
                '{}<span title="Date when last changed">Changed</span>{}'.format(sort_start, sort_end), 
                '{}<span title="Buttons">DCT</span>{}'.format(sort_start, sort_end)
                ]
            related_objects.append(setdefs)

            # [3] =============================================================
            # Make sure the resulting list ends up in the viewable part
            context['related_objects'] = related_objects
        except:
            msg = oErr.get_error_message()
            oErr.DoError("ResearchSetDetails/add_to_context")

        # REturn the total context
        return context

    def get_actions(self):
        html = []
        buttons = ['remove']    # This contains all the button names that need to be added

        # Start the whole div
        html.append("<div class='blinded'>")
        
        # Add components
        if 'up' in buttons: 
            html.append("<a class='related-up' ><span class='glyphicon glyphicon-arrow-up'></span></a>")
        if 'down' in buttons: 
            html.append("<a class='related-down'><span class='glyphicon glyphicon-arrow-down'></span></a>")
        if 'remove' in buttons: 
            html.append("<a class='related-remove'><span class='glyphicon glyphicon-remove'></span></a>")

        # Finish up the div
        html.append("&nbsp;</div>")

        # COmbine the list into a string
        sHtml = "\n".join(html)
        # Return out HTML string
        return sHtml

    def get_field_value(self, type, instance, custom, kwargs=None):
        sBack = ""
        collection_types = ['hist', 'ssgd' ]

        if not instance is None:
            if type == "manu":
                if custom == "title":
                    url = reverse("manuscript_details", kwargs={'pk': instance.id})
                    sBack = "<span class='clickable'><a href='{}' class='nostyle'>{}, {}, <span class='signature'>{}</span></a><span>".format(
                        url, instance.get_city(), instance.get_library(), instance.idno)
                elif custom == "size":
                    # Get the number of SSGs related to items in this manuscript
                    count = EqualGold.objects.filter(sermondescr_super__sermon__msitem__manu=instance).order_by('id').distinct().count()
                    sBack = "{}".format(count)
            elif type in collection_types:
                if custom == "title":
                    sTitle = "none"
                    if instance is None:
                        sBack = sTitle
                    else:
                        if type == "hist":
                            url = reverse("collhist_details", kwargs={'pk': instance.id})
                        else:
                            if instance.scope == "publ":
                                url = reverse("collpubl_details", kwargs={'pk': instance.id})
                            else:
                                url = reverse("collpriv_details", kwargs={'pk': instance.id})
                        if kwargs != None and 'name' in kwargs:
                            title = "{} (dataset name: {})".format( kwargs['name'], instance.name)
                        else:
                            title = instance.name
                        sBack = "<span class='clickable'><a href='{}' class='nostyle'>{}</a></span>".format(url, title)
                elif custom == "size":
                    # Get the number of SSGs related to items in this collection
                    count = "-1" if instance is None else instance.super_col.count()
                    sBack = "{}".format(count)
            elif type == "setdef":
                if custom == "buttons":
                    # Create the launch button
                    url = reverse("setdef_details", kwargs={'pk': instance.id})
                    sBack = "<a href='{}' class='btn btn-xs jumbo-1'>Show</a>".format(url)
                elif custom == "name":
                    url = reverse("setdef_details", kwargs={'pk': instance.id})
                    sBack = "<span class='clickable'><a href='{}' class='nostyle'>{}</a></span>".format(url, instance.name)
            elif type == "setlist":
                if custom == "buttons":
                    # Create the remove button
                    sBack = "<a class='btn btn-xs jumbo-2'><span class='related-remove'>Delete</span></a>"

        return sBack


class SetDefListView(BasicList):
    """Listview of ResearchSet"""

    model = SetDef
    listform = SetDefForm
    has_select2 = True
    bUseFilter = True
    prefix = "sdef"
    plural_name = "DCT definitions"
    new_button = True
    use_team_group = True
    order_cols = ['name', 'researchset__name', 'saved']
    order_default = order_cols
    order_heads = [
        {'name': 'Name',           'order': 'o=1','type': 'str', 'field': 'name', 'linkdetails': True, 'main': True},
        {'name': 'Research set',   'order': 'o=2','type': 'str', 'custom': 'rset'                                },
        {'name': 'Date',           'order': 'o=3','type': 'str', 'custom': 'date', 'align': 'right', 'linkdetails': True},
        {'name': 'DCT',            'order': 'o=4','type': 'str', 'custom': 'dct',  'align': 'right'},
                ]
    filters = [ {"name": "Name",       "id": "filter_name",      "enabled": False} ]
    searches = [
        {'section': '', 'filterlist': [
            {'filter': 'name', 'dbfield': 'name', 'keyS': 'name'}
            ]},
        {'section': 'other', 'filterlist': [
            {'filter': 'profile',   'fkfield': 'researchset__profile',  'keyFk': 'id', 'infield': 'id'},
            {'filter': 'scope',     'dbfield': 'scope',                 'keyS': 'scope'}
            ]},
         ]

    def initializations(self):
        # Some things are needed for initialization

        # No return
        return None

    def get_own_list(self):
        # Get the user
        username = self.request.user.username
        user = User.objects.filter(username=username).first()
        # Get to the profile of this user
        qs = Profile.objects.filter(user=user)
        return qs

    def adapt_search(self, fields):
        lstExclude=None
        qAlternative = None
        x = fields
        profile = Profile.get_user_profile( self.request.user.username)
        fields['profile'] = profile.id
        return fields, lstExclude, qAlternative

    def get_field_value(self, instance, custom):
        sBack = ""
        sTitle = ""

        if custom == "date":
            sBack = instance.saved.strftime("%d/%b/%Y %H:%M")
        elif custom == "rset":
            sBack = instance.researchset.name
        elif custom == "dct":
            html = []
            # Find the first DCT for this research set
            url = reverse('setdef_details', kwargs={'pk': instance.id})
            html.append("<a href='{}' title='Show this DCT'><span class='glyphicon glyphicon-open' style='color: darkblue;'></span></a>".format(url))
            sBack = "\n".join(html)

        return sBack, sTitle
    
    def adapt_search(self, fields):
        lstExclude=None
        qAlternative = None

        # Show private datasets as well as those with scope "team", provided the person is in the team
        ownlist = self.get_own_list()
        if user_is_ingroup(self.request, app_editor):
            fields['scope'] = ( ( Q(researchset__scope="priv") & Q(researchset__profile__in=ownlist)  ) | Q(researchset__scope="team") )
        else:
            fields['scope'] = ( Q(researchset__scope="priv") & Q(researchset__profile__in=ownlist)  )

        return fields, lstExclude, qAlternative


class SetDefEdit(BasicDetails):
    model = SetDef
    mForm = SetDefForm
    prefix = 'sdef'
    prefix_type = "simple"
    title = "DCT definition"
    use_team_group = True
    mainitems = []

    def add_to_context(self, context, instance):
        """Add to the existing context"""

        # Define the main items to show and edit
        context['mainitems'] = [
            {'type': 'line',  'label': "Name:",         'value': instance.name,  'field_key': 'name'  },
            {'type': 'safe',  'label': "Notes:",        'value': instance.get_notes_html(), 'field_key': 'notes' },
            {'type': 'plain', 'label': "Owner:",        'value': instance.researchset.profile.user.username },
            {'type': 'plain', 'label': "Created:",      'value': instance.get_created()         },
            {'type': 'plain', 'label': "Saved:",        'value': instance.get_saved()           },
            ]
        sHiddenWarning = instance.hidden_warning()
        if len(sHiddenWarning) > 0:
            context['mainitems'].append(
                {'type': 'safe',  'label': "", 'value': sHiddenWarning },
            )

        # Signal that we do have select2
        context['has_select2'] = True

        # Add a button back to the research set I belong to
        rset = instance.researchset
        if rset  != None:
            topleftlist = []
            rset_url = reverse('researchset_details', kwargs={'pk': rset.id})
            buttonspecs = {'label': "<span class='glyphicon glyphicon-wrench'></span>", 
                    'title': "Back to my research set: '{}'".format(rset.name), 
                    'url': rset_url}
            topleftlist.append(buttonspecs)
            context['topleftbuttons'] = topleftlist
            # ALso make the rset url availabl
            context['rset_url'] = rset_url

        # Determine what the permission level is of this collection for the current user
        # (1) Is this user a different one than the one who created the collection?
        profile_owner = instance.researchset.profile
        profile_user = Profile.get_user_profile(self.request.user.username)
        # (2) Set default permission
        permission = ""
        if profile_owner.id == profile_user.id:
            # (3) Any creator of the collection may write it
            permission = "write"
        else:
            # (4) permission for different users
            if context['is_app_editor']:
                # (5) what if the user is an app_editor?
                if instance.researchset.scope == "publ":
                    # Editors may read/write collections with 'public' scope
                    permission = "write"
                elif instance.researchset.scope == "team":
                    # Editors may read collections with 'team' scope
                    permission = "read"
            else:
                # (5) any other users
                if instance.researchset.scope == "publ":
                    # All users may read collections with 'public' scope
                    permission = "read"

        context['permission'] = permission

        # Return the context we have made
        return context


class SetDefDetails(SetDefEdit):
    """The HTML variant of [ResearchSetEdit]"""

    rtype = "html"
    listviewtitle = "All my DCTs"

    def custom_init(self, instance):
        oErr = ErrHandle()
        try:
            # Check if we get any addtype and addid values
            addtype = self.qd.get("addtype", None)
            addid = self.qd.get("addid", None)
            if addtype != None and addid != None:
                # We have something to add
                researchset = instance.researchset
                order = researchset.researchset_setlists.count() + 1
                setlisttype = ""
                setlist = None
                # Note: are we creating or adding an existing one?
                mode = ""
                if addtype == "manu":
                    # Add a manuscript
                    setlisttype = "manu"
                    # Check existence
                    obj = SetList.objects.filter(
                        researchset=researchset, setlisttype=setlisttype, manuscript_id=addid).first()
                    if obj == None:
                        # Create this setlist
                        setlist = SetList.objects.create(
                            researchset=researchset, order = order,
                            setlisttype=setlisttype, manuscript_id=addid)
                        mode = "create"
                    else:
                        # Pick up its correct order
                        order = obj.order
                        # Adapt mode
                        mode = "exists"
                elif addtype == "coll":
                    # Add a collection
                    setlisttype = "hist"
                    # Check existence
                    obj = SetList.objects.filter(
                        researchset=researchset, setlisttype=setlisttype, collection_id=addid).first()
                    if obj == None:
                        # Create this setlist
                        setlist = SetList.objects.create(
                            researchset=researchset, order = order,
                            setlisttype=setlisttype, collection_id=addid)
                        mode = "create"
                    else:
                        # Pick up its correct order
                        order = obj.order
                        # Adapt mode
                        mode = "exists"
                elif addtype == "ssgd":
                    # Add a collection
                    setlisttype = "ssgd"
                    pass

                if mode == "create":
                    # Make sur ssglists are re-calculated for this researchset
                    researchset.update_ssglists(True)
                    # Walk all SetDefs in this research set
                    with transaction.atomic():
                        for sdef in researchset.researchset_setdefs.all():
                            bNeedSaving = False
                            # Is this the setdef I am in?
                            if sdef.id == instance.id:
                                # Yes, this is my setdef: add it to the include list
                                contents = json.loads(sdef.contents)
                                lst_order = contents.get("lst_order", None)
                                if lst_order != None and not order in lst_order:
                                    lst_order.append(order)
                                    sdef.contents = json.dumps(contents)
                                    bNeedSaving = True
                            else:
                                # No, this is not my setdef: switch it off here
                                contents = json.loads(sdef.contents)
                                lst_exclude = contents.get("lst_exclude", [])
                                if not order in lst_exclude:
                                    lst_exclude.append(order)
                                    contents['lst_exclude'] = lst_exclude
                                    sdef.contents = json.dumps(contents)
                                    bNeedSaving = True
                            # IN all cases: save results
                            if bNeedSaving: sdef.save()
                elif mode == "exists":
                    # This particular list already exists.
                    # It needs to be switched 'on' in the current Sdef
                    contents = json.loads(instance.contents)
                    # If needed, add in lst_order
                    lst_order = contents.get("lst_order", None)
                    if lst_order != None and not order in lst_order:
                        lst_order.append(order)
                        contents['lst_order'] = lst_order
                    # If needed, take it out of exclude
                    lst_exclude = contents.get("lst_exclude", None)
                    if lst_exclude != None and order in lst_exclude:
                        lst_exclude.pop(lst_exclude.index(order))
                        contents['lst_exclude'] = lst_exclude
                    # Adapt changes
                    instance.contents = json.dumps(contents)
                    instance.save()

        except:
            msg = oErr.get_error_message()
            oErr.DoError("SetDefDetails/custom_init")
        return None

    def add_to_context(self, context, instance):
        # Perform the standard initializations:
        context = super(SetDefDetails, self).add_to_context(context, instance)

        oErr = ErrHandle()
        template_name = "dct/dct_view.html"

        try:
            username = self.request.user.username
            team_group = app_editor

            # Authorization: only app-editors may edit!
            bMayEdit = user_is_ingroup(self.request, team_group)

            # Show the DCT according to the parameters that I can find
            parameters = json.loads(instance.contents)
            if len(parameters) > 0:
                # Okay, fetch the parameters and put them into the context
                pass

            # Make sure the research set is part of the context
            context['setlist'] = [ 1, 2, 3]

            context['dctdata_url'] = reverse('setdef_data', kwargs={'pk': instance.id})
            context['dctdetails_url'] = reverse('setdef_details', kwargs={'pk': instance.id})
            context['csrf'] = '<input type="hidden" name="csrfmiddlewaretoken" value="{}" />'.format(
                get_token(self.request))
            context['mayedit'] = bMayEdit

            ## Calculate the size of the research set
            #x = instance.researchset.researchset_setlists.count()

            # Create the DCT with a template
            dct_view = render_to_string(template_name, context)

            # Add the visualization we made
            context['add_to_details'] = dct_view

            # Define navigation buttons
            self.custombuttons = [
                {"name": "dct_tools", "title": "Back to DCT tool page", "icon": "wrench", "template_name": "seeker/scount_histogram.html" }
                ]
        except:
            msg = oErr.get_error_message()
            oErr.DoError("SetDefDetails/add_to_context")

        # REturn the total context
        return context


class SetDefData(BasicPart):
    """Provide the data for the indicated SetDef element"""

    MainModel = SetDef

    def add_to_context(self, context):

        # Gather all necessary data
        data = {}

        oErr = ErrHandle()
        try:
            # issue #756: THIS SHOULD NOT BE USED - any user may work on DCTs
            ## Check validity
            #if not self.userpermissions("w"):
            #    # Don't do anything
            #    return context

            # Get the SetDef object
            setdef = self.obj

            # Find out what we are doing here
            mode = self.qd.get("save_mode", "")
            params = self.qd.get("params")
            if mode == "save":
                # Simple saving of current object
                if params != None:
                    setdef.contents = params
                    setdef.save()
                    data['targeturl'] = reverse('setdef_details', kwargs={'pk': setdef.id})
            elif mode == "savenew":
                # Save as a new item and open that one
                setdef_new = SetDef.objects.create(
                    researchset=setdef.researchset,
                    contents=params)
                data['targeturl'] = reverse('setdef_details', kwargs={'pk': setdef_new.id})

            else:
                # Get to the setdef object
                contents = setdef.get_contents()
                do_calc_pm = ('recalc' in contents['params'])

                # Set the pivot row to the default value, if it is not yet defined
                if not 'pivot_col' in contents['params']:
                    contents['params']['pivot_col'] = 0
                    do_calc_pm = True

                if do_calc_pm:
                    # We need to calculate (or re-calculate) the PM based on the whole research set
                    pivot_col = setdef.researchset.calculate_pm()
                    contents['params']['pivot_col'] = pivot_col
                    # Make sure to also save this
                    contents['params'].pop("recalc", "")
                    setdef.contents = json.dumps(contents['params'])
                    setdef.save()

                # REturn the contents
                data['contents'] = contents
            # FIll in the [data] part of the context with all necessary information
            context['data'] = data
        except:
            msg = oErr.get_error_message()
            oErr.DoError("SetDefData")
        return context


class SetDefDownload(BasicPart):
    """Downloading for DCTs"""

    MainModel = SetDef
    # template_name = "seeker/download_status.html"
    template_name = None
    action = "download"
    dtype = ""

    def custom_init(self):
        """Calculate stuff"""
        
        dt = self.qd.get('downloadtype', "")
        if dt != None and dt != '':
            self.dtype = dt

    def userpermissions(self, sType = "w"):
        """Basic check for valid user permissions"""

        bResult = False
        oErr = ErrHandle()
        try:
            # First step: authentication
            if user_is_authenticated(self.request):
                bResult = True
            # Otherwise: no permissions!
        except:
            oErr.DoError("SetDefDownload/userpermissions")
        return bResult

    def get_data(self, prefix, dtype, response=None):
        """Gather the data as CSV, including a header line and comma-separated"""

        # Initialize
        lData = []
        sData = ""
        oErr = ErrHandle()

        try:

            if dtype == "json":
                # Retrieve the actual data from self.data
                sData = self.qd.get('downloaddata', "[]")
                # Load it as object (from JSON)
                oData = json.loads(sData)
                # Save it as string, but with indentation for easy reading
                sData = json.dumps(oData, indent=2)
            elif dtype == "dct-svg":
                # Note: this does not occur - no SVG is used
                pass
            elif dtype == "dct-png":
                # Note: the Javascript routine provides the needed information
                pass
            elif dtype == "csv" or dtype == "xlsx":
                # Retrieve the actual data from self.data
                sData = self.qd.get('downloaddata', "[]")
                # Load it as object (from JSON)
                lst_rows = json.loads(sData)

                # Create CSV string writer
                output = StringIO()
                delimiter = "\t" if dtype == "csv" else ","
                csvwriter = csv.writer(output, delimiter=delimiter, quotechar='"')

                # Headers: the column names are largely determined by the first row in the JSON information
                row = lst_rows[0]
                header_fields = ['top', 'middle', 'main', 'size']
                for field in header_fields:
                    headers = []
                    # First column processing
                    if field == "top": 
                        headers.append("Gryson/Clavis")
                    else:
                        headers.append("")
                    # Processing of the remaining columns
                    for item in row[1:]:
                        oHeader = item['header']
                        if field in oHeader:
                            headers.append(oHeader[field])
                        else:
                            headers.append("")
                    # Output this header row
                    csvwriter.writerow(headers)

                # Process the remaining rows in the list of input rows
                for lst_row in lst_rows[1:]:
                    # Start an output row
                    row = []
                    # Walk through the columns
                    for idx, col in enumerate(lst_row):
                        if idx == 0:
                            # THis is the first column: get the siglist
                            siglist = ", ".join(col['siglist'])
                            row.append(siglist)
                        else:
                            # This is a different column
                            row.append(col['txt'])
                    # Output this row
                    csvwriter.writerow(row)

                # Convert to string
                sData = output.getvalue()
                output.close()
        except:
            msg = oErr.get_error_message()
            oErr.DoError("SetDefDownload/get_data")

        return sData



# =================== Model views for EXCEL IMPORT ========


class ImportSetListView(BasicList):
    """Listview of ImportSet"""

    model = ImportSet
    listform = ImportSetForm
    has_select2 = True
    bUseFilter = True
    prefix = "impset"
    sg_name = "Excel import submission"
    plural_name = "Excel import submissions"
    new_button = True
    use_team_group = True
    order_cols = ['order', 'name', 'importtype', 'status', 'profile__user__username', 'saved', 'created']
    order_default = order_cols
    order_heads = [
        {'name': 'Order',   'order': 'o=1','type': 'int', 'field': 'order',     'linkdetails': True},
        {'name': 'File',    'order': 'o=2','type': 'str', 'custom': 'filename', 'linkdetails': True, 'main': True},
        {'name': 'Type',    'order': 'o=3','type': 'str', 'custom': 'type',     'linkdetails': True},
        {'name': 'Status',  'order': 'o=4','type': 'str', 'custom': 'status',   'linkdetails': True},
        {'name': 'Owner',   'order': 'o=5','type': 'str', 'custom': 'owner',    'linkdetails': True},
        {'name': 'Saved',   'order': 'o=6','type': 'str', 'custom': 'date',     'linkdetails': True, 'align': 'right'},
        {'name': 'Created', 'order': 'o=7','type': 'str', 'custom': 'created',  'linkdetails': True, 'align': 'right'},
                ]
    filters = [ 
        {"name": "Name",    "id": "filter_name",      "enabled": False},
        {"name": "Owner",   "id": "filter_owner",     "enabled": False},
        {"name": "Type",    "id": "filter_type",      "enabled": False},
        ]
    searches = [
        {'section': '', 'filterlist': [
            {'filter': 'name',  'dbfield': 'name',      'keyS': 'fname',  
             'keyList': 'namelist', 'infield': 'name' },
            {'filter': 'owner', 'fkfield': 'profile',   'keyList': 'ownlist', 'infield': 'id' },
            {'filter': 'type',  'dbfield': 'importtype',     'keyList': 'importtypelist',
             'keyType': 'fieldchoice',  'infield': 'abbr' }
            ]},
        {'section': 'other', 'filterlist': [] }
         ]

    def initializations(self):
        # Some things are needed for initialization
        return None

    def get_field_value(self, instance, custom):
        sBack = ""
        sTitle = ""

        if custom == "date":
            # sBack = instance.saved.strftime("%d/%b/%Y %H:%M")
            sBack = instance.get_saved()
        elif custom == "created":
            # sBack = instance.created.strftime("%d/%b/%Y %H:%M")
            sBack = instance.get_created()
        elif custom == "filename":
            sBack = instance.get_name()
        elif custom == "type":
            sBack = instance.get_type()
        elif custom == "status":
            sBack = instance.get_status()
        elif custom == "owner":
            sBack = instance.profile.user.username

        return sBack, sTitle

    def adapt_search(self, fields):
        lstExclude=None
        qAlternative = None
        oErr = ErrHandle()
        try:
            pass
        except:
            msg = oErr.get_error_message()
            oErr.DoError("ImportSetListView/adapt_search")

        return fields, lstExclude, qAlternative


class ImportSetEdit(BasicDetails):
    model = ImportSet
    mForm = ImportSetForm
    prefix = 'impset'
    prefix_type = "simple"
    title = "Import submission"
    use_team_group = True
    mainitems = []

    def add_to_context(self, context, instance):
        """Add to the existing context"""

        oErr = ErrHandle()
        try:
            is_app_editor = context['is_app_editor']
            # Define the main items to show and edit
            context['mainitems'] = [
                {'type': 'line',  'label': "Excel file:",   'value': instance.get_name_html(),   'field_key': 'excel'  },
                {'type': 'safe',  'label': "Notes:",        'value': instance.get_notes_html(),  'field_key': 'notes' },
                {'type': 'plain', 'label': "Type:",         'value': instance.get_type(),        'field_key': 'importtype'},
                {'type': 'safe',  'label': "Status:",       'value': instance.get_status(True),     },
                {'type': 'plain', 'label': "Owner:",        'value': instance.get_owner()           },
                {'type': 'plain', 'label': "Projects:",     'value': instance.get_projects_html(),'field_list': 'projlist' },
                {'type': 'plain', 'label': "Created:",      'value': instance.get_created()         },
                {'type': 'plain', 'label': "Saved:",        'value': instance.get_saved()           },
                {'type': 'plain', 'label': "Report:",       'value': instance.get_report_html()     },
                {'type': 'safe',  'label': "",              'value': self.get_button(instance, is_app_editor)     },
                ]
            
            # Signal that we do have select2
            context['has_select2'] = True

            # Determine what the permission level is of this collection for the current user
            # (1) Is this user a different one than the one who created the collection?
            profile_owner = instance.profile
            profile_user = Profile.get_user_profile(self.request.user.username)
            # (2) Set default permission
            permission = ""
            if profile_owner.id == profile_user.id:
                # (3) Any creator of the ImportSet may write it
                permission = "write"
            else:
                # (4) permission for different users
                if context['is_app_moderator']:
                    # (5) what if the user is an app_moderator?
                    permission = "write"
                else:
                    # (5) any other users may only read
                    permission = "read"

            context['permission'] = permission
        except:
            msg = oErr.get_error_message()
            oErr.DoError("ImportSetEdit/add_to_context")

        # Return the context we have made
        return context

    def before_save(self, form, instance):
        bStatus = True
        msg = ""
        oErr = ErrHandle()
        try:
            # Do we have changed data?
            if hasattr(form, "changed_data"):
                changed = form.changed_data
                # Has the excel been changed?
                if "excel" in changed:
                    # The excel has changed - reset some stuff
                    form.instance.status = "chg"
                    form.instance.report = ""
        except:
            msg = oErr.get_error_message()
            oErr.DoError("ImportSetEdit/before_save")
    
        return bStatus, msg

    def after_save(self, form, instance):
        """What to do after saving the instance?"""

        def assign_default(profile):
            oErr = ErrHandle()
            try:
                # Get the default assign projects
                qs = profile.project_approver.filter(status="incl")
                # Assign those in here
                for obj in qs:
                    instance.projects.add(obj.project)
            except:
                msg = oErr.get_error_message()
                oErr.DoError("ImportSetEdit/assign_default")

        bStatus = True
        msg = ""
        oErr = ErrHandle()
        try:
            # Get my profile
            profile = self.request.user.user_profiles.first()
            # (1) Check: does this importset have projects already?
            if instance.projects.count() == 0:
                # No projects yet: assign the default projects for this user
                assign_default(profile)
            else:
                # (2) 'projects'
                projlist = form.cleaned_data['projlist']
                adapt_m2m(ImportSetProject, instance, "importset", projlist, "project")
                # But what if the number of projects reduces to zero?
                if instance.projects.count() == 0:
                    # Then we still assign the default project
                    assign_default(profile)

        except:
            msg = oErr.get_error_message()
            oErr.DoError("ImportSetEdit/after_save")

        # Return as usual
        return bStatus, msg

    def get_button(self, instance, is_app_editor):
        """Create and show the buttons that are appropriate at this stage"""

        sBack = ""
        oErr = ErrHandle()
        html = []
        try:
            if not instance is None:
                context = dict(instance=instance)
                context['importmode'] = instance.get_importmode()
                context['is_app_editor'] = is_app_editor
                sBack = render_to_string("dct/xlsimp_button.html", context, self.request)
 
        except:
            msg = oErr.get_error_message()
            oErr.DoError("ImportSetEdit/get_button")

        return sBack

    def check_hlist(self, instance):
        """Check if a hlist parameter is given, and hlist saving is called for"""

        oErr = ErrHandle()
        bChanges = False
        bDebug = True
        prefix = "super"

        try:
            arg_hlist = "{}-hlist".format(prefix)
            arg_savenew = "{}-savenew".format(prefix)
            if arg_hlist in self.qd and arg_savenew in self.qd:
                # Interpret the list of information that we receive
                hlist = json.loads(self.qd[arg_hlist])
                ## Interpret the savenew parameter
                #savenew = self.qd[arg_savenew]

                ## Make sure we are not saving
                #self.do_not_save = True
                ## But that we do a new redirect
                #self.newRedirect = True

                ## Change the redirect URL
                #if self.redirectpage == "":
                #    self.redirectpage = reverse('stemmaset_details', kwargs={'pk': instance.id})

                ## What we have is the ordered list of Manuscript id's that are part of this collection
                #with transaction.atomic():
                #    # Make sure the orders are correct
                #    for idx, item_id in enumerate(hlist):
                #        order = idx + 1
                #        lstQ = [Q(stemmaset=instance)]
                #        lstQ.append(Q(**{"id": item_id}))
                #        obj = StemmaItem.objects.filter(*lstQ).first()
                #        if obj != None:
                #            if obj.order != order:
                #                obj.order = order
                #                obj.save()
                #                bChanges = True
                ## See if any need to be removed
                #existing_item_id = [str(x.id) for x in StemmaItem.objects.filter(stemmaset=instance)]
                #delete_id = []
                #for item_id in existing_item_id:
                #    if not item_id in hlist:
                #        delete_id.append(item_id)
                #if len(delete_id)>0:
                #    lstQ = [Q(stemmaset=instance)]
                #    lstQ.append(Q(**{"id__in": delete_id}))
                #    StemmaItem.objects.filter(*lstQ).delete()
                #    bChanges = True

                #if bChanges:
                #    # (6) Re-calculate the set of setlists
                #    force = True if bDebug else False
                #    #instance.update_ssglists(force)

            return True
        except:
            msg = oErr.get_error_message()
            oErr.DoError("ImportSetEdit/check_hlist")
            return False


class ImportSetDetails(ImportSetEdit):
    """The HTML variant of [ImportSetEdit]"""

    rtype = "html"
    
    def custom_init(self, instance):
        if instance != None:
            # Check for hlist saving
            self.check_hlist(instance)
        return None

    def add_to_context(self, context, instance):
        # First process what needs to be done anyway
        context = super(ImportSetDetails, self).add_to_context(context, instance)

        sBack = ""
        oErr = ErrHandle()
        html = []
        try:
            # Do we have an instance defined?
            if not instance is None:
                context['importmode'] = instance.get_importmode()
                context['instance'] = instance
                sButtons = render_to_string("dct/xlsimp_form.html", context, self.request)
                context['after_details'] = sButtons
        except:
            msg = oErr.get_error_message()
            oErr.DoError("ImportSetDetails/add_to_context")
        return context

    def before_save(self, form, instance):
        
        bStatus = True
        msg = ""
        oErr = ErrHandle()
        try:
            # First do the more basic one
            bStatus, msg = super(ImportSetDetails, self).before_save(form, instance)
            
            # Do we already have an instance?
            if instance == None or instance.id == None:
                # See if we have the profile id
                profile = Profile.get_user_profile(self.request.user.username)
                form.instance.profile = profile
            else:
                profile = instance.profile

            # Do we have cleaned data?
            if hasattr(form, "cleaned_data"):
                cleaned = form.cleaned_data

                # (1) Preliminary order
                order = 1
                obj = profile.profile_importsetitems.all().order_by("-order").first()
                if obj != None:
                    order = obj.order + 1

                # (4) Re-calculate the order
                instance.adapt_order()
        except:
            msg = oErr.get_error_message()
            oErr.DoError("ImportSetEdit/before_save")

        # Return as usual
        return bStatus, msg


class ImportSetProcess(BasicPart):
    """Process an imported Excel defined in an ImportSet"""

    MainModel = ImportSet

    def add_to_context(self, context):

        # Gather all necessary data
        data = {}

        oErr = ErrHandle()
        try:
            # Check validity
            if not self.userpermissions("w"):
                # Don't do anything
                return context

            # Get the SetDef object
            importset = self.obj

            # Find out what we are doing here
            importmode = importset.get_importmode()

            # Action depends on the import mode
            if importmode == "verify":
                # We need to verify the Excel
                result = importset.do_verify()
                data['result'] = result

                data['targeturl'] = reverse('importset_details', kwargs={'pk': importset.id})
            elif importmode == "submit":
                # Double check that the status is okay, and then submit it
                status = importset.status
                if status == "ver":
                    # Yes, it has been verified: now submit it
                    profile = self.request.user.user_profiles.first()
                    # result = importset.do_submit(profile)
                    # Note: the profile is of the submitter, not necessarily of the moderator
                    result = importset.do_submit()
                    data['result'] = result

                # Always
                data['targeturl'] = reverse('importset_details', kwargs={'pk': importset.id})
            else:
                # Undefined importmode?
                oErr.Status("Undefined importmode [{}]".format(importmode))

            if not "targeturl" in data:
                oErr.Status("targeturl is not defined in data")
 
            context['data'] = data
        except:
            msg = oErr.get_error_message()
            oErr.DoError("ImportSetProcess")
        return context


class ImportSetDownload(BasicPart):
    """Facilitate downloading one imported file"""

    MainModel = ImportSet
    template_name = "seeker/download_status.html"
    action = "download"
    dtype = "excel"       # downloadtype

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
        manu_fields = []
        oErr = ErrHandle()

        try:
            # Need to know who this user (profile) is
            profile = Profile.get_user_profile(self.request.user.username)
            username = profile.user.username
            team_group = app_editor

            # Make sure we only look at lower-case Dtype
            dtype = dtype.lower()

            # Get the instance
            instance = self.obj

            # Is this Excel?
            if dtype == "excel" or dtype == "xlsx":
                # Find and open the appropriate workbook
                wb = openpyxl.load_workbook(instance.excel.path)

                # Save it
                wb.save(response)
                sData = response
        except:
            msg = oErr.get_error_message()
            oErr.DoError("ImportSetDownload/get_data")

        return sData

# =================== Model views for EXCEL REVIEW ========


class ImportReviewListView(BasicList):
    """Listview of ImportReview"""

    model = ImportReview
    listform = ImportReviewForm
    has_select2 = True
    bUseFilter = True
    prefix = "imprev"
    sg_name = "Excel import review"
    plural_name = "Excel import reviews"
    new_button = True
    use_team_group = True
    order_cols = ['importset__profile__user__username', 'order', 'importset__name', 'importset__importtype', 
                  'moderator__user__username', 'importset__status', 'status', 'saved', 'created']
    order_default = order_cols
    order_heads = [
        {'name': 'Owner',   'order': 'o=1','type': 'str', 'custom': 'owner',    'linkdetails': True},
        {'name': 'Order',   'order': 'o=2','type': 'int', 'field': 'order',     'linkdetails': True},
        {'name': 'File',    'order': 'o=3','type': 'str', 'custom': 'filename', 'linkdetails': True, 'main': True},
        {'name': 'Type',    'order': 'o=4','type': 'str', 'custom': 'type',     'linkdetails': True},
        {'name': 'Moderator','order':'o=5','type': 'str', 'custom': 'moderator','linkdetails': True},
        {'name': 'Status',  'order': 'o=6','type': 'str', 'custom': 'stimport', 'linkdetails': True},
        {'name': 'Review',  'order': 'o=7','type': 'str', 'custom': 'streview', 'linkdetails': True},
        {'name': 'Saved',   'order': 'o=8','type': 'str', 'custom': 'date',     'linkdetails': True, 'align': 'right'},
        {'name': 'Created', 'order': 'o=9','type': 'str', 'custom': 'created',  'linkdetails': True, 'align': 'right'},
                ]
    filters = [ 
        {"name": "Name",    "id": "filter_name",      "enabled": False},
        {"name": "Owner",   "id": "filter_owner",     "enabled": False},
        {"name": "Type",    "id": "filter_type",      "enabled": False},
        ]
    searches = [
        {'section': '', 'filterlist': [
            {'filter': 'name',  'dbfield': 'name',      'keyS': 'fname',  
             'keyList': 'namelist', 'infield': 'name' },
            {'filter': 'owner', 'fkfield': 'profile',   'keyList': 'ownlist', 'infield': 'id' },
            {'filter': 'type',  'dbfield': 'importtype','keyList': 'importtypelist',
             'keyType': 'fieldchoice',  'infield': 'abbr' }
            ]},
        {'section': 'other', 'filterlist': [] }
         ]

    def initializations(self):
        # Some things are needed for initialization
        return None

    def get_field_value(self, instance, custom):
        sBack = ""
        sTitle = ""

        if custom == "date":
            # sBack = instance.saved.strftime("%d/%b/%Y %H:%M")
            sBack = instance.get_saved()
        elif custom == "created":
            # sBack = instance.created.strftime("%d/%b/%Y %H:%M")
            sBack = instance.get_created()
        elif custom == "filename":
            sBack = instance.importset.get_name()
        elif custom == "type":
            sBack = instance.importset.get_type()
        elif custom == "streview":
            sBack = instance.get_status()
        elif custom == "stimport":
            sBack = instance.importset.get_status()
        elif custom == "owner":
            sBack = instance.get_owner()
        elif custom == "moderator":
            sBack = instance.get_moderator()

        return sBack, sTitle

    def adapt_search(self, fields):
        lstExclude=None
        qAlternative = None
        oErr = ErrHandle()
        try:
            pass
        except:
            msg = oErr.get_error_message()
            oErr.DoError("ImportReviewListView/adapt_search")

        return fields, lstExclude, qAlternative


class ImportReviewEdit(BasicDetails):
    model = ImportReview
    mForm = ImportReviewForm
    prefix = 'imprev'
    prefix_type = "simple"
    title = "Import review"
    use_team_group = True
    mainitems = []

    def add_to_context(self, context, instance):
        """Add to the existing context"""

        oErr = ErrHandle()
        try:
            is_app_editor = context['is_app_editor']
            # Define the main items to show and edit
            context['mainitems'] = [
                {'type': 'line',  'label': "Submission:",'value': instance.get_submission()                         },
                {'type': 'line',  'label': "Details:",  'value': self.get_import_details(instance, is_app_editor)   },
                {'type': 'plain', 'label': "Created:",  'value': instance.get_created()                             },
                {'type': 'plain', 'label': "Saved:",    'value': instance.get_saved()                               },
                {'type': 'safe',  'label': "Status:",   'value': instance.get_status(True),                         },
                {'type': 'safe',  'label': "Moderator:",'value': instance.get_moderator(),                          },
                {'type': 'safe',  'label': "Verdict",   'value': self.get_button(instance, is_app_editor)           },
                {'type': 'safe',  'label': "Notes:",    'value': instance.get_notes_html(),  'field_key': 'notes'   },
                ]
            
            # Signal that we do have select2
            context['has_select2'] = True

            # Determine what the permission level is of this collection for the current user
            # (1) Is this user a different one than the one who created the collection?
            profile_owner = instance.moderator
            profile_user = Profile.get_user_profile(self.request.user.username)
            # (2) Set default permission
            permission = ""
            if not profile_owner is None and profile_owner.id == profile_user.id:
                # (3) Any creator of the ImportReview may write it
                permission = "write"
            else:
                # (4) permission for different users
                if context['is_app_moderator']:
                    # (5) what if the user is an app_moderator?
                    permission = "write"
                else:
                    # (5) any other users may only read
                    permission = "read"

            context['permission'] = permission
        except:
            msg = oErr.get_error_message()
            oErr.DoError("ImportReviewEdit/add_to_context")

        # Return the context we have made
        return context

    def get_import_details(self, instance, is_app_editor):
        """Collect the import details in a HTML string"""

        sBack = ""
        oErr = ErrHandle()
        try:
            if not instance is None:
                context = dict(instance = instance.importset)
                context['is_app_editor'] = is_app_editor
                sBack = render_to_string("dct/xlsimp_details.html", context, self.request)
        except:
            msg = oErr.get_error_message()
            oErr.DoError("ImportReviewEdit/get_import_details")
        return sBack

    def before_save(self, form, instance):
        bStatus = True
        msg = ""
        oErr = ErrHandle()
        try:
            # Do we have changed data?
            if hasattr(form, "changed_data"):
                changed = form.changed_data
                # Has the excel been changed?
                if "excel" in changed:
                    # The excel has changed - reset some stuff
                    form.instance.status = "chg"
                    form.instance.report = ""
        except:
            msg = oErr.get_error_message()
            oErr.DoError("ImportReviewEdit/before_save")
    
        return bStatus, msg

    def get_button(self, instance, is_app_editor):
        """Create and show the buttons that are appropriate at this stage"""

        sBack = ""
        oErr = ErrHandle()
        html = []
        try:
            if not instance is None:
                context = dict(instance=instance)
                # context['importmode'] = instance.get_importmode()
                context['is_app_editor'] = is_app_editor
                sBack = render_to_string("dct/xlsrev_button.html", context, self.request)
 
        except:
            msg = oErr.get_error_message()
            oErr.DoError("ImportReviewEdit/get_button")

        return sBack

    def check_hlist(self, instance):
        """Check if a hlist parameter is given, and hlist saving is called for"""

        oErr = ErrHandle()
        bChanges = False
        bDebug = True
        prefix = "super"

        try:
            arg_hlist = "{}-hlist".format(prefix)
            arg_savenew = "{}-savenew".format(prefix)
            if arg_hlist in self.qd and arg_savenew in self.qd:
                # Interpret the list of information that we receive
                hlist = json.loads(self.qd[arg_hlist])
                ## Interpret the savenew parameter
                #savenew = self.qd[arg_savenew]

                ## Make sure we are not saving
                #self.do_not_save = True
                ## But that we do a new redirect
                #self.newRedirect = True

                ## Change the redirect URL
                #if self.redirectpage == "":
                #    self.redirectpage = reverse('stemmaset_details', kwargs={'pk': instance.id})

                ## What we have is the ordered list of Manuscript id's that are part of this collection
                #with transaction.atomic():
                #    # Make sure the orders are correct
                #    for idx, item_id in enumerate(hlist):
                #        order = idx + 1
                #        lstQ = [Q(stemmaset=instance)]
                #        lstQ.append(Q(**{"id": item_id}))
                #        obj = StemmaItem.objects.filter(*lstQ).first()
                #        if obj != None:
                #            if obj.order != order:
                #                obj.order = order
                #                obj.save()
                #                bChanges = True
                ## See if any need to be removed
                #existing_item_id = [str(x.id) for x in StemmaItem.objects.filter(stemmaset=instance)]
                #delete_id = []
                #for item_id in existing_item_id:
                #    if not item_id in hlist:
                #        delete_id.append(item_id)
                #if len(delete_id)>0:
                #    lstQ = [Q(stemmaset=instance)]
                #    lstQ.append(Q(**{"id__in": delete_id}))
                #    StemmaItem.objects.filter(*lstQ).delete()
                #    bChanges = True

                #if bChanges:
                #    # (6) Re-calculate the set of setlists
                #    force = True if bDebug else False
                #    #instance.update_ssglists(force)

            return True
        except:
            msg = oErr.get_error_message()
            oErr.DoError("ImportReviewEdit/check_hlist")
            return False


class ImportReviewDetails(ImportReviewEdit):
    """The HTML variant of [ImportReviewEdit]"""

    rtype = "html"
    
    def custom_init(self, instance):
        if instance != None:
            # Check for hlist saving
            self.check_hlist(instance)
        return None

    def add_to_context(self, context, instance):
        # First process what needs to be done anyway
        context = super(ImportReviewDetails, self).add_to_context(context, instance)

        sBack = ""
        oErr = ErrHandle()
        html = []
        try:
            # Do we have an instance defined?
            if not instance is None:
                context['instance'] = instance
                # TODO: adapt
                sButtons = render_to_string("dct/xlsrev_form.html", context, self.request)
                context['after_details'] = sButtons
        except:
            msg = oErr.get_error_message()
            oErr.DoError("ImportReviewDetails/add_to_context")
        return context

    def before_save(self, form, instance):
        
        bStatus = True
        msg = ""
        oErr = ErrHandle()
        try:
            # First do the more basic one
            bStatus, msg = super(ImportReviewDetails, self).before_save(form, instance)
            
            # Do we already have an instance?
            if instance == None or instance.id == None:
                # See if we have the profile id
                profile = Profile.get_user_profile(self.request.user.username)
                form.instance.profile = profile
            else:
                profile = instance.profile

            # Do we have cleaned data?
            if hasattr(form, "cleaned_data"):
                cleaned = form.cleaned_data

                # (1) Preliminary order
                order = 1
                obj = profile.profile_importsetitems.all().order_by("-order").first()
                if obj != None:
                    order = obj.order + 1

                # (4) Re-calculate the order
                instance.adapt_order()
        except:
            msg = oErr.get_error_message()
            oErr.DoError("ImportReviewEdit/before_save")

        # Return as usual
        return bStatus, msg


class ImportReviewProcess(BasicPart):
    """Process a verdict"""

    MainModel = ImportReview

    def add_to_context(self, context):

        # Gather all necessary data
        data = {}

        oErr = ErrHandle()
        try:
            # Check validity
            if not self.userpermissions("w"):
                # Don't do anything
                return context

            # Get the ImportReview object
            importreview = self.obj

            # Find out what we are doing here
            importverdict = self.qd.get("importverdict")
            if importverdict is None:
                importverdict = "rej"

            # Set the verdict in the ImportReview model
            profile = self.request.user.user_profiles.first()
            result = importreview.do_process(profile, importverdict)
            data['result'] = result
            # Always
            data['targeturl'] = reverse('importreview_details', kwargs={'pk': importreview.id})

            if not "targeturl" in data:
                oErr.Status("targeturl is not defined in data")
 
            context['data'] = data
        except:
            msg = oErr.get_error_message()
            oErr.DoError("ImportReviewProcess")
        return context

