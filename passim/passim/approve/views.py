"""
Definition of views for the APPROVE app.
"""

from django.db.models import Q
from django.urls import reverse
from django.shortcuts import render
from django.template.loader import render_to_string

from passim.seeker.models import COLLECTION_SCOPE, SPEC_TYPE, LINK_TYPE, get_crpp_date, \
    Author, Collection, Profile, EqualGold, Collection, CollectionSuper, Manuscript, SermonDescr, \
    Keyword, SermonGold, EqualGoldLink, FieldChoice
from passim.approve.models import EqualChange
from passim.approve.forms import EqualChangeForm
from passim.basic.views import BasicList, BasicDetails

import json, copy

# Take from my own app
from passim.utils import ErrHandle


def get_goldset_html(goldlist):
    context = {}
    template_name = 'seeker/super_goldset.html'
    sBack = ""
    if goldlist != None:
        # Add to context
        context['goldlist'] = SermonGold.objects.filter(id__in=goldlist).order_by('siglist')
        context['is_app_editor'] = False
        context['object_id'] = None
        # Calculate with the template
        sBack = render_to_string(template_name, context)
    return sBack

def equalchange_json_to_html(instance, type):
    """Convert the proposed change from JSON into an HTML representation"""

    html = []
    oErr = ErrHandle()
    try:
        # Get the field's value
        attrvalue = getattr(instance, type)
        if attrvalue != None and attrvalue != "":
            oItem = json.loads(attrvalue)
            # Find out what type this is
            field = oItem.get('field')
            if field != None:
                if field == "author":
                    # Process author FK
                    author_id = oItem.get("id")
                    if author_id != None and author_id != "":
                        author = Author.objects.filter(id=author_id).first()
                        if author != None:
                            authorname = author.name
                            # Add to html
                            html.append(authorname)
                elif field == "incipit":
                    # Process incipit string
                    incipit = oItem.get("text")
                    # Add to html
                    html.append(incipit)
                elif field == "explicit":
                    # Process explicit string
                    explicit = oItem.get("text")
                    # Add to html
                    html.append(explicit)
                elif field == "keywords":
                    # Process list of FK-to-keyword
                    kwlist = oItem.get('kwlist')
                    if kwlist != None:
                        # Process the list
                        qs = Keyword.objects.filter(id__in=kwlist).values('name')
                        lst_kw = []
                        for kw in qs:
                            # Create a display for this topic
                            lst_kw.append("<span class='keyword'>{}</span>".format(kw['name']))
                        html.append(", ".join(lst_kw))
                elif field == "hcs":
                    # Process list of FK-to-collection
                    hclist = oItem.get('collist_hist')
                    if hclist != None:
                        # Process the list
                        qs = Collection.objects.filter(id__in=hclist).values('name')
                        lst_hc = []
                        for hc in qs:
                            # Create a display for this topic
                            lst_hc.append("<span class='collection'>{}</span>".format(hc['name']))
                        html.append(", ".join(lst_hc))
                elif field == "golds":
                    # Process list of FK-to-SermonGold
                    goldlist = oItem.get('goldlist')
                    if goldlist != None:
                        # Process the list
                        html.append(get_goldset_html(goldlist))
                elif field == "supers":
                    # Process list of EqualGoldLink specifications
                    linklist = oItem.get('superlist')
                    if linklist != None:
                        # TODO: Process the list
                        lst_super = []
                        number = 0
                        for superlink in linklist:
                            lst_super.append("<tr class='view-row'>")
                            sSpectype = ""
                            sAlternatives = ""
                            number += 1

                            # Get the values from [superlink]
                            linktype = superlink.get("linktype")
                            spectype = superlink.get("spectype")
                            alternatives = superlink.get("alternatives")
                            note = superlink.get("note")
                            dst_id = superlink.get("dst")
                            dst = SermonGold.objects.filter(id=dst_id).first()

                            if spectype != None and len(spectype) > 1:
                                # Show the specification type
                                sSpectype = "<span class='badge signature gr'>{}</span>".format(
                                    FieldChoice.get_english(SPEC_TYPE, spectype))
                            if alternatives != None and alternatives == "true":
                                sAlternatives = "<span class='badge signature cl' title='Alternatives'>A</span>"
                            lst_super.append("<td valign='top' class='tdnowrap'><span class='badge signature ot'>{}</span>{}</td>".format(
                                FieldChoice.get_english(LINK_TYPE, linktype), sSpectype))

                            sTitle = ""
                            sNoteShow = ""
                            sNoteDiv = ""
                            if note != None and len(note) > 1:
                                sTitle = "title='{}'".format(note)
                                sNoteShow = "<span class='badge signature btn-warning' title='Notes' data-toggle='collapse' data-target='#ssgnote_{}'>N</span>".format(
                                    number)
                                sNoteDiv = "<div id='ssgnote_{}' class='collapse explanation'>{}</div>".format(
                                    number, note)
                            url = reverse('equalgold_details', kwargs={'pk': dst_id})
                            lst_super.append("<td valign='top'><a href='{}' {}>{}</a>{}{}{}</td>".format(
                                url, sTitle, dst.get_view(), sAlternatives, sNoteShow, sNoteDiv))
                            lst_super.append("</tr>")
                        if len(lst_super) > 0:
                            html.append("<table><tbody>{}</tbody></table>".format( "".join(lst_super)))
        else:
            html.append("empty")
    except:
        msg = oErr.get_error_message()
        oErr.DoError("equalchange_json_to_html")

    # Return the HTML as a string
    sBack = "\n".join(html)
    return sBack

