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
import os
import time

# ======= Partial implementation of Bio ================
from Bio import Phylo
from Bio.Phylo.TreeConstruction import *

# ======= imports from my own application ==============
from passim.settings import APP_PREFIX, MEDIA_DIR, WRITABLE_DIR
from passim.utils import ErrHandle
from passim.basic.views import BasicList, BasicDetails, BasicPart, \
    app_uploader, app_editor, app_moderator, app_user, app_userplus, user_is_ingroup, user_is_superuser, user_is_authenticated
#from passim.seeker.views import get_application_context, get_breadcrumbs, user_is_ingroup, nlogin, user_is_authenticated, \
#    user_is_superuser, get_selectitem_info
from passim.seeker.models import Profile
from passim.stemma.models import StemmaItem, StemmaSet, StemmaCalc
from passim.stemma.forms import StemmaSetForm, EqualSelectForm
from passim.seeker.views import stemma_editor, stemma_user
from passim.seeker.views import EqualGoldListView
from passim.stemma.algorithms import lf_new4

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
# stemma_editor = "stemma_editor"
# stemma_user = "stemma_user"

def get_application_context(request, context):
    context['is_app_uploader'] = user_is_ingroup(request, app_uploader)
    context['is_app_editor'] = user_is_ingroup(request, app_editor)
    context['is_enrich_editor'] = user_is_ingroup(request, enrich_editor)
    context['is_app_moderator'] = user_is_superuser(request) or user_is_ingroup(request, app_moderator)
    context['is_stemma_editor'] = user_is_ingroup(request, stemma_editor) or context['is_app_moderator']
    context['is_stemma_user'] = user_is_ingroup(request, stemma_user)
    return context




# =================== Alternative simple views ============



class StemmaDashboard(BasicDetails):
    model = StemmaSet
    mForm = None
    title = "Stemma dashboard"
    mainitems = []
    rtype = "html"
    template_name = "stemma/syncstemma.html"

    def add_to_context(self, context, instance):
        oErr = ErrHandle()
        try:
            # TODO: possibly remove 'stale' StemmaCalc objects??

            # Create or get a new StemmaCalc object
            obj = StemmaCalc.objects.filter(stemmaset=instance).first()
            if obj is None:
                # Create one
                obj = StemmaCalc.objects.create(stemmaset=instance)
            else:
                # There already is one
                sStatus = obj.get_status()
                if not sStatus in ["ok", "ready", "finished"]:
                    # Now reset the status
                    obj.set_status("reset")
                else:
                    # Need a real reset
                    # stop the current calculation
                    obj.signal = "interrupt"
                    obj.save()
                    # Wait for three seconds
                    time.sleep(4)
                    # Now reset the status
                    obj.set_status("reset")

            context['stemmacalc_id'] = obj.id
            # Get the name of the stemmaset
            sName = instance.get_name_markdown()
            context['stemmaset_name'] = sName
            qs = instance.stemmaset_stemmaitems.all().order_by("order")
            lst_ssgs = []
            for obj in qs:
                ssg = obj.equal
                oSsgInfo = {}
                oSsgInfo['author'] = ssg.get_author()
                oSsgInfo['code'] = ssg.get_passimcode_markdown()
                oSsgInfo['siglist'] = ssg.get_siglist()
                oSsgInfo['size'] = ssg.get_size()
                lst_ssgs.append(oSsgInfo)
            context['stemmaset_ssgs'] = lst_ssgs
        except:
            msg = oErr.get_error_message()
            oErr.DoError("StemmaDashboard/add_to_context")

        # Return the context we have made
        return context
    

