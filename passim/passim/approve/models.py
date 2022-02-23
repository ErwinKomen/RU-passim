"""Models for the APPROVE app: approval by editors of a SSG modification or creation

"""
from django.apps.config import AppConfig
from django.apps import apps
from django.db import models, transaction
from django.contrib.auth.models import User, Group
from django.db.models import Q
from django.db.models.functions import Lower
from django.db.models.query import QuerySet 
from django.urls import reverse


from markdown import markdown
import json, copy

# Take from my own app
from passim.utils import ErrHandle
from passim.settings import TIME_ZONE
from passim.seeker.models import get_current_datetime, get_crpp_date, build_abbr_list, \
    APPROVAL_TYPE, ACTION_TYPE, \
    EqualGold, Profile, Project2, ProjectEditor

STANDARD_LENGTH=255
LONG_STRING=255
ABBR_LENGTH = 5

class EqualChange(models.Model):
    """A proposal to change the value of one field within one SSG"""

    # [1] obligatory link to the SSG
    super = models.ForeignKey(EqualGold, on_delete=models.CASCADE, related_name="superproposals")
    # [1] a proposal belongs to a particular user's profilee
    profile = models.ForeignKey(Profile, on_delete=models.CASCADE, related_name="profileproposals")
    # [1] The name of the field for which a change is being suggested
    field = models.CharField("Field name", max_length=LONG_STRING)
    # [0-1] The current field's value (which may be none, if a new SSG is suggested)
    current = models.TextField("Current value", null=True, blank=True)
    # [0-1] The proposed value for the field as a stringified JSON
    change = models.TextField("Proposed value", default="{}")

    # [1] The approval status of this proposed change
    atype = models.CharField("Approval", choices=build_abbr_list(APPROVAL_TYPE), max_length=5, default="def")
    # [0-1] A system-created comment on the approval and processing
    comment = models.TextField("Comment", null=True, blank=True)

    # [1] And a date: the date of saving this manuscript
    created = models.DateTimeField(default=get_current_datetime)
    saved = models.DateTimeField(null=True, blank=True)

    # Fields for which changes need to be monitored
    approve_fields = [
        {'field': 'newauthor',          'tofld': 'author',   'type': 'fk', 'display': 'Author'},
        {'field': 'newincipit',         'tofld': 'incipit',  'type': 'string', 'display': 'Incipit'},
        {'field': 'newexplicit',        'tofld': 'explicit', 'type': 'string', 'display': 'Explicit'},
        {'field': 'keywords',           'tofld': 'keywords', 'type': 'm2m-inline',  'listfield': 'kwlist', 'display': 'Keywords'},
        {'field': 'collections',        'tofld': 'hcs',      'type': 'm2m-inline',  'listfield': 'collist_hist',
         'lstQ': [Q(settype="hc")],  
         'display': 'Historical collections' },
        {'field': 'equal_goldsermons',  'tofld': 'golds',    'type': 'm2o',         'listfield': 'goldlist', 'display': 'Sermons Gold'},
        {'field': 'equalgold_src',      'tofld': 'supers',   'type': 'm2m-addable', 'listfield': 'superlist', 'display': 'Links',
         'prefix': 'ssglink', 'formfields': [
             {'field': 'linktype',      'type': 'string'},
             {'field': 'spectype',      'type': 'string'},
             {'field': 'note',          'type': 'string'},
             {'field': 'alternatives',  'type': 'string'},
             {'field': 'dst',           'type': 'fk'},
             ]},
        ]

    def __str__(self):
        """Show who proposes what kind of change"""
        sBack = "{}: [{}] on ssg {}".format(
            self.profile.user.username, self.field, self.super.id)
        return sBack

    def add_item(super, profile, field, oChange, oCurrent=None):
        """Add one item"""

        oErr = ErrHandle()
        obj = None
        try:
            # Make sure to stringify, sorting the keys
            change = json.dumps(oChange, sort_keys=True)
            if oCurrent is None:
                current = None
            else:
                current = json.dumps(oCurrent, sort_keys=True)

            # Look for this particular change, supposing it has not changed yet
            obj = EqualChange.objects.filter(super=super, profile=profile, field=field, current=current, change=change).first()
            if obj == None or obj.changeapprovals.count() > 0:
                # Less restricted: look for any suggestion for a change on this field that has not been reviewed by anyone yet.
                bFound = False
                for obj in EqualChange.objects.filter(super=super, profile=profile, field=field, atype="def"):
                    if obj.changeapprovals.exclude(atype="def").count() == 0:
                        # We can use this one
                        bFound = True
                        obj.current = current
                        obj.change = change
                        obj.atype = "def"
                        obj.save()

                        break
                # What if nothing has been found?
                if not bFound:
                    # Only in that case do we make a new suggestion
                    obj = EqualChange.objects.create(super=super, profile=profile, field=field, current=current, change=change)
        except:
            msg = oErr.get_error_message()
            oErr.DoError("EqualChange/add_item")
        return obj

    def check_projects(profile):
        """Check of [profile] needs to have any EqualApprove objects

        And if he does: create them for him
        """

        oErr = ErrHandle()
        iCount = 0
        try:
            # Walk through all the changes that I have suggested
            qs = EqualChange.objects.filter(profile=profile)
            for change in qs:
                # Check the approval of this particular one
                iCount += change.check_approval()
            # All should be up to date now
        except:
            msg = oErr.get_error_message()
            oErr.DoError("EqualChange/check_projects")
        return iCount

    def check_approval(self):
        """Check if all who need it have an EqualApprove object for this one"""

        oErr = ErrHandle()
        iCount = 0
        try:
            # Check which editors should have an approval object (excluding myself)
            change = self
            profile = self.profile
            lst_approver = change.get_approver_list(profile)
            for approver in lst_approver:
                # Check if an EqualApprove exists
                approval = EqualApproval.objects.filter(change=change, profile=approver).first()
                if approval is None:
                    # Create one
                    approval = EqualApproval.objects.create(change=change, profile=approver)
                    iCount = 1
        except:
            msg = oErr.get_error_message()
            oErr.DoError("EqualChange/check_approval")
        return iCount

    def get_approval_count(self):
        """Check how many approvals are left to be made for this change"""

        oErr = ErrHandle()
        iCount = 0
        iTotal = 0
        try:
            # Count the number of approvals I need to have
            iTotal = self.changeapprovals.count()
            # Count the number of non-accepting approvals
            iCount = self.changeapprovals.exclude(atype="acc").count()
        except:
            msg = oErr.get_error_message()
            oErr.DoError("EqualChange/get_approval_count")
        return iCount, iTotal

    def get_approver_list(self, excl=None):
        """Get the list of editors that need to approve this change
        
        If [excl] is specified, then this object is excluded from the list of Profile objects returned
        """

        oErr = ErrHandle()
        lstBack = None
        try:
            # Default: return the empty list
            lstBack = Profile.objects.none()
            # Get all the projects to which this SSG 'belongs'
            lst_project = [x['id'] for x in self.super.projects.all().values("id")]
            # Note: only SSGs that belong to more than one project need to be reviewed
            if len(lst_project) > 1:
                # Get all the editors associated with these projects
                lst_profile_id = [x['profile_id'] for x in ProjectEditor.objects.filter(project__id__in=lst_project).values('profile_id').distinct()]
                if len(lst_profile_id) > 0:
                    if excl == None:
                        lstBack = Profile.objects.filter(id__in=lst_profile_id)
                    else:
                        lstBack = Profile.objects.filter(id__in=lst_profile_id).exclude(id=excl.id)
        except:
            msg = oErr.get_error_message()
            oErr.DoError("EqualChange/get_approver_list")
        return lstBack

    def get_code(self):
        """Get the passim code for this object"""

        sBack = self.super.get_code()
        return sBack

    def get_code_html(self):
        """Get the PASSIM code, including a link to follow it"""
        return self.super.get_passimcode_markdown()

    def get_display_name(self):
        """Get the display name of this field"""

        sBack = self.field
        for oItem in self.approve_fields:
            if self.field == oItem['tofld']:
                sBack = oItem['display']
                break
        return sBack

    def get_review_list(profile, all=False):
        """Get the list of objects this editor needs to review"""

        oErr = ErrHandle()
        lstBack = []
        try:
            # Default: return the empty list
            # lstBack = EqualChange.objects.none()
            # Get the list of projects for this user
            lst_project_id = profile.projects.all().values("id")
            if len(lst_project_id) > 0:
                # Get the list of EqualChange objects linked to any of these projects
                lstQ = []
                lstQ.append(Q(super__equal_proj__project__id__in=lst_project_id))
                if not all:
                    lstQ.append(Q(atype='def'))
                lstBack = [x['id'] for x in EqualChange.objects.exclude(profile=profile).filter(*lstQ).distinct().values('id')]
                # lstBack = EqualChange.objects.exclude(profile=profile).filter(*lstQ).distinct()
        except:
            msg = oErr.get_error_message()
            oErr.DoError("EqualChange/get_review_list")
        return lstBack

    def get_saved(self):
        """Get the date of saving"""

        saved = self.created if self.saved is None else self.saved
        sBack = saved.strftime("%d/%b/%Y %H:%M")
        return sBack

    def get_status_history(self):
        """Show all editor's approvals for this item"""

        sBack = ""
        oErr = ErrHandle()
        try:
            html = []
            for obj in self.changeapprovals.all().order_by('-saved'):
                name = obj.profile.user.username
                status = obj.get_atype_display()
                dated = get_crpp_date(obj.saved, True)
                html.append("<b>{}</b>: {} - {}".format(name, status, dated))
            sBack = "<br />".join(html)
        except:
            msg = oErr.get_error_message()
            oErr.DoError("EqualChange/get_status_history")
        return sBack

    def save(self, force_insert = False, force_update = False, using = None, update_fields = None):
        # Adapt the save date
        self.saved = get_current_datetime()

        # Actual saving
        response = super(EqualChange, self).save(force_insert, force_update, using, update_fields)

        # Check whether all needed approvars have an EqualApproval object
        self.check_approval()

        # Return the response when saving
        return response