def approval_parse_changes(profile, cleaned_data, super):
    """Check if there are any changes, add them into EqualChange objects, and return how many there are"""

    oErr = ErrHandle()
    iCount = 0
    try:
        # Get the current data: this is the old stuff
        current = EqualGold.objects.filter(id=super.id).first()

        # Check how many projects are connected to this ssG:
        projects = current.projects.all()
        if projects.count() > 1:

            # Check for changes
            for oField in EqualChange.approve_fields:
                # Get all possible field attributes
                field = oField.get("field")
                type = oField.get("type")
                to_field = oField.get("tofld")
                listfield = oField.get("listfield")
                lstQ = oField.get("lstQ")

                # Action depends on the type this is
                bAddChange = False
                if type == "string":
                    # Get the current text
                    sTextCurrent = getattr(current, field)
                    # Get the suggestion text
                    sTextChange = cleaned_data[field]

                    # Signal that the change needs processing
                    if sTextChange != sTextCurrent:
                        oCurrent = dict(field=to_field, text=sTextCurrent)
                        oChange = dict(field=to_field, text=sTextChange)
                        bAddChange = True
                elif type == "fk":
                    # Get the current id (FK)
                    id_current = None if getattr(current, field) is None else getattr(current, field).id
                    # Get the suggestion id (FK)
                    id_change = None if cleaned_data[field] is None else cleaned_data[field].id

                    # Signal that the change needs processing
                    if id_change != id_current:
                        oCurrent = dict(field=to_field, id=id_current)
                        oChange = dict(field=to_field, id=id_change)
                        bAddChange = True

                elif type == "m2m-inline" or type == "m2o" or type == "m2m-addable":
                    # Get the current m2m values as a list of id's
                    if lstQ is None:
                        lst_id_current = [x['id'] for x in getattr(current, field).all().values("id")]
                    else:
                        lst_id_current = [x['id'] for x in getattr(current, field).filter(*lstQ).values("id")]
                    # Get the suggestion
                    lst_id_change = [x.id for x in cleaned_data[listfield]]
                    
                    # Signal that the change needs processing
                    if set(lst_id_change) != set(lst_id_current):
                        oCurrent = dict(field=to_field)
                        oCurrent[listfield] = lst_id_current
                        oChange = dict(field=to_field)
                        oChange[listfield] = lst_id_change
                        bAddChange = True

                # Does the change need to be processed?
                if bAddChange:
                    # Create a new EqualChange object
                    obj = EqualChange.add_item(super, profile, to_field, oChange, oCurrent)
                    # Signal the amount of changes that are to be approved
                    iCount += 1

    except:
        msg = oErr.get_error_message()
        oErr.DoError("approval_parse_changes")
        iCount = 0
    return iCount

