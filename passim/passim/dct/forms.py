"""
Definition of forms.
"""

from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.utils.translation import gettext_lazy as _
from django.forms import ModelMultipleChoiceField, ModelChoiceField
from django.forms.widgets import *
from django.db.models import F
from django_select2.forms import Select2MultipleWidget, ModelSelect2MultipleWidget, ModelSelect2Widget

# From my own application
from passim.utils import ErrHandle
from passim.basic.forms import BasicModelForm, BasicSimpleForm
from passim.dct.models import *
from passim.seeker.models import Profile, FieldChoice


# =============== WIDGETS ===============================================
class ManuidOneWidget(ModelSelect2Widget):
    model = Manuscript
    search_fields = [ 'idno__icontains', 'library__lcity__name__icontains', 'library__name__icontains']

    def label_from_instance(self, obj):
        return obj.get_full_name()

    def get_queryset(self):
        qs = self.queryset
        if qs == None:
            qs = Manuscript.objects.filter(mtype='man').order_by('library__lcity__name', 'library__name', 'idno').distinct()
        return qs


class CollOneWidget(ModelSelect2Widget):
    model = Collection
    search_fields = [ 'name__icontains' ]
    type = None
    settype = "pd"

    def label_from_instance(self, obj):
        return obj.name

    def get_queryset(self):
        username = self.attrs.pop('username', '')
        team_group = self.attrs.pop('team_group', '')
        if self.type:
            qs = Collection.get_scoped_queryset(self.type, username, team_group, settype=self.settype)
        else:
            qs = Collection.get_scoped_queryset(None, username, team_group, settype=self.settype)
        return qs


class CollOneSuperWidget(CollOneWidget):
    """Like CollOne, but then for: EqualGold = super sermon gold"""
    type = "super"
    settype = "pd"


class CollOneHistWidget(CollOneWidget):
    """Like CollOne, but then for: EqualGold = super sermon gold"""
    type = "super"
    settype = "hc"


class ProfileOneWidget(ModelSelect2Widget):
    model = Profile
    search_fields = [ 'user__username__icontains' ]

    def label_from_instance(self, obj):
        return obj.user.username

    def get_queryset(self):
        return Profile.objects.all().order_by('user__username').distinct()


class ProfileWidget(ModelSelect2MultipleWidget):
    model = Profile
    search_fields = [ 'user__username__icontains' ]

    def label_from_instance(self, obj):
        return obj.user.username

    def get_queryset(self):
        return Profile.objects.all().order_by('user__username').distinct()


class ResearchSetOneWidget(ModelSelect2Widget):
    model = ResearchSet
    search_fields = [ 'name__icontains' ]
    type = None
    qs = None

    def label_from_instance(self, obj):
        return obj.name

    def get_queryset(self):
        if self.qs is None:
            profile = self.attrs.pop('profile', '')
            qs = ResearchSet.objects.filter(profile=profile)
            self.qs = qs
        else:
            qs = self.qs
        return qs


class SaveGroupOneWidget(ModelSelect2Widget):
    model = SaveGroup
    search_fields = [ 'name__icontains' ]
    type = None
    qs = None

    def label_from_instance(self, obj):
        return obj.name

    def get_queryset(self):
        if self.qs is None:
            profile = self.attrs.pop('profile', '')
            qs = SaveGroup.objects.filter(profile=profile)
            self.qs = qs
        else:
            qs = self.qs
        return qs


class SelItemTypeWidget(ModelSelect2MultipleWidget):
    model = FieldChoice
    search_fields = [ 'english_name__icontains']

    def label_from_instance(self, obj):
        return obj.english_name

    def get_queryset(self):
        return FieldChoice.objects.filter(field=SELITEM_TYPE).order_by("english_name")


# ================ FORMS ================================================