class EqualApproval(models.Model):
    """This is one person (profile) approving one particular change suggestion"""

    # [1] obligatory link to the SSG
    change = models.ForeignKey(EqualChange, on_delete=models.CASCADE, related_name="changeapprovals")
    # [1] an approval belongs to a particular user's profile
    profile = models.ForeignKey(Profile, on_delete=models.CASCADE, related_name="profileapprovals")

    # [1] The approval status of this proposed change
    atype = models.CharField("Approval", choices=build_abbr_list(APPROVAL_TYPE), max_length=5, default="def")
    # [0-1] A comment on the reason for rejecting a proposal
    comment = models.TextField("Comment", null=True, blank=True)

    # [1] And a date: the date of saving this manuscript
    created = models.DateTimeField(default=get_current_datetime)
    saved = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        """Show this approval"""
        sBack = "{}: [{}] on ssg {}={}".format( # iets eruit halen?)
            self.profile.user.username, self.change.field, self.change.super.id, self.atype) # iets eruit halen?
        return sBack

    def get_comment_html(self):
        """Get the comment, translating markdown"""

        sBack = "-"
        if not self.comment is None:
            sBack = markdown(self.comment)
        return sBack

    def get_mytask(profile):
        """Find out which items [profile] needs to approve"""

        qs = EqualApproval.objects.filter(profile=profile, atype="def")
        return qs

    def get_mytask_count(profile):
        """Find out how many items [profile] needs to approve"""

        qs = EqualApproval.get_mytask(profile)
        return qs.count()

    def get_saved(self):
        """Get the date of saving"""

        saved = self.created if self.saved is None else self.saved
        sBack = saved.strftime("%d/%b/%Y %H:%M")
        return sBack

    def save(self, force_insert = False, force_update = False, using = None, update_fields = None):
        # Adapt the save date
        self.saved = get_current_datetime()

        # Actual saving
        response = super(EqualApproval, self).save(force_insert, force_update, using, update_fields)

        # Return the response when saving
        return response


