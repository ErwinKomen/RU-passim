"""
Definition of DCT-related views and procedures for the SEEKER app.

DCT = Dynamic Comparative Table
"""

# View imports
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
import json
import csv

# ======= imports from my own application ======
from passim.settings import APP_PREFIX, MEDIA_DIR, WRITABLE_DIR
from passim.utils import ErrHandle
from passim.basic.views import BasicList, BasicDetails, BasicPart
from passim.seeker.views import get_application_context, get_breadcrumbs, user_is_ingroup, nlogin, user_is_authenticated, user_is_superuser
from passim.seeker.models import SermonDescr, EqualGold, Manuscript, Signature, Profile, CollectionSuper, Collection, Project2
from passim.seeker.models import get_crpp_date, get_current_datetime, process_lib_entries, get_searchable, get_now_time
from passim.dct.models import ResearchSet, SetList, SetDef, get_passimcode, get_goldsig_dct, \
    SavedItem, SavedSearch, SelectItem
from passim.dct.forms import ResearchSetForm, SetDefForm
from passim.approve.models import EqualChange, EqualApproval

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

        # Find the project that we need to 'cancel'
        project = Project2.objects.filter(name__icontains="luc de coninck").first()
        if not project is None:
            # Find all the manuscripts that need removing
            qs = Manuscript.objects.filter(manuscript_proj__project=project, stype=stype, mtype=mtype)

            # Remove them
            qs.delete()

        # Render and return the page
        return redirect('mypassim')
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

# =================== MY OWN DCT pages ===============
def mypassim(request):
    """Renders the MyPassim page (=PRE, Personal Research Environment)."""
    
    oErr = ErrHandle()
    try:
        # Get the request right
        assert isinstance(request, HttpRequest)

        # Double check: the person must have been logged-in
        if not user_is_authenticated(request):
            # Indicate that use must log in
            return nlogin(request)

        # Specify the template
        template_name = 'mypassim.html'
        context =  {'title':'My PASSIM',
                    'year':get_current_datetime().year,
                    'pfx': APP_PREFIX,
                    'site_url': admin.site.site_url}
        context = get_application_context(request, context)

        profile = Profile.get_user_profile(request.user.username)
        context['profile'] = profile
        context['rset_count'] = ResearchSet.objects.filter(profile=profile).count()
        context['dct_count'] = SetDef.objects.filter(researchset__profile=profile).count()
        context['count_datasets'] = Collection.objects.filter(settype="pd", owner=profile).count()

        # COunting table sizes for the super user
        if user_is_superuser(request):
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

        # Figure out any editing rights
        qs = profile.projects.all()
        context['edit_projects'] = "(none)"
        if context['is_app_editor'] and qs.count() > 0:
            html = []
            for obj in qs:
                url = reverse('project2_details', kwargs={'pk': obj.id})
                html.append("<span class='project'><a href='{}'>{}</a></span>".format(url, obj.name))
            context['edit_projects'] = ",".join(html)

        # Figure out which projects this editor may handle
        if context['is_app_editor']:
            qs = profile.project_editor.filter(status="incl")
            if qs.count() == 0:
                sDefault = "(none)"
            else:
                html = []
                for obj in qs:
                    project = obj.project
                    url = reverse('project2_details', kwargs={'pk': project.id})
                    html.append("<span class='project'><a href='{}'>{}</a></span>".format(url, project.name))
                sDefault = ", ".join(html)
            context['default_projects'] = sDefault

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

        # How many do I need to approve?

        # Process this visit
        context['breadcrumbs'] = get_breadcrumbs(request, "My PASSIM", True)
    except:
        msg = oErr.get_error_message()
        oErr.DoError("mypassim")

    return render(request,template_name, context)