class StemmaStart(BasicPart):
    """Start the analysis of the indicated stemmaset"""

    MainModel = StemmaCalc

    def add_to_context(self, context):

        # Initialize data return, just in case
        data = {'status': 'error', 'message': 'interrupt'}
        context['data'] = data

        # Gather all necessary data
        oErr = ErrHandle()
        try:
            # Get the StemmaCalc object
            instance = self.obj

            # (1) Prepare the texts for analysis
            if instance.set_status("preparing") == "interrupt": return context
            sTexts, lst_codes = self.prepare_texts()

            # (2) Execute the Leitfehler Algorithm on the combined fulltexts
            if instance.set_status("leitfehler") == "interrupt": return context
            lst_leitfehler, distMatrix = lf_new4(sTexts, instance)

            # (3) Store the result within the StemmaSet object
            if instance.set_status("Store results") == "interrupt": return context
            instance.store_lf(lst_leitfehler)

            # (4) Make sure to indicate that we are ready
            if instance.set_status("ready") == "interrupt": return context

            # (5) Collect the data into one table
            lHtml = []
            lHtml.append("<table><thead><tr><th>Label</th><th>numbers</th></tr>")
            lHtml.append("<tbody>")
            for oLeitRow in lst_leitfehler:
                lHtml.append("<tr>")
                lHtml.append("<td>{}</td>".format(oLeitRow[0]))
                lHtml.append("<td>")
                for item in oLeitRow[1:]:
                    lHtml.append("{} ".format(item))
                lHtml.append("</td>")
                lHtml.append("</tr>")
            lHtml.append("</tbody></table>")
            sMsg = "\n".join(lHtml)

            # (6) Convert into tree using FITCH
            constructor = DistanceTreeConstructor()
            tree = constructor.upgma(distMatrix)
            #scorer = ParsimonyScorer()
            #searcher = NNITreeSearcher(scorer)
            #constructor = ParsimonyTreeConstructor(searcher)

            # FIll in the [data] part of the context with all necessary information
            data['status'] = "finished"
            data['message'] = sMsg
            context['data'] = data
        except:
            msg = oErr.get_error_message()
            oErr.DoError("StemmaStart/add_to_context")
        return context

    def prepare_texts(self):
        """Required format:
        
        * one witness, one line; 
        * beginning "A          | " (for ms. "A"). 
        * Ms. names must not be longer than 3 chars.
        """

        def get_code(number):
            x_0 = number % 10
            x_1 = number // 10 % 10 * 10
            x_2 = number // 100 % 10 * 100
            s_0 = chr(ord('A') + x_0)
            s_1 = chr(ord('A') + x_1)
            s_2 = chr(ord('A') + x_2)
            sBack = "{}{}{}".format(s_2, s_1, s_0)
            return sBack

        sBack = ""
        lst_codes = []
        oErr = ErrHandle()
        try:
            lst_text = []
            order = 0

            # Get the stemmaset object
            stemmaset = self.obj.stemmaset

            # Get a view of all objects
            qs = stemmaset.stemmaset_stemmaitems.all().order_by("order")

            # First element in the list is the number of items
            lst_text.append("{}".format(qs.count()))

            # Now iterate
            for obj in qs:
                # Transform number into code
                code = get_code(order)
                # Get the SSG from the obj
                ssg = obj.equal
                if not ssg is None:
                    # Get the fulltext
                    fulltext = ssg.srchfulltext
                    sText = "{}       | {}".format(code, fulltext.replace("\n", " "))
                    lst_text.append(sText)

                    # Also keep track of what belongs to what
                    lst_codes.append(dict(code=code, equal_id=ssg.id))
                # Make room for the next text
                order += 1
            # Combine the text into one whole
            sBack = "\n".join(lst_text)

        except:
            msg = oErr.get_error_message()
            oErr.DoError("StemmaStart/prepare_texts")
        return sBack, lst_codes


class StemmaProgress(BasicPart):
    """Start the analysis of the indicated stemmaset"""

    MainModel = StemmaCalc

    def add_to_context(self, context):

        # Gather all necessary data
        data = {}

        oErr = ErrHandle()
        try:
            # Get the StemmaCalc object
            instance = self.obj

            # HERE IS WHERE THE PROGRESS OF THE ANALYSIS IS MONITORED
            data['type'] = "stemma"
            data['status'] = instance.get_status()
            data['message'] = instance.get_message()

            # FIll in the [data] part of the context with all necessary information
            context['data'] = data
        except:
            msg = oErr.get_error_message()
            oErr.DoError("StemmaProgress/add_to_context")
        return context


