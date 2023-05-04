"""
Definition of forms.
"""

from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.utils.translation import ugettext_lazy as _
from django.forms import ModelMultipleChoiceField, ModelChoiceField
from django.forms.widgets import *
from django.db.models import F
from django_select2.forms import Select2MultipleWidget, ModelSelect2MultipleWidget, ModelSelect2Widget

# From my own application
from passim.utils import ErrHandle
from passim.basic.forms import BasicModelForm, BasicSimpleForm
from passim.dct.models import *
from passim.seeker.models import Profile


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


# ================ FORMS ================================================

class ResearchSetForm(BasicModelForm):
    profileid = forms.CharField(required=False)
    manulist = ModelChoiceField(queryset=None, required=False,
            widget=ManuidOneWidget(attrs={'data-placeholder': 'Select manuscript...', 'style': 'width: 100%;'}))
    histlist = ModelChoiceField(queryset=None, required=False)
    ssgdlist = ModelChoiceField(queryset=None, required=False)
    ownlist  = ModelMultipleChoiceField(queryset=None, required=False, 
                widget=ProfileWidget(attrs={'data-placeholder': 'Select multiple profiles...', 'style': 'width: 100%;', 'class': 'searching'}))
    ssgdname = forms.CharField(label="Name", required=False, 
            widget=forms.TextInput(attrs={'class': 'typeahead searching input-sm', 
                                          'placeholder': 'User-defined name (optional)...',  'style': 'width: 100%;'}))

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
                        'data-placeholder': 'Select a historical collection...', 'style': 'width: 100%;', 'class': 'searching'})
            self.fields['ssgdlist'].widget = CollOneSuperWidget( attrs={'username': username, 'team_group': team_group,'settype': 'pd',
                        'data-placeholder': 'Select a personal dataset of SSGs...', 'style': 'width: 100%;', 'class': 'searching'})

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
            widget=ManuidOneWidget(attrs={'data-placeholder': 'Select manuscript...', 'style': 'width: 100%;'}))
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
                        'data-placeholder': 'Select a historical collection...', 'style': 'width: 100%;', 'class': 'searching'})
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
                            'data-placeholder': 'Select a research set...', 'style': 'width: 100%;', 'class': 'searching'})

                # The rsetone information is needed for "selection-to-DCT" processing
                self.fields['rsetone'].queryset = ResearchSet.objects.filter(profile=profile)

        except:
            msg = oErr.get_error_message()
            oErr.DoError("rsetselform")