def approval_parse_formset(profile, frm_prefix, new_data, super):
    """Check if the addition of this form in a formset needs approval, and if so add an EqualChange object"""

    oErr = ErrHandle()
    iCount = 0
    try:
        # Get the current data: this is the old stuff
        current = EqualGold.objects.filter(id=super.id).first()

        # Check how many projects are connected to this ssG:
        projects = current.projects.all()
        if projects.count() > 1:

            # Check for the right field information
            for oForm in EqualChange.approve_fields:
                prefix = oForm.get("prefix")
                if not prefix is None and prefix == frm_prefix:
                    # Get the fields to be processed of this form
                    to_field = oForm.get("tofld")
                    listfield = oForm.get("listfield")

                    # Create a dictionary with these values
                    oChange = dict(field=to_field)

                    oFields = oForm.get('formfields')
                    oItem = {}
                    for oField in oFields:
                        # Get the field name and the type
                        field = oField.get("field")
                        type = oField.get("type")

                        oItem[field] = new_data.get(field)
                    oChange[listfield] = [ oItem ]

                    # Note: sThe dictionary with current values is empty, since it is an addition

                    # Create a new EqualChange object
                    obj = EqualChange.add_item(super, profile, to_field, oChange)
                    # Signal that one has been created
                    iCount += 1
    except:
        msg = oErr.get_error_message()
        oErr.DoError("approval_parse_formset")
        iCount = 0
    return iCount

def approval_pending(super):
    """Get all pending approvals"""

    atype_list = ['def', 'mod']
    qs = EqualChange.objects.filter(super=super, atype__in=atype_list)
    return qs

def approval_pending_list(super):
    """GEt a list of pending approvals"""

    oErr = ErrHandle()
    html = []
    try:
        qs = approval_pending(super)
        for obj in qs:
            saved = obj.created.strftime("%d/%b/%Y %H:%M") if not obj.saved else obj.saved.strftime("%d/%b/%Y %H:%M")
            oApproval = dict(
                field=obj.get_display_name(),
                editor=obj.profile.user.username,
                atype=obj.get_atype_display(),
                created=obj.created.strftime("%d/%b/%Y %H:%M"),
                saved=saved,
                change=equalchange_json_to_html(obj, "change"))
            html.append(oApproval)
    except:
        msg = oErr.get_error_message()
        oErr.DoError("approval_pending_list")
    return html


# ========================================================= MODEL views =========================================================

class EqualChangeListView(BasicList):
    """Listview of EqualChange"""

    model = EqualChange
    listform = EqualChangeForm
    has_select2 = True
    bUseFilter = True
    new_button = False
    use_team_group = True
    prefix = "any"
    basic_name_prefix = "equalchange"
    order_cols = ['profile__user__username', 'saved', 'super__code', 'field', 'atype']
    order_default = ['profile__user__username', '-saved', 'super__code', 'field', 'atype']
    order_heads = [
        {'name': 'User',            'order': 'o=1', 'type': 'str', 'custom': 'user',    'linkdetails': True},
        {'name': 'Date',            'order': 'o=2', 'type': 'str', 'custom': 'date',    'linkdetails': True},
        {'name': 'Authority File',  'order': 'o=3', 'type': 'str', 'custom': 'code',    'linkdetails': True, 'align': 'right'},
        {'name': 'Field',           'order': 'o=4', 'type': 'str', 'custom': 'field',   'linkdetails': True, 'main': True},
        {'name': 'Status',          'order': 'o=5', 'type': 'str', 'custom': 'atype',   'linkdetails': True},
        ]
    filters = [ 
        {"name": "Authority File",  "id": "filter_code",      "enabled": False},
        {"name": "User",            "id": "filter_user",      "enabled": False},
        ]
    searches = [
        {'section': '', 'filterlist': [
            {'filter': 'code',          'fkfield': 'super',    'help': 'passimcode',
             'keyS': 'passimcode', 'keyFk': 'code', 'keyList': 'passimlist', 'infield': 'id'},
            {'filter': 'user', 'fkfield': 'profile', 'keyFk': 'id', 'keyList': 'profilelist', 'infield': 'id'}
            ]},
        {'section': 'other', 'filterlist': [
            {'filter': 'atype',     'dbfield': 'atype',    'keyS': 'atype'},
            ]}
         ]

    def initializations(self):
        if self.prefix == "any":
            # Provide all changes
            self.plural_name = "All field changes"
            self.sg_name = "Field change"
        elif self.prefix == "user":
            # Restricted to a particular user...
            self.plural_name = "User field changes"
            self.sg_name = "User field change"
            self.order_cols = ['saved', 'super__code', 'field', 'atype']
            self.order_default = ['saved', 'super__code', 'field', 'atype']
            self.order_heads = [
                {'name': 'Date',            'order': 'o=1', 'type': 'str', 'custom': 'date',    'linkdetails': True},
                {'name': 'Authority File',  'order': 'o=2', 'type': 'str', 'custom': 'code',    'linkdetails': True, 'align': 'right'},
                {'name': 'Field',           'order': 'o=3', 'type': 'str', 'custom': 'field',   'linkdetails': True, 'main': True},
                {'name': 'Status',          'order': 'o=4', 'type': 'str', 'custom': 'atype',   'linkdetails': True},
                ]
            self.filters = [{"name": "Authority File",       "id": "filter_code",      "enabled": False}]
            self.searches = [
                {'section': '', 'filterlist': [
                    {'filter': 'code',          'fkfield': 'super',    'help': 'passimcode',
                     'keyS': 'passimcode', 'keyFk': 'code', 'keyList': 'passimlist', 'infield': 'id'},
                    ]},
                {'section': 'other', 'filterlist': [
                    {'filter': 'atype',     'dbfield': 'atype',    'keyS': 'atype'},
                    ]}
                 ]
        return None

    def get_field_value(self, instance, custom):
        sBack = ""
        sTitle = ""
        if custom == "date":
            saved = instance.created if instance.saved is None else instance.saved
            sBack = saved.strftime("%d/%b/%Y %H:%M")
        elif custom == "user":
            sBack = instance.profile.user.username
        elif custom == "atype":
            sBack = instance.get_atype_display()
        elif custom == "code":
            sBack = instance.get_code()
        elif custom == "field":
            sBack = instance.get_display_name()
        return sBack, sTitle