class ResearchSetForm(BasicModelForm):
    profileid = forms.CharField(required=False)
    manulist = ModelChoiceField(queryset=None, required=False,
            widget=ManuidOneWidget(attrs={'data-minimum-input-length': 0, 'data-placeholder': 'Select manuscript...', 'style': 'width: 100%;'}))
    histlist = ModelChoiceField(queryset=None, required=False)
    ssgdlist = ModelChoiceField(queryset=None, required=False)
    ownlist  = ModelMultipleChoiceField(queryset=None, required=False, 
                widget=ProfileWidget(attrs={'data-minimum-input-length': 0, 'data-placeholder': 'Select multiple profiles...', 'style': 'width: 100%;', 'class': 'searching'}))
    ssgdname = forms.CharField(label="Name", required=False, 
            widget=forms.TextInput(attrs={'class': 'typeahead searching input-sm', 
                                          'placeholder': 'User-defined name (optional)...',  'style': 'width: 100%;'}))
    dctname = forms.CharField(label="Name", required=False, 
            widget=forms.TextInput(attrs={'class': 'typeahead searching input-sm', 
                                          'placeholder': 'Specify a name for the DCT...',  'style': 'width: 100%;'}))

    class Meta:
        model = ResearchSet
        fields = ['name', 'notes', 'scope']
        widgets={'name':    forms.TextInput(attrs={'style': 'width: 100%;', 'placeholder': 'The name of this research set...'}),
                 'notes':   forms.Textarea(attrs={'rows': 1, 'cols': 40, 'style': 'height: 40px; width: 100%;',
                                                       'placeholder': 'Optionally add your own notes...'}),
                 'scope':       forms.Select(attrs={'style': 'width: 100%;'})
                 }

    def __init__(self, *args, **kwargs):
        # Obligatory for this type of form!!!
        self.username = kwargs.pop('username', "")
        self.team_group = kwargs.pop('team_group', "")
        self.userplus = kwargs.pop('userplus', "")
        # Start by executing the standard handling
        super(ResearchSetForm, self).__init__(*args, **kwargs)

        oErr = ErrHandle()
        try:
            username = self.username
            profile = Profile.get_user_profile(username)
            team_group = self.team_group

            # Some fields are not required
            self.fields['name'].required = False
            self.fields['notes'].required = False
            self.fields['scope'].required = False

            # Make sure the profile is set correctly
            self.fields['profileid'].initial = profile.id

            # Set the widgets correctly
            self.fields['histlist'].widget = CollOneHistWidget( attrs={'username': username, 'team_group': team_group, 'settype': 'hc',
                        'data-minimum-input-length': 0, 'data-placeholder': 'Select a historical collection...', 'style': 'width: 100%;', 'class': 'searching'})
            self.fields['ssgdlist'].widget = CollOneSuperWidget( attrs={'username': username, 'team_group': team_group,'settype': 'pd',
                        'data-minimum-input-length': 0, 'data-placeholder': 'Select a personal dataset of SSGs...', 'style': 'width: 100%;', 'class': 'searching'})

            self.fields['ownlist'].queryset = Profile.objects.all()

            # Set queryset(s) - for details view
            self.fields['manulist'].queryset = Manuscript.objects.none()

            # Note: the collection filters must use the SCOPE of the collection
            self.fields['histlist'].queryset = Collection.get_scoped_queryset('super', username, team_group, settype="hc")
            self.fields['ssgdlist'].queryset = Collection.get_scoped_queryset('super', username, team_group, settype="pd")
            
            # Get the instance
            if 'instance' in kwargs:
                instance = kwargs['instance']
                # Adapt the profile if this is needed
                self.fields['profileid'].initial = instance.profile.id

                # Give a choice of manuscripts that are not linked to this researchset
                manu_ids = [x['manuscript__id'] for x in SetList.objects.filter(setlisttype='manu', 
                                    researchset=instance, manuscript__isnull=False).values('manuscript__id')]
                qs = Manuscript.objects.filter(mtype='man').exclude(id__in=manu_ids).order_by(
                    'library__lcity__name', 'library__name', 'idno')
                self.fields['manulist'].queryset = qs
                self.fields['manulist'].widget.queryset = qs
        except:
            msg = oErr.get_error_message()
            oErr.DoError("ResearchSetForm")
        return None


