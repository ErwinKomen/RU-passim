"""
Definition of views for the APPROVE app.
"""

from django.db import transaction
from django.db.models import Q
from django.urls import reverse
from django.shortcuts import render
from django.template.loader import render_to_string

from passim.seeker.models import COLLECTION_SCOPE, SPEC_TYPE, LINK_TYPE, LINK_BIDIR, \
    get_crpp_date, get_current_datetime, get_reverse_spec,  \
    Author, Collection, Profile, EqualGold, Collection, CollectionSuper, Manuscript, SermonDescr, \
    Keyword, SermonGold, EqualGoldLink, FieldChoice, EqualGoldKeyword, Project2, ProjectApprover
from passim.approve.models import EqualChange, EqualApproval, EqualAdd, EqualAddApproval
from passim.approve.forms import EqualChangeForm, EqualApprovalForm, EqualAddForm, EqualAddApprovalForm
from passim.basic.views import BasicList, BasicDetails, adapt_m2m, adapt_m2o, add_rel_item, app_editor

import json, copy

# Take from my own app
from passim.utils import ErrHandle

# =================================== SUPPORT functions API ====================================================================

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

def equaladd_to_accept(instance):
    """Accept the addition or deletion of the SSG : implement it and set my status
    
    Note: the [instance] is an object EqualAdd
    """

    oErr = ErrHandle()
    bBack = True
    try:
        # Figure out whether this is an addition or a delection
        action = instance.action
        action_message = "addition to" if action == "add" else "removal from"

        # Get to the actual SSG
        super = instance.super

        if action == "add":
            # We must add the SSG: change the SSG's atype to 'acc'
            super.atype = "acc"
            super.save()
            # Add the project to this SSG
            super.projects.add(instance.project)
            # Make sure that our addition or deletion to accepted
            instance.atype = "acc"

        elif action == "rem":
            # The action is to delete the project from this SSG
            super.projects.remove(instance.project)
            # Make sure that our deletion is set to accepted
            instance.atype = "acc"
        elif action == "del":
            # The action is to delete the SSG altogether
            instance.atype = "acc"
            # Perform the actual deletion
            super.delete()
        else:
            oErr.Status("equaladd_to_accept: unknown action [{}]".format(action))
            return bBack

        # Finish off the comment
        instance.comment = "This project {} the SSG/AF has been successfully processed on: {}".format(
            action_message, get_crpp_date(get_current_datetime(), True))
        instance.save()

    except:
        msg = oErr.get_error_message()
        oErr.DoError("equaladd_to_accept")
        bBack = False
    return bBack

