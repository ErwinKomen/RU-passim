"""
Definition of forms.
"""

from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.utils.translation import ugettext_lazy as _
from django.forms.widgets import *
from passim.seeker.models import *

def init_choices(obj, sFieldName, sSet, maybe_empty=False):
    if (obj.fields != None and sFieldName in obj.fields):
        obj.fields[sFieldName].choices = build_choice_list(sSet, maybe_empty=maybe_empty)
        obj.fields[sFieldName].help_text = get_help(sSet)



class BootstrapAuthenticationForm(AuthenticationForm):
    """Authentication form which uses boostrap CSS."""
    username = forms.CharField(max_length=254,
                               widget=forms.TextInput({
                                   'class': 'form-control',
                                   'placeholder': 'User name'}))
    password = forms.CharField(label=_("Password"),
                               widget=forms.PasswordInput({
                                   'class': 'form-control',
                                   'placeholder':'Password'}))


class SignUpForm(UserCreationForm):
    first_name = forms.CharField(max_length=30, required=False, help_text='Optional.')
    last_name = forms.CharField(max_length=30, required=False, help_text='Optional.')
    email = forms.EmailField(max_length=254, help_text='Required. Inform a valid email address.')

    class Meta:
        model = User
        fields = ('username', 'first_name', 'last_name', 'email', 'password1', 'password2', )


class SearchSermonForm(forms.Form):
    author = forms.CharField(label=_("Author"), required=False)
    incipit = forms.CharField(label=_("Incipit"), required=False)
    explicit = forms.CharField(label=_("Explicit"), required=False)
    title = forms.CharField(label=_("Title"), required=False)
    clavis = forms.CharField(label=_("Clavis"), required=False)
    gryson = forms.CharField(label=_("Gryson"), required=False)
    feast = forms.CharField(label=_("Feast"), required=False)
    keyword = forms.CharField(label=_("Keyword"), required=False)

class SearchManuscriptForm(forms.Form):
    country = forms.CharField(label=_("Country"), required=False, 
                           widget=forms.TextInput(attrs={'class': 'typeahead searching countries input-sm', 'placeholder': 'Country...', 'style': 'width: 100%;'}))
    city = forms.CharField(label=_("City"), required=False, 
                           widget=forms.TextInput(attrs={'class': 'typeahead searching cities input-sm', 'placeholder': 'City...',  'style': 'width: 100%;'}))
    library = forms.CharField(label=_("Library"), required=False, 
                           widget=forms.TextInput(attrs={'class': 'typeahead searching libraries input-sm', 'placeholder': 'Name of library...',  'style': 'width: 100%;'}))
    signature = forms.CharField(label=_("Signature"), required=False, 
                           widget=forms.TextInput(attrs={'class': 'input-sm searching', 'placeholder': 'Signature...',  'style': 'width: 100%;'}))
    name = forms.CharField(label=_("Title"), required=False, 
                           widget=forms.TextInput(attrs={'class': 'input-sm searching', 'placeholder': 'Title...',  'style': 'width: 100%;'}))

class ManuscriptForm(forms.ModelForm):
    country = forms.CharField(label=_("Country"), required=False, 
                           widget=forms.TextInput(attrs={'class': 'typeahead searching countries input-sm', 'placeholder': 'Country...', 'style': 'width: 100%;'}))
    city = forms.CharField(label=_("City"), required=False, 
                           widget=forms.TextInput(attrs={'class': 'typeahead searching cities input-sm', 'placeholder': 'City...',  'style': 'width: 100%;'}))
    libname = forms.CharField(label=_("Library"), required=False, 
                           widget=forms.TextInput(attrs={'class': 'typeahead searching libraries input-sm', 'placeholder': 'Name of library...',  'style': 'width: 100%;'}))

    class Meta:
        ATTRS_FOR_FORMS = {'class': 'form-control'};

        model = Manuscript
        fields = ('name', 'yearstart', 'yearfinish', 'library', 'idno', 'origin', 'url', 'support', 'extent', 'format')
        widgets={'library': forms.TextInput(attrs={'class': 'typeahead searching libraries input-sm', 'placeholder': 'Name of library...',  'style': 'width: 100%;'}),
                 'name': forms.TextInput(attrs={'style': 'width: 100%;'}),
                 'yearstart': forms.TextInput(attrs={'style': 'width: 40%;'}),
                 'yearfinish': forms.TextInput(attrs={'style': 'width: 40%;'}),
                 'idno': forms.TextInput(attrs={'style': 'width: 100%;'}),
                 'origin': forms.Select(attrs={'style': 'width: 100%;'}),
                 'url': forms.TextInput(attrs={'style': 'width: 100%;'}),
                 'support': forms.TextInput(attrs={'style': 'width: 100%;'}),
                 'extent': forms.TextInput(attrs={'style': 'width: 100%;'}),
                 'format': forms.TextInput(attrs={'style': 'width: 100%;'}),
                 }

    def __init__(self, *args, **kwargs):
        # Start by executing the standard handling
        super(ManuscriptForm, self).__init__(*args, **kwargs)
        # Get the instance
        if 'instance' in kwargs:
            instance = kwargs['instance']
            # If there is an instance, then check if a library is specified
            library = instance.library
            if library != None:
                # In this case: get the city and the country
                city = library.city.name
                country = library.country.name
                if country == None and city != None and city != "":
                    country = library.city.country.name
                # Put them in the fields
                self.fields['city'].initial = city
                self.fields['country'].initial = country
                # Also: make sure we put the library NAME in the initial
                self.fields['libname'].initial = library.name



class SearchCollectionForm(forms.Form):
    country = forms.CharField(label=_("Country"), required=False)
    city = forms.CharField(label=_("City"), required=False)
    library = forms.CharField(label=_("Library"), required=False)
    signature = forms.CharField(label=_("Signature"), required=False)


class LibrarySearchForm(forms.ModelForm):

    class Meta:

        ATTRS_FOR_FORMS = {'class': 'form-control'};

        model = Library
        fields = ('country', 'city', 'libtype', 'name')


class AuthorSearchForm(forms.ModelForm):

    class Meta:
        ATTRS_FOR_FORMS = {'class': 'form-control'};

        model = Author
        fields = ('name',)


class UploadFileForm(forms.Form):
    """This is for uploading just one file"""

    file_source = forms.FileField(label="Specify which file should be loaded")


class UploadFilesForm(forms.Form):
    """This is for uploading multiple files"""

    files_field = forms.FileField(label="Specify which file(s) should be loaded",
                                  widget=forms.ClearableFileInput(attrs={'multiple': True}))



