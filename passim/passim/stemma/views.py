"""
Definition of Stemmatology-related views and procedures for the STEMMA app.

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
import copy
import json
import csv

# ======= imports from my own application ======
from passim.settings import APP_PREFIX, MEDIA_DIR, WRITABLE_DIR
from passim.utils import ErrHandle
from passim.basic.views import BasicList, BasicDetails, BasicPart, \
    app_uploader, app_editor, app_moderator, app_user, app_userplus, user_is_ingroup, user_is_superuser, user_is_authenticated
#from passim.seeker.views import get_application_context, get_breadcrumbs, user_is_ingroup, nlogin, user_is_authenticated, \
#    user_is_superuser, get_selectitem_info
from passim.seeker.models import Profile
from passim.stemma.models import StemmaItem, StemmaSet
from passim.stemma.forms import StemmaSetForm
from passim.seeker.views import stemma_editor, stemma_user
from passim.seeker.views import EqualGoldListView


# =================== Model views for the DCT ========


class StemmaSetListView(BasicList):
    """Listview of StemmaSet"""

    model = StemmaSet
    listform = StemmaSetForm
    has_select2 = True
    bUseFilter = True
    prefix = "stmset"
    sg_name = "Stemmatology research set"
    plural_name = "Stemmatology research sets"
    new_button = True
    use_team_group = True
    order_cols = ['name', 'scope', 'profile__user__username', 'saved', '']
    order_default = order_cols
    order_heads = [
        {'name': 'Name',    'order': 'o=1','type': 'str', 'field': 'name',                      'linkdetails': True, 'main': True},
        {'name': 'Scope',   'order': 'o=2','type': 'str', 'custom': 'scope',                    'linkdetails': True},
        {'name': 'Owner',   'order': 'o=3','type': 'str', 'custom': 'owner',                    'linkdetails': True},
        {'name': 'Date',    'order': 'o=4','type': 'str', 'custom': 'date',   'align': 'right', 'linkdetails': True},
        {'name': 'Stemma',  'order': 'o=5','type': 'str', 'custom': 'stemma', 'align': 'right'},
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
        elif custom == "stemma":
            html = []
            sBack = ""
            ## Find the first DCT for this research set
            #dct = SetDef.objects.filter(StemmaSet=instance).first()
            #if dct == None:
            #    sBack = "-"
            #else:
            #    url = reverse('setdef_details', kwargs={'pk': dct.id})
            #    html.append("<a href='{}' title='Show the default DCT for this research set'><span class='glyphicon glyphicon-open' style='color: darkblue;'></span></a>".format(url))
            #    sBack = "\n".join(html)
        elif custom == "scope":
            sBack = instance.get_scope_display()
        elif custom == "owner":
            sBack = instance.profile.user.username

        return sBack, sTitle

    def add_to_context(self, context, initial):
        context['is_stemma_user'] = user_is_ingroup(stemma_user)
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


class StemmaSetEdit(BasicDetails):
    model = StemmaSet
    mForm = StemmaSetForm
    prefix = 'stmset'
    prefix_type = "simple"
    title = "StemmaSet"
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
                    self.redirectpage = reverse('StemmaSet_details', kwargs={'pk': instance.id})

                # What we have is the ordered list of Manuscript id's that are part of this collection
                with transaction.atomic():
                    # Make sure the orders are correct
                    for idx, item_id in enumerate(hlist):
                        order = idx + 1
                        lstQ = [Q(StemmaSet=instance)]
                        lstQ.append(Q(**{"id": item_id}))
                        obj = SetList.objects.filter(*lstQ).first()
                        if obj != None:
                            if obj.order != order:
                                obj.order = order
                                obj.save()
                                bChanges = True
                # See if any need to be removed
                existing_item_id = [str(x.id) for x in SetList.objects.filter(StemmaSet=instance)]
                delete_id = []
                for item_id in existing_item_id:
                    if not item_id in hlist:
                        delete_id.append(item_id)
                if len(delete_id)>0:
                    lstQ = [Q(StemmaSet=instance)]
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
            oErr.DoError("StemmaSetEdit/check_hlist")
            return False
    

class StemmaSetDetails(StemmaSetEdit):
    """The HTML variant of [StemmaSetEdit]"""

    rtype = "html"
    listviewtitle = "Stemmatology page"
    
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

            # (1) Preliminary order
            order = 1
            obj = instance.stemmaset_stemmaitems.all().order_by("-order").first()
            if obj != None:
                order = obj.order + 1

            # (4) Re-calculate the order
            instance.adapt_order()
            ## (6) Re-calculate the set of setlists
            #instance.update_ssglists()
        # Return as usual
        return bStatus, msg

    def add_to_context(self, context, instance):
        # Perform the standard initializations:
        context = super(StemmaSetDetails, self).add_to_context(context, instance)

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
            # Get all 'StemmaItem' objects that are part of this 'StemmaSet'
            supers = dict(title="Authority files within this Stemmatology research set", prefix="super")
            if resizable: supers['gridclass'] = "resizable dragdrop"
            supers['savebuttons'] = bMayEdit
            supers['saveasbutton'] = True
            supers['classes'] = 'collapse'

            qs_stemmaitem = instance.stemmaset_stemmaitems.all().order_by(
                    'order', 'equal__author__name', 'equal__firstsig', 'equal__srchincipit', 'equal__srchexplicit')
            check_order(qs_stemmaitem)

            # Walk these collection sermons
            for idx, obj in enumerate(qs_stemmaitem):
                rel_item = []
                item = obj.super

                # Leave if this is too much
                if idx > self.max_items:
                    break

                # SSG: Order in Manuscript
                #add_one_item(rel_item, index, False, align="right")
                #index += 1
                add_one_item(rel_item, obj.order, False, align="right", draggable=True)

                # SSG: Author
                add_one_item(rel_item, self.get_field_value("super", item, "author"), resizable)

                # SSG: Passim code
                add_one_item(rel_item, self.get_field_value("super", item, "code"), False)

                # SSG: Gryson/Clavis = signature
                add_one_item(rel_item, self.get_field_value("super", item, "sig"), False)

                # SSG: Inc/Expl
                add_one_item(rel_item, self.get_field_value("super", item, "incexpl"), False, main=True)

                # SSG: Size (number of SG in equality set)
                add_one_item(rel_item, self.get_field_value("super", item, "size"), False)

                # Actions that can be performed on this item
                if bMayEdit:
                    add_one_item(rel_item, self.get_actions())

                # Add this line to the list
                rel_list.append(dict(id=item.id, cols=rel_item))
            
            supers['rel_list'] = rel_list
            supers['columns'] = [
                '{}<span title="Default order">Order<span>{}'.format(sort_start_int, sort_end),
                '{}<span title="Author">Author</span>{}'.format(sort_start, sort_end), 
                '{}<span title="PASSIM code">Passim</span>{}'.format(sort_start, sort_end), 
                '{}<span title="Gryson or Clavis codes of sermons gold in this set">Gryson/Clavis</span>{}'.format(sort_start, sort_end), 
                '{}<span title="Incipit and explicit">inc...expl</span>{}'.format(sort_start, sort_end), 
                '{}<span title="Number of Sermons Gold part of this set">Size</span>{}'.format(sort_start_int, sort_end)
                ]
            if bMayEdit:
                supers['columns'].append("")
            related_objects.append(supers)

            # [3] =============================================================
            # Make sure the resulting list ends up in the viewable part
            context['related_objects'] = related_objects
        except:
            msg = oErr.get_error_message()
            oErr.DoError("StemmaSetDetails/add_to_context")

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
        elif type == "super":
            sBack, sTitle = EqualGoldListView.get_field_value(None, instance, custom)

        return sBack




