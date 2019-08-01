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
                 'incipit':     forms.TextInput(attrs={'class': 'typeahead searching gldincipits input-sm', 'placeholder': 'Incipit...', 'style': 'width: 100%;'}),
                 'explicit':    forms.TextInput(attrs={'class': 'typeahead searching gldexplicits input-sm', 'placeholder': 'Explicit...', 'style': 'width: 100%;'})
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
                           widget=forms.TextInput(attrs={'class': 'input-sm searching', 'placeholder': 'Name or title...',  'style': 'width: 100%;'}))
    idno = forms.CharField(label=_("Idno"), required=False, 
                           widget=forms.TextInput(attrs={'class': 'typeahead searching manuidnos input-sm', 'placeholder': 'Identifier...',  'style': 'width: 100%;'}))


class SermonForm(forms.ModelForm):
    # parent_id = forms.CharField(required=False)
    authorname = forms.CharField(label=_("Author"), required=False, 
                           widget=forms.TextInput(attrs={'class': 'typeahead searching authors input-sm', 'placeholder': 'Author...', 'style': 'width: 100%;'}))
    nickname_ta = forms.CharField(label=_("Alternative"), required=False, 
                           widget=forms.TextInput(attrs={'class': 'typeahead searching nicknames input-sm', 'placeholder': 'Other author...', 'style': 'width: 100%;'}))
    libname_ta = forms.CharField(label=_("Library"), required=False, 
                           widget=forms.TextInput(attrs={'class': 'typeahead searching libraries input-sm', 'placeholder': 'Name of library...',  'style': 'width: 100%;'}))
    signature = forms.CharField(label=_("Signature"), required=False,
        widget=forms.TextInput(attrs={'class': 'typeahead searching signatures input-sm', 'placeholder': 'Signature (Gryson, Clavis)...', 'style': 'width: 100%;'}))
    siggryson = forms.CharField(label=_("Signature"), required=False,
        widget=forms.TextInput(attrs={'class': 'typeahead searching siggrysons input-sm', 'placeholder': 'Gryson code...', 'style': 'width: 100%;'}))
    sigclavis = forms.CharField(label=_("Signature"), required=False,
        widget=forms.TextInput(attrs={'class': 'typeahead searching sigclavises input-sm', 'placeholder': 'Clavis number...', 'style': 'width: 100%;'}))
    manuidno = forms.CharField(label=_("Manuscript"), required=False,
        widget=forms.TextInput(attrs={'class': 'typeahead searching manuidnos input-sm', 'placeholder': 'Manuscript identifier...', 'style': 'width: 100%;'}))

    class Meta:
        ATTRS_FOR_FORMS = {'class': 'form-control'};

        model = SermonDescr
        fields = ['title', 'author', 'nickname', 'locus', 'incipit', 'explicit', 'quote', 'clavis', 'gryson', 
                  'feast', 'bibleref', 'edition', 'additional', 'note', 'keyword', 'stype']
        widgets={'title':       forms.TextInput(attrs={'style': 'width: 100%;'}),
                 'author':      forms.TextInput(attrs={'style': 'width: 100%;'}),
                 'nickname':    forms.TextInput(attrs={'style': 'width: 100%;'}),
                 'locus':       forms.TextInput(attrs={'style': 'width: 40%;'}),
                 'clavis':      forms.TextInput(attrs={'class': 'typeahead searching sigclavises input-sm', 'placeholder': 'Clavis number...', 'style': 'width: 100%;'}),
                 'gryson':      forms.TextInput(attrs={'class': 'typeahead searching siggrysons input-sm', 'placeholder': 'Gryson code...', 'style': 'width: 100%;'}),
                 'edition':     forms.TextInput(attrs={'style': 'width: 100%;'}),
                 'feast':       forms.TextInput(attrs={'style': 'width: 100%;'}),
                 'keyword':     forms.TextInput(attrs={'style': 'width: 100%;'}),

                 'incipit':     forms.TextInput(attrs={'class': 'typeahead searching srmincipits input-sm', 'placeholder': 'Incipit...', 'style': 'width: 100%;'}),
                 'explicit':    forms.TextInput(attrs={'class': 'typeahead searching srmexplicits input-sm', 'placeholder': 'Explicit...', 'style': 'width: 100%;'}),
                 'stype':       forms.Select(attrs={'style': 'width: 100%;'}),

                 # larger areas
                 'quote':       forms.Textarea(attrs={'rows': 1, 'cols': 40, 'style': 'height: 40px; width: 100%;'}),
                 'bibleref':    forms.Textarea(attrs={'rows': 1, 'cols': 40, 'style': 'height: 40px; width: 100%;'}),
                 'additional':  forms.Textarea(attrs={'rows': 1, 'cols': 40, 'style': 'height: 40px; width: 100%;'}),
                 'note':        forms.Textarea(attrs={'rows': 1, 'cols': 40, 'style': 'height: 40px; width: 100%;'}),
                 }

    def __init__(self, *args, **kwargs):
        # Start by executing the standard handling
        super(SermonForm, self).__init__(*args, **kwargs)
        # Some fields are not required
        self.fields['stype'].required = False
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


