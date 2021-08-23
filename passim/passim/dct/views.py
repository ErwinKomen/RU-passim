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
from django.shortcuts import get_object_or_404, render, redirect
from django.template.loader import render_to_string
from django.template import Context
import json

# ======= imports from my own application ======
from passim.settings import APP_PREFIX, MEDIA_DIR, WRITABLE_DIR
from passim.utils import ErrHandle
from passim.basic.views import BasicList, BasicDetails
from passim.seeker.views import get_application_context, get_breadcrumbs
from passim.seeker.models import SermonDescr, EqualGold, Manuscript, Signature, Profile, CollectionSuper, Collection
from passim.seeker.models import get_crpp_date, get_current_datetime, process_lib_entries, get_searchable, get_now_time
from passim.dct.models import ResearchSet, SetList
from passim.dct.forms import ResearchSetForm


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


def get_passimcode(super_id, super_code):
    code = super_code if super_code and super_code != "" else "(nocode_{})".format(super_id)
    return code

def get_goldsig_dct(super_id):
    """Get the best signature according to DCT rules"""

    sBack = ""
    first = None
    editype_preferences = ['gr', 'cl', 'ot']
    for editype in editype_preferences:
        siglist = Signature.objects.filter(gold__equal_id=super_id, editype=editype).order_by('code').values('code')
        if len(siglist) > 0:
            code = siglist[0]['code']
            sBack = "{}: {}".format(editype, code)
            break
    return sBack

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
    order_cols = ['name', 'saved']
    order_default = ['name', 'saved']
    order_heads = [{'name': 'Name',           'order': 'o=1','type': 'str', 'field': 'name', 'linkdetails': True, 'main': True},
                   {'name': 'Date',           'order': 'o=1','type': 'str', 'custom': 'date', 'align': 'right', 'linkdetails': True},
                ]
    filters = [ {"name": "Name",       "id": "filter_name",      "enabled": False} ]
    searches = [
        {'section': '', 'filterlist': [
            {'filter': 'name', 'dbfield': 'name', 'keyS': 'name'}
            ]}
         ]

    def initializations(self):
        # Some things are needed for initialization
        return None

    def get_field_value(self, instance, custom):
        sBack = ""
        sTitle = ""

        if custom == "date":
            sBack = instance.saved.strftime("%d/%b/%Y %H:%M")

        return sBack, sTitle

    def add_to_context(self, context, initial):

        return context


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

        # Return the context we have made
        return context

    def check_hlist(self, instance):
        """Check if a hlist parameter is given, and hlist saving is called for"""

        oErr = ErrHandle()

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
                    if SetList.objects.filter(researchset=instance, manuscript=manu).count() == 0:
                        # (2) Calculate the JSON list
                        contents = json.dumps( manuscript_ssgs(manu))
                        # (3) Create the new list
                        setlist = SetList.objects.create(
                            researchset=instance, order=order, 
                            setlisttype=setlisttype, manuscript=manu, contents=contents)
                elif hist!= None:
                    # This is a historical collection
                    setlisttype = "hist"
                    # Check its presence
                    if SetList.objects.filter(researchset=instance, collection=hist).count() == 0:
                        # (2) Calculate the JSON list
                        contents = json.dumps( collection_ssgs(hist))
                        # (3) Create the new list
                        setlist = SetList.objects.create(
                            researchset=instance, order=order, 
                            setlisttype=setlisttype, collection=hist, contents=contents)
                elif ssgd != None:
                    # This is a personal or public dataset of SSGs
                    setlisttype = "ssgd"
                    # Check its presence
                    if SetList.objects.filter(researchset=instance, collection=ssgd).count() == 0:
                        # (2) Calculate the JSON list
                        contents = json.dumps( collection_ssgs(ssgd))
                        # (3) Create the new list
                        setlist = SetList.objects.create(
                            researchset=instance, order=order, 
                            setlisttype=setlisttype, collection=ssgd, contents=contents)
                # (4) Re-calculate the order
                instance.adapt_order()
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

        # All PDs: show the content
        related_objects = []
        lstQ = []
        rel_list =[]
        resizable = True
        index = 1
        sort_start = '<span class="sortable"><span class="fa fa-sort sortshow"></span>&nbsp;'
        sort_start_int = '<span class="sortable integer"><span class="fa fa-sort sortshow"></span>&nbsp;'
        sort_end = '</span>'

        oErr = ErrHandle()

        try:

            # Get all 'SetList' objects that are part of this 'ResearchSet'
            setlists = dict(title="Lists within this research set", prefix="setlists")  
            if resizable: setlists['gridclass'] = "resizable dragdrop"
            setlists['savebuttons'] = True
            setlists['saveasbutton'] = False

            qs_setlist = instance.researchset_setlists.all().order_by(
                    'order', 'setlisttype')
            check_order(qs_setlist)

            # Walk these collection sermons
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
                add_one_item(rel_item, self.get_field_value(obj.setlisttype, item, "title"), False, main=True)

                # SetList: Size (number of SSG in this manu/coll)
                add_one_item(rel_item, self.get_field_value(obj.setlisttype, item, "size"), False)

                # Actions that can be performed on this item
                add_one_item(rel_item, self.get_actions())

                # Add this line to the list
                rel_list.append(dict(id=obj.id, cols=rel_item))
            
            setlists['rel_list'] = rel_list
            setlists['columns'] = [
                '{}<span title="Default order">Order<span>{}'.format(sort_start_int, sort_end),
                '{}<span title="Type of setlist">Type of this setlist</span>{}'.format(sort_start, sort_end), 
                '{}<span title="The title of the manuscript/dataset/collection">Title</span>{}'.format(sort_start, sort_end), 
                '{}<span title="Number of SSGs part of this setlist">Size</span>{}'.format(sort_start_int, sort_end), 
                ''
                ]
            related_objects.append(setlists)

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

        # Start the whole spane
        html.append("<div class='blinded'>")
        
        # Add components
        if 'up' in buttons: 
            html.append("<a class='related-up' ><span class='glyphicon glyphicon-arrow-up'></span></a>")
        if 'down' in buttons: 
            html.append("<a class='related-down'><span class='glyphicon glyphicon-arrow-down'></span></a>")
        if 'remove' in buttons: 
            html.append("<a class='related-remove'><span class='glyphicon glyphicon-remove'></span></a>")

        # Finish up the span
        html.append("&nbsp;</span>")

        # COmbine the list into a string
        sHtml = "\n".join(html)
        # Return out HTML string
        return sHtml

    def get_field_value(self, type, instance, custom):
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
                    title = instance.name
                    sBack = "<span class='clickable'><a href='{}' class='nostyle'>{}</a></span>".format(url, title)
            elif custom == "size":
                # Get the number of SSGs related to items in this collection
                count = "-1" if instance is None else instance.super_col.count()
                sBack = "{}".format(count)

        return sBack
