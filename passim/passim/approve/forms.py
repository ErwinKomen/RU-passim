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
from passim.approve.models import *
from passim.seeker.models import Profile, FieldChoice


# =============== WIDGETS ===============================================
class AtypeWidget(ModelSelect2MultipleWidget):
    model = FieldChoice
    search_fields = [ 'english_name__icontains']

    def label_from_instance(self, obj):
        return obj.english_name

    def get_queryset(self):
        return FieldChoice.objects.filter(field=APPROVAL_TYPE).order_by("english_name")


class EqualGoldMultiWidget(ModelSelect2MultipleWidget):
    model = EqualGold
    search_fields = ['code__icontains', 'id__icontains', 'author__name__icontains', 'equal_goldsermons__siglist__icontains']
    addonly = False

    def label_from_instance(self, obj):
        # sLabel = obj.get_label(do_incexpl = False)
        sLabel = obj.get_code()
        return sLabel

    def get_queryset(self):
        if self.addonly:
            qs = EqualGold.objects.none()
        else:
            qs = EqualGold.objects.filter(code__isnull=False, moved__isnull=True).order_by('code').distinct()
        return qs


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




# ================ FORMS ================================================
class EqualAddForm(forms.ModelForm):
    """Form to list and to edit EqualAdd items"""

    profilelist = ModelMultipleChoiceField(queryset=None, required=False, 
                widget=ProfileWidget(attrs={'data-placeholder': 'Select multiple users...', 'style': 'width: 100%;', 'class': 'searching'}))
    passimlist  = ModelMultipleChoiceField(queryset=None, required=False, 
                widget=EqualGoldMultiWidget(attrs={'data-placeholder': 'Select multiple passim codes...', 'style': 'width: 100%;', 
                                                       'class': 'searching'}))
    atypelist   = ModelMultipleChoiceField(queryset=None, required=False, 
                widget=AtypeWidget(attrs={'data-placeholder': 'Select multiple approval types...', 'style': 'width: 100%;'}))

    class Meta:
        model = EqualAdd
        fields = ['super', 'profile', 'atype']
        widgets={'profile': ProfileOneWidget(attrs={'data-placeholder': 'Select one user profile...', 'style': 'width: 100%;'}),
                 }

    def __init__(self, *args, **kwargs):
        self.username = kwargs.pop('username', "")
        self.team_group = kwargs.pop('team_group', "")
        self.userplus = kwargs.pop('userplus', "")
        # Start by executing the standard handling
        super(EqualAddForm, self).__init__(*args, **kwargs)

        oErr = ErrHandle()
        try:
            # Some fields are not required
            self.fields['super'].required = False            
            self.fields['profile'].required = False
            self.fields['atype'].required = False

            # Set queryset(s) - for details view
            self.fields['profilelist'].queryset = Profile.objects.all().order_by('user__username')
            self.fields['passimlist'].queryset = EqualGold.objects.filter(code__isnull=False, moved__isnull=True).order_by('code')
            self.fields['atypelist'].queryset = FieldChoice.objects.filter(field=APPROVAL_TYPE).order_by("english_name")

            # Get the instance
            if 'instance' in kwargs:
                instance = kwargs['instance']   

        except:
            msg = oErr.get_error_message()
            oErr.DoError("EqualChangeForm")
        return None


class EqualAddApprovalForm(forms.ModelForm):
    """Form to list and to edit EqualAddApproval items"""

    profilelist = ModelMultipleChoiceField(queryset=None, required=False, 
                widget=ProfileWidget(attrs={'data-placeholder': 'Select multiple users...', 'style': 'width: 100%;', 'class': 'searching'}))
    passimlist  = ModelMultipleChoiceField(queryset=None, required=False, 
                widget=EqualGoldMultiWidget(attrs={'data-placeholder': 'Select multiple passim codes...', 'style': 'width: 100%;', 
                                                       'class': 'searching'}))
    atypelist   = ModelMultipleChoiceField(queryset=None, required=False, 
                widget=AtypeWidget(attrs={'data-placeholder': 'Select multiple approval types...', 'style': 'width: 100%;'}))

    class Meta:
        model = EqualAddApproval
        fields = ['add', 'profile', 'comment', 'atype']
        widgets={'profile':  ProfileOneWidget(attrs={'data-placeholder': 'Select one user profile...', 'style': 'width: 100%;'}),
                 'comment':  forms.Textarea(attrs={'rows': 1, 'cols': 40, 'style': 'height: 40px; width: 100%;', 
                                                   'class': 'searching', 'placeholder': 'Any comment on your choice...'}),
                 'atype':    forms.Select(attrs={'style': 'width: 100%;'})
                 }

    def __init__(self, *args, **kwargs):
        self.username = kwargs.pop('username', "")
        self.team_group = kwargs.pop('team_group', "")
        self.userplus = kwargs.pop('userplus', "")
        # Start by executing the standard handling
        super(EqualAddApprovalForm, self).__init__(*args, **kwargs)

        oErr = ErrHandle()
        try:
            # Some fields are not required  TH: hier add?
            self.fields['add'].required = False 
            self.fields['comment'].required = False
            self.fields['profile'].required = False
            self.fields['atype'].required = False

            # Set queryset(s) - for details view
            self.fields['profilelist'].queryset = Profile.objects.all().order_by('user__username')
            self.fields['passimlist'].queryset = EqualGold.objects.filter(code__isnull=False, moved__isnull=True).order_by('code')
            self.fields['atypelist'].queryset = FieldChoice.objects.filter(field=APPROVAL_TYPE).order_by("english_name")

            # Get the instance
            if 'instance' in kwargs:
                instance = kwargs['instance']   

        except:
            msg = oErr.get_error_message()
            oErr.DoError("EqualAddApprovalForm")
        return None