class SetDefForm(BasicModelForm):
    """Used for listview and details view of SetDef"""

    manulist = ModelChoiceField(queryset=None, required=False,
            widget=ManuidOneWidget(attrs={'data-minimum-input-length': 0, 'data-placeholder': 'Select manuscript...', 'style': 'width: 100%;'}))
    histlist = ModelChoiceField(queryset=None, required=False)

    class Meta:
        model = SetDef
        fields = ['name', 'notes']
        widgets={'name':    forms.TextInput(attrs={'style': 'width: 100%;', 'placeholder': 'The name of this DCT...'}),
                 'notes':   forms.Textarea(attrs={'rows': 1, 'cols': 40, 'style': 'height: 40px; width: 100%;',
                                                       'placeholder': 'Optionally add your own notes...'})
                 }

    def __init__(self, *args, **kwargs):
        # Obligatory for this type of form!!!
        self.username = kwargs.pop('username', "")
        self.team_group = kwargs.pop('team_group', "")
        self.userplus = kwargs.pop('userplus', "")
        # Start by executing the standard handling
        super(SetDefForm, self).__init__(*args, **kwargs)

        oErr = ErrHandle()
        try:
            # Some fields are not required
            self.fields['name'].required = False
            self.fields['notes'].required = False

            # Set queryset(s) - for details view
            self.fields['manulist'].queryset = Manuscript.objects.none()

            # Set the widgets correctly
            self.fields['histlist'].widget = CollOneHistWidget( attrs={'username': self.username, 'team_group': self.team_group, 'settype': 'hc',
                        'data-minimum-input-length': 0, 'data-placeholder': 'Select a historical collection...', 'style': 'width: 100%;', 'class': 'searching'})
            # Note: the collection filters must use the SCOPE of the collection
            self.fields['histlist'].queryset = Collection.get_scoped_queryset('super', self.username, self.team_group, settype="hc")

            # Get the instance
            if 'instance' in kwargs:
                instance = kwargs['instance']   

        except:
            msg = oErr.get_error_message()
            oErr.DoError("SetDefForm")
        return None


class RsetSelForm(BasicSimpleForm):
    """Form to facilitate selecting a research set for DCT work"""

    rsetone     = ModelChoiceField(queryset=None, required=False)

    def __init__(self, *args, **kwargs):
        # NOTE: we do need to have the user here
        self.user = kwargs.pop('user')
        # Start by executing the standard handling
        super(RsetSelForm, self).__init__(*args, **kwargs)

        oErr = ErrHandle()
        try:
            # Get the profile from the username
            if self.user is None:
                # Just show this on the server log
                oErr.Status("WARNING: RsetSelForm: no user supplied")
            else:
                profile = self.user.user_profiles.first()
                # Set the widgets correctly
                self.fields['rsetone'].widget = ResearchSetOneWidget(attrs={'profile': profile, 
                            'data-minimum-input-length': 0, 'data-placeholder': 'Select a research set...', 'style': 'width: 100%;', 'class': 'searching'})

                # The rsetone information is needed for "selection-to-DCT" processing
                self.fields['rsetone'].queryset = ResearchSet.objects.filter(profile=profile)

        except:
            msg = oErr.get_error_message()
            oErr.DoError("rsetselform")


class SgroupSelForm(BasicSimpleForm):
    """Form to facilitate selecting a savegroup"""

    sgroupone = ModelChoiceField(queryset=None, required=False)
    sgroupadd = forms.CharField(label="Name", required=False, 
            widget=forms.TextInput(attrs={'class': 'typeahead searching input-sm', 
                    'placeholder': 'Name for the new Save Group...',  'style': 'width: 100%;'}))

    def __init__(self, *args, **kwargs):
        # NOTE: we do need to have the user here
        self.user = kwargs.pop('user')
        # Start by executing the standard handling
        super(SgroupSelForm, self).__init__(*args, **kwargs)

        oErr = ErrHandle()
        try:
            # Get the profile from the username
            if self.user is None:
                # Just show this on the server log
                oErr.Status("WARNING: SgroupSelForm: no user supplied")
            else:
                profile = self.user.user_profiles.first()
                # Set the widgets correctly
                self.fields['sgroupone'].widget = SaveGroupOneWidget(attrs={'profile': profile, 
                            'data-minimum-input-length': 0, 'data-placeholder': 'Select a save group...', 'style': 'width: 100%;', 'class': 'searching'})

                # The rsetone information is needed for "selection-to-DCT" processing
                self.fields['sgroupone'].queryset = SaveGroup.objects.filter(profile=profile)

        except:
            msg = oErr.get_error_message()
            oErr.DoError("SgroupSelForm")