class SermonDescrSignatureForm(forms.ModelForm):
    class Meta:
        ATTRS_FOR_FORMS = {'class': 'form-control'};

        model = SermonSignature
        fields = ['code', 'editype', 'sermon']
        widgets={'editype':     forms.Select(attrs={'style': 'width: 100%;'})
                 }

    def __init__(self, *args, **kwargs):
        # Start by executing the standard handling
        super(SermonDescrSignatureForm, self).__init__(*args, **kwargs)
        # Initialize choices for editype
        init_choices(self, 'editype', EDI_TYPE, bUseAbbr=True)


class SermonDescrGoldForm(forms.ModelForm):
    class Meta:
        ATTRS_FOR_FORMS = {'class': 'form-control'};

        model = SermonDescrGold
        fields = ['sermon', 'linktype', 'gold' ]
        widgets={'linktype':    forms.Select(attrs={'style': 'width: 100%;'})
                 }

    def __init__(self, *args, **kwargs):
        # Start by executing the standard handling
        super(SermonDescrGoldForm, self).__init__(*args, **kwargs)
        # Initialize choices for linktype
        init_choices(self, 'linktype', LINK_TYPE, bUseAbbr=True)
        # Get the instance
        if 'instance' in kwargs:
            instance = kwargs['instance']
            if instance != None:
                #  NOTE: the following has no effect because we use bound fields
                #       self.fields['linktype'].initial = instance.linktype
                #       self.fields['dst'].initial = instance.dst
                pass


class SermonGoldForm(forms.ModelForm):
    authorname = forms.CharField(label=_("Author"), required=False, 
        widget=forms.TextInput(attrs={'class': 'typeahead searching authors input-sm', 'placeholder': 'Author...', 'style': 'width: 100%;'}))
    signature = forms.CharField(label=_("Signature"), required=False,
        widget=forms.TextInput(attrs={'class': 'typeahead searching signatures input-sm', 'placeholder': 'Signature/code (Gryson, Clavis)...', 'style': 'width: 100%;'}))
    keyword = forms.CharField(label=_("Keyword"), required=False,
        widget=forms.TextInput(attrs={'class': 'typeahead searching keywords input-sm', 'placeholder': 'Keyword(s)...', 'style': 'width: 100%;'}))

    class Meta:
        ATTRS_FOR_FORMS = {'class': 'form-control'};

        model = SermonGold
        fields = ['author', 'incipit', 'explicit', 'bibliography', 'stype' ]
        widgets={'author':      forms.TextInput(attrs={'style': 'width: 100%;'}),
                 'incipit':     forms.TextInput(attrs={'class': 'typeahead searching gldincipits input-sm', 'placeholder': 'Incipit...', 'style': 'width: 100%;'}),
                 'explicit':    forms.TextInput(attrs={'class': 'typeahead searching gldexplicits input-sm', 'placeholder': 'Explicit...', 'style': 'width: 100%;'}),
                 'bibliography': forms.Textarea(attrs={'rows': 2, 'cols': 40, 'style': 'height: 80px; width: 100%; font-family: monospace'}),
                 'stype':       forms.Select(attrs={'style': 'width: 100%;'})
                 }

    def __init__(self, *args, **kwargs):
        # Start by executing the standard handling
        super(SermonGoldForm, self).__init__(*args, **kwargs)
        # Some fields are not required
        self.fields['stype'].required = False
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
                #  NOTE: the following has no effect because we use bound fields
                #       self.fields['linktype'].initial = instance.linktype
                #       self.fields['dst'].initial = instance.dst
                pass


