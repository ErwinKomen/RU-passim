"""
Definition of forms.
"""

from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.utils.translation import ugettext_lazy as _
from django.forms.widgets import *
from passim.seeker.models import *

def init_choices(obj, sFieldName, sSet, maybe_empty=False, bUseAbbr=False):
    if (obj.fields != None and sFieldName in obj.fields):
        if bUseAbbr:
            obj.fields[sFieldName].choices = build_abbr_list(sSet, maybe_empty=maybe_empty)
        else:
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
    """Note: only for SEARCHING"""

    author = forms.CharField(label=_("Author"), required=False)
    incipit = forms.CharField(label=_("Incipit"), required=False)
    explicit = forms.CharField(label=_("Explicit"), required=False)
    title = forms.CharField(label=_("Title"), required=False)
    signature = forms.CharField(label=_("Signature"), required=False)
    feast = forms.CharField(label=_("Feast"), required=False)
    keyword = forms.CharField(label=_("Keyword"), required=False)


class SelectGoldForm(forms.ModelForm):
    """Note: only for searching and selecting"""

    source_id = forms.CharField(label=_("Source"), required=False)
    authorname = forms.CharField(label=_("Author"), 
        required=False, 
        widget=forms.TextInput(attrs={'class': 'typeahead searching authors input-sm', 'placeholder': 'Author...', 'style': 'width: 100%;'}))
    signature = forms.CharField(label=_("Signature"), 
        required=False,
        widget=forms.TextInput(attrs={'class': 'typeahead searching signatures input-sm', 'placeholder': 'Signature (Gryson, Clavis)...', 'style': 'width: 100%;'}))

    class Meta:
        ATTRS_FOR_FORMS = {'class': 'form-control'};

        model = SermonGold
        fields = ['author', 'incipit', 'explicit' ]
        widgets={
                 'author':      forms.TextInput(attrs={'style': 'width: 100%;'}),
                 'incipit':     forms.TextInput(attrs={'class': 'typeahead searching incipits input-sm', 'placeholder': 'Incipit...', 'style': 'width: 100%;'}),
                 'explicit':    forms.TextInput(attrs={'class': 'typeahead searching explicits input-sm', 'placeholder': 'Explicit...', 'style': 'width: 100%;'})
                 }

    def __init__(self, *args, **kwargs):
        # Start by executing the standard handling
        super(SelectGoldForm, self).__init__(*args, **kwargs)
        # Make sure to set required and optional fields
        self.fields['source_id'].required = False
        self.fields['signature'].required = False
        self.fields['authorname'].required = False
        if 'author' in self.fields: self.fields['author'].required = False
        if 'incipit' in self.fields: self.fields['incipit'].required = False
        if 'explicit' in self.fields: self.fields['explicit'].required = False
        # Get the instance
        if 'instance' in kwargs:
            instance = kwargs['instance']
            # If there is an instance, then check the author specification
            sAuthor = "" if not instance.author else instance.author.name
            self.fields['authorname'].initial = sAuthor


class SearchManuscriptForm(forms.Form):
    """Note: only for SEARCHING"""

    country = forms.CharField(label=_("Country"), required=False, 
                           widget=forms.TextInput(attrs={'class': 'typeahead searching countries input-sm', 'placeholder': 'Country...', 'style': 'width: 100%;'}))
    city = forms.CharField(label=_("City"), required=False, 
                           widget=forms.TextInput(attrs={'class': 'typeahead searching cities input-sm', 'placeholder': 'City...',  'style': 'width: 100%;'}))
    library = forms.CharField(label=_("Library"), required=False, 
                           widget=forms.TextInput(attrs={'class': 'typeahead searching libraries input-sm', 'placeholder': 'Name of library...',  'style': 'width: 100%;'}))
    signature = forms.CharField(label=_("Signature"), required=False, 
                           widget=forms.TextInput(attrs={'class': 'typeahead searching signatures input-sm', 'placeholder': 'Signature...',  'style': 'width: 100%;'}))
    name = forms.CharField(label=_("Title"), required=False, 
                           widget=forms.TextInput(attrs={'class': 'input-sm searching', 'placeholder': 'Title...',  'style': 'width: 100%;'}))