# =================== Model views for STEMMATOLOGY ========


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
        context['is_stemma_user'] = user_is_ingroup(self.request, stemma_user)
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

        oErr = ErrHandle()
        try:
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


            context['is_stemma_editor'] = user_is_ingroup(self.request, stemma_editor) or context['is_app_moderator']
            context['is_stemma_user'] = user_is_ingroup(self.request, stemma_user)

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

            # Only if the user has permission
            if context['is_stemma_editor']:
                # This user may add items to a StemmaSet
                initial = dict(instance=instance)
                context['stemitemForm'] = EqualSelectForm(initial)
                add_html = render_to_string("stemma/stemitem_add.html", context, self.request)
                context['after_details'] = add_html

            context['permission'] = permission
        except:
            msg = oErr.get_error_message()
            oErr.DoError("StemmaSetEdit/add_to_context")

        # Return the context we have made
        return context

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
                # Interpret the savenew parameter
                savenew = self.qd[arg_savenew]

                # Make sure we are not saving
                self.do_not_save = True
                # But that we do a new redirect
                self.newRedirect = True

                # Change the redirect URL
                if self.redirectpage == "":
                    self.redirectpage = reverse('stemmaset_details', kwargs={'pk': instance.id})

                # What we have is the ordered list of Manuscript id's that are part of this collection
                with transaction.atomic():
                    # Make sure the orders are correct
                    for idx, item_id in enumerate(hlist):
                        order = idx + 1
                        lstQ = [Q(stemmaset=instance)]
                        lstQ.append(Q(**{"id": item_id}))
                        obj = StemmaItem.objects.filter(*lstQ).first()
                        if obj != None:
                            if obj.order != order:
                                obj.order = order
                                obj.save()
                                bChanges = True
                # See if any need to be removed
                existing_item_id = [str(x.id) for x in StemmaItem.objects.filter(stemmaset=instance)]
                delete_id = []
                for item_id in existing_item_id:
                    if not item_id in hlist:
                        delete_id.append(item_id)
                if len(delete_id)>0:
                    lstQ = [Q(stemmaset=instance)]
                    lstQ.append(Q(**{"id__in": delete_id}))
                    StemmaItem.objects.filter(*lstQ).delete()
                    bChanges = True

                if bChanges:
                    # (6) Re-calculate the set of setlists
                    force = True if bDebug else False
                    #instance.update_ssglists(force)

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
            supers['classes'] = ''

            qs_stemmaitem = instance.stemmaset_stemmaitems.all().order_by(
                    'order', 'equal__author__name', 'equal__firstsig', 'equal__srchincipit', 'equal__srchexplicit')
            check_order(qs_stemmaitem)

            # Walk these collection sermons
            for idx, obj in enumerate(qs_stemmaitem):
                rel_item = []
                item = obj.equal

                # SSG: Order in Manuscript
                #add_one_item(rel_item, index, False, align="right")
                #index += 1
                add_one_item(rel_item, obj.order, False, align="right", draggable=True)

                # SSG: Author
                add_one_item(rel_item, self.get_field_value("super", item, "author"), resizable)

                # SSG: Passim code
                add_one_item(rel_item, self.get_field_value("super", item, "code"), resizable) #, False) # , main=True)

                # SSG: Gryson/Clavis = signature
                add_one_item(rel_item, self.get_field_value("super", item, "sig"), resizable) #, False)

                # SSG: Inc/Expl
                add_one_item(rel_item, self.get_field_value("super", item, "incexpl"), resizable, main=True) #, False)

                # SSG: Size (number of SG in equality set)
                add_one_item(rel_item, self.get_field_value("super", item, "size"), resizable) #, False)

                # Actions that can be performed on this item
                if bMayEdit:
                    add_one_item(rel_item, self.get_actions())

                # Add this line to the list
                rel_list.append(dict(id=obj.id, cols=rel_item))
            
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

        oErr = ErrHandle()
        try:
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
                if custom == "code":
                    url = reverse('equalgold_details', kwargs={'pk': instance.id})
                    sBack = "<span class='badge signature ot'><a class='nostyle' href='{}'>{}</a></span>".format(
                        url, sBack)
        except:
            msg = oErr.get_error_message()
            oErr.DoError("StemmaSetDetails/get_field_value")

        return sBack


class StemmaSetAdd(BasicPart):
    """Add a SSG/AF to a stemmaset"""

    MainModel = StemmaSet

    def add_to_context(self, context):

        # Gather all necessary data
        data = {}

        oErr = ErrHandle()
        try:
            # Get the object
            instance = self.obj

            # Check ... something
            if not instance is None:
                mode = self.qd.get("mode")

                if mode == "add_item":
                    # Get the SSG to be added
                    frmThis = EqualSelectForm(self.request.POST)
                    if frmThis.is_valid():
                        cleaned = frmThis.cleaned_data
                        ssgone = cleaned.get("ssgone")
                        # Check if this SSG is not yet part of the StemmaSet
                        obj = StemmaItem.objects.filter(stemmaset=instance, equal=ssgone).first()
                        if obj is None:
                            order = 1
                            largest = StemmaItem.objects.filter(stemmaset=instance).order_by("-order").first()
                            if not largest is None:
                                order = largest.order + 1
                            obj = StemmaItem.objects.create(stemmaset=instance, equal=ssgone, order=order)
                # Make sure to set the correct redirect page
                data['targeturl'] = reverse("stemmaset_details", kwargs={'pk': instance.id})
            # FIll in the [data] part of the context with all necessary information
            context['data'] = data
        except:
            msg = oErr.get_error_message()
            oErr.DoError("StemmaSetAdd/add_to_context")
        return context