# =================== MyPassim as model view attempt ======
class MyPassimEdit(BasicDetails):
    model = Profile
    mform = None
    prefix = "pre"  # Personal Research Environment
    prefix_type = "simple"
    title = "MY PASSIM"
    template_name = "dct/mypassim.html"
    mainitems = []

    def custom_init(self, instance):
        if user_is_authenticated(self.request):
            # Get the profile id of this user
            profile = Profile.get_user_profile(self.request.user.username)
            self.object = profile
        else:
            pass
        return None

    def add_to_context(self, context, instance):
        oErr = ErrHandle()
        try:
            profile = self.object
            context['profile'] = profile
            context['rset_count'] = ResearchSet.objects.filter(profile=profile).count()
            context['dct_count'] = SetDef.objects.filter(researchset__profile=profile).count()
            context['count_datasets'] = Collection.objects.filter(settype="pd", owner=profile).count()

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

            # Figure out any editing rights
            qs = profile.projects.all()
            context['edit_projects'] = "(none)"
            if context['is_app_editor'] and qs.count() > 0:
                html = []
                for obj in qs:
                    url = reverse('project2_details', kwargs={'pk': obj.id})
                    html.append("<span class='project'><a href='{}'>{}</a></span>".format(url, obj.name))
                context['edit_projects'] = ",".join(html)

            # Figure out which projects this editor may handle
            if context['is_app_editor']:
                qs = profile.project_editor.filter(status="incl")
                if qs.count() == 0:
                    sDefault = "(none)"
                else:
                    html = []
                    for obj in qs:
                        project = obj.project
                        url = reverse('project2_details', kwargs={'pk': project.id})
                        html.append("<span class='project'><a href='{}'>{}</a></span>".format(url, project.name))
                    sDefault = ", ".join(html)
                context['default_projects'] = sDefault

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
            context['related_objects'] = self.get_related_objects(profile)

        except:
            msg = oErr.get_error_message()
            oErr.DoError("mypassimedit/add_to_context")

        return context

    def get_related_objects(self, instance):
        """Calculate and add related objects:

        Currently:
            - Saved items
        To be extended (see issue #408):
            - Saved searches
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
                    if obj.order < 0:
                        obj.order = idx + 1
                        obj.save()

        username = self.request.user.username
        team_group = app_editor

        # Authorization: only app-editors may edit!
        bMayEdit = user_is_ingroup(self.request, team_group)
            
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
            if resizable: sitemset['gridclass'] = "resizable dragdrop"
            sitemset['savebuttons'] = bMayEdit
            sitemset['saveasbutton'] = False

            qs_sitemlist = instance.profile_saveditems.all().order_by('order', 'sitemtype')
            # Also store the count
            sitemset['count'] = qs_sitemlist.count()
            sitemset['instance'] = instance
            sitemset['detailsview'] = reverse('mypassim_details') #, kwargs={'pk': instance.id})
            # These elements have an 'order' attribute, so they  may be corrected
            check_order(qs_sitemlist)

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

                # Add this line to the list
                rel_list.append(dict(id=obj.id, cols=rel_item))
            
            sitemset['rel_list'] = rel_list
            sitemset['columns'] = [
                '{}<span title="Default order">Order<span>{}'.format(sort_start_int, sort_end),
                '{}<span title="Type of saved item">Item</span>{}'.format(sort_start, sort_end), 
                '{}<span title="The title of the manuscript/sermon/authority-file/dataset/collection">Title</span>{}'.format(sort_start, sort_end), 
                '{}<span title="Number of SSGs part of this item">Size</span>{}'.format(sort_start_int, sort_end)
                ]
            if bMayEdit:
                sitemset['columns'].append("")
            related_objects.append(sitemset)

            # [2] ===============================================================
            # Deal with Saved Searches!!!!
            # TODO: implement

        except:
            msg = oErr.get_error_message()
            oErr.DoError("mypassimedit/get_related_objects")

        # Return the adapted context
        return related_objects

    def get_field_value(self, type, instance, custom, kwargs=None):
        sBack = ""
        collection_types = ['hc', 'pd' ]

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
                #url = reverse("equalgold_details", kwargs = {'pk': instance.id})
                #sBack = "<span class='clickable'><a href='{}' class='nostyle'><span class='signature'>{}</span>: {}</a><span>".format(
                #    url, instance.msitem.codico.manuscript.idno, instance.get_locus())
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
                sBack = "<a class='btn btn-xs jumbo-2'><span class='related-remove'>Delete</span></a>"

        return sBack

    def check_hlist(self, instance):
        """Check if a hlist parameter is given, and hlist saving is called for"""

        oErr = ErrHandle()
        bChanges = False
        bDebug = True

        try:
            arg_hlist = "svitem-hlist"
            arg_savenew = "svitem-savenew"
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
                    self.redirectpage = reverse('mypassim_details')

                # What we have is the ordered list of Manuscript id's that are part of this collection
                with transaction.atomic():
                    # Make sure the orders are correct
                    for idx, item_id in enumerate(hlist):
                        order = idx + 1
                        lstQ = [Q(profile=instance)]
                        lstQ.append(Q(**{"id": item_id}))
                        obj = SavedItem.objects.filter(*lstQ).first()
                        if obj != None:
                            if obj.order != order:
                                obj.order = order
                                obj.save()
                                bChanges = True
                # See if any need to be removed
                existing_item_id = [str(x.id) for x in SavedItem.objects.filter(profile=instance)]
                delete_id = []
                for item_id in existing_item_id:
                    if not item_id in hlist:
                        delete_id.append(item_id)
                if len(delete_id)>0:
                    lstQ = [Q(profile=instance)]
                    lstQ.append(Q(**{"id__in": delete_id}))
                    SavedItem.objects.filter(*lstQ).delete()
                    bChanges = True

                if bChanges:
                    # (6) Re-calculate the order
                    SavedItem.update_order(instance)

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



# ================= Views for SavedItem, SelectItem ================

class SavedItemApply(BasicPart):
    """Either add or remove an item as saved data"""

    MainModel = Profile

    def add_to_context(self, context):

        oErr = ErrHandle()
        data = dict(status="ok")
       
        try:
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
                #qs = SavedItem.objects.filter(profile=profile).order_by('order', 'id')
                #with transaction.atomic():
                #    order = 1
                #    for obj in qs:
                #        if obj.order != order:
                #            obj.order = order
                #            obj.save()
                #        order += 1
        except:
            msg = oErr.get_error_message()
            oErr.DoError("SavedItemApply")
            data['status'] = "error"

        context['data'] = data
        return context


class SelectItemApply(BasicPart):
    """Either add or remove an item as saved data"""

    MainModel = Profile

    def add_to_context(self, context):

        oErr = ErrHandle()
        data = dict(status="ok")
       
        try:
            # We already know who we are
            profile = self.obj

            # Retrieve necessary parameters
            selitemtype = self.qd.get("selitemtype")
            selitemaction = self.qd.get("selitemaction")
            selitemid = self.qd.get("selitemid")
            itemid = self.qd.get("itemid")

            itemset = dict(manu="manuscript", serm="sermon", ssg="equal", hc="collection", pd="collection")
            itemidfield = itemset[selitemtype]

            if selitemaction == "add":
                # We are going to add an item as a saveditem
                obj = SelectItem.objects.create(
                    profile=profile, selitemtype=selitemtype)
                # The particular attribute to set depends on the selitemtype
                setattr(obj, "{}_id".format(itemidfield), itemid)
                obj.save()
                data['action'] = "added"
            elif selitemaction == "remove" and not saveditemid is None:
                # We need to remove *ALL* relevant items
                lstQ = []
                lstQ.append(Q(profile=profile))
                lstQ.append(Q(selitemtype=selitemtype))
                lstQ.append(Q(**{"{}_id".format(itemidfield): itemid}))
                delete_id = SelectItem.objects.filter(*lstQ).values("id")
                if len(delete_id) > 0:
                    SelectItem.objects.filter(id__in=delete_id).delete()
                data['action'] = "removed"

        except:
            msg = oErr.get_error_message()
            oErr.DoError("SelectItemApply")
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
            add_html = render_to_string("dct/setlist_add.html", context, self.request)
            context['mainitems'].append( {'type': 'line',  'label': "Add:",        'value': add_html})


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

            # Create the DCT with a template
            dct_view = render_to_string(template_name, context)

            # Add the visualisation we made
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
        return context


class SetDefDownload(BasicPart):
    """Downloading for DCTs"""

    MainModel = SetDef
    template_name = "seeker/download_status.html"
    action = "download"
    dtype = ""

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