class SermonForm(forms.ModelForm):
    # parent_id = forms.CharField(required=False)
    authorname = forms.CharField(label=_("Author"), required=False, 
                           widget=forms.TextInput(attrs={'class': 'typeahead searching authors input-sm', 'placeholder': 'Author...', 'style': 'width: 100%;'}))
    nickname_ta = forms.CharField(label=_("Alternative"), required=False, 
                           widget=forms.TextInput(attrs={'class': 'typeahead searching nicknames input-sm', 'placeholder': 'Other author...', 'style': 'width: 100%;'}))
    libname_ta = forms.CharField(label=_("Library"), required=False, 
                           widget=forms.TextInput(attrs={'class': 'typeahead searching libraries input-sm', 'placeholder': 'Name of library...',  'style': 'width: 100%;'}))

    class Meta:
        ATTRS_FOR_FORMS = {'class': 'form-control'};

        model = SermonDescr
        fields = ['title', 'author', 'nickname', 'locus', 'incipit', 'explicit', 'quote', 'clavis', 'gryson', 
                  'feast', 'bibleref', 'edition', 'additional', 'note', 'keyword']
        widgets={'title':       forms.TextInput(attrs={'style': 'width: 100%;'}),
                 'author':      forms.TextInput(attrs={'style': 'width: 100%;'}),
                 'nickname':    forms.TextInput(attrs={'style': 'width: 100%;'}),
                 'locus':       forms.TextInput(attrs={'style': 'width: 40%;'}),
                 'clavis':      forms.TextInput(attrs={'style': 'width: 100%;'}),
                 'gryson':      forms.TextInput(attrs={'style': 'width: 100%;'}),
                 'edition':     forms.TextInput(attrs={'style': 'width: 100%;'}),
                 'feast':       forms.TextInput(attrs={'style': 'width: 100%;'}),
                 'keyword':     forms.TextInput(attrs={'style': 'width: 100%;'}),

                 'incipit':     forms.Textarea(attrs={'rows': 1, 'cols': 40, 'style': 'height: 40px; width: 100%;'}),
                 'explicit':    forms.Textarea(attrs={'rows': 1, 'cols': 40, 'style': 'height: 40px; width: 100%;'}),
                 'quote':       forms.Textarea(attrs={'rows': 1, 'cols': 40, 'style': 'height: 40px; width: 100%;'}),
                 'bibleref':    forms.Textarea(attrs={'rows': 1, 'cols': 40, 'style': 'height: 40px; width: 100%;'}),
                 'additional':  forms.Textarea(attrs={'rows': 1, 'cols': 40, 'style': 'height: 40px; width: 100%;'}),
                 'note':        forms.Textarea(attrs={'rows': 1, 'cols': 40, 'style': 'height: 40px; width: 100%;'}),
                 }

    def __init__(self, *args, **kwargs):
        # Start by executing the standard handling
        super(SermonForm, self).__init__(*args, **kwargs)
        # Get the instance
        if 'instance' in kwargs:
            instance = kwargs['instance']
            # If there is an instance, then check the author specification
            sAuthor = "" if not instance.author else instance.author.name
            # If there is an instance, then check the nickname specification
            sNickName = "" if not instance.nickname else instance.nickname.name
            self.fields['authorname'].initial = sAuthor
            self.fields['authorname'].required = False
            self.fields['nickname_ta'].initial = sNickName
            self.fields['nickname_ta'].required = False


class SermonGoldForm(forms.ModelForm):
    authorname = forms.CharField(label=_("Author"), required=False, 
        widget=forms.TextInput(attrs={'class': 'typeahead searching authors input-sm', 'placeholder': 'Author...', 'style': 'width: 100%;'}))
    signature = forms.CharField(label=_("Signature"), required=False,
        widget=forms.TextInput(attrs={'class': 'typeahead searching signatures input-sm', 'placeholder': 'Signature (Gryson, Clavis)...', 'style': 'width: 100%;'}))

    class Meta:
        ATTRS_FOR_FORMS = {'class': 'form-control'};

        model = SermonGold
        fields = ['author', 'incipit', 'explicit', 'bibliography' ]
        widgets={'author':      forms.TextInput(attrs={'style': 'width: 100%;'}),
                 'incipit':     forms.TextInput(attrs={'style': 'width: 100%;'}),
                 'explicit':    forms.TextInput(attrs={'style': 'width: 100%;'}),
                 'bibliography': forms.Textarea(attrs={'rows': 2, 'cols': 40, 'style': 'height: 80px; width: 100%; font-family: monospace'})
                 }

    def __init__(self, *args, **kwargs):
        # Start by executing the standard handling
        super(SermonGoldForm, self).__init__(*args, **kwargs)
        # Get the instance
        if 'instance' in kwargs:
            instance = kwargs['instance']
            # If there is an instance, then check the author specification
            sAuthor = "" if not instance.author else instance.author.name
            self.fields['authorname'].initial = sAuthor
            self.fields['authorname'].required = False


class SermonGoldSameForm(forms.ModelForm):
    class Meta:
        ATTRS_FOR_FORMS = {'class': 'form-control'};

        model = SermonGoldSame
        fields = ['src', 'linktype', 'dst' ]
        widgets={'linktype':    forms.Select(attrs={'style': 'width: 100%;'})
                 }

    def __init__(self, *args, **kwargs):
        # Start by executing the standard handling
        super(SermonGoldSameForm, self).__init__(*args, **kwargs)
        # Initialize choices for linktype
        init_choices(self, 'linktype', LINK_TYPE, bUseAbbr=True)
        # Get the instance
        if 'instance' in kwargs:
            instance = kwargs['instance']
            if instance != None:
                pass
                #  NOTE: the following has no effect because we use bound fields
                #       self.fields['linktype'].initial = instance.linktype
                #       self.fields['dst'].initial = instance.dst