class EqualChangeForm(forms.ModelForm):
    """Form to list and to edit EqualChange items"""

    profilelist = ModelMultipleChoiceField(queryset=None, required=False, 
                widget=ProfileWidget(attrs={'data-placeholder': 'Select multiple users...', 'style': 'width: 100%;', 'class': 'searching'}))
    passimlist  = ModelMultipleChoiceField(queryset=None, required=False, 
                widget=EqualGoldMultiWidget(attrs={'data-placeholder': 'Select multiple passim codes...', 'style': 'width: 100%;', 
                                                       'class': 'searching'}))
    atypelist   = ModelMultipleChoiceField(queryset=None, required=False, 
                widget=AtypeWidget(attrs={'data-placeholder': 'Select multiple approval types...', 'style': 'width: 100%;'}))

    class Meta:
        model = EqualChange
        fields = ['super', 'field', 'profile', 'atype']
        widgets={'field':    forms.TextInput(attrs={'style': 'width: 100%;', 'placeholder': 'Field name...'}),
                 'profile': ProfileOneWidget(attrs={'data-placeholder': 'Select one user profile...', 'style': 'width: 100%;'}),
                 }

    def __init__(self, *args, **kwargs):
        self.username = kwargs.pop('username', "")
        self.team_group = kwargs.pop('team_group', "")
        self.userplus = kwargs.pop('userplus', "")
        # Start by executing the standard handling
        super(EqualChangeForm, self).__init__(*args, **kwargs)

        oErr = ErrHandle()
        try:
            # Some fields are not required
            self.fields['super'].required = False
            self.fields['field'].required = False
            self.fields['profile'].required = False
            self.fields['atype'].required = False

            # Set queryset(s) - for details view
            self.fields['profilelist'].queryset = Profile.objects.all().order_by('user__username')
            self.fields['passimlist'].queryset = EqualGold.objects.filter(code__isnull=False, moved__isnull=True).order_by('code')
            self.fields['atypelist'].queryset = FieldChoice.objects.filter(field=APPROVAL_TYPE).order_by("english_name")

            # Get the instance
            if 'instance' in kwargs:
                instance = kwargs['instance']   

        except:
            msg = oErr.get_error_message()
            oErr.DoError("EqualChangeForm")
        return None


class EqualApprovalForm(forms.ModelForm):
    """Form to list and to edit EqualApproval items"""

    profilelist = ModelMultipleChoiceField(queryset=None, required=False, 
                widget=ProfileWidget(attrs={'data-placeholder': 'Select multiple users...', 'style': 'width: 100%;', 'class': 'searching'}))
    passimlist  = ModelMultipleChoiceField(queryset=None, required=False, 
                widget=EqualGoldMultiWidget(attrs={'data-placeholder': 'Select multiple passim codes...', 'style': 'width: 100%;', 
                                                       'class': 'searching'}))
    atypelist   = ModelMultipleChoiceField(queryset=None, required=False, 
                widget=AtypeWidget(attrs={'data-placeholder': 'Select multiple approval types...', 'style': 'width: 100%;'}))

    class Meta:
        model = EqualApproval
        fields = ['change', 'profile', 'comment', 'atype']
        widgets={'profile':  ProfileOneWidget(attrs={'data-placeholder': 'Select one user profile...', 'style': 'width: 100%;'}),
                 'comment':  forms.Textarea(attrs={'rows': 1, 'cols': 40, 'style': 'height: 40px; width: 100%;', 
                                                   'class': 'searching', 'placeholder': 'Any comment on your choice...'}),
                 'atype':    forms.Select(attrs={'style': 'width: 100%;'})
                 }

    def __init__(self, *args, **kwargs):
        self.username = kwargs.pop('username', "")
        self.team_group = kwargs.pop('team_group', "")
        self.userplus = kwargs.pop('userplus', "")
        # Start by executing the standard handling
        super(EqualApprovalForm, self).__init__(*args, **kwargs)

        oErr = ErrHandle()
        try:
            # Some fields are not required
            self.fields['change'].required = False
            self.fields['comment'].required = False
            self.fields['profile'].required = False
            self.fields['atype'].required = False

            # Set queryset(s) - for details view
            self.fields['profilelist'].queryset = Profile.objects.all().order_by('user__username')
            self.fields['passimlist'].queryset = EqualGold.objects.filter(code__isnull=False, moved__isnull=True).order_by('code')
            self.fields['atypelist'].queryset = FieldChoice.objects.filter(field=APPROVAL_TYPE).order_by("english_name")

            # Get the instance
            if 'instance' in kwargs:
                instance = kwargs['instance']   

        except:
            msg = oErr.get_error_message()
            oErr.DoError("EqualApprovalForm")
        return None