class EqualGoldForm(forms.ModelForm):
    gold = forms.CharField(label=_("Destination gold sermon"), required=True)

    class Meta:
        ATTRS_FOR_FORMS = {'class': 'form-control'};

        model = EqualGold
        fields = [ ]


class EqualGoldLinkForm(forms.ModelForm):
    gold = forms.CharField(label=_("Destination gold sermon"), required=False)

    class Meta:
        ATTRS_FOR_FORMS = {'class': 'form-control'};

        model = EqualGoldLink
        fields = ['src', 'linktype', 'dst' ]
        widgets={'linktype':    forms.Select(attrs={'style': 'width: 100%;'})
                 }

    def __init__(self, *args, **kwargs):
        # Start by executing the standard handling
        super(EqualGoldLinkForm, self).__init__(*args, **kwargs)
        # Initialize choices for linktype
        init_choices(self, 'linktype', LINK_TYPE, bUseAbbr=True)
        # Make sure to set required and optional fields
        self.fields['dst'].required = False
        # Get the instance
        if 'instance' in kwargs:
            instance = kwargs['instance']
            if instance != None:
                #  NOTE: the following has no effect because we use bound fields
                #       self.fields['linktype'].initial = instance.linktype
                #       self.fields['dst'].initial = instance.dst
                pass


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


class SermonGoldKeywordForm(forms.ModelForm):
    name = forms.CharField(label=_("Keyword"), required=False, 
                           widget=forms.TextInput(attrs={'class': 'typeahead searching keywords input-sm', 'placeholder': 'Keyword...',  'style': 'width: 100%;'}))

    class Meta:
        ATTRS_FOR_FORMS = {'class': 'form-control'};

        model = SermonGoldKeyword
        fields = ['gold', 'keyword']

    def __init__(self, *args, **kwargs):
        # Start by executing the standard handling
        super(SermonGoldKeywordForm, self).__init__(*args, **kwargs)
        # Set the keyword to optional for best processing
        self.fields['keyword'].required = False
        # Get the instance
        if 'instance' in kwargs:
            instance = kwargs['instance']
            # Check if the initial name should be added
            if instance.keyword != None:
                kw = instance.keyword.name
                self.fields['name'].initial = kw


class ManuscriptProvForm(forms.ModelForm):
    name = forms.CharField(label=_("Name"), required=False, 
                           widget=forms.TextInput(attrs={'placeholder': 'Name...',  'style': 'width: 100%;'}))
    note = forms.CharField(label=_("Note"), required=False,
                           widget = forms.Textarea(attrs={'rows': 1, 'cols': 40, 'style': 'height: 40px; width: 100%;'}))
    location = forms.CharField(required=False)
    location_ta = forms.CharField(label=_("Location"), required=False, 
                           widget=forms.TextInput(attrs={'class': 'typeahead searching locations input-sm', 'placeholder': 'Location...',  'style': 'width: 100%;'}))

    class Meta:
        ATTRS_FOR_FORMS = {'class': 'form-control'};

        model = ProvenanceMan
        fields = ['provenance', 'manuscript']

    def __init__(self, *args, **kwargs):
        # Start by executing the standard handling
        super(ManuscriptProvForm, self).__init__(*args, **kwargs)
        # Set the keyword to optional for best processing
        self.fields['name'].required = False
        self.fields['note'].required = False
        self.fields['provenance'].required = False
        self.fields['location'].required = False
        self.fields['location_ta'].required = False
        # Get the instance
        if 'instance' in kwargs:
            instance = kwargs['instance']
            # Check if the initial name should be added
            if instance.provenance != None:
                self.fields['name'].initial = instance.provenance.name
                self.fields['note'].initial = instance.provenance.note
                if instance.provenance.location != None:
                    self.fields['location_ta'].initial = instance.provenance.location.get_loc_name()