def equalchange_json_to_html(instance, type, profile=None):
    """Convert the proposed change from JSON into an HTML representation"""

    def link_to_row(superlink, number):
        """Translate one link into HTML table row"""

        sBack = ""
        html = []
        try:
            html.append("<tr class='view-row'>")
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
            html.append("<td valign='top' class='tdnowrap'><span class='badge signature ot'>{}</span>{}</td>".format(
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
            if dst is None:
                url = "(removed)"
                dst_view = "(dst was: {})".format(dst_id)
            else:
                url = reverse('equalgold_details', kwargs={'pk': dst_id})
                dst_view = dst.get_view()
            html.append("<td valign='top'><a href='{}' {}>{}</a>{}{}{}</td>".format(
                url, sTitle, dst_view, sAlternatives, sNoteShow, sNoteDiv))
            html.append("</tr>")

            # Combine
            sBack = "\n".join(html)
        except:
            msg = oErr.get_error_message()
            oErr.DoError("link_to_row")
        return number, sBack

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
                elif field == "fulltext":
                    # Process fulltext string
                    fulltext = oItem.get("text")
                    # Add to html
                    html.append(fulltext)
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
                        if profile is None:
                            other_priv_hcs = []
                        else:
                            # Adapt the list: remove all private HCs from which I am not the owner
                            other_priv_hcs = [x['id'] for x in Collection.objects.filter(id__in=hclist, settype='hc', scope='priv').exclude(owner=profile).values('id')]

                        # Process the list
                        qs = Collection.objects.filter(id__in=hclist).values('id', 'name', 'owner__user__username')
                        lst_hc = []
                        for hc in qs:
                            # Create a display for this topic
                            if hc['id'] in other_priv_hcs:
                                lst_hc.append("<span class='collection private' title='This is a private HC of {}'><b>P</b> {}</span>".format(
                                    hc['owner__user__username'], hc['name']))
                            else:
                                lst_hc.append("<span class='collection'>{}</span>".format(hc['name']))
                        html.append(", ".join(lst_hc))
                elif field == "golds":
                    # Process list of FK-to-SermonGold
                    goldlist = oItem.get('goldlist')
                    if goldlist != None:
                        # Process the list
                        html.append(get_goldset_html(goldlist))
                elif field == "supers":
                    # Needed for super processing
                    number = 0
                    # Process list of EqualGoldLink specifications
                    linklist = oItem.get('superlist', [])
                    if len(linklist) > 0:
                        # TODO: Process the list
                        lst_super = []
                        for superlink in EqualGoldLink.objects.filter(id__in=linklist).values('dst', 'linktype', 'spectype', 'alternatives', 'note'):
                            number, oLink = link_to_row(superlink, number)
                            lst_super.append(oLink)
                        if len(lst_super) > 0:
                            html.append("<h4>Set of links:</h4><table><tbody>{}</tbody></table>".format( "".join(lst_super)))

                    # Check if links have been added via 'formfields'
                    lst_adding = oItem.get('formfields', [])
                    if len(lst_adding) > 0:
                        # TODO: Process the list
                        lst_super = []
                        for superlink in lst_adding:
                            number, oLink = link_to_row(superlink, number)
                            lst_super.append(oLink)
                        if len(lst_super) > 0:
                            html.append("<h4>Adding:</h4><table><tbody>{}</tbody></table>".format( "".join(lst_super)))

        elif instance.field == "supers":
            html.append("<i>(no changes)</i>")
        else:
            html.append("empty")
    except:
        msg = oErr.get_error_message()
        oErr.DoError("equalchange_json_to_html")

    # Return the HTML as a string
    sBack = "\n".join(html)
    return sBack

def equalchange_json_to_accept(instance):
    """Accept the change: implement it and set my status"""

    def link_add(super, oItem):
        """Add the superlink, connecting it to [super]"""

        obj = None
        try:
            # Get the correct information from [oItem]
            linktype = oItem.get("linktype")
            alternatives = oItem.get("alternatives")
            spectype = oItem.get("spectype")
            note = oItem.get("note")
            dst_id = oItem.get("dst")
            if dst_id != None and linktype != None and spectype != None:
                # This should create and save a link
                obj = EqualGoldLink.objects.create(src=super, dst_id=dst_id, linktype=linktype,
                        spectype=spectype, alternatives=alternatives, note=note)
        except:
            msg = oErr.get_error_message()
            oErr.DoError("equalchange_json_to_accept/link_add")
        return obj

    oErr = ErrHandle()
    bBack = True
    try:
        # Execute the change
        oItem = json.loads(instance.change)
        # Make sure we have the SSG object ready
        super = instance.super
        bSuperNeedSaving = False
        # Find out what type this is
        field = oItem.get('field')
        if field != None:
            if field == "author":
                # Process author FK
                author_id = oItem.get("id")
                if author_id != None and author_id != "":
                    author = Author.objects.filter(id=author_id).first()
                    if author != None:
                        # First: possibly create a moved
                        moved = EqualGold.create_moved(super)
                        # Assign it to the SSG
                        super.author = author
                        bSuperNeedSaving = True
            elif field == "incipit":
                # Process incipit string
                super.incipit = oItem.get("text")
                bSuperNeedSaving = True
            elif field == "explicit":
                # Process explicit string
                super.explicit = oItem.get("text")
                bSuperNeedSaving = True
            elif field == "keywords":
                # Process list of FK-to-keyword
                kwlist_ids = oItem.get('kwlist')
                if kwlist_ids != None:
                    kwlist = Keyword.objects.filter(id__in=kwlist_ids)
                    adapt_m2m(EqualGoldKeyword, super, "equal", kwlist, "keyword")

            elif field == "hcs":
                # Process list of FK-to-collection
                hclist = oItem.get('collist_hist')
                if hclist != None:
                    collist_ssg = Collection.objects.filter(id__in=hclist)
                    adapt_m2m(CollectionSuper, super, "super", collist_ssg, "collection")
            elif field == "golds":
                # Process list of FK-to-SermonGold
                goldlist_ids = oItem.get('goldlist')
                if goldlist_ids != None:
                    # Process the list
                    goldlist = SermonGold.objects.filter(id__in=goldlist_ids)
                    ssglist = [x.equal for x in goldlist]
                    adapt_m2o(SermonGold, super, "equal", goldlist)
                    # Adapt the SSGs needed
                    for ssg in ssglist:
                        # Adapt the SG count value
                        ssg.set_sgcount()
                        # Adapt the 'firstsig' value
                        ssg.set_firstsig()

            elif field == "supers":
                # Both changes as well as additions need the [super_added] lists
                super_added = []
                # Process list of EqualGoldLink specifications
                superlist = oItem.get('superlist')
                if superlist != None:
                    # Emend the [superlist], which should be a qs
                    superlist = EqualGoldLink.objects.filter(id__in=superlist)
                    # Process the list
                    super_deleted = []
                    adapt_m2m(EqualGoldLink, super, "src", superlist, "dst", 
                              extra = ['linktype', 'alternatives', 'spectype', 'note'], related_is_through=True,
                              added=super_added, deleted=super_deleted)
                    # Check for partial links in 'deleted'
                    for obj in super_deleted:
                        # This if-clause is not needed: anything that needs deletion should be deleted
                        # if obj.linktype in LINK_BIDIR:
                        # First find and remove the other link
                        reverse = EqualGoldLink.objects.filter(src=obj.dst, dst=obj.src, linktype=obj.linktype).first()
                        if reverse != None:
                            reverse.delete()
                        # Then remove myself
                        obj.delete()
                # Check if links have been added via 'formfields'
                lst_adding = oItem.get('formfields')
                if lst_adding != None:
                    # Process the list of items to be added
                    for oItem in lst_adding:
                        # Create a new EqualGoldLink based on [oItem]
                        obj = link_add(super, oItem)
                        # Add this item in the super_added list
                        super_added.append(obj)

                # Make sure to add the reverse link in the bidirectionals
                for obj in super_added:
                    if obj.linktype in LINK_BIDIR:
                        # Find the reversal
                        reverse = EqualGoldLink.objects.filter(src=obj.dst, dst=obj.src, linktype=obj.linktype).first()
                        if reverse == None:
                            # Create the reversal 
                            reverse = EqualGoldLink.objects.create(src=obj.dst, dst=obj.src, linktype=obj.linktype)
                            # Other adaptations
                            bNeedSaving = False
                            # Set the correct 'reverse' spec type
                            if obj.spectype != None and obj.spectype != "":
                                reverse.spectype = get_reverse_spec(obj.spectype)
                                bNeedSaving = True
                            # Possibly copy note
                            if obj.note != None and obj.note != "":
                                reverse.note = obj.note
                                bNeedSaving = True
                            # Need saving? Then save
                            if bNeedSaving:
                                reverse.save()

            # Need any saving?
            if bSuperNeedSaving:
                # Save the SSG
                super.save()

        # Make sure that our state changes to accepted
        instance.atype = "acc"
        instance.comment = "This change has been successfully processed on: {}".format(get_crpp_date(get_current_datetime(), True))
        instance.save()
    except:
        msg = oErr.get_error_message()
        oErr.DoError("equalchange_json_to_accept")
        bBack = False
    return bBack

def approval_parse_adding(profile, qs_projlist, super, allow_adding = None):
    """Process this user [profile] suggesting to ADD SSG [super] to projects [qs_projlist]
    
    Note: this function is called from seeker/view EqualGoldEdit, before_save()
    """

    oErr = ErrHandle()
    iCount = 0
    try:
        # Walk all the projects to which this project is supposed to be added
        if len(qs_projlist) > 0:
            for prj in qs_projlist:
                # Check if we have an EqualAdd object for this
                #  (don't include [profile] in this test; a different user may have suggested the same thing)
                obj = EqualAdd.objects.filter(project=prj, super=super, action="add").first()                
                if obj is None:
                    # Double check conditions: 
                    # (1) status of the current user
                    is_approver = profile.projects.filter(id=prj.id).exists()
                    # (2) number of approvers for this project
                    num_approvers = prj.project_approver.count()

                    if is_approver and num_approvers == 1:
                        # There is no need to ask for approval: the project may be added right away
                        if not allow_adding is None:
                            # Add info to allow_adding
                            allow_adding.append(dict(project=prj, super=super))
                    else:
                        # Create an object
                        obj = EqualAdd.objects.create(project=prj, super=super, profile=profile, action="add") 
                        # Increment the counter
                        iCount += 1

    except:
        msg = oErr.get_error_message()
        oErr.DoError("approval_parse_adding")
        iCount = 0
    return iCount

def approval_parse_removing(profile, qs_projlist, super, allow_removing = None):
    """Process this user [profile] suggesting to REMOVE SSG [super] from projects [qs_projlist]
    
    Note: this function is called from seeker/view EqualGoldEdit, before_save()
    """

    oErr = ErrHandle
    iCount = 0
    try:
        # Walk all the projects to which this project is supposed to be added
        if len(qs_projlist) > 0:
            for prj in qs_projlist:
                # Check if we have an EqualAdd object for this
                #  (don't include [profile] in this test; a different user may have suggested the same thing)
                obj = EqualAdd.objects.filter(project=prj, super=super, action="rem").first()                
                if obj is None:
                    # Double check conditions: 
                    # (1) number of projects attached to this SSG
                    count_projects = super.projects.count()
                    # (2) status of the current user
                    is_approver = profile.projects.filter(id=prj.id).exists()
                    # (3) number of approvers for this project
                    num_approvers = prj.project_approver.count()

                    if count_projects > 1 and is_approver and num_approvers == 1:
                        # There is no need to ask for approval: the project may be removed right away
                        if not allow_removing is None:
                            # Add info to allow_removing
                            allow_removing.append(dict(project=prj, super=super))
                    else:
                        # Create an object
                        obj = EqualAdd.objects.create(project=prj, super=super, profile=profile, action="rem") 
                        # Increment the counter
                        iCount += 1

    except:
        msg = oErr.get_error_message()
        oErr.DoError("approval_parse_removing")
        iCount = 0
    return iCount

def approval_parse_deleting(profile, qs_projlist, super):
    """Process this user [profile] suggesting to REMOVE SSG [super] altogether
    
    Note: this function is called from seeker/view EqualGoldEdit, before_save()
    """

    oErr = ErrHandle()
    iCount = 0
    action = "del"
    try:
        # Walk all the projects to which this SSG belongs
        if qs_projlist.count() > 1:
            # (1) Get all projects attached to this SSG
            proj_all_ids = [x.id for x in super.projects.all()]
            # (2) Figur out all projects to which [profile] has editor access
            proj_profile_ids = [x.id for x in profile.projects.all()]
            # proj_profile_ids = [x.project.id for x in ProjectApprover.objects.filter(profile=profile, status="incl")]
            # (3) get the list of projects for which consent is needed
            proj_need_ids = []
            for prj_id in proj_all_ids:
                if not prj_id in proj_profile_ids:
                    proj_need_ids.append(prj_id)
            # Check if any action is required
            if len(proj_need_ids) > 0:
                # We need to check agreement for all projects in this list
                for prj_id in proj_need_ids:
                    # Check if we have an EqualAdd object for this
                    #  (don't include [profile] in this test; a different user may have suggested the same thing)
                    obj = EqualAdd.objects.filter(project_id=prj_id, super=super, action=action).first()                
                    if obj is None:
                        # Create an object
                        obj = EqualAdd.objects.create(project_id=prj_id, super=super, profile=profile, action=action) 
                    # Increment the counter
                    iCount += 1

    except:
        msg = oErr.get_error_message()
        oErr.DoError("approval_parse_deleting")
        iCount = 0
    return iCount

def approval_parse_changes(profile, cleaned_data, super):
    """Check if there are any changes, add them into EqualChange objects, and return how many there are"""

    oErr = ErrHandle()
    iCount = 0
    bNeedReload = False
    try:
        # Get the current data: this is the old stuff
        current = EqualGold.objects.filter(id=super.id).first()

        # Check how many projects are connected to this ssG:
        projects = current.projects.all()
        if projects.count() > 1:

            # Check if this person has approval rights in the projects above
            profile_projects = [x['project__id'] for x in profile.project_approver.all().values("project__id")]
            lst_need = []
            for project in projects:
                if not project.id in profile_projects:
                    lst_need.append(project.id)

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
                    sTextCurrent = getattr(current, to_field)
                    # Get the suggestion text
                    sTextChange = cleaned_data[field]

                    # Signal that the change needs processing
                    if sTextChange != sTextCurrent:
                        oCurrent = dict(field=to_field, text=sTextCurrent)
                        oChange = dict(field=to_field, text=sTextChange)
                        bAddChange = True
                elif type == "fk":
                    # Get the current id (FK)
                    id_current = None if getattr(current, to_field) is None else getattr(current, to_field).id
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

                    # Special processing?
                    if to_field == "hcs":
                        # This is special - the lst_id_change must include all private HCs from other people for this particular collection
                        hc_others = Collection.objects.filter(super_col__super=current, settype="hc", scope="priv").exclude(owner=profile).values('id')
                        for item in hc_others:
                            lst_id_change.append(item['id'])
                    
                    # Signal that the change needs processing
                    if set(lst_id_change) != set(lst_id_current):
                        oCurrent = dict(field=to_field)
                        oCurrent[listfield] = lst_id_current
                        oChange = dict(field=to_field)
                        oChange[listfield] = lst_id_change
                        bAddChange = True

                # Does the change need to be processed?
                if bAddChange:
                    # Do we need the consent of other projects?
                    if len(lst_need) == 0:
                        # The current person may approve any other pending changes that result in [oChange]
                        change = json.dumps(oChange, sort_keys=True)
                        qs = EqualChange.objects.filter(super=super, field=to_field, change=change)
                        for obj in qs:
                            obj.atype = "app"
                            obj.save()

                    else:
                        # Create a new EqualChange object
                        obj = EqualChange.add_item(super, profile, to_field, oChange, oCurrent)
                        # Signal the amount of changes that are to be approved
                        iCount += 1
                        # Signal that the user needs to do a clean-reloading of the page
                        if listfield == "superlist":
                            # Signal reloading
                            bNeedReload = True
                            ## Repair the cleaned_data - doesn't work like that, unfortunately...
                            #cleaned_data['superlist'] = EqualGoldLink.objects.filter(id__in=lst_id_current)

    except:
        msg = oErr.get_error_message()
        oErr.DoError("approval_parse_changes")
        iCount = 0
    return iCount, bNeedReload

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
                    # listfield = oForm.get("listfield")
                    # formfields = oForm.get("formfields")

                    # Create a dictionary with these values
                    oChange = dict(field=to_field)

                    oFields = oForm.get('formfields')
                    oItem = {}
                    for oField in oFields:
                        # Get the field name and the type
                        field = oField.get("field")
                        type = oField.get("type")

                        oItem[field] = new_data.get(field)
                    # oChange[listfield] = [ oItem ]
                    oChange["formfields"] = [ oItem ]

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
    """Get all pending approvals for SSG changes"""

    qs = EqualChange.objects.none()
    if not super is None:
        atype_list = ['def', 'mod']
        qs = EqualChange.objects.filter(super=super, atype__in=atype_list)
    return qs

def addapproval_pending(super):
    """Get all pending approvals for SSG additions"""

    qs = EqualAdd.objects.none()
    if not super is None:
        atype_list = ['def', 'mod']
        qs = EqualAdd.objects.filter(super=super, atype__in=atype_list)
    return qs

def approval_pending_list(super):
    """Get a list of pending approvals for SSG changes"""

    oErr = ErrHandle()
    html = []
    try:
        qs = approval_pending(super)
        for obj in qs:
            saved = obj.created.strftime("%d/%b/%Y %H:%M") if not obj.saved else obj.saved.strftime("%d/%b/%Y %H:%M")
            oApproval = dict(
                id=obj.id,
                field=obj.get_display_name(),
                editor=obj.profile.user.username,
                atype=obj.get_atype_display(),
                statushistory = obj.get_status_history(),
                created=obj.created.strftime("%d/%b/%Y %H:%M"),
                saved=saved,
                change=equalchange_json_to_html(obj, "change"))
            html.append(oApproval)
    except:
        msg = oErr.get_error_message()
        oErr.DoError("approval_pending_list")
    return html

def addapproval_pending_list(super):
    """Get a list of pending approvals for SSG additions"""

    oErr = ErrHandle()
    html = []
    try:
        qs = addapproval_pending(super)
        for obj in qs:
            saved = obj.created.strftime("%d/%b/%Y %H:%M") if not obj.saved else obj.saved.strftime("%d/%b/%Y %H:%M")
            oApproval = dict(
                id=obj.id,                
                editor=obj.profile.user.username,
                atype=obj.get_atype_display(),
                statushistory = obj.get_status_history(),
                created=obj.created.strftime("%d/%b/%Y %H:%M"),
                saved=saved,
                add=equaladd_json_to_html(obj, "addition"))
            html.append(oApproval)
    except:
        msg = oErr.get_error_message()
        oErr.DoError("addapproval_pending_list")
    return html


# ========================================================= MODEL views =========================================================

class EqualAddList(BasicList):
    """Listview of EqualAdd"""
    model = EqualAdd
    listform = EqualAddForm 
    has_select2 = True
    bUseFilter = True
    new_button = False
    use_team_group = True
    prefix = "all"
    basic_name_prefix = "equaladd"
    order_cols = ['profile__user__username', 'saved', 'action', 'project__name', 'super__code', 'atype']
    order_default = ['profile__user__username', '-saved', 'action', 'project__name', 'super__code', 'atype']
    order_heads = [
        {'name': 'User',            'order': 'o=1', 'type': 'str', 'custom': 'user',    'linkdetails': True},
        {'name': 'Date',            'order': 'o=2', 'type': 'str', 'custom': 'date',    'linkdetails': True},
        {'name': 'Action ',         'order': 'o=3', 'type': 'str', 'custom': 'action',  'linkdetails': True},
        {'name': 'Project ',        'order': 'o=4', 'type': 'str', 'custom': 'project', 'linkdetails': True},        
        {'name': 'Authority File',  'order': 'o=5', 'type': 'str', 'custom': 'code',    'linkdetails': True, 'main': True},
        {'name': 'Status',          'order': 'o=6', 'type': 'str', 'custom': 'atype',   'linkdetails': True},
        ]
    filters = [ 
        {"name": "Authority File",  "id": "filter_code",      "enabled": False},
        {"name": "User",            "id": "filter_user",      "enabled": False},
        {"name": "Approval type",   "id": "filter_approval",  "enabled": False},
        ]
    searches = [
        {'section': '', 'filterlist': [
            {'filter': 'code',          'fkfield': 'super',     'help': 'passimcode',
             'keyS': 'passimcode', 'keyFk': 'code', 'keyList': 'passimlist', 'infield': 'id'},
            {'filter': 'user',          'fkfield': 'profile',   'keyFk': 'id', 'keyList': 'profilelist', 'infield': 'id'},
            {'filter': 'approval',      'dbfield': 'atype',     'keyList': 'atypelist',
             'keyType': 'fieldchoice',  'infield': 'abbr' }
            ]},
        {'section': 'other', 'filterlist': [
            {'filter': 'atype',     'dbfield': 'atype',    'keyS': 'atype'},
            ]}
         ]

    def initializations(self):
        if self.prefix == "all":
            # Provide all changes
            self.plural_name = "All Authority File project changes"
            self.sg_name = "Authority File project addition/removal"
        elif self.prefix == "user":
            # Restricted to a particular user...
            self.plural_name = "User Authority File project changes"
            self.sg_name = "User Authority File project addition/removal"
            self.order_cols = ['saved', 'action', 'project__name', 'super__code', 'atype']
            self.order_default = ['saved', 'action', 'project__name', 'super__code', 'atype']
            self.order_heads = [
                {'name': 'Date',            'order': 'o=1', 'type': 'str', 'custom': 'date',    'linkdetails': True},
                {'name': 'Action ',         'order': 'o=2', 'type': 'str', 'custom': 'action',  'linkdetails': True},
                {'name': 'Project ',        'order': 'o=3', 'type': 'str', 'custom': 'project', 'linkdetails': True},        
                {'name': 'Authority File',  'order': 'o=4', 'type': 'str', 'custom': 'code',    'linkdetails': True, 'main': True},
                {'name': 'Status',          'order': 'o=5', 'type': 'str', 'custom': 'atype',   'linkdetails': True},
                ]
            self.filters = [
                {"name": "Authority File",  "id": "filter_code",      "enabled": False},
                {"name": "Approval type",   "id": "filter_approval",  "enabled": False},
                ]
            self.searches = [
                {'section': '', 'filterlist': [
                    {'filter': 'code',          'fkfield': 'super',    'help': 'passimcode',
                     'keyS': 'passimcode', 'keyFk': 'code', 'keyList': 'passimlist', 'infield': 'id'},
                    {'filter': 'approval',      'dbfield': 'atype',     'keyList': 'atypelist',
                     'keyType': 'fieldchoice',  'infield': 'abbr' }
                    ]},
                {'section': 'other', 'filterlist': [
                    {'filter': 'atype',     'dbfield': 'atype',    'keyS': 'atype'},
                    {'filter': 'user', 'fkfield': 'profile', 'keyFk': 'id', 'keyList': 'profilelist', 'infield': 'id'}
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
        elif custom == "action":
            sBack = instance.get_action_display()
        elif custom == "project":
            sBack = instance.project.name
        elif custom == "code":
            sBack = instance.get_code()        
        return sBack, sTitle

    def adapt_search(self, fields):
        # Adapt the search to the keywords that *may* be shown
        lstExclude=[]
        qAlternative = None
        oErr = ErrHandle()

        try:
            if self.prefix == "all":
                # No adaptation needed
                pass
            elif self.prefix == "user":
                # Figure out who is asking
                profile = Profile.get_user_profile(self.request.user.username)
                # Restrict the profile
                fields['profilelist'] = Profile.objects.filter(id=profile.id)

        except:
            msg = oErr.get_error_message()
            oErr.DoError("EqualAddListView/adapt_search")

        return fields, lstExclude, qAlternative


class EqualAddUList(EqualAddList):

    prefix = "user"


class EqualChangeList(BasicList):
    """Listview of EqualChange"""

    model = EqualChange
    listform = EqualChangeForm
    has_select2 = True
    bUseFilter = True
    new_button = False
    use_team_group = True
    prefix = "all"
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
        {"name": "Approval type",   "id": "filter_approval",  "enabled": False},
        ]
    searches = [
        {'section': '', 'filterlist': [
            {'filter': 'code',          'fkfield': 'super',     'help': 'passimcode',
             'keyS': 'passimcode', 'keyFk': 'code', 'keyList': 'passimlist', 'infield': 'id'},
            {'filter': 'user',          'fkfield': 'profile',   'keyFk': 'id', 'keyList': 'profilelist', 'infield': 'id'},
            {'filter': 'approval',      'dbfield': 'atype',     'keyList': 'atypelist',
             'keyType': 'fieldchoice',  'infield': 'abbr' }
            ]},
        {'section': 'other', 'filterlist': [
            {'filter': 'atype',     'dbfield': 'atype',    'keyS': 'atype'},
            ]}
         ]

    def initializations(self):
        if self.prefix == "all":
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
            self.filters = [
                {"name": "Authority File",  "id": "filter_code",      "enabled": False},
                {"name": "Approval type",   "id": "filter_approval",  "enabled": False},
                ]
            self.searches = [
                {'section': '', 'filterlist': [
                    {'filter': 'code',          'fkfield': 'super',    'help': 'passimcode',
                     'keyS': 'passimcode', 'keyFk': 'code', 'keyList': 'passimlist', 'infield': 'id'},
                    {'filter': 'approval',      'dbfield': 'atype',     'keyList': 'atypelist',
                     'keyType': 'fieldchoice',  'infield': 'abbr' }
                    ]},
                {'section': 'other', 'filterlist': [
                    {'filter': 'atype',     'dbfield': 'atype',    'keyS': 'atype'},
                    # {'filter': 'superacc',  'dbfield': '$dummy',   'keyS': 'superacc'},
                    {'filter': 'user', 'fkfield': 'profile', 'keyFk': 'id', 'keyList': 'profilelist', 'infield': 'id'}
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

    def adapt_search(self, fields):
        # Adapt the search to the keywords that *may* be shown
        lstExclude=[]
        qAlternative = None
        oErr = ErrHandle()

        try:
            if self.prefix == "all":
                # No adaptation needed
                pass
            elif self.prefix == "user":
                # Figure out who is asking
                profile = Profile.get_user_profile(self.request.user.username)
                # Restrict the profile
                fields['profilelist'] = Profile.objects.filter(id=profile.id)

                # Make sure to exclude all field changes, that have already perculated
                # lstExclude.append(Q(super__atype='acc'))

        except:
            msg = oErr.get_error_message()
            oErr.DoError("EqualChangeListView/adapt_search")

        return fields, lstExclude, qAlternative


class EqualChangeUlist(EqualChangeList):

    prefix = "user"


class EqualAddEdit(BasicDetails): # Waarom is dit niet op basis van BasicEdit?
    model = EqualAdd
    mForm = EqualAddForm
    prefix = "all"
    basic_name_prefix = "equaladd"
    title = "Authority File addition"
    no_delete = True            # Don't allow users to remove an addition (?)
    mainitems = []

    def custom_init(self, instance):
        oErr = ErrHandle()
        try:
            if not instance is None:
                # Need to know who this user (profile) is
                profile = Profile.get_user_profile(self.request.user.username)

                # Am I the owner of this record?
                if profile.id == instance.profile.id:
                    # Is this the 'user' one?
                    if self.prefix == "user" and instance.atype != "acc":
                        # Allow myself to delete this suggestion, since it has not been accepted yet
                        self.no_delete = False
        except:
            msg = oErr.get_error_message()
            oErr.DoError("EqualChangeEdit/custom_init")
        return None

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
            #{'type': 'plain', 'label': "Field val",     'value': instance.field,    'field_key': "field",   'empty': 'hide'},
            {'type': 'plain', 'label': "Atype val",     'value': instance.atype,    'field_key': "atype",   'empty': 'hide'},
            # --------------------------------------------
            {'type': 'plain', 'label': "Authority File:",'value': instance.get_code_html()},        #,   'field_key': 'super'},
            #{'type': 'plain', 'label': "Field:",        'value': instance.get_display_name()},      #,   'field_key': 'field'},
            {'type': 'plain', 'label': "Action:",       'value': instance.get_action_display()},     #,  'field_key': 'action'},
            {'type': 'plain', 'label': "Date:",         'value': instance.get_saved()},
            {'type': 'plain', 'label': "Status:",       'value': instance.get_atype_display()},     #,  'field_key': 'atype'},
            #{'type': 'safe',  'label': "Current:",      'value': equalchange_json_to_html(instance, "current", profile)},
            #{'type': 'safe',  'label': "Proposed:",     'value': equalchange_json_to_html(instance, "change", profile)},
            ]
        # Only add the 'comment', if it is there (and read-only)
        if not instance.comment is None and instance.comment != "":
            mainitems_main.append({'type': 'plain', 'label': "Comment:", 'value': instance.comment})
        for item in mainitems_main: 
            context['mainitems'].append(item)

        # Signal that we do have select2
        context['has_select2'] = True

        # Return the context we have made
        return context


class EqualChangeEdit(BasicDetails):
    model = EqualChange
    mForm = EqualChangeForm
    prefix = "all"
    basic_name_prefix = "equalchange"
    title = "Field change"
    no_delete = True            # Don't allow users to remove a field change that they have entered
    mainitems = []

    def custom_init(self, instance):
        oErr = ErrHandle()
        try:
            if not instance is None:
                # Need to know who this user (profile) is
                profile = Profile.get_user_profile(self.request.user.username)

                # Am I the owner of this record?
                if profile.id == instance.profile.id:
                    # Is this the 'user' one?
                    if self.prefix == "user" and instance.atype != "acc":
                        # Allow myself to delete this suggestion, since it has not been accepted yet
                        self.no_delete = False
        except:
            msg = oErr.get_error_message()
            oErr.DoError("EqualChangeEdit/custom_init")
        return None

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
            {'type': 'plain', 'label': "Authority File:",'value': instance.get_code_html()},        #,          'field_key': 'super'},
            {'type': 'plain', 'label': "Field:",        'value': instance.get_display_name()},      #,   'field_key': 'field'},
            {'type': 'plain', 'label': "Date:",         'value': instance.get_saved()},
            {'type': 'plain', 'label': "Status:",       'value': instance.get_atype_display()},     #,  'field_key': 'atype'},
            {'type': 'safe',  'label': "Current:",      'value': equalchange_json_to_html(instance, "current", profile)},
            {'type': 'safe',  'label': "Proposed:",     'value': equalchange_json_to_html(instance, "change", profile)},
            ]
        # Only add the 'comment', if it is there (and read-only)
        if not instance.comment is None and instance.comment != "":
            mainitems_main.append({'type': 'plain', 'label': "Comment:", 'value': instance.comment})
        for item in mainitems_main: 
            context['mainitems'].append(item)

        # Signal that we do have select2
        context['has_select2'] = True

        # Return the context we have made
        return context


class EqualAddDetails(EqualAddEdit):
    """HTML output for an EqualAdd object"""

    rtype = "html"

    def add_to_context(self, context, instance):
        """Add to the existing context"""

        # Start by executing the standard handling
        super(EqualAddDetails, self).add_to_context(context, instance)

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
            # Lists of related objects
            context['related_objects'] = []

            # Need to know who this user (profile) is
            username = self.request.user.username
            team_group = app_editor

            # List of approvers related to the this Addition 
            approvers = dict(title="Approvals", prefix="appr", gridclass="resizable")

            rel_list =[]
            qs = instance.addapprovals.all().order_by('atype', '-saved')
            for item in qs:
                add = item.add
                url = reverse('equaladdapprovaluser_details', kwargs={'pk': item.id}) # is er niet equaladdapprovaluser_details moet in URLS.py
                url_chg = reverse('equaladduser_details', kwargs={'pk': add.id})
                rel_item = []

                # S: Order number for this approval
                add_rel_item(rel_item, index, False, align="right")
                index += 1

                # Who is this?
                approver = item.profile.user.username
                add_rel_item(rel_item, approver, False, main=False, link=url)

                # Which project(s) does this person have?
                projects_md = item.profile.get_approver_projects_markdown()
                add_rel_item(rel_item, projects_md, False, main=False, link=url)

                # Approval status
                astatus = item.get_atype_display()
                add_rel_item(rel_item, astatus, False, nowrap=False, main=False, link=url)

                # Comments on this approval
                comment_txt = item.get_comment_html()
                add_rel_item(rel_item, comment_txt, False, nowrap=False, main=True, link=url)

                # Add this line to the list
                rel_list.append(dict(id=item.id, cols=rel_item))

            approvers['rel_list'] = rel_list

            approvers['columns'] = [
                '{}<span>#</span>{}'.format(sort_start_int, sort_end), 
                '{}<span>Approver</span>{}'.format(sort_start, sort_end), 
                '{}<span>Project(s)</span>{}'.format(sort_start, sort_end), 
                '{}<span>Approval status</span>{}'.format(sort_start, sort_end), 
                '{}<span>Note</span>{}'.format(sort_start, sort_end), 
                ]
            related_objects.append(approvers)
            
            # Add all related objects to the context
            context['related_objects'] = related_objects

        except:
            msg = oErr.get_error_message()
            oErr.DoError("EqualAddDetails/add_to_context")

        # Return the context we have made
        return context


class EqualChangeDetails(EqualChangeEdit):
    """HTML output for an EqualChange object"""

    rtype = "html"

    def add_to_context(self, context, instance):
        """Add to the existing context"""

        # Start by executing the standard handling
        super(EqualChangeDetails, self).add_to_context(context, instance)

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
            # Lists of related objects
            context['related_objects'] = []

            # Need to know who this user (profile) is
            username = self.request.user.username
            team_group = app_editor

            # List of approvers related to the this Change 
            approvers = dict(title="Approvals", prefix="appr", gridclass="resizable")

            rel_list =[]
            qs = instance.changeapprovals.all().order_by('atype', '-saved')
            for item in qs:
                change = item.change
                url = reverse('equalapprovaluser_details', kwargs={'pk': item.id})
                url_chg = reverse('equalchangeuser_details', kwargs={'pk': change.id})
                rel_item = []

                # S: Order number for this approval
                add_rel_item(rel_item, index, False, align="right")
                index += 1

                # Who is this?
                approver = item.profile.user.username
                add_rel_item(rel_item, approver, False, main=False, link=url)

                # Which project(s) does this person have?
                projects_md = item.profile.get_approver_projects_markdown()
                add_rel_item(rel_item, projects_md, False, main=False, link=url)

                # Approval status
                astatus = item.get_atype_display()
                add_rel_item(rel_item, astatus, False, nowrap=False, main=False, link=url)

                # Comments on this approval
                comment_txt = item.get_comment_html()
                add_rel_item(rel_item, comment_txt, False, nowrap=False, main=True, link=url)

                # Add this line to the list
                rel_list.append(dict(id=item.id, cols=rel_item))

            approvers['rel_list'] = rel_list

            approvers['columns'] = [
                '{}<span>#</span>{}'.format(sort_start_int, sort_end), 
                '{}<span>Approver</span>{}'.format(sort_start, sort_end), 
                '{}<span>Project(s)</span>{}'.format(sort_start, sort_end), 
                '{}<span>Approval status</span>{}'.format(sort_start, sort_end), 
                '{}<span>Note</span>{}'.format(sort_start, sort_end), 
                ]
            related_objects.append(approvers)
            
            # Add all related objects to the context
            context['related_objects'] = related_objects

        except:
            msg = oErr.get_error_message()
            oErr.DoError("EqualChangeDetails/add_to_context")

        # Return the context we have made
        return context


class EqualChangeUserEdit(EqualChangeEdit):
    """User-specific equal change editing"""
    
    prefix = "user"
    title = "Field change"


class EqualChangeUserDetails(EqualChangeDetails):
    """HTML output for an EqualChangeUser object"""

    prefix = "user"
    title = "Field change"


class EqualAddUserEdit(EqualAddEdit):
    """User-specific equal addition editing"""
    
    prefix = "user"
    title = "Authority file addition"


class EqualAddUserDetails(EqualAddDetails):
    """HTML output for an EqualAddUser object"""

    prefix = "user"
    title = "Authority file addition"


class EqualApprovalList(BasicList):
    """Listview of EqualChange"""

    model = EqualApproval
    listform = EqualApprovalForm
    has_select2 = True
    bUseFilter = True
    new_button = False
    use_team_group = True
    prefix = "all"
    basic_name_prefix = "equalapproval"
    order_cols = ['profile__user__username', 'saved', 'change__super__code', 'change__field', 'change__profile__user__username', 'atype']
    order_default = ['profile__user__username', '-saved', 'change__super__code', 'change__field', 'change__profile__user__username', 'atype']
    order_heads = [
        {'name': 'User',            'order': 'o=1', 'type': 'str', 'custom': 'user',    'linkdetails': True},
        {'name': 'Date',            'order': 'o=2', 'type': 'str', 'custom': 'date',    'linkdetails': True},
        {'name': 'Authority File',  'order': 'o=3', 'type': 'str', 'custom': 'code',    'linkdetails': True, 'align': 'right'},
        {'name': 'Field',           'order': 'o=4', 'type': 'str', 'custom': 'field',   'linkdetails': True, 'main': True},
        {'name': 'Proposer',        'order': 'o=4', 'type': 'str', 'custom': 'proposer','linkdetails': True},
        {'name': 'Status',          'order': 'o=5', 'type': 'str', 'custom': 'atype',   'linkdetails': True},
        ]
    filters = [ 
        {"name": "Authority File",  "id": "filter_code",      "enabled": False},
        {"name": "User",            "id": "filter_user",      "enabled": False},
        {"name": "Approval type",   "id": "filter_approval",  "enabled": False},
        ]
    searches = [
        {'section': '', 'filterlist': [
            {'filter': 'code',          'fkfield': 'change__super',    'help': 'passimcode',
             'keyS': 'passimcode', 'keyFk': 'code', 'keyList': 'passimlist', 'infield': 'id'},
            {'filter': 'user', 'fkfield': 'profile', 'keyFk': 'id', 'keyList': 'profilelist', 'infield': 'id'},
            {'filter': 'approval',      'dbfield': 'atype',     'keyList': 'atypelist',
             'keyType': 'fieldchoice',  'infield': 'abbr' }
            ]},
        {'section': 'other', 'filterlist': [
            {'filter': 'atype',     'dbfield': 'atype',    'keyS': 'atype'},
            ]}
         ]

    def initializations(self):
        if self.prefix == "all":
            # Provide all changes
            self.plural_name = "All field approvals"
            self.sg_name = "Field approval"
        elif self.prefix == "user":
            # Restricted to a particular user...
            self.plural_name = "Field approvals"
            self.sg_name = "Field approval"
            self.order_cols = ['saved', 'change__super__code', 'change__field', 'change__profile__user__username', 'atype']
            self.order_default = ['-saved', 'change__super__code', 'change__field', 'change__profile__user__username', 'atype']
            self.order_heads = [
                {'name': 'Date',            'order': 'o=1', 'type': 'str', 'custom': 'date',    'linkdetails': True},
                {'name': 'Authority File',  'order': 'o=2', 'type': 'str', 'custom': 'code',    'linkdetails': True, 'align': 'right'},
                {'name': 'Field',           'order': 'o=3', 'type': 'str', 'custom': 'field',   'linkdetails': True, 'main': True},
                {'name': 'Proposer',        'order': 'o=4', 'type': 'str', 'custom': 'proposer','linkdetails': True},
                {'name': 'Status',          'order': 'o=5', 'type': 'str', 'custom': 'atype',   'linkdetails': True},
                ]
            self.filters = [
                {"name": "Authority File",       "id": "filter_code",      "enabled": False},
                {"name": "Approval type",   "id": "filter_approval",  "enabled": False},
                ]
            self.searches = [
                {'section': '', 'filterlist': [
                    {'filter': 'code',          'fkfield': 'change__super',    'help': 'passimcode',
                     'keyS': 'passimcode', 'keyFk': 'code', 'keyList': 'passimlist', 'infield': 'id'},
                    {'filter': 'approval',      'dbfield': 'atype',     'keyList': 'atypelist',
                     'keyType': 'fieldchoice',  'infield': 'abbr' }
                    ]},
                {'section': 'other', 'filterlist': [
                    {'filter': 'atype',     'dbfield': 'atype',    'keyS': 'atype'},
                    {'filter': 'user', 'fkfield': 'profile', 'keyFk': 'id', 'keyList': 'profilelist', 'infield': 'id'}
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
        elif custom == "proposer":
            sBack = instance.change.profile.user.username
        elif custom == "atype":
            sBack = instance.get_atype_display()
        elif custom == "code":
            sBack = instance.change.get_code()
        elif custom == "field":
            sBack = instance.change.get_display_name()
        return sBack, sTitle

    def adapt_search(self, fields):
        # Adapt the search to the keywords that *may* be shown
        lstExclude=[]
        qAlternative = None
        oErr = ErrHandle()

        try:
            if self.prefix == "all":
                # No adaptation needed
                pass
            elif self.prefix == "user":
                # Figure out who is asking
                profile = Profile.get_user_profile(self.request.user.username)
                # Restrict the profile
                fields['profilelist'] = Profile.objects.filter(id=profile.id)

        except:
            msg = oErr.get_error_message()
            oErr.DoError("EqualChangeListView/adapt_search")

        return fields, lstExclude, qAlternative


class EqualApprovalUlist(EqualApprovalList):

    prefix = "user"


class EqualAddApprovalList(BasicList):
    """Listview of EqualAddApproval"""

    model = EqualAddApproval
    listform = EqualAddApprovalForm
    has_select2 = True
    bUseFilter = True
    new_button = False
    use_team_group = True
    prefix = "all"
    basic_name_prefix = "equaladdapproval"
    order_cols = ['profile__user__username', 'saved', 'add__action', 'add__super__code', 'atype']
    order_default = ['profile__user__username', '-saved', 'add__action', 'add__super__code', 'atype']
    order_heads = [
        {'name': 'User',            'order': 'o=1', 'type': 'str', 'custom': 'user',    'linkdetails': True},
        {'name': 'Date',            'order': 'o=2', 'type': 'str', 'custom': 'date',    'linkdetails': True},
        {'name': 'Action',          'order': 'o=3', 'type': 'str', 'custom': 'action',  'linkdetails': True},       
        {'name': 'Authority File',  'order': 'o=4', 'type': 'str', 'custom': 'code',    'linkdetails': True, 'main': True},
        {'name': 'Status',          'order': 'o=5', 'type': 'str', 'custom': 'atype',   'linkdetails': True},
        ]
    filters = [ 
        {"name": "Authority File",  "id": "filter_code",      "enabled": False},
        {"name": "User",            "id": "filter_user",      "enabled": False},
        {"name": "Approval type",   "id": "filter_approval",  "enabled": False},
        ]
    searches = [
        {'section': '', 'filterlist': [
            {'filter': 'code',          'fkfield': 'add__super',    'help': 'passimcode',
             'keyS': 'passimcode', 'keyFk': 'code', 'keyList': 'passimlist', 'infield': 'id'},
            {'filter': 'user', 'fkfield': 'profile', 'keyFk': 'id', 'keyList': 'profilelist', 'infield': 'id'},
            {'filter': 'approval',      'dbfield': 'atype',     'keyList': 'atypelist',
             'keyType': 'fieldchoice',  'infield': 'abbr' }
            ]},
        {'section': 'other', 'filterlist': [
            {'filter': 'atype',     'dbfield': 'atype',    'keyS': 'atype'},
            ]}
         ]

    def initializations(self):
        if self.prefix == "all":
            # Provide all additions
            self.plural_name = "All Authority File project approvals"
            self.sg_name = "Authority File project approval"
        elif self.prefix == "user":
            # Restricted to a particular user...
            self.plural_name = "Authority File project approvals"
            self.sg_name = "Authority File project approval"
            self.order_cols = ['saved', 'add__action', 'add__super__code', 'atype']
            self.order_default = ['-saved', 'add__action', 'add__super__code', 'atype']
            self.order_heads = [
                {'name': 'Date',            'order': 'o=1', 'type': 'str', 'custom': 'date',    'linkdetails': True},
                {'name': 'Action',          'order': 'o=2', 'type': 'str', 'custom': 'action',  'linkdetails': True},       
                {'name': 'Authority File',  'order': 'o=3', 'type': 'str', 'custom': 'code',    'linkdetails': True, 'main': True},
                {'name': 'Status',          'order': 'o=4', 'type': 'str', 'custom': 'atype',   'linkdetails': True},
                ]
            self.filters = [
                {"name": "Authority File",  "id": "filter_code",      "enabled": False},
                {"name": "Approval type",   "id": "filter_approval",  "enabled": False},
                ]
            self.searches = [
                {'section': '', 'filterlist': [
                    {'filter': 'code',          'fkfield': 'add__super',    'help': 'passimcode',
                     'keyS': 'passimcode', 'keyFk': 'code', 'keyList': 'passimlist', 'infield': 'id'},
                    {'filter': 'approval',      'dbfield': 'atype',     'keyList': 'atypelist',
                     'keyType': 'fieldchoice',  'infield': 'abbr' }
                    ]},
                {'section': 'other', 'filterlist': [
                    {'filter': 'atype',     'dbfield': 'atype',    'keyS': 'atype'},
                    {'filter': 'user', 'fkfield': 'profile', 'keyFk': 'id', 'keyList': 'profilelist', 'infield': 'id'}
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
        elif custom == "action":
            sBack = "{} {}".format(
                instance.add.get_action_display(), instance.add.project.name)
        elif custom == "code":
            sBack = instance.add.get_code()
        return sBack, sTitle

    def adapt_search(self, fields):
        # Adapt the search to the keywords that *may* be shown
        lstExclude=[]
        qAlternative = None
        oErr = ErrHandle()

        try:
            if self.prefix == "all":
                # No adaptation needed
                pass
            elif self.prefix == "user":
                # Figure out who is asking
                profile = Profile.get_user_profile(self.request.user.username)
                # Restrict the profile
                fields['profilelist'] = Profile.objects.filter(id=profile.id)

        except:
            msg = oErr.get_error_message()
            oErr.DoError("EqualAddListView/adapt_search")

        return fields, lstExclude, qAlternative


class EqualAddApprovalUList(EqualAddApprovalList):

    prefix = "user"


class EqualApprovalEdit(BasicDetails):
    model = EqualApproval
    mForm = EqualApprovalForm
    prefix = "all"
    basic_name_prefix = "equalapproval"
    title = "Change approval"
    no_delete = True            # Don't allow users to remove a field change that they have entered
    mainitems = []

    def custom_init(self, instance):
        oErr = ErrHandle()
        try:
            # Need to know who this user (profile) is
            profile = Profile.get_user_profile(self.request.user.username)
            # An item is readonly, if I am not the one who is supposed to comment on it
            if profile.id != instance.profile.id:
                self.permission = "readonly"
        except:
            msg = oErr.get_error_message()
            oErr.DoError("EqualApprovalEdit/custom_init")

        return None

    def add_to_context(self, context, instance):
        """Add to the existing context"""

        oErr = ErrHandle()
        try:
            # Need to know who this user (profile) is
            profile = Profile.get_user_profile(self.request.user.username)

            # Define the main items to show and edit
            context['mainitems'] = []

            # Add user or not?
            if self.prefix == "user":
                context['mainitems'].append({'type': 'line',  'label': "User:",'value': instance.profile.user.username})

            # Check if the approval has been 'locked'
            locked = (instance.change.atype == "acc")
            # An item is also 'locked', if I am not the one who is supposed to comment on it
            if profile.id != instance.profile.id:
                locked = True

            # Add the normal information
            mainitems_main = [
                # -------- HIDDEN field values (these are defined in [EqualApprovalForm] ---------------
                {'type': 'plain', 'label': "Profile id",    'value': profile.id,        'field_key': "profile", 'empty': 'hide'},
                {'type': 'plain', 'label': "Change id",     'value': instance.change.id,'field_key': "change",  'empty': 'hide'},
                # --------------------------------------------
                {'type': 'plain', 'label': "Authority File:",'value': instance.change.get_code_html()},         #,   'field_key': 'super'},
                {'type': 'plain', 'label': "Field:",        'value': instance.change.get_display_name()},       #,   'field_key': 'field'},
                {'type': 'safe',  'label': "Proposed by:",  'value': instance.change.get_proposer(),
                 'title': 'The user who suggested the change'         },
                {'type': 'plain', 'label': "Date:",         'value': instance.get_saved(),
                 'title': 'Date on which the suggestion has been made'},
                {'type': 'plain', 'label': "Status:",       'value': instance.get_atype_display()},             #,   'field_key': 'atype'},
                {'type': 'safe',  'label': "Comment:",      'value': instance.get_comment_html()},              #,   'field_key': 'comment'},
                {'type': 'safe',  'label': "Current:",      'value': equalchange_json_to_html(instance.change, "current", profile)},
                {'type': 'safe',  'label': "Proposed:",     'value': equalchange_json_to_html(instance.change, "change", profile)},
                ]
            # Only add the 'comment', if it is there (and read-only)
            if locked:
                # Possibly show the comment
                if not instance.change.comment is None and instance.change.comment != "":
                    mainitems_main.append({'type': 'line', 'label': "Processed:", 'value': instance.change.comment})
            else:
                # Make sure fields status and comment are editable
                editables = {'Status:': 'atype', 'Comment:': 'comment'}
                for item in mainitems_main:
                    if item['label'] in editables:
                        item['field_key'] = editables[item['label']]
            # Add the list of approvals here
            context['changeapprovals'] = instance.change.changeapprovals.all().order_by('atype', '-saved')
            sApprovals = render_to_string('approve/change_approvals.html', context, self.request)
            oItem = dict(type='line', label='', value=sApprovals)
            mainitems_main.append(oItem)

            for item in mainitems_main: 
                context['mainitems'].append(item)

            # Signal that we do have select2
            context['has_select2'] = True
        except:
            msg = oErr.get_error_message()
            oErr.DoError("EqualApprovalEdit/add_to_context")

        # Return the context we have made
        return context

    def after_save(self, form, instance):
        msg = ""
        bResult = True
        oErr = ErrHandle()
        
        try:
            # Is this something tangible?
            if not instance is None and instance.id != None and not self.permission == "readonly":
                # Get to the change itself from EqualChange
                change = instance.change

                # Is this EqualChange object already finished?
                if not change is None and change.atype != "acc":
                    # Check how many approvals there should be and how many are left
                    #   (issue #527 changed this to be the number of projects needed and left)
                    iLeft, iNeeded = change.get_approval_count()
                    if iNeeded > 0 and iLeft == 0:
                        # The last approval has been saved: we may implement the change
                        equalchange_json_to_accept(change)
                        # Look for any left-over EqualApproval objects
                        with transaction.atomic():
                            for obj in change.changeapprovals.all():
                                # Check if this has been processed
                                if obj.atype == "def":
                                    # THis has not been processed, it is still at the default value
                                    # Issue #527: set it to [aut] (automatically accepted)
                                    obj.atype = "aut"
                                    obj.save()
                                    # Result: this EqualApproval object will no longer appear on the list of SSG changes to be approved
                    elif change.changeapprovals.exclude(atype="def").count() == 0:
                        # Do some more careful checking: all approvals are now known
                        iRejected = change.changeapprovals.filter(atype='rej').count()
                        if iRejected == iNeeded:
                            # This suggestion has been rejected completely
                            change.atype = "rej"
                            change.save()
                        else:
                            # Not everything is rejected means: modifications are needed
                            change.atype = "mod"
                            change.save()
                    elif change.changeapprovals.filter(atype='rej').count() == iNeeded:
                        # This suggestion has been rejected completely
                        change.atype = "rej"
                        change.save()


        except:
            msg = oErr.get_error_message()
            oErr.DoError("EqualApprovalEdit/after_save")
            bResult = False
        return bResult, msg


class EqualApprovalDetails(EqualApprovalEdit):
    """HTML output for an EqualApproval object"""

    rtype = "html"

    def add_to_context(self, context, instance):
        """Add to the existing context"""

        # Start by executing the standard handling
        super(EqualApprovalDetails, self).add_to_context(context, instance)

        related_objects = []
        lstQ = []
        rel_list =[]
        resizable = True
        index = 1
        sort_start = '<span class="sortable"><span class="fa fa-sort sortshow"></span>&nbsp;'
        sort_start_int = '<span class="sortable integer"><span class="fa fa-sort sortshow"></span>&nbsp;'
        sort_end = '</span>'

        bDoApprovers = False

        oErr = ErrHandle()
        try:
            # Lists of related objects
            context['related_objects'] = []

            # Need to know who this user (profile) is
            username = self.request.user.username
            team_group = app_editor

            if bDoApprovers:
                # List of approvers related to the this Change 
                approvers = dict(title="Approvals", prefix="appr", gridclass="resizable")

                rel_list =[]
                qs = instance.change.changeapprovals.all().order_by('atype', '-saved')
                for item in qs:
                    change = item.change
                    url = reverse('equalapprovaluser_details', kwargs={'pk': item.id})
                    url_chg = reverse('equalchangeuser_details', kwargs={'pk': change.id})
                    rel_item = []

                    # S: Order number for this approval
                    add_rel_item(rel_item, index, False, align="right")
                    index += 1

                    # Who is this?
                    approver = item.profile.user.username
                    add_rel_item(rel_item, approver, False, main=False, link=url)

                    # Which project(s) does this person have?
                    projects_md = item.profile.get_approver_projects_markdown()
                    add_rel_item(rel_item, projects_md, False, main=False, link=url)

                    # Approval status
                    astatus = item.get_atype_display()
                    add_rel_item(rel_item, astatus, False, nowrap=False, main=False, link=url)

                    # Comments on this approval
                    comment_txt = item.get_comment_html()
                    add_rel_item(rel_item, comment_txt, False, nowrap=False, main=True, link=url)

                    # Add this line to the list
                    rel_list.append(dict(id=item.id, cols=rel_item))

                approvers['rel_list'] = rel_list

                approvers['columns'] = [
                    '{}<span>#</span>{}'.format(sort_start_int, sort_end), 
                    '{}<span>Approver</span>{}'.format(sort_start, sort_end), 
                    '{}<span>Project(s)</span>{}'.format(sort_start, sort_end), 
                    '{}<span>Approval status</span>{}'.format(sort_start, sort_end), 
                    '{}<span>Note</span>{}'.format(sort_start, sort_end), 
                    ]
                related_objects.append(approvers)
            
            # Add all related objects to the context
            context['related_objects'] = related_objects

        except:
            msg = oErr.get_error_message()
            oErr.DoError("EqualApprovalDetails/add_to_context")

        # Return the context we have made
        return context


class EqualApprovalUserEdit(EqualApprovalEdit):
    """User-specific equal change editing"""
    
    prefix = "user"
    title = "Change approval"


class EqualApprovalUserDetails(EqualApprovalDetails):
    """HTML output for an EqualApprovalUser object"""

    prefix = "user"
    title = "Change approval"


class EqualAddApprovalEdit(BasicDetails):
    model = EqualAddApproval
    mForm = EqualAddApprovalForm
    prefix = "all"
    basic_name_prefix = "equaladdapproval"
    title = "Authority File project approval"
    no_delete = True            # Don't allow users to remove a field change that they have entered
    mainitems = []

    def custom_init(self, instance):
        oErr = ErrHandle()
        try:
            # Need to know who this user (profile) is
            profile = Profile.get_user_profile(self.request.user.username)
            # An item is readonly, if I am not the one who is supposed to comment on it
            if profile.id != instance.profile.id:
                self.permission = "readonly"
        except:
            msg = oErr.get_error_message()
            oErr.DoError("EqualAddApprovalEdit/custom_init")

        return None

    def add_to_context(self, context, instance):
        """Add to the existing context"""

        oErr = ErrHandle()
        try:
            # Need to know who this user (profile) is
            profile = Profile.get_user_profile(self.request.user.username)

            # Define the main items to show and edit
            context['mainitems'] = []

            # Add user or not?
            if self.prefix == "user":
                context['mainitems'].append({'type': 'line',  'label': "User:",'value': instance.profile.user.username})

            # Check if the approval has been 'locked'
            locked = (instance.add.atype == "acc")
            # An item is also 'locked', if I am not the one who is supposed to comment on it
            if profile.id != instance.profile.id:
                locked = True

            # Add the normal information
            mainitems_main = [
                # -------- HIDDEN field values (these are defined in [EqualApprovalForm] ---------------
                {'type': 'plain', 'label': "Profile id",    'value': profile.id,        'field_key': "profile", 'empty': 'hide'},
                {'type': 'plain', 'label': "Add id",     'value': instance.add.id,      'field_key': "add",  'empty': 'hide'},
                # --------------------------------------------
                {'type': 'plain', 'label': "Authority File:",'value': instance.add.get_code_html()},         #,   'field_key': 'super'},                
                {'type': 'plain', 'label': "Date:",         'value': instance.get_saved()},
                {'type': 'plain', 'label': "Action:",       'value': instance.add.get_action_display()}, 
                {'type': 'plain', 'label': "Status:",       'value': instance.get_atype_display()},             #,   'field_key': 'atype'},
                {'type': 'safe',  'label': "Comment:",      'value': instance.get_comment_html()},              #,   'field_key': 'comment'},
                #{'type': 'safe',  'label': "Current:",      'value': equaladd_json_to_html(instance.add, "current", profile)},
                #{'type': 'safe',  'label': "Proposed:",     'value': equaladd_json_to_html(instance.add, "add", profile)},
                {'type': 'safe',  'label': 'Approvals:',    'value': self.get_approvals_html(instance)},
                ]
            # Only add the 'comment', if it is there (and read-only)
            if locked:
                # Possibly show the comment
                if not instance.add.comment is None and instance.add.comment != "":
                    mainitems_main.append({'type': 'plain', 'label': "Processed:", 'value': instance.add.comment})
            else:
                # Make sure fields status and comment are editable
                editables = {'Status:': 'atype', 'Comment:': 'comment'}
                for item in mainitems_main:
                    if item['label'] in editables:  
                        item['field_key'] = editables[item['label']]

            for item in mainitems_main: 
                context['mainitems'].append(item)

            # Signal that we do have select2
            context['has_select2'] = True
        except:
            msg = oErr.get_error_message() # hier mis
            oErr.DoError("EqualAddApprovalEdit/add_to_context")

        # Return the context we have made
        return context

    def get_approvals_html(self, instance):
        """Get the approvals for this particular project addition/removal"""

        oErr = ErrHandle()
        sBack = ""
        template = "approve/add_approval.html"
        try:
            approvals = instance.add.addapprovals.all().order_by('atype', '-saved')
            context = dict(approval=instance, approvals=approvals)
            sBack = render_to_string(template, context, self.request)
        except:
            msg = oErr.get_error_message()
            oErr.DoError("EqualAddApprovalEdit/get_approvals_html")
            bResult = False
        return sBack

    def after_save(self, form, instance):
        msg = ""
        bResult = True
        oErr = ErrHandle()
        
        try:
            # Is this something tangible?
            if not instance is None and instance.id != None and not self.permission == "readonly":
                # Get to the addition itself from EqualAdd
                add = instance.add

                # Is this EqualAdd object already finished?
                if not add is None and add.atype != "acc":
                    # Check how many approvals there should be and how many are left
                    #  EK, issue #528: get_approval_count() has been changed to provide the number of projects left and needed
                    iLeft, iNeeded = add.get_approval_count()
                    if iNeeded > 0 and iLeft == 0:
                        # Look for any left-over EqualApproval objects
                        with transaction.atomic():
                            for obj in add.addapprovals.all():
                                # Check if this has been processed
                                if obj.atype == "def":
                                    # THis has not been processed, it is still at the default value
                                    # Issue #527: set it to [aut] (automatically accepted)
                                    obj.atype = "aut"
                                    obj.save()
                                    # Result: this EqualApproval object will no longer appear on the list of SSG changes to be approved
                        # The last approval has been saved: we may implement the addition
                        equaladd_to_accept(add)
                    elif add.addapprovals.exclude(atype="def").count() == 0:
                        # Do some more careful checking: all addapprovals are now known
                        iRejected = add.addapprovals.filter(atype='rej').count()
                        if iRejected == iNeeded:
                            # This addition has been rejected completely
                            add.atype = "rej"
                            add.save()
                        else:
                            # Not everything is rejected means: modifications are needed
                            add.atype = "mod"
                            add.save()
                    elif add.addapprovals.filter(atype='rej').count() == iNeeded:
                        # This addition has been rejected completely
                        add.atype = "rej"
                        add.save()


        except:
            msg = oErr.get_error_message()
            oErr.DoError("EqualAddApprovalEdit/after_save")
            bResult = False
        return bResult, msg


class EqualAddApprovalDetails(EqualAddApprovalEdit):
    """HTML output for an EqualApproval object"""

    rtype = "html"

    def add_to_context(self, context, instance):
        """Add to the existing context"""

        # Start by executing the standard handling
        super(EqualAddApprovalDetails, self).add_to_context(context, instance)

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
            # Lists of related objects
            context['related_objects'] = []

            # Need to know who this user (profile) is
            username = self.request.user.username
            team_group = app_editor

            # List of approvers related to the this addition 
            approvers = dict(title="Approvals", prefix="appr", gridclass="resizable")

            rel_list =[]
            qs = instance.add.addapprovals.all().order_by('atype', '-saved')
            for item in qs:
                add = item.add
                url = reverse('equaladdapprovaluser_details', kwargs={'pk': item.id})
                url_chg = reverse('equaladduser_details', kwargs={'pk': add.id})
                rel_item = []

                # S: Order number for this approval
                add_rel_item(rel_item, index, False, align="right")
                index += 1

                # Who is this?
                approver = item.profile.user.username
                add_rel_item(rel_item, approver, False, main=False, link=url)

                # Which project(s) does this person have?
                projects_md = item.profile.get_approver_projects_markdown()
                add_rel_item(rel_item, projects_md, False, main=False, link=url)

                # Approval status
                astatus = item.get_atype_display()
                add_rel_item(rel_item, astatus, False, nowrap=False, main=False, link=url)

                # Comments on this approval
                comment_txt = item.get_comment_html()
                add_rel_item(rel_item, comment_txt, False, nowrap=False, main=True, link=url)

                # Add this line to the list
                rel_list.append(dict(id=item.id, cols=rel_item))

            approvers['rel_list'] = rel_list
            
            # Dit is het onderste gedeelte, de table
            approvers['columns'] = [
                '{}<span>#</span>{}'.format(sort_start_int, sort_end), 
                '{}<span>Approver</span>{}'.format(sort_start, sort_end), 
                '{}<span>Project(s)</span>{}'.format(sort_start, sort_end), 
                '{}<span>Approval status</span>{}'.format(sort_start, sort_end), 
                '{}<span>Note</span>{}'.format(sort_start, sort_end), 
                ]
            related_objects.append(approvers)
            
            # Add all related objects to the context
            context['related_objects'] = None # related_objects

        except:
            msg = oErr.get_error_message()
            oErr.DoError("EqualAddApprovalDetails/add_to_context")

        # Return the context we have made
        return context


class EqualAddApprovalUserEdit(EqualAddApprovalEdit):
    """User-specific equal addition editing"""
    
    prefix = "user"
    title = "Addition approval"


class EqualAddApprovalUserDetails(EqualAddApprovalDetails):
    """HTML output for an EqualApprovalUser object"""

    prefix = "user"
    title = "Addition approval"