class EqualAdd(models.Model):
    """This is one person (profile) adding one particular EqualGold to a new project"""

    # [1] obligatory link to the SSG
    super = models.ForeignKey(EqualGold, on_delete=models.CASCADE, related_name="equaladdings")
    # [1] an addition belongs to a particular user's profile
    profile = models.ForeignKey(Profile, on_delete=models.CASCADE, related_name="profileaddings")    
    # [1] each addition belongs to a particular project     
    project = models.ForeignKey(Project2, on_delete=models.CASCADE, related_name="projectaddings")

    # [1] The kind of action: adding or removing ('add', 'rem')
    action = models.CharField("Action", choices=build_abbr_list(ACTION_TYPE), max_length=5, default="add")

    # [1] The approval status of this proposed change
    atype = models.CharField("Approval", choices=build_abbr_list(APPROVAL_TYPE), max_length=5, default="def")
    # [0-1] A comment on the reason for rejecting an addition
    comment = models.TextField("Comment", null=True, blank=True)

    # [1] And a date: the date of saving this addition
    created = models.DateTimeField(default=get_current_datetime)
    saved = models.DateTimeField(null=True, blank=True)
    
    def __str__(self):
        """Show who proposes which addition"""
        sBack = "{}: on ssg {}".format(
            self.profile.user.username, self.super.id) 
        print(sBack)
        return sBack

    def add_item(super, profile):
        """Add one item"""

        oErr = ErrHandle()
        obj = None
        try:
            # Look for this particular addition, supposing it has not been added yet TH:werkt dit zo? Niet dus, hier gaat er iets mis. 
            obj = EqualAdd.objects.filter(super=super, profile=profile).first() 
            if obj == None or obj.addapprovals.count() > 0:
                # Less restricted: look for any addition of a SSG/AF that has not been reviewed by anyone yet. TH: nodig??
                bFound = False
                for obj in EqualAdd.objects.filter(super=super, profile=profile, atype="def"):
                    if obj.addapprovals.exclude(atype="def").count() == 0:
                        # We can use this one
                        bFound = True
                        obj.atype = "def" 
                        obj.save()
                        break
                # What if nothing has been found?
                if not bFound:
                    # Only in that case do we make a new addition
                    obj = EqualAdd.objects.create(super=super, profile=profile)
        except:
            msg = oErr.get_error_message()
            oErr.DoError("EqualAdd/add_item")
        return obj

    def check_projects(profile):
        """Check of [profile] needs to have any EqualAdd objects

        And if he does: create them for him
        """

        oErr = ErrHandle()
        iCount = 0
        try:
            # Walk through all the additions that I have suggested
            qs = EqualAdd.objects.filter(profile=profile)
            for add in qs:
                # Check the approval of this particular one
                iCount += add.check_approval()
            # All should be up to date now
        except:
            msg = oErr.get_error_message()
            oErr.DoError("EqualAdd/check_projects")
        return iCount

    def check_approval(self):
        """Check if all who need it have an EqualAddApproval object for this one"""
        # Not yet working
        oErr = ErrHandle()
        iCount = 0
        try:
            # Check which editors should have an approval object (excluding myself)
            add = self
            profile = self.profile
            lst_approver = add.get_approver_list(profile) # Hierna vliegt hij eruit is leeg
            for approver in lst_approver:
                # Check if an EqualAddApproval exists 
                approval = EqualAddApproval.objects.filter(add=add, profile=approver).first()
                if approval is None:
                    # Create one
                    approval = EqualAddApproval.objects.create(add=add, profile=approver)
                    iCount = 1
        except:
            msg = oErr.get_error_message()
            oErr.DoError("EqualAdd/check_approval") 
        return iCount

    def get_approval_count(self):
        """Check how many approvals are left to be made for this addition"""

        oErr = ErrHandle()
        iCount = 0
        iTotal = 0
        try:
            # Count the number of approvals I need to have
            iTotal = self.addapprovals.count()
            # Count the number of non-accepting approvals
            iCount = self.addapprovals.exclude(atype="acc").count()
        except:
            msg = oErr.get_error_message()
            oErr.DoError("EqualAdd/get_approval_count") 
        return iCount, iTotal

    def get_approver_list(self, excl=None):
        """Get the list of editors that need to approve this addition
        
        If [excl] is specified, then this object is excluded from the list of Profile objects returned
        """

        oErr = ErrHandle()
        lstBack = None
        try:
            # Default: return the empty list
            lstBack = Profile.objects.none()
            # Get all the projects to which this SSG 'belongs'
            lst_project = [x['id'] for x in self.super.projects.all().values("id")] 
            # Get the id of the new project
            id_new_project = self.project_id
            # Add this to the list
            lst_project.append(id_new_project)
            # Note: only SSGs that belong to more than one project need to be reviewed 
            if len(lst_project) > 1:
                # Get all the editors associated with these projects
                lst_profile_id = [x['profile_id'] for x in ProjectEditor.objects.filter(project__id__in=lst_project).values('profile_id').distinct()]
                if len(lst_profile_id) > 0:
                    if excl == None:
                        lstBack = Profile.objects.filter(id__in=lst_profile_id)
                    else:
                        lstBack = Profile.objects.filter(id__in=lst_profile_id).exclude(id=excl.id)
        except:
            msg = oErr.get_error_message()
            oErr.DoError("EqualAdd/get_approver_list") 
        return lstBack

    def get_code(self):
        """Get the PASSIM code for this object"""
        sBack = self.super.get_code()
        return sBack

    def get_code_html(self):
        """Get the PASSIM code, including a link to follow it"""
        return self.super.get_passimcode_markdown()

    def get_display_name(self):
        """Get the display name of this field""" #TH: KAN WEG?

        sBack = self.field
        for oItem in self.approve_fields:
            if self.field == oItem['tofld']:
                sBack = oItem['display']
                break
        return sBack

    def get_review_list(profile, all=False):
        """Get the list of objects this editor needs to review"""

        oErr = ErrHandle()
        lstBack = []
        try:
            # Default: return the empty list
            # lstBack = EqualChange.objects.none()
            # Get the list of projects for this user
            lst_project_id = profile.projects.all().values("id")
            if len(lst_project_id) > 0:
                # Get the list of EqualAdd objects linked to any of these projects 
                lstQ = []
                lstQ.append(Q(super__equal_proj__project__id__in=lst_project_id))
                if not all:
                    lstQ.append(Q(atype='def'))
                lstBack = [x['id'] for x in EqualAdd.objects.exclude(profile=profile).filter(*lstQ).distinct().values('id')]
                # lstBack = EqualChange.objects.exclude(profile=profile).filter(*lstQ).distinct()
        except:
            msg = oErr.get_error_message()
            oErr.DoError("EqualAdd/get_review_list") 
        return lstBack

    def get_saved(self):
        """Get the date of saving"""

        saved = self.created if self.saved is None else self.saved
        sBack = saved.strftime("%d/%b/%Y %H:%M")
        return sBack

    def get_status_history(self):
        """Show all editor's approvals for this item"""

        sBack = ""
        oErr = ErrHandle()
        try:
            html = []
            for obj in self.addapprovals.all().order_by('-saved'):
                name = obj.profile.user.username
                status = obj.get_atype_display()
                dated = get_crpp_date(obj.saved, True)
                html.append("<b>{}</b>: {} - {}".format(name, status, dated))
            sBack = "<br />".join(html)
        except:
            msg = oErr.get_error_message()
            oErr.DoError("EqualAdd/get_status_history")
        return sBack

    def save(self, force_insert = False, force_update = False, using = None, update_fields = None): 
        # Adapt the save date
        self.saved = get_current_datetime()

        # Actual saving
        response = super(EqualAdd, self).save(force_insert, force_update, using, update_fields)

        # Check whether all needed approvers have an EqualApproval object
        self.check_approval() 

        # Return the response when saving
        return response