class OriginForm(forms.ModelForm):
    location_ta = forms.CharField(label=_("Location"), required=False, 
                           widget=forms.TextInput(attrs={'class': 'typeahead searching locations input-sm', 'placeholder': 'Location...',  'style': 'width: 100%;'}))

    class Meta:
        ATTRS_FOR_FORMS = {'class': 'form-control'};

        model = Origin
        fields = ['name', 'location', 'note']
        widgets={'name':     forms.TextInput(attrs={'placeholder': 'Name...', 'style': 'width: 100%;'}),
                 'location': forms.TextInput(attrs={'style': 'width: 100%;'}),
                 'note':     forms.Textarea(attrs={'rows': 1, 'cols': 40, 'placeholder': 'Note on this origin...', 'style': 'height: 40px; width: 100%;'})
                 }

    def __init__(self, *args, **kwargs):
        # Start by executing the standard handling
        super(OriginForm, self).__init__(*args, **kwargs)
        # Set the keyword to optional for best processing
        self.fields['name'].required = False
        self.fields['note'].required = False
        self.fields['location'].required = False
        self.fields['location_ta'].required = False
        # Get the instance
        if 'instance' in kwargs:
            instance = kwargs['instance']
            # Check if the initial name should be added
            if instance != None:
                self.fields['name'].initial = instance.name
                self.fields['note'].initial = instance.note
                if instance.location != None:
                    self.fields['location_ta'].initial = instance.location.get_loc_name()



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
        fields = ['name', 'yearstart', 'yearfinish', 'library', 'idno', 'origin', 'url', 'support', 'extent', 'format', 'literature', 'stype']
        widgets={'library':     forms.TextInput(attrs={'style': 'width: 100%;'}),
                 'name':        forms.TextInput(attrs={'style': 'width: 100%;'}),
                 'yearstart':   forms.TextInput(attrs={'style': 'width: 40%;'}),
                 'yearfinish':  forms.TextInput(attrs={'style': 'width: 40%;'}),
                 'idno':        forms.TextInput(attrs={'class': 'typeahead searching manuidnos input-sm', 'placeholder': 'Identifier...',  'style': 'width: 100%;'}),
                 'origin':      forms.TextInput(attrs={'style': 'width: 100%;'}),
                 'url':         forms.TextInput(attrs={'style': 'width: 100%;'}),
                 'format':      forms.TextInput(attrs={'style': 'width: 100%;'}),
                 'extent':      forms.Textarea(attrs={'rows': 1, 'cols': 40, 'style': 'height: 40px; width: 100%;'}),
                 'literature':  forms.Textarea(attrs={'rows': 1, 'cols': 40, 'style': 'height: 40px; width: 100%;'}),
                 'support':     forms.Textarea(attrs={'rows': 1, 'cols': 40, 'style': 'height: 40px; width: 100%;'}),
                 'stype':       forms.Select(attrs={'style': 'width: 100%;'})
                 }

    def __init__(self, *args, **kwargs):
        # Start by executing the standard handling
        super(ManuscriptForm, self).__init__(*args, **kwargs)
        # Some fields are not required
        self.fields['stype'].required = False
        # Get the instance
        if 'instance' in kwargs:
            instance = kwargs['instance']
            # If there is an instance, then check if a library is specified
            library = instance.library
            if library != None:
                # In this case: get the city and the country
                city = library.get_city_name()
                country = library.get_country_name()
                if (country == None or country == "") and city != None and city != "":
                    # We have a city, but the country is not specified...
                    lstQ = []
                    lstQ.append(Q(loctype__name="country"))
                    lstQ.append(Q(relations_location=library.lcity))
                    obj = Location.objects.filter(*lstQ).first()
                    if obj != None:
                        country = obj.name
                # Put them in the fields
                self.fields['city_ta'].initial = city
                self.fields['country_ta'].initial = country
                # Also: make sure we put the library NAME in the initial
                self.fields['libname_ta'].initial = library.name
            # Look after origin
            origin = instance.origin
            self.fields['origname_ta'].initial = "" if origin == None else origin.name