class SermonGoldSignatureForm(forms.ModelForm):
    class Meta:
        ATTRS_FOR_FORMS = {'class': 'form-control'};

        model = Signature
        fields = ['code', 'editype', 'gold']
        widgets={'editype':     forms.Select(attrs={'style': 'width: 100%;'})
                 }

    def __init__(self, *args, **kwargs):
        # Start by executing the standard handling
        super(SermonGoldSignatureForm, self).__init__(*args, **kwargs)
        # Initialize choices for editype
        init_choices(self, 'editype', EDI_TYPE, bUseAbbr=True)


class SermonGoldEditionForm(forms.ModelForm):
    class Meta:
        ATTRS_FOR_FORMS = {'class': 'form-control'};

        model = Edition
        fields = ['name', 'gold']
        widgets={'name':     forms.TextInput(attrs={'class': 'typeahead searching editions input-sm', 'placeholder': 'Critical text edition...', 'style': 'width: 100%;'})
                 }


class SermonGoldFtextlinkForm(forms.ModelForm):
    class Meta:
        ATTRS_FOR_FORMS = {'class': 'form-control'};

        model = Ftextlink
        fields = ['url', 'gold']
        widgets={'url':     forms.URLInput(attrs={'placeholder': 'Full text URLs...', 'style': 'width: 100%;'})
                 }


class ManuscriptForm(forms.ModelForm):
    country_ta = forms.CharField(label=_("Country"), required=False, 
                           widget=forms.TextInput(attrs={'class': 'typeahead searching countries input-sm', 'placeholder': 'Country...', 'style': 'width: 100%;'}))
    city_ta = forms.CharField(label=_("City"), required=False, 
                           widget=forms.TextInput(attrs={'class': 'typeahead searching cities input-sm', 'placeholder': 'City...',  'style': 'width: 100%;'}))
    libname_ta = forms.CharField(label=_("Library"), required=False, 
                           widget=forms.TextInput(attrs={'class': 'typeahead searching libraries input-sm', 'placeholder': 'Name of library...',  'style': 'width: 100%;'}))
    origname_ta = forms.CharField(label=_("Origin"), required=False, 
                           widget=forms.TextInput(attrs={'class': 'typeahead searching origins input-sm', 'placeholder': 'Origin...',  'style': 'width: 100%;'}))

    class Meta:
        ATTRS_FOR_FORMS = {'class': 'form-control'};

        model = Manuscript
        fields = ('name', 'yearstart', 'yearfinish', 'library', 'idno', 'origin', 'url', 'support', 'extent', 'format')
        widgets={'library': forms.TextInput(attrs={'style': 'width: 100%;'}),
                 'name': forms.TextInput(attrs={'style': 'width: 100%;'}),
                 'yearstart': forms.TextInput(attrs={'style': 'width: 40%;'}),
                 'yearfinish': forms.TextInput(attrs={'style': 'width: 40%;'}),
                 'idno': forms.TextInput(attrs={'style': 'width: 100%;'}),
                 'origin': forms.TextInput(attrs={'style': 'width: 100%;'}),
                 'url': forms.TextInput(attrs={'style': 'width: 100%;'}),
                 'extent': forms.TextInput(attrs={'style': 'width: 100%;'}),
                 'format': forms.TextInput(attrs={'style': 'width: 100%;'}),

                 'support': forms.Textarea(attrs={'rows': 1, 'cols': 40, 'style': 'height: 40px; width: 100%;'}),
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
                self.fields['city_ta'].initial = city
                self.fields['country_ta'].initial = country
                # Also: make sure we put the library NAME in the initial
                self.fields['libname_ta'].initial = library.name
            # Look after origin
            origin = instance.origin
            self.fields['origname_ta'].initial = "" if origin == None else origin.name


class SearchCollectionForm(forms.Form):
    country = forms.CharField(label=_("Country"), required=False)
    city = forms.CharField(label=_("City"), required=False)
    library = forms.CharField(label=_("Library"), required=False)
    signature = forms.CharField(label=_("Signature code"), required=False)


class LibrarySearchForm(forms.ModelForm):

    class Meta:

        ATTRS_FOR_FORMS = {'class': 'form-control'};

        model = Library
        fields = ('country', 'city', 'libtype', 'name')


class AuthorEditForm(forms.ModelForm):

    class Meta:
        model = Author
        fields = ['name', 'abbr']
        widgets={'name':      forms.TextInput(attrs={'placeholder': 'Name of this author', 'style': 'width: 100%;'}),
                 'abbr':     forms.TextInput(attrs={'placeholder': 'Abbreviation as e.g. used in Gryson', 'style': 'width: 100%;'})
                 }


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