class SaveGroupForm(BasicModelForm):

    class Meta:
        model = SaveGroup
        fields = ['name']
        widgets={'name':    forms.TextInput(attrs={'style': 'width: 100%;', 'placeholder': 'The name of this saved items group...'})
                 }

    def __init__(self, *args, **kwargs):
        # Obligatory for this type of form!!!
        self.username = kwargs.pop('username', "")
        self.team_group = kwargs.pop('team_group', "")
        self.userplus = kwargs.pop('userplus', "")
        # Start by executing the standard handling
        super(SaveGroupForm, self).__init__(*args, **kwargs)

        oErr = ErrHandle()
        try:
            username = self.username
            profile = Profile.get_user_profile(username)
            team_group = self.team_group

            # Some fields are not required
            self.fields['name'].required = False

            # Make sure the profile is set correctly
            # self.fields['profileid'].initial = profile.id

            
            # Get the instance
            if 'instance' in kwargs:
                instance = kwargs['instance']
                # Adapt the profile if this is needed

        except:
            msg = oErr.get_error_message()
            oErr.DoError("SaveGroupForm")
        return None


class ImportSetForm(BasicModelForm):
    profileid = forms.CharField(required=False)
    ownlist  = ModelMultipleChoiceField(queryset=None, required=False, 
        widget=ProfileWidget(attrs={'data-minimum-input-length': 0, 'data-placeholder': 'Select multiple profiles...', 
                                    'style': 'width: 100%;', 'class': 'searching'}))
    selitemtypelist   = ModelMultipleChoiceField(queryset=None, required=False, 
                widget=SelItemTypeWidget(attrs={'data-minimum-input-length': 0, 'data-placeholder': 
                                    'Select multiple types...', 'style': 'width: 100%;'}))

    class Meta:
        model = ImportSet
        fields = ['excel', 'notes', 'selitemtype']  # 'profile', 
        widgets={
            #'profile': ProfileOneWidget(attrs={'data-minimum-input-length': 0, 
            #                        'data-placeholder': 'Select one user profile...', 'style': 'width: 100%;'}),
            'excel':   forms.FileInput(attrs={'style': 'width: 100%;', 'placeholder': 'Excel file'}),
            'notes':   forms.Textarea(attrs={'rows': 1, 'cols': 40, 'style': 'height: 40px; width: 100%;',
                                    'placeholder': 'Optionally add your own notes...'}),
            'selitemtype':  forms.Select(attrs={'style': 'width: 100%;'})
                 }

    def __init__(self, *args, **kwargs):
        # Obligatory for this type of form!!!
        self.username = kwargs.pop('username', "")
        self.team_group = kwargs.pop('team_group', "")
        self.userplus = kwargs.pop('userplus', "")
        # Start by executing the standard handling
        super(ImportSetForm, self).__init__(*args, **kwargs)

        oErr = ErrHandle()
        try:
            username = self.username
            profile = Profile.get_user_profile(username)
            team_group = self.team_group

            # Some fields are not required
            self.fields['excel'].required = False
            # self.fields['profile'].required = False
            self.fields['notes'].required = False
            self.fields['selitemtype'].required = False

            # Make sure the profile is set correctly
            # self.fields['profileid'].initial = profile.id

            # Set queryset(s) - for details view
            self.fields['ownlist'].queryset = Profile.objects.all()
            self.fields['selitemtypelist'].queryset = FieldChoice.objects.filter(field=SELITEM_TYPE).order_by("english_name")
            
            # Get the instance
            if 'instance' in kwargs:
                instance = kwargs['instance']
                # Adapt the profile if this is needed
                # self.fields['profileid'].initial = instance.profile.id

        except:
            msg = oErr.get_error_message()
            oErr.DoError("ImportSetForm")
        return None