class LocationForm(forms.ModelForm):

    class Meta:
        ATTRS_FOR_FORMS = {'class': 'form-control'};

        model = Location
        fields = ['name', 'loctype']
        widgets={'name':        forms.TextInput(attrs={'style': 'width: 100%;'}),
                 'loctype':     forms.Select(attrs={'style': 'width: 100%;'})
                 }

    def __init__(self, *args, **kwargs):
        # Start by executing the standard handling
        super(LocationForm, self).__init__(*args, **kwargs)
        # All fields are required
        # Get the instance
        if 'instance' in kwargs:
            instance = kwargs['instance']


class LocationRelForm(forms.ModelForm):
    partof_ta = forms.CharField(label=_("Part of"), required=False, 
                           widget=forms.TextInput(attrs={'class': 'typeahead searching locations input-sm', 'placeholder': 'Part of...',  'style': 'width: 100%;'}))
    partof = forms.CharField(required=False)

    class Meta:
        ATTRS_FOR_FORMS = {'class': 'form-control'};

        model = LocationRelation
        fields = ['container', 'contained']

    def __init__(self, *args, **kwargs):
        # Start by executing the standard handling
        super(LocationRelForm, self).__init__(*args, **kwargs)

        # Set other parameters
        self.fields['partof_ta'].required = False
        self.fields['partof'].required = False
        self.fields['container'].required = False
        # Get the instance
        if 'instance' in kwargs:
            instance = kwargs['instance']
            # Check if the initial name should be added
            if instance.container != None:
                self.fields['partof_ta'].initial = instance.container.get_loc_name()


class SearchCollectionForm(forms.Form):
    country = forms.CharField(label=_("Country"), required=False)
    city = forms.CharField(label=_("City"), required=False)
    library = forms.CharField(label=_("Library"), required=False)
    signature = forms.CharField(label=_("Signature code"), required=False)


class LibrarySearchForm(forms.Form):
    country = forms.CharField(label=_("Country"), required=False, 
                           widget=forms.TextInput(attrs={'class': 'typeahead searching countries input-sm', 'placeholder': 'Country...', 'style': 'width: 100%;'}))
    city = forms.CharField(label=_("City"), required=False, 
                           widget=forms.TextInput(attrs={'class': 'typeahead searching cities input-sm', 'placeholder': 'City...',  'style': 'width: 100%;'}))
    name = forms.CharField(label=_("Library"), required=False, 
                           widget=forms.TextInput(attrs={'class': 'typeahead searching libraries input-sm', 'placeholder': 'Name of library...',  'style': 'width: 100%;'}))


class ReportEditForm(forms.ModelForm):

    class Meta:
        model = Report
        fields = ['user', 'created', 'reptype', 'contents']
        widgets={'user':         forms.TextInput(attrs={'style': 'width: 100%;'}),
                 'created':      forms.TextInput(attrs={'style': 'width: 100%;'}),
                 'reptype':      forms.TextInput(attrs={'style': 'width: 100%;'}),
                 'contents':     forms.Textarea(attrs={'rows': 1, 'cols': 40, 'style': 'height: 40px; width: 100%;'})
                 }


class SourceEditForm(forms.ModelForm):

    class Meta:
        model = SourceInfo
        fields = [ 'code', 'url']
        widgets={'url':          forms.TextInput(attrs={'style': 'width: 100%;'}),
                 'code':     forms.Textarea(attrs={'rows': 1, 'cols': 40, 'style': 'height: 40px; width: 100%;'})
                 }


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


class SearchUrlForm(forms.Form):
    """Specify an URL"""

    search_url = forms.URLField(label="Give the URL",
                                widget=forms.URLInput(attrs={'placeholder': 'Enter the search URL...', 'style': 'width: 100%;'}))
