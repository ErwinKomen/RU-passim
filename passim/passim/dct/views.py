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
import json

# ======= imports from my own application ======
from passim.settings import APP_PREFIX, MEDIA_DIR, WRITABLE_DIR
from passim.utils import ErrHandle
from passim.basic.views import BasicList, BasicDetails, BasicPart
from passim.seeker.views import get_application_context, get_breadcrumbs, user_is_ingroup
from passim.seeker.models import SermonDescr, EqualGold, Manuscript, Signature, Profile, CollectionSuper, Collection
from passim.seeker.models import get_crpp_date, get_current_datetime, process_lib_entries, get_searchable, get_now_time
from passim.dct.models import ResearchSet, SetList, SetDef, get_passimcode, get_goldsig_dct
from passim.dct.forms import ResearchSetForm, SetDefForm

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

def test_dct(request):

    oErr = ErrHandle()
    # Specify the template
    template_name = 'dct/dct.html'
    context = {'title': 'DCT','pfx': APP_PREFIX }
    try:
        assert isinstance(request, HttpRequest)

        context['year'] = get_current_datetime().year
        context['site_url'] = admin.site.site_url

        manu_ids = [1909, 1912, 1813, 1796]
        manus = Manuscript.objects.filter(id__in=manu_ids)
        lBack = dct_manulist(manus, True)
        context['setlist'] = lBack

    except:
        msg = oErr.get_error_message()
        oErr.DoError("test_dct")

    sHtml = render_to_string(template_name, context, request)
    response = HttpResponse(sHtml)
    return response

# =================== MY OWN DCT pages ===============
def mypassim(request):
    """Renders the MyPassim page (=PRE)."""
    assert isinstance(request, HttpRequest)
    # Specify the template
    template_name = 'mypassim.html'
    context =  {'title':'My Passim',
                'year':get_current_datetime().year,
                'pfx': APP_PREFIX,
                'site_url': admin.site.site_url}
    context = get_application_context(request, context)

    profile = Profile.get_user_profile(request.user.username)
    context['rset_count'] = ResearchSet.objects.filter(profile=profile).count()
    context['dct_count'] = SetDef.objects.filter(researchset__profile=profile).count()

    # Process this visit
    context['breadcrumbs'] = get_breadcrumbs(request, "My Passim", True)

    return render(request,template_name, context)



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
                    add_one_item(rel_item, self.get_actions())

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
            buttonspecs = {'label': "M", 
                    'title': "Back to my research set {}".format(rset.name), 
                    'url': reverse('researchset_details', kwargs={'pk': rset.id})}
            topleftlist.append(buttonspecs)
            context['topleftbuttons'] = topleftlist

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
            context['csrf'] = '<input type="hidden" name="csrfmiddlewaretoken" value="{}" />'.format(
                get_token(self.request))
            context['mayedit'] = bMayEdit

            # Create the DCT with a template
            dct_view = render_to_string(template_name, context)

            # Add the visualisation we made
            context['add_to_details'] = dct_view
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