class EqualAddApproval(models.Model):
    """This is one person (profile) approving one particular EqualGold addition"""

    # [1] obligatory link to EqualAdd
    add = models.ForeignKey(EqualAdd, on_delete=models.CASCADE, related_name="addapprovals")
    # [1] an approval belongs to a particular user's profile
    profile = models.ForeignKey(Profile, on_delete=models.CASCADE, related_name="profileaddapprovals")

    # [1] The approval status of this proposed addition
    atype = models.CharField("Approval", choices=build_abbr_list(APPROVAL_TYPE), max_length=5, default="def")
    # [0-1] A comment on the reason for rejecting an addition
    comment = models.TextField("Comment", null=True, blank=True)

    # [1] And a date: the date of saving this approval
    created = models.DateTimeField(default=get_current_datetime)
    saved = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        """Show this approval"""
        sBack = "{}: [{}] on ssg {}={}".format(
            self.profile.user.username, self.add.super.id, self.atype)
        return sBack

    def get_comment_html(self):
        """Get the comment, translating markdown"""

        sBack = "-"
        if not self.comment is None:
            sBack = markdown(self.comment)
        return sBack

    def get_mytask(profile):
        """Find out which additions [profile] needs to approve"""

        qs = EqualAddApproval.objects.filter(profile=profile, atype="def")
        return qs

    def get_mytask_count(profile):
        """Find out how many additions [profile] needs to approve"""

        qs = EqualAddApproval.get_mytask(profile)
        return qs.count()

    def get_saved(self):
        """Get the date of saving"""

        saved = self.created if self.saved is None else self.saved
        sBack = saved.strftime("%d/%b/%Y %H:%M")
        return sBack

    def save(self, force_insert = False, force_update = False, using = None, update_fields = None): # Aanpassen?
        # Adapt the save date
        self.saved = get_current_datetime()

        # Actual saving
        response = super(EqualAddApproval, self).save(force_insert, force_update, using, update_fields)

        # Return the response when saving
        return response