class EqualChangeUserListview(EqualChangeListView):
    """User-specific view of proposed changes"""

    prefix = "user"


class EqualChangeEdit(BasicDetails):
    model = EqualChange
    mForm = EqualChangeForm
    prefix = "any"
    basic_name_prefix = "equalchange"
    title = "Field change"
    no_delete = True            # Don't allow users to remove a field change that they have entered
    mainitems = []

    def add_to_context(self, context, instance):
        """Add to the existing context"""

        # Need to know who this user (profile) is
        profile = Profile.get_user_profile(self.request.user.username)

        # Define the main items to show and edit
        context['mainitems'] = []

        # Add user or not?
        if self.prefix == "user":
            context['mainitems'].append({'type': 'line',  'label': "User:",'value': instance.profile.user.username})

        # Add the normal information
        mainitems_main = [
            # -------- HIDDEN field values (these are defined in [EqualChangeForm] ---------------
            {'type': 'plain', 'label': "Profile id",    'value': profile.id,        'field_key': "profile", 'empty': 'hide'},
            {'type': 'plain', 'label': "Super id",      'value': instance.super.id, 'field_key': "super",   'empty': 'hide'},
            {'type': 'plain', 'label': "Field val",     'value': instance.field,    'field_key': "field",   'empty': 'hide'},
            {'type': 'plain', 'label': "Atype val",     'value': instance.atype,    'field_key': "atype",   'empty': 'hide'},
            # --------------------------------------------
            {'type': 'plain', 'label': "Authority File:",'value': instance.get_code()}, #,          'field_key': 'super'},
            {'type': 'plain', 'label': "Field:",        'value': instance.get_display_name()}, #,   'field_key': 'field'},
            {'type': 'plain', 'label': "Date:",         'value': instance.get_saved()},
            {'type': 'plain', 'label': "Status:",       'value': instance.get_atype_display()}, #,  'field_key': 'atype'},
            {'type': 'safe',  'label': "Current:",      'value': equalchange_json_to_html(instance, "current")},
            {'type': 'safe',  'label': "Proposed:",     'value': equalchange_json_to_html(instance, "change")},
            ]
        for item in mainitems_main: 
            context['mainitems'].append(item)

        # Signal that we do have select2
        context['has_select2'] = True

        # Return the context we have made
        return context


class EqualChangeDetails(EqualChangeEdit):
    """HTML output for an EqualChange object"""

    rtype = "html"


class EqualChangeUserEdit(EqualChangeEdit):
    """User-specific equal change editing"""
    
    prefix = "user"
    title = "Field change"


class EqualChangeUserDetails(EqualChangeUserEdit):
    """HTML output for an EqualChangeUser object"""

    rtype = "html"


