"""
Definition of forms.
"""

from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.utils.translation import ugettext_lazy as _
from django.forms import ModelMultipleChoiceField, ModelChoiceField
from django.forms.widgets import *
from django_select2.forms import Select2MultipleWidget, ModelSelect2MultipleWidget, ModelSelect2TagWidget, ModelSelect2Widget, HeavySelect2Widget
from passim.seeker.models import *

def init_choices(obj, sFieldName, sSet, maybe_empty=False, bUseAbbr=False):
    if (obj.fields != None and sFieldName in obj.fields):
        if bUseAbbr:
            obj.fields[sFieldName].choices = build_abbr_list(sSet, maybe_empty=maybe_empty)
        else:
            obj.fields[sFieldName].choices = build_choice_list(sSet, maybe_empty=maybe_empty)
        obj.fields[sFieldName].help_text = get_help(sSet)


# ================= WIDGETS =====================================


class ManuidWidget(ModelSelect2MultipleWidget):
    model = Manuscript
    search_fields = [ 'idno__icontains']

    def label_from_instance(self, obj):
        return obj.idno

    def get_queryset(self):
        return Manuscript.objects.all().order_by('idno').distinct()


class SignatureWidget(ModelSelect2MultipleWidget):
    model = Signature
    search_fields = [ 'code__icontains' ]

    def label_from_instance(self, obj):
        return obj.code

    def get_queryset(self):
        return Signature.objects.all().order_by('code').distinct()


class KeywordWidget(ModelSelect2MultipleWidget):
    model = Keyword
    search_fields = [ 'name__icontains' ]

    def label_from_instance(self, obj):
        return obj.name

    def get_queryset(self):
        return Keyword.objects.all().order_by('name').distinct()


class LitrefWidget(ModelSelect2Widget):
    model = Litref
    search_fields = [ 'full__icontains' ]

    def label_from_instance(self, obj):
        # The label only gives the SHORT version!!
        short = obj.get_short()
        full = obj.full
        # Determine here what to return...
        return full

    def get_queryset(self):
        return Litref.objects.exclude(full="").order_by('full').distinct()


class LitrefSgWidget(ModelSelect2MultipleWidget):
    model = LitrefSG
    search_fields = [ 'reference__full__icontains' ]

    def label_from_instance(self, obj):
        # The label only gives the SHORT version!!
        return obj.get_short()

    def get_queryset(self):
        return LitrefSG.objects.all().order_by('reference__full', 'pages').distinct()


class EdirefSgWidget(ModelSelect2MultipleWidget):
    model = EdirefSG
    search_fields = [ 'reference__full__icontains' ]

    def label_from_instance(self, obj):
        # The label only gives the SHORT version!!
        return obj.get_short()

    def get_queryset(self):
        return EdirefSG.objects.all().order_by('reference__full', 'pages').distinct()


class ProjectWidget(ModelSelect2MultipleWidget):
    model = Project
    search_fields = [ 'name__icontains' ]

    def label_from_instance(self, obj):
        return obj.name

    def get_queryset(self):
        return Project.objects.all().order_by('name').distinct()


class ProfileWidget(ModelSelect2MultipleWidget):
    model = Profile
    search_fields = [ 'user__username__icontains' ]

    def label_from_instance(self, obj):
        return obj.user.username

    def get_queryset(self):
        return Profile.objects.all().order_by('user__username').distinct()


class CollectionWidget(ModelSelect2MultipleWidget):
    model = Collection
    search_fields = [ 'name__icontains' ]
    type = None

    def label_from_instance(self, obj):
        return obj.name

    def get_queryset(self):
        if self.type:
            return Collection.objects.filter(type=self.type).order_by('name').distinct()
        else:
            return Collection.objects.filter().order_by('name').distinct()

class CollectionSermoWidget(CollectionWidget):
    type = "sermo"

class CollectionManuWidget(CollectionWidget):
    type = "manu"

class CollectionGoldWidget(CollectionWidget):
    type = "gold"

class CollectionSuperWidget(CollectionWidget):
    type = "super"


class ProjectOneWidget(ModelSelect2Widget):
    model = Project
    search_fields = [ 'name__icontains' ]

    def label_from_instance(self, obj):
        return obj.name

    def get_queryset(self):
        return Project.objects.all().order_by('name').distinct()


#class ManuIdnoWidget(HeavySelect2Widget):



class AuthorWidget(ModelSelect2MultipleWidget):
    model = Author
    search_fields = [ 'name__icontains']

    def label_from_instance(self, obj):
        return obj.name

    def get_queryset(self):
        return Author.objects.all().order_by('name').distinct()


class LocationWidget(ModelSelect2MultipleWidget):
    model = Location
    search_fields = [ 'name__icontains']

    def label_from_instance(self, obj):
        sLabel = "{} ({})".format(obj.name, obj.loctype)
        # sLabel = obj.name
        return sLabel


# ================= FORMS =======================================


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
    typeaheads = ["authors", "signatures", "gldexplicits", "gldincipits"]

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
                           widget=forms.TextInput(attrs={'class': 'typeahead searching manuidnos input-sm', 'placeholder': 'Shelfmark...',  'style': 'width: 100%;'}))
    typeaheads = ["countries", "cities", "libraries", "signatures", "manuidnos", "gldsiggrysons", "gldsigclavises"]


class SearchManuForm(forms.ModelForm):
    """Manuscript search form"""

    manuidlist  = ModelMultipleChoiceField(queryset=None, required=False, 
                            widget=ManuidWidget(attrs={'data-placeholder': 'Select multiple manuscript identifiers...', 'style': 'width: 100%;'}))

    country     = forms.CharField(required=False)
    country_ta  = forms.CharField(label=_("Country"), required=False, 
                           widget=forms.TextInput(attrs={'class': 'typeahead searching countries input-sm', 'placeholder': 'Country...', 'style': 'width: 100%;'}))
    city        = forms.CharField(required=False)
    city_ta     = forms.CharField(label=_("City"), required=False, 
                           widget=forms.TextInput(attrs={'class': 'typeahead searching cities input-sm', 'placeholder': 'City...',  'style': 'width: 100%;'}))
    libname_ta  = forms.CharField(label=_("Library"), required=False, 
                           widget=forms.TextInput(attrs={'class': 'typeahead searching libraries input-sm', 'placeholder': 'Name of library...',  'style': 'width: 100%;'}))
    origin_ta   = forms.CharField(label=_("Origin"), required=False, 
                           widget=forms.TextInput(attrs={'class': 'typeahead searching origins input-sm', 'placeholder': 'Origin (location)...',  'style': 'width: 100%;'}))
    prov        = forms.CharField(required=False)
    prov_ta     = forms.CharField(label=_("Provenance"), required=False, 
                           widget=forms.TextInput(attrs={'class': 'typeahead searching locations input-sm', 'placeholder': 'Provenance (location)...',  'style': 'width: 100%;'}))
    date_from   = forms.IntegerField(label=_("Date start"), required = False,
                                     widget=forms.TextInput(attrs={'placeholder': 'Starting from...',  'style': 'width: 30%;', 'class': 'searching'}))
    date_until  = forms.IntegerField(label=_("Date until"), required = False,
                                     widget=forms.TextInput(attrs={'placeholder': 'Until (including)...',  'style': 'width: 30%;', 'class': 'searching'}))
    signature   = forms.CharField(label=_("Signature"), required=False,
                            widget=forms.TextInput(attrs={'class': 'typeahead searching signatures input-sm', 'placeholder': 'Signatures (Gryson, Clavis) using wildcards...', 'style': 'width: 100%;'}))
    signatureid = forms.CharField(label=_("Signature ID"), required=False)
    siglist     = ModelMultipleChoiceField(queryset=None, required=False, 
                            widget=SignatureWidget(attrs={'data-placeholder': 'Select multiple signatures (Gryson, Clavis)...', 'style': 'width: 100%;', 'class': 'searching'}))
    keyword = forms.CharField(label=_("Keyword"), required=False,
                widget=forms.TextInput(attrs={'class': 'typeahead searching keywords input-sm', 'placeholder': 'Keyword(s)...', 'style': 'width: 100%;'}))
    kwlist     = ModelMultipleChoiceField(queryset=None, required=False, 
                widget=KeywordWidget(attrs={'data-placeholder': 'Select multiple keywords...', 'style': 'width: 100%;', 'class': 'searching'}))
    prjlist     = ModelMultipleChoiceField(queryset=None, required=False, 
                widget=ProjectWidget(attrs={'data-placeholder': 'Select multiple projects...', 'style': 'width: 100%;', 'class': 'searching'}))
    typeaheads = ["countries", "cities", "libraries", "origins", "locations", "signatures", "keywords", "manuidnos", "gldsiggrysons", "gldsigclavises"]

    class Meta:
        ATTRS_FOR_FORMS = {'class': 'form-control'};

        model = Manuscript
        fields = ['name', 'yearstart', 'yearfinish', 'library', 'idno', 'origin', 'url', 'support', 'extent', 'format', 'stype']
        widgets={'library':     forms.TextInput(attrs={'style': 'width: 100%;', 'class': 'searching'}),
                 'name':        forms.TextInput(attrs={'style': 'width: 100%;', 'class': 'searching'}),
                 'yearstart':   forms.TextInput(attrs={'style': 'width: 40%;', 'class': 'searching'}),
                 'yearfinish':  forms.TextInput(attrs={'style': 'width: 40%;', 'class': 'searching'}),
                 'idno':        forms.TextInput(attrs={'class': 'typeahead searching manuidnos input-sm', 'placeholder': 'Shelfmarks using wildcards...',  'style': 'width: 100%;'}),
                 'origin':      forms.TextInput(attrs={'style': 'width: 100%;', 'class': 'searching'}),
                 'url':         forms.TextInput(attrs={'style': 'width: 100%;', 'class': 'searching'}),
                 'format':      forms.TextInput(attrs={'style': 'width: 100%;', 'class': 'searching'}),
                 'extent':      forms.Textarea(attrs={'rows': 1, 'cols': 40, 'style': 'height: 40px; width: 100%;', 'class': 'searching'}),
                 'support':     forms.Textarea(attrs={'rows': 1, 'cols': 40, 'style': 'height: 40px; width: 100%;', 'class': 'searching'}),
                 'stype':       forms.Select(attrs={'style': 'width: 100%;'})
                 }

    def __init__(self, *args, **kwargs):
        # Start by executing the standard handling
        super(SearchManuForm, self).__init__(*args, **kwargs)
        
        # NONE of the fields are required in the SEARCH form!
        self.fields['stype'].required = False
        self.fields['name'].required = False
        self.fields['yearstart'].required = False
        self.fields['yearfinish'].required = False
        self.fields['manuidlist'].queryset = Manuscript.objects.all().order_by('idno')
        self.fields['siglist'].queryset = Signature.objects.all().order_by('code')
        self.fields['kwlist'].queryset = Keyword.objects.all().order_by('name')
        self.fields['prjlist'].queryset = Project.objects.all().order_by('name')

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


class SermonForm(forms.ModelForm):
    # Helper fields for SermonDescr fields
    authorname  = forms.CharField(label=_("Author"), required=False, 
                           widget=forms.TextInput(attrs={'class': 'typeahead searching authors input-sm', 'placeholder': 'Authors using wildcards...', 'style': 'width: 100%;'}))
    authorlist  = ModelMultipleChoiceField(queryset=None, required=False, 
                            widget=AuthorWidget(attrs={'data-placeholder': 'Select multiple authors...', 'style': 'width: 100%;', 'class': 'searching'}))
    manuidno    = forms.CharField(label=_("Manuscript"), required=False,
                            widget=forms.TextInput(attrs={'class': 'typeahead searching manuidnos input-sm', 'placeholder': 'Shelfmarks using wildcards...', 'style': 'width: 100%;'}))
    manuidlist  = ModelMultipleChoiceField(queryset=None, required=False, 
                            widget=ManuidWidget(attrs={'data-placeholder': 'Select multiple manuscript identifiers...', 'style': 'width: 100%;'}))
    signature   = forms.CharField(label=_("Signature"), required=False,
                            widget=forms.TextInput(attrs={'class': 'typeahead searching signatures input-sm', 'placeholder': 'Signatures (Gryson, Clavis) using wildcards...', 'style': 'width: 100%;'}))
    signatureid = forms.CharField(label=_("Signature ID"), required=False)
    siglist     = ModelMultipleChoiceField(queryset=None, required=False, 
                            widget=SignatureWidget(attrs={'data-placeholder': 'Select multiple signatures (Gryson, Clavis)...', 'style': 'width: 100%;', 'class': 'searching'}))
    keyword = forms.CharField(label=_("Keyword"), required=False,
                widget=forms.TextInput(attrs={'class': 'typeahead searching keywords input-sm', 'placeholder': 'Keyword(s)...', 'style': 'width: 100%;'}))
    kwlist     = ModelMultipleChoiceField(queryset=None, required=False, 
                widget=KeywordWidget(attrs={'data-placeholder': 'Select multiple keywords...', 'style': 'width: 100%;', 'class': 'searching'}))
    collection = forms.CharField(label=_("Collection"), required=False,
                widget=forms.TextInput(attrs={'class': 'searching input-sm', 'placeholder': 'Collection(s)...', 'style': 'width: 100%;'}))
    collist     = ModelMultipleChoiceField(queryset=None, required=False, 
                widget=CollectionSermoWidget(attrs={'data-placeholder': 'Select multiple collections...', 'style': 'width: 100%;', 'class': 'searching'}))
   
    # Fields for searching sermons through their containing manuscripts
    country     = forms.CharField(required=False)
    country_ta  = forms.CharField(label=_("Country"), required=False, 
                           widget=forms.TextInput(attrs={'class': 'typeahead searching countries input-sm', 'placeholder': 'Country...', 'style': 'width: 100%;'}))
    city        = forms.CharField(required=False)
    city_ta     = forms.CharField(label=_("City"), required=False, 
                           widget=forms.TextInput(attrs={'class': 'typeahead searching cities input-sm', 'placeholder': 'City...',  'style': 'width: 100%;'}))
    library     = forms.CharField(required=False)
    libname_ta  = forms.CharField(label=_("Library"), required=False, 
                           widget=forms.TextInput(attrs={'class': 'typeahead searching libraries input-sm', 'placeholder': 'Name of library...',  'style': 'width: 100%;'}))
    origin      = forms.CharField(required=False)
    origin_ta   = forms.CharField(label=_("Origin"), required=False, 
                           widget=forms.TextInput(attrs={'class': 'typeahead searching origins input-sm', 'placeholder': 'Origin (location)...',  'style': 'width: 100%;'}))
    prov        = forms.CharField(required=False)
    prov_ta     = forms.CharField(label=_("Provenance"), required=False, 
                           widget=forms.TextInput(attrs={'class': 'typeahead searching locations input-sm', 'placeholder': 'Provenance (location)...',  'style': 'width: 100%;'}))
    date_from   = forms.IntegerField(label=_("Date start"), required = False,
                                     widget=forms.TextInput(attrs={'placeholder': 'Starting from...',  'style': 'width: 30%;', 'class': 'searching'}))
    date_until  = forms.IntegerField(label=_("Date until"), required = False,
                                     widget=forms.TextInput(attrs={'placeholder': 'Until (including)...',  'style': 'width: 30%;', 'class': 'searching'}))
    typeaheads = ["authors", "manuidnos", "signatures", "keywords", "countries", "cities", "libraries", "origins", "locations", "srmincipits", "srmexplicits", "gldsiggrysons", "gldsigclavises"]

    class Meta:
        ATTRS_FOR_FORMS = {'class': 'form-control'};

        model = SermonDescr
        fields = ['title', 'subtitle', 'author', 'locus', 'incipit', 'explicit', 'quote', 'manu',
                  'feast', 'bibleref', 'bibnotes', 'additional', 'note', 'stype']
                  #, 'clavis', 'gryson', 'keyword']
        widgets={'title':       forms.Textarea(attrs={'rows': 1, 'cols': 40, 'style': 'height: 40px; width: 100%;', 'class': 'searching'}),
                 'subtitle':    forms.TextInput(attrs={'style': 'width: 100%;', 'class': 'searching'}),
                 'author':      forms.TextInput(attrs={'style': 'width: 100%;'}),
                 'nickname':    forms.TextInput(attrs={'style': 'width: 100%;'}),
                 'locus':       forms.TextInput(attrs={'style': 'width: 100%;', 'class': 'searching'}),
                 'bibnotes':    forms.TextInput(attrs={'placeholder': 'Bibliography notes...', 'style': 'width: 100%;', 'class': 'searching'}),
                 'feast':       forms.TextInput(attrs={'style': 'width: 100%;', 'class': 'searching'}),

                 'incipit':     forms.TextInput(attrs={'class': 'typeahead searching srmincipits input-sm', 'placeholder': 'Incipit...', 'style': 'width: 100%;'}),
                 'explicit':    forms.TextInput(attrs={'class': 'typeahead searching srmexplicits input-sm', 'placeholder': 'Explicit...', 'style': 'width: 100%;'}),
                 'stype':       forms.Select(attrs={'style': 'width: 100%;'}),

                 # On the verge of leaving...
                 #'keyword':     forms.TextInput(attrs={'style': 'width: 100%;'}),

                 # larger areas
                 'quote':       forms.Textarea(attrs={'rows': 1, 'cols': 40, 'style': 'height: 40px; width: 100%;', 'class': 'searching'}),
                 'bibleref':    forms.Textarea(attrs={'rows': 1, 'cols': 40, 'style': 'height: 40px; width: 100%;', 'class': 'searching'}),
                 'additional':  forms.Textarea(attrs={'rows': 1, 'cols': 40, 'style': 'height: 40px; width: 100%;', 'class': 'searching'}),
                 'note':        forms.Textarea(attrs={'rows': 1, 'cols': 40, 'style': 'height: 40px; width: 100%;', 'class': 'searching'}),
                 }

    def __init__(self, *args, **kwargs):
        # Start by executing the standard handling
        super(SermonForm, self).__init__(*args, **kwargs)
        # Some fields are not required
        self.fields['stype'].required = False
        self.fields['manu'].required = False
        self.fields['siglist'].queryset = Signature.objects.all().order_by('code')
        self.fields['manuidlist'].queryset = Manuscript.objects.all().order_by('idno')
        self.fields['authorlist'].queryset = Author.objects.all().order_by('name')
        self.fields['kwlist'].queryset = Keyword.objects.all().order_by('name')
        self.fields['collist'].queryset = Collection.objects.filter(type='gold').order_by('name')
        
        # Get the instance
        if 'instance' in kwargs:
            instance = kwargs['instance']
            # If there is an instance, then check the author specification
            sAuthor = "" if not instance.author else instance.author.name

            ## If there is an instance, then check the nickname specification
            #sNickName = "" if not instance.nickname else instance.nickname.name
            self.fields['authorname'].initial = sAuthor
            self.fields['authorname'].required = False
            self.fields['collist'].initial = [x.pk for x in instance.collections.all().order_by('name')]

class KeywordForm(forms.ModelForm):
    """Keyword list"""

    keyword_ta = forms.CharField(label=_("Keyword"), required=False,
                widget=forms.TextInput(attrs={'class': 'typeahead searching keywords input-sm', 'placeholder': 'Keyword(s)...', 'style': 'width: 100%;'}))
    kwlist     = ModelMultipleChoiceField(queryset=None, required=False, 
                widget=KeywordWidget(attrs={'data-placeholder': 'Select multiple keywords...', 'style': 'width: 100%;', 'class': 'searching'}))
    typeaheads = ["keywords"]

    class Meta:
        ATTRS_FOR_FORMS = {'class': 'form-control'};

        model = Keyword
        fields = ['name']
        widgets={'name':        forms.TextInput(attrs={'style': 'width: 100%;', 'class': 'searching'})
                 }

    def __init__(self, *args, **kwargs):
        # Start by executing the standard handling
        super(KeywordForm, self).__init__(*args, **kwargs)
        # Some fields are not required
        self.fields['name'].required = False
        self.fields['kwlist'].queryset = Keyword.objects.all().order_by('name')
        # Get the instance
        if 'instance' in kwargs:
            instance = kwargs['instance']


class ProjectForm(forms.ModelForm):
    """Project list"""

    project_ta = forms.CharField(label=_("Keyword"), required=False,
                widget=forms.TextInput(attrs={'class': 'typeahead searching projects input-sm', 'placeholder': 'Project(s)...', 'style': 'width: 100%;'}))
    prjlist     = ModelMultipleChoiceField(queryset=None, required=False, 
                widget=ProjectWidget(attrs={'data-placeholder': 'Select multiple projects...', 'style': 'width: 100%;', 'class': 'searching'}))
    typeaheads = ["projects"]

    class Meta:
        ATTRS_FOR_FORMS = {'class': 'form-control'};

        model = Project
        fields = ['name']
        widgets={'name':        forms.TextInput(attrs={'style': 'width: 100%;', 'class': 'searching'})
                 }

    def __init__(self, *args, **kwargs):
        # Start by executing the standard handling
        super(ProjectForm, self).__init__(*args, **kwargs)
        # Some fields are not required
        self.fields['name'].required = False
        self.fields['prjlist'].queryset = Project.objects.all().order_by('name')
        # Get the instance
        if 'instance' in kwargs:
            instance = kwargs['instance']


class CollectionForm(forms.ModelForm):
    """Collection list"""

    collection_ta = forms.CharField(label=_("Collection"), required=False,
                widget=forms.TextInput(attrs={'class': 'typeahead searching collections input-sm', 'placeholder': 'Collection(s)...', 'style': 'width: 100%;'}))
    collist     = ModelMultipleChoiceField(queryset=None, required=False, 
                widget=CollectionWidget(attrs={'data-placeholder': 'Select multiple collections...', 'style': 'width: 100%;', 'class': 'searching'}))
    ownlist     = ModelMultipleChoiceField(queryset=None, required=False, 
                widget=ProfileWidget(attrs={'data-placeholder': 'Select multiple profiles...', 'style': 'width: 100%;', 'class': 'searching'}))
    typeaheads = ["collections"]

    class Meta:
        ATTRS_FOR_FORMS = {'class': 'form-control'};

        model = Collection
        fields = ['name', 'owner', 'descrip', 'readonly', 'url']
        widgets={'name':        forms.TextInput(attrs={'style': 'width: 100%;', 'class': 'searching'}), 
                 'owner':       forms.TextInput(attrs={'style': 'width: 100%;'}),
                 'descrip':     forms.TextInput(attrs={'style': 'width: 100%;'}),
                 'readonly':    forms.CheckboxInput(),
                 'url':         forms.TextInput(attrs={'style': 'width: 100%;'}),
                 }

    def __init__(self, *args, **kwargs):
        # Start by executing the standard handling
        super(CollectionForm, self).__init__(*args, **kwargs)
        # Get the prefix
        prefix = kwargs['prefix']
        # Some fields are not required
        self.fields['name'].required = False
        self.fields['owner'].required = False
        self.fields['descrip'].required = False
        self.fields['readonly'].required = False
        self.fields['url'].required = False
        self.fields['collist'].queryset = Collection.objects.filter(type=prefix).order_by('name')
        self.fields['ownlist'].queryset = Profile.objects.all()
        # Get the instance
        if 'instance' in kwargs:
            instance = kwargs['instance']


class SermonDescrSignatureForm(forms.ModelForm):
    class Meta:
        ATTRS_FOR_FORMS = {'class': 'form-control'};

        model = SermonSignature
        # fields = ['code', 'editype', 'sermon']
        fields = ['code', 'editype']
        widgets={'editype':     forms.Select(attrs={'style': 'width: 100%;'}),
                 'code':        forms.TextInput(attrs={'class': 'typeahead searching signaturetype input-sm', 'placeholder': 'Signature...', 'style': 'width: 100%;'})
                 }
    typeaheads = ["signatures", "gldsiggrysons", "gldsigclavises"]

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


class SermonDescrKeywordForm(forms.ModelForm):
    name = forms.CharField(label=_("Keyword"), required=False, 
                           widget=forms.TextInput(attrs={'class': 'typeahead searching keywords input-sm', 'placeholder': 'Keyword...',  'style': 'width: 100%;'}))
    typeaheads = ["keywords"]

    class Meta:
        ATTRS_FOR_FORMS = {'class': 'form-control'};

        model = SermonDescrKeyword
        fields = ['sermon', 'keyword']

    def __init__(self, *args, **kwargs):
        # Start by executing the standard handling
        super(SermonDescrKeywordForm, self).__init__(*args, **kwargs)
        # Set the keyword to optional for best processing
        self.fields['keyword'].required = False
        # Get the instance
        if 'instance' in kwargs:
            instance = kwargs['instance']
            # Check if the initial name should be added
            if instance.keyword != None:
                kw = instance.keyword.name
                self.fields['name'].initial = kw





class SermonGoldForm(forms.ModelForm):
    authorname = forms.CharField(label=_("Author"), required=False, 
                widget=forms.TextInput(attrs={'class': 'typeahead searching authors input-sm', 'placeholder': 'Author...', 'style': 'width: 100%;'}))
    signature = forms.CharField(label=_("Signature"), required=False,
                widget=forms.TextInput(attrs={'class': 'typeahead searching signatures input-sm', 'placeholder': 'Signature/code (Gryson, Clavis)...', 'style': 'width: 100%;'}))
    signatureid = forms.CharField(label=_("Signature ID"), required=False)
    siglist     = ModelMultipleChoiceField(queryset=None, required=False, 
                widget=SignatureWidget(attrs={'data-placeholder': 'Select multiple signatures (Gryson, Clavis)...', 'style': 'width: 100%;', 'class': 'searching'}))
    keyword = forms.CharField(label=_("Keyword"), required=False,
                widget=forms.TextInput(attrs={'class': 'typeahead searching keywords input-sm', 'placeholder': 'Keyword(s)...', 'style': 'width: 100%;'}))
    kwlist     = ModelMultipleChoiceField(queryset=None, required=False, 
                widget=KeywordWidget(attrs={'data-placeholder': 'Select multiple keywords...', 'style': 'width: 100%;', 'class': 'searching'}))
    kwnew       = forms.CharField(label=_("New keyword"), required=False, 
                widget=forms.TextInput(attrs={'placeholder': 'Keyword...', 'style': 'width: 100%;'}))
    authorlist  = ModelMultipleChoiceField(queryset=None, required=False, 
                widget=AuthorWidget(attrs={'data-placeholder': 'Select multiple authors...', 'style': 'width: 100%;', 'class': 'searching'}))
    edilist     = ModelMultipleChoiceField(queryset=None, required=False, 
                widget=EdirefSgWidget(attrs={'data-placeholder': 'Select multiple references...', 'style': 'width: 100%;', 'class': 'searching'}))
    collection = forms.CharField(label=_("Collection"), required=False,
                widget=forms.TextInput(attrs={'class': 'searching input-sm', 'placeholder': 'Collection(s)...', 'style': 'width: 100%;'}))
    collist     = ModelMultipleChoiceField(queryset=None, required=False, 
                widget=CollectionGoldWidget(attrs={'data-placeholder': 'Select multiple collections...', 'style': 'width: 100%;', 'class': 'searching'}))
    typeaheads = ["authors", "signatures", "keywords", "gldincipits", "gldexplicits"]

    class Meta:
        ATTRS_FOR_FORMS = {'class': 'form-control'};

        model = SermonGold
        fields = ['author', 'incipit', 'explicit', 'bibliography', 'stype', 'srchincipit', 'srchexplicit' ]
        widgets={'author':      forms.TextInput(attrs={'style': 'width: 100%;'}),
                 'incipit':     forms.TextInput(attrs={'class': 'typeahead searching gldincipits input-sm', 'placeholder': 'Incipit...', 'style': 'width: 100%;'}),
                 'explicit':    forms.TextInput(attrs={'class': 'typeahead searching gldexplicits input-sm', 'placeholder': 'Explicit...', 'style': 'width: 100%;'}),
                 'bibliography': forms.Textarea(attrs={'rows': 2, 'cols': 40, 'style': 'height: 80px; width: 100%; font-family: monospace', 'class': 'searching'}),
                 'stype':       forms.Select(attrs={'style': 'width: 100%;'})
                 }

    def __init__(self, *args, **kwargs):
        # Start by executing the standard handling
        super(SermonGoldForm, self).__init__(*args, **kwargs)
        # Some fields are not required
        self.fields['stype'].required = False
        self.fields['siglist'].queryset = Signature.objects.all().order_by('code')
        self.fields['kwlist'].queryset = Keyword.objects.all().order_by('name')
        self.fields['authorlist'].queryset = Author.objects.all().order_by('name')
        self.fields['edilist'].queryset = EdirefSG.objects.all().order_by('reference__full', 'pages').distinct()
        self.fields['collist'].queryset = Collection.objects.filter(type='gold').order_by('name')
        
        # Get the instance
        if 'instance' in kwargs:
            instance = kwargs['instance']
            # If there is an instance, then check the author specification
            sAuthor = "" if not instance.author else instance.author.name
            self.fields['authorname'].initial = sAuthor
            self.fields['authorname'].required = False
            # Set initial values for lists, where appropriate. NOTE: need to have the initial ID values
            self.fields['kwlist'].initial = [x.pk for x in instance.keywords.all().order_by('name')]
            self.fields['siglist'].initial = [x.pk for x in instance.goldsignatures.all().order_by('editype', 'code')]
            self.fields['edilist'].initial = [x.pk for x in instance.sermon_gold_editions.all().order_by('reference__full', 'pages')]
            self.fields['collist'].initial = [x.pk for x in instance.collections.all().order_by('name')]

        # We are okay
        return None


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
    

class SuperSermonGoldForm(forms.ModelForm):
    authorname = forms.CharField(label=_("Author"), required=False, 
                widget=forms.TextInput(attrs={'class': 'typeahead searching authors input-sm', 'placeholder': 'Author...', 'style': 'width: 100%;'}))
    authorlist  = ModelMultipleChoiceField(queryset=None, required=False, 
                widget=AuthorWidget(attrs={'data-placeholder': 'Select multiple authors...', 'style': 'width: 100%;', 'class': 'searching'}))
    signature = forms.CharField(label=_("Signature"), required=False,
                widget=forms.TextInput(attrs={'class': 'typeahead searching signatures input-sm', 'placeholder': 'Signature/code (Gryson, Clavis)...', 'style': 'width: 100%;'}))
    signatureid = forms.CharField(label=_("Signature ID"), required=False)
    siglist     = ModelMultipleChoiceField(queryset=None, required=False, 
                widget=SignatureWidget(attrs={'data-placeholder': 'Select multiple signatures (Gryson, Clavis)...', 'style': 'width: 100%;', 'class': 'searching'}))
    collection = forms.CharField(label=_("Collection"), required=False,
                widget=forms.TextInput(attrs={'class': 'searching input-sm', 'placeholder': 'Collection(s)...', 'style': 'width: 100%;'}))
    collist     = ModelMultipleChoiceField(queryset=None, required=False, 
                widget=CollectionSuperWidget(attrs={'data-placeholder': 'Select multiple collections...', 'style': 'width: 100%;', 'class': 'searching'}))
    typeaheads = ["authors", "gldincipits", "gldexplicits"]

    class Meta:
        ATTRS_FOR_FORMS = {'class': 'form-control'};

        model = EqualGold
        fields = ['author', 'incipit', 'explicit', 'code', 'number']
        widgets={'author':      forms.TextInput(attrs={'style': 'width: 100%;'}),
                 'code':        forms.TextInput(attrs={'class': 'searching', 'style': 'width: 100%;', 'data-placeholder': 'Passim code'}),
                 'number':      forms.TextInput(attrs={'class': 'searching', 'style': 'width: 100%;', 'data-placeholder': 'Author number'}),
                 'incipit':     forms.TextInput(attrs={'class': 'typeahead searching gldincipits input-sm', 'placeholder': 'Incipit...', 'style': 'width: 100%;'}),
                 'explicit':    forms.TextInput(attrs={'class': 'typeahead searching gldexplicits input-sm', 'placeholder': 'Explicit...', 'style': 'width: 100%;'})
                 }

    def __init__(self, *args, **kwargs):
        # Start by executing the standard handling
        super(SuperSermonGoldForm, self).__init__(*args, **kwargs)
        # Some fields are not required
        self.fields['authorlist'].queryset = Author.objects.all().order_by('name')
        self.fields['siglist'].queryset = Signature.objects.all().order_by('code')
        self.fields['collist'].queryset = Collection.objects.filter(type='gold').order_by('name')
        # Get the instance
        if 'instance' in kwargs:
            instance = kwargs['instance']
            # If there is an instance, then check the author specification
            sAuthor = "" if not instance.author else instance.author.name
            self.fields['authorname'].initial = sAuthor
            self.fields['authorname'].required = False
            self.fields['collist'].initial = [x.pk for x in instance.collections.all().order_by('name')]

        # We are okay
        return None


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
    newgr  = forms.CharField(label=_("Signature"), required=False, help_text="editable", 
               widget=forms.TextInput(attrs={'class': 'input-sm', 'placeholder': 'Gryson code...',  'style': 'width: 100%;'}))
    newcl  = forms.CharField(label=_("Signature"), required=False, help_text="editable", 
               widget=forms.TextInput(attrs={'class': 'input-sm', 'placeholder': '...or Clavis code...',  'style': 'width: 100%;'}))
    newot  = forms.CharField(label=_("Signature"), required=False, help_text="editable", 
               widget=forms.TextInput(attrs={'class': 'input-sm', 'placeholder': '...or Other code...',  'style': 'width: 100%;'}))
    typeaheads = ["signatures"]

    class Meta:
        ATTRS_FOR_FORMS = {'class': 'form-control'};

        model = Signature
        fields = ['code', 'editype']
        widgets={'editype':     forms.Select(attrs={'style': 'width: 100%;'}),
                 'code':        forms.TextInput(attrs={'class': 'typeahead searching signaturetype input-sm', 'placeholder': 'Signature...', 'style': 'width: 100%;'})
                 }

    def __init__(self, *args, **kwargs):
        # Start by executing the standard handling
        super(SermonGoldSignatureForm, self).__init__(*args, **kwargs)
        # Initialize choices for editype
        init_choices(self, 'editype', EDI_TYPE, bUseAbbr=True)
        # Set the keyword to optional for best processing
        self.fields['code'].required = False
        self.fields['editype'].required = False

    def clean(self):
        # Run any super class cleaning
        cleaned_data = super(SermonGoldSignatureForm, self).clean()
        gold = cleaned_data.get("gold")
        editype = cleaned_data.get("editype")
        code = cleaned_data.get("code")
        if editype == "":
            newgr = cleaned_data.get("newgr")
            if newgr != "":
                code = newgr
                editype = "gr"
            else:
                newcl = cleaned_data.get("newcl")
                if newcl != "":
                    code = newcl
                    editype = "cl"
                else:
                    newot = cleaned_data.get("newot")
                    if newot != "":
                        code = newot
                        editype = "ot"
        # Do we actually have something?

        # Check if any of [name] or [newkw] already exists
        if code == "" or editype == "":
            # No keyword chosen
            raise forms.ValidationError(
                    "No signature specified to attach to this gold sermon"
                )
        else:
            # Check if [code|editype] already exists
            signature = Signature.objects.filter(gold=gold, code=code, editype=editype).first()
            if signature:
                # This combination already exists
                raise forms.ValidationError(
                        "This signature already exists for this gold sermon"
                    )
        

class SermonGoldEditionForm(forms.ModelForm):
    # EK: Added for Sermon Gold new approach 
    oneref = forms.ModelChoiceField(queryset=None, required=False, help_text="editable", 
               widget=LitrefWidget(attrs={'data-placeholder': 'Select one reference...', 'style': 'width: 100%;', 'class': 'searching'}))
    newpages  = forms.CharField(label=_("Page range"), required=False, help_text="editable", 
               widget=forms.TextInput(attrs={'class': 'input-sm', 'placeholder': 'Page range...',  'style': 'width: 100%;'}))
    # ORIGINAL:
    litref = forms.CharField(required=False)
    litref_ta = forms.CharField(label=_("Reference"), required=False, 
                           widget=forms.TextInput(attrs={'class': 'typeahead searching litrefs input-sm', 'placeholder': 'Reference...',  'style': 'width: 100%;'}))
    typeaheads = ["litrefs"]

    class Meta:
        ATTRS_FOR_FORMS = {'class': 'form-control'};

        model = EdirefSG
        fields = ['reference', 'sermon_gold', 'pages']
        widgets={'pages':     forms.TextInput(attrs={'placeholder': 'Page range...', 'style': 'width: 100%;'})
                 }

    def __init__(self, *args, **kwargs):
        # Start by executing the standard handling
        super(SermonGoldEditionForm, self).__init__(*args, **kwargs)
        self.fields['reference'].required = False
        self.fields['litref'].required = False
        self.fields['litref_ta'].required = False
        # EK: Added for Sermon Gold new approach 
        self.fields['newpages'].required = False
        self.fields['oneref'].required = False
        self.fields['oneref'].queryset = Litref.objects.exclude(full="").order_by('full')
        # Get the instance
        if 'instance' in kwargs:
            instance = kwargs['instance']
            # Check if the initial reference should be added
            if instance.reference != None:
                self.fields['litref_ta'].initial = instance.reference.get_short() 

    def save(self, commit=True, *args, **kwargs):
        response = super(SermonGoldEditionForm, self).save(commit, **kwargs)
        iStop = 1
        return response

    def clean(self):
        cleaned_data = super(SermonGoldEditionForm, self).clean()
        litref = cleaned_data.get("litref")
        oneref = cleaned_data.get("oneref")     # EK: added for new approach (also in the "if-statement")
        reference = cleaned_data.get("reference")
        if reference == None and (litref == None or litref == "") and (oneref == None or oneref == ""):
            #litref_ta = cleaned_data.get("litref_ta")
            #obj = Litref.objects.filter(full=litref_ta).first()
            #if obj == None:
            raise forms.ValidationError("Cannot find the reference. Make sure to select it. If it is not available, add it in Zotero and import it in Passim")
   

class SermonGoldKeywordForm(forms.ModelForm):
    name   = forms.CharField(label=_("Keyword"), required=False, help_text="", 
               widget=forms.TextInput(attrs={'class': 'typeahead searching keywords input-sm', 'placeholder': 'Keyword...',  'style': 'width: 100%;'}))
    newkw  = forms.CharField(label=_("Keyword (new)"), required=False, help_text="editable", 
               widget=forms.TextInput(attrs={'class': 'input-sm', 'placeholder': 'Keyword...',  'style': 'width: 100%;'}))
    typeaheads = ["keywords"]

    class Meta:
        ATTRS_FOR_FORMS = {'class': 'form-control'};

        model = SermonGoldKeyword
        fields = ['gold', 'keyword']

    def __init__(self, *args, **kwargs):
        # Start by executing the standard handling
        super(SermonGoldKeywordForm, self).__init__(*args, **kwargs)
        # Set the keyword to optional for best processing
        self.fields['newkw'].required = False
        self.fields['keyword'].required = False
        # Get the instance
        if 'instance' in kwargs:
            instance = kwargs['instance']
            # Check if the initial name should be added
            if instance.keyword != None:
                kw = instance.keyword.name
                self.fields['name'].initial = kw

    def save(self, commit=True, *args, **kwargs):
        response = super(SermonGoldKeywordForm, self).save(commit, **kwargs)
        iStop = 1
        return response

    def clean(self):
        # Run any super class cleaning
        cleaned_data = super(SermonGoldKeywordForm, self).clean()
        name = cleaned_data.get("name")
        newkw = cleaned_data.get("newkw")
        gold = cleaned_data.get("gold")
        # Check if any of [name] or [newkw] already exists
        keyword = None
        sName = name if name != "" else newkw
        if sName == "":
            # No keyword chosen
            raise forms.ValidationError(
                    "No keyword specified to attach to this gold sermon".format(sName)
                )
        else:
            keyword = Keyword.objects.filter(name=sName).first()
            if keyword:
                # There is a keyword: check for the combination
                if SermonGoldKeyword.objects.filter(gold=gold, keyword=keyword).count() > 0:
                    # This combination already exists
                    raise forms.ValidationError("Keyword [{}] is already attached to this gold sermon".format(sName))


class SuperSermonGoldCollectionForm(forms.ModelForm):
    name   = forms.CharField(label=_("Collection"), required=False, help_text="", 
               widget=forms.TextInput(attrs={'class': 'searching input-sm', 'placeholder': 'Collection...',  'style': 'width: 100%;'}))
    newcol = forms.CharField(label=_("Collection (new)"), required=False, help_text="editable", 
               widget=forms.TextInput(attrs={'class': 'input-sm', 'placeholder': 'Collection...',  'style': 'width: 100%;'}))
    #typeaheads = ["keywords"]

    class Meta:
        ATTRS_FOR_FORMS = {'class': 'form-control'};

        model = CollectionSuper
        fields = ['super', 'collection']

    def __init__(self, *args, **kwargs):
        # Start by executing the standard handling
        super(SuperSermonGoldCollectionForm, self).__init__(*args, **kwargs)
        # Set the keyword to optional for best processing
        self.fields['newcol'].required = False
        self.fields['collection'].required = False
        # Get the instance
        if 'instance' in kwargs:
            instance = kwargs['instance']
            # Check if the initial name should be added
            if instance.collection != None:
                col = instance.collection.name
                self.fields['name'].initial = col


class SermonGoldCollectionForm(forms.ModelForm):
    name   = forms.CharField(label=_("Collection"), required=False, help_text="", 
               widget=forms.TextInput(attrs={'class': 'searching input-sm', 'placeholder': 'Collection...',  'style': 'width: 100%;'}))
    newcol = forms.CharField(label=_("Collection (new)"), required=False, help_text="editable", 
               widget=forms.TextInput(attrs={'class': 'input-sm', 'placeholder': 'Collection...',  'style': 'width: 100%;'}))
    #typeaheads = ["keywords"]

    class Meta:
        ATTRS_FOR_FORMS = {'class': 'form-control'};

        model = CollectionGold
        fields = ['gold', 'collection']

    def __init__(self, *args, **kwargs):
        # Start by executing the standard handling
        super(SermonGoldCollectionForm, self).__init__(*args, **kwargs)
        # Set the keyword to optional for best processing
        self.fields['newcol'].required = False
        self.fields['collection'].required = False
        # Get the instance
        if 'instance' in kwargs:
            instance = kwargs['instance']
            # Check if the initial name should be added
            if instance.collection != None:
                col = instance.collection.name
                self.fields['name'].initial = col
            

class ManuscriptCollectionForm(forms.ModelForm):
    name   = forms.CharField(label=_("Collection"), required=False, help_text="", 
               widget=forms.TextInput(attrs={'class': 'searching input-sm', 'placeholder': 'Collection...',  'style': 'width: 100%;'}))
    newcol = forms.CharField(label=_("Collection (new)"), required=False, help_text="editable", 
               widget=forms.TextInput(attrs={'class': 'input-sm', 'placeholder': 'Collection...',  'style': 'width: 100%;'}))
    #typeaheads = ["keywords"]

    class Meta:
        ATTRS_FOR_FORMS = {'class': 'form-control'};

        model = CollectionMan
        fields = ['manuscript', 'collection']

    def __init__(self, *args, **kwargs):
        # Start by executing the standard handling
        super(ManuscriptCollectionForm, self).__init__(*args, **kwargs)
        # Set the keyword to optional for best processing
        self.fields['newcol'].required = False
        self.fields['collection'].required = False
        # Get the instance
        if 'instance' in kwargs:
            instance = kwargs['instance']
            # Check if the initial name should be added
            if instance.collection != None:
                col = instance.collection.name
                self.fields['name'].initial = col

class SermonDescrCollectionForm(forms.ModelForm):
    name = forms.CharField(label=_("Collection"), required=False, 
                           widget=forms.TextInput(attrs={'class': 'typeahead searching collections input-sm', 'placeholder': 'Collection...',  'style': 'width: 100%;'}))
   # newcol = forms.CharField(label=_("Collection (new)"), required=False, help_text="editable", 
   #            widget=forms.TextInput(attrs={'class': 'input-sm', 'placeholder': 'Collection...',  'style': 'width: 100%;'}))
    typeaheads = ["collections"]
    
    class Meta:
        ATTRS_FOR_FORMS = {'class': 'form-control'};

        model = CollectionSerm
        fields = ['sermon', 'collection']

    def __init__(self, *args, **kwargs):
        # Start by executing the standard handling
        super(SermonDescrCollectionForm, self).__init__(*args, **kwargs)
        # Set the keyword to optional for best processing
        # self.fields['newcol'].required = False 
        self.fields['collection'].required = False
        # Get the instance
        if 'instance' in kwargs:
            instance = kwargs['instance']
            # Check if the initial name should be added
            if instance.collection != None:
                col = instance.collection.name
                # self.fields['collection'].initial = col
                self.fields['name'].initial = col






class SermonGoldLitrefForm(forms.ModelForm):
    litref = forms.CharField(required=False)
    litref_ta = forms.CharField(label=_("Reference"), required=False, 
                           widget=forms.TextInput(attrs={'class': 'typeahead searching litrefs input-sm', 'placeholder': 'Reference...',  'style': 'width: 100%;'}))
    typeaheads = ["litrefs"]

    class Meta:
        ATTRS_FOR_FORMS = {'class': 'form-control'};

        model = LitrefSG
        fields = ['reference', 'sermon_gold', 'pages']
        widgets={'pages':     forms.TextInput(attrs={'placeholder': 'Page range...', 'style': 'width: 100%;'})
                 }

    def __init__(self, *args, **kwargs):
        # Start by executing the standard handling
        super(SermonGoldLitrefForm, self).__init__(*args, **kwargs)
        self.fields['reference'].required = False
        self.fields['litref'].required = False
        self.fields['litref_ta'].required = False
        # Get the instance
        if 'instance' in kwargs:
            instance = kwargs['instance']
            # Check if the initial reference should be added
            if instance.reference != None:
                self.fields['litref_ta'].initial = instance.reference.get_full()

    def clean(self):
        cleaned_data = super(SermonGoldLitrefForm, self).clean()
        litref = cleaned_data.get("litref")
        reference = cleaned_data.get("reference")
        if reference == None and (litref == None or litref == ""):
            #litref_ta = cleaned_data.get("litref_ta")
            #obj = Litref.objects.filter(full=litref_ta).first()
            #if obj == None:
            raise forms.ValidationError("Cannot find the reference. Make sure to select it. If it is not available, add it in Zotero and import it in Passim")


class ManuscriptProvForm(forms.ModelForm):
    name = forms.CharField(label=_("Name"), required=False, 
                           widget=forms.TextInput(attrs={'placeholder': 'Name...',  'style': 'width: 100%;'}))
    note = forms.CharField(label=_("Note"), required=False,
                           widget = forms.Textarea(attrs={'rows': 1, 'cols': 40, 'style': 'height: 40px; width: 100%;'}))
    location = forms.CharField(required=False)
    location_ta = forms.CharField(label=_("Location"), required=False, 
                           widget=forms.TextInput(attrs={'class': 'typeahead searching locations input-sm', 'placeholder': 'Location...',  'style': 'width: 100%;'}))
    typeaheads = ["locations"]

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
                    # self.fields['location_ta'].initial = instance.provenance.location.name
                    # Make sure the location is set to the correct number
                    self.fields['location'].initial = instance.provenance.location.id


class ManuscriptLitrefForm(forms.ModelForm):
    litref = forms.CharField(required=False)
    litref_ta = forms.CharField(label=_("Reference"), required=False, 
                           widget=forms.TextInput(attrs={'class': 'typeahead searching litrefs input-sm', 'placeholder': 'Reference...',  'style': 'width: 100%;'}))
    typeaheads = ["litrefs"]

    class Meta:
        ATTRS_FOR_FORMS = {'class': 'form-control'};

        model = LitrefMan
        fields = ['reference', 'manuscript', 'pages']
        widgets={'pages':     forms.TextInput(attrs={'placeholder': 'Page range...', 'style': 'width: 100%;'})
                 }

    def __init__(self, *args, **kwargs):
        # Start by executing the standard handling
        super(ManuscriptLitrefForm, self).__init__(*args, **kwargs)
        self.fields['reference'].required = False
        self.fields['litref'].required = False
        self.fields['litref_ta'].required = False
        # Get the instance
        if 'instance' in kwargs:
            instance = kwargs['instance']
            # Check if the initial reference should be added
            if instance.reference != None:
                self.fields['litref_ta'].initial = instance.reference.get_full()

    def clean(self):
        cleaned_data = super(ManuscriptLitrefForm, self).clean()
        litref = cleaned_data.get("litref")
        reference = cleaned_data.get("reference")
        if reference == None and (litref == None or litref == ""):
            #litref_ta = cleaned_data.get("litref_ta")
            #obj = Litref.objects.filter(full=litref_ta).first()
            #if obj == None:
            raise forms.ValidationError("Cannot find the reference. Make sure to select it. If it is not available, add it in Zotero and import it in Passim")


class ManuscriptExtForm(forms.ModelForm):
    class Meta:
        ATTRS_FOR_FORMS = {'class': 'form-control'};

        model = ManuscriptExt
        fields = ['url']
        widgets={'url':     forms.TextInput(attrs={'placeholder': 'External link (URL)...', 'style': 'width: 100%;'})
                 }

    def __init__(self, *args, **kwargs):
        # Start by executing the standard handling
        super(ManuscriptExtForm, self).__init__(*args, **kwargs)

        # Get the instance
        if 'instance' in kwargs:
            instance = kwargs['instance']


class ManuscriptKeywordForm(forms.ModelForm):
    name = forms.CharField(label=_("Keyword"), required=False, 
                           widget=forms.TextInput(attrs={'class': 'typeahead searching keywords input-sm', 'placeholder': 'Keyword...',  'style': 'width: 100%;'}))
    typeaheads = ["keywords"]

    class Meta:
        ATTRS_FOR_FORMS = {'class': 'form-control'};

        model = ManuscriptKeyword
        fields = ['manuscript', 'keyword']

    def __init__(self, *args, **kwargs):
        # Start by executing the standard handling
        super(ManuscriptKeywordForm, self).__init__(*args, **kwargs)
        # Set the keyword to optional for best processing
        self.fields['keyword'].required = False
        # Get the instance
        if 'instance' in kwargs:
            instance = kwargs['instance']
            # Check if the initial name should be added
            if instance.keyword != None:
                kw = instance.keyword.name
                self.fields['name'].initial = kw


class OriginForm(forms.ModelForm):
    location_ta = forms.CharField(label=_("Location"), required=False, 
                           widget=forms.TextInput(attrs={'class': 'typeahead searching locations input-sm', 'placeholder': 'Location...',  'style': 'width: 100%;'}))
    locationlist = ModelMultipleChoiceField(queryset=None, required=False,
                            widget=LocationWidget(attrs={'data-placeholder': 'Location...', 'style': 'width: 100%;'}))
    typeaheads = ["locations"]

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
        self.fields['locationlist'].queryset = Location.objects.all().order_by('loctype__level', 'name')
        # Get the instance
        if 'instance' in kwargs:
            instance = kwargs['instance']
            # Check if the initial name should be added
            if instance != None:
                self.fields['name'].initial = instance.name
                self.fields['note'].initial = instance.note
                if instance.location != None:
                    self.fields['location_ta'].initial = instance.location.get_loc_name()


class LibraryForm(forms.ModelForm):
    location_ta = forms.CharField(label=_("Location"), required=False, 
                           widget=forms.TextInput(attrs={'class': 'typeahead searching locations input-sm', 'placeholder': 'Location...',  'style': 'width: 100%;'}))
    typeaheads = ["locations"]

    class Meta:
        ATTRS_FOR_FORMS = {'class': 'form-control'};

        model = Library
        fields = ['name', 'libtype', 'idLibrEtab', 'location', 'lcity', 'lcountry']
        widgets={'name':     forms.TextInput(attrs={'placeholder': 'Name...', 'style': 'width: 100%;'}),
                 'location': forms.TextInput(attrs={'style': 'width: 100%;'}),
                 'lcity':    forms.TextInput(attrs={'style': 'width: 100%;'}),
                 'lcountry': forms.TextInput(attrs={'style': 'width: 100%;'}),
                 'libtype':  forms.Select()
                 }

    def __init__(self, *args, **kwargs):
        # Start by executing the standard handling
        super(LibraryForm, self).__init__(*args, **kwargs)
        # Set the keyword to optional for best processing
        self.fields['name'].required = False
        self.fields['libtype'].required = False
        self.fields['location'].required = False
        self.fields['location_ta'].required = False
        self.fields['lcity'].required = False
        self.fields['lcountry'].required = False
        # Get the instance
        if 'instance' in kwargs:
            instance = kwargs['instance']
            # Check if the initial name should be added
            if instance != None:
                self.fields['name'].initial = instance.name
                self.fields['libtype'].initial = instance.libtype
                self.fields['lcity'].initial = instance.lcity
                self.fields['lcountry'].initial = instance.lcountry
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
    collection = forms.CharField(label=_("Collection"), required=False,
                widget=forms.TextInput(attrs={'class': 'searching input-sm', 'placeholder': 'Collection(s)...', 'style': 'width: 100%;'}))
    collist     = ModelMultipleChoiceField(queryset=None, required=False, 
                widget=CollectionManuWidget(attrs={'data-placeholder': 'Select multiple collections...', 'style': 'width: 100%;', 'class': 'searching'}))
    typeaheads = ["countries", "cities", "libraries", "origins", "manuidnos"]

    class Meta:
        ATTRS_FOR_FORMS = {'class': 'form-control'};

        model = Manuscript
        fields = ['name', 'yearstart', 'yearfinish', 'library', 'idno', 'origin', 'url', 'support', 'extent', 'format', 'stype', 'project']
        widgets={'library':     forms.TextInput(attrs={'style': 'width: 100%;'}),
                 'name':        forms.TextInput(attrs={'style': 'width: 100%;'}),
                 'yearstart':   forms.TextInput(attrs={'style': 'width: 40%;'}),
                 'yearfinish':  forms.TextInput(attrs={'style': 'width: 40%;'}),
                 'idno':        forms.TextInput(attrs={'class': 'typeahead searching manuidnos input-sm', 'placeholder': 'Identifier...',  'style': 'width: 100%;'}),
                 'origin':      forms.TextInput(attrs={'style': 'width: 100%;'}),
                 'url':         forms.TextInput(attrs={'style': 'width: 100%;'}),
                 'format':      forms.TextInput(attrs={'style': 'width: 100%;'}),
                 'extent':      forms.Textarea(attrs={'rows': 1, 'cols': 40, 'style': 'height: 40px; width: 100%;'}),
                 # 'literature':  forms.Textarea(attrs={'rows': 1, 'cols': 40, 'style': 'height: 40px; width: 100%;'}),
                 'support':     forms.Textarea(attrs={'rows': 1, 'cols': 40, 'style': 'height: 40px; width: 100%;'}),
                 'stype':       forms.Select(attrs={'style': 'width: 100%;'}),
                 'project':     ProjectOneWidget(attrs={'data-placeholder': 'Select one project...', 'style': 'width: 100%;', 'class': 'searching'})
                 }

    def __init__(self, *args, **kwargs):
        # Start by executing the standard handling
        super(ManuscriptForm, self).__init__(*args, **kwargs)
        # Some fields are not required
        self.fields['stype'].required = False
        self.fields['yearstart'].required = False
        self.fields['yearfinish'].required = False
        self.fields['name'].required = False
        self.fields['collist'].queryset = Collection.objects.filter(type='manu').order_by('name')

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
            self.fields['collist'].initial = [x.pk for x in instance.collections.all().order_by('name')]



class LocationForm(forms.ModelForm):
    locationlist = ModelMultipleChoiceField(queryset=None, required=False,
                            widget=LocationWidget(attrs={'data-placeholder': 'Select containing locations...', 'style': 'width: 100%;'}))

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
            # Set the items that *may* be shown
            instance = kwargs['instance']
            qs = Location.objects.exclude(id=instance.id).order_by('loctype__level', 'name')
            self.fields['locationlist'].queryset = qs
            self.fields['locationlist'].widget.queryset = qs

            # Set the list of initial items
            my_list = [x.id for x in instance.hierarchy(False)]
            self.initial['locationlist'] = my_list
        else:
            self.fields['locationlist'].queryset = Location.objects.all().order_by('loctype__level', 'name')


class LocationRelForm(forms.ModelForm):
    partof_ta = forms.CharField(label=_("Part of"), required=False, 
                           widget=forms.TextInput(attrs={'class': 'typeahead searching locations input-sm', 'placeholder': 'Part of...',  'style': 'width: 100%;'}))
    partof = forms.CharField(required=False)
    typeaheads = ["locations"]

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


class DaterangeForm(forms.ModelForm):

    class Meta:
        ATTRS_FOR_FORMS = {'class': 'form-control'};

        model = Daterange
        fields = ['yearstart', 'yearfinish', 'reference', 'pages']
        widgets={'reference':   forms.TextInput(attrs={'style': 'width: 100%;'}),
                 'pages':       forms.TextInput(attrs={'style': 'width: 100%;'}),
                 'yearstart':   forms.TextInput(attrs={'style': 'width: 100%;'}),
                 'yearfinish':  forms.TextInput(attrs={'style': 'width: 100%;'})
                 }

    def __init__(self, *args, **kwargs):
        # Start by executing the standard handling
        super(DaterangeForm, self).__init__(*args, **kwargs)

        # Set other parameters
        self.fields['yearstart'].required = True
        self.fields['yearfinish'].required = True
        self.fields['reference'].required = False
        self.fields['pages'].required = False
        # Get the instance
        if 'instance' in kwargs:
            instance = kwargs['instance']


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
    typeaheads = ["countries", "cities", "libraries"]


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
    profile_ta = forms.CharField(label=_("Collector"), required=False,
                widget=forms.TextInput(attrs={'class': 'typeahead searching users input-sm', 'placeholder': 'Collector(s)...', 'style': 'width: 100%;'}))
    profilelist = ModelMultipleChoiceField(queryset=None, required=False, 
                widget=ProfileWidget(attrs={'data-placeholder': 'Select collector(s)...', 'style': 'width: 100%;', 'class': 'searching'}))

    class Meta:
        model = SourceInfo
        fields = ['profile', 'code', 'url']
        widgets={'url':         forms.TextInput(attrs={'style': 'width: 100%;'}),
                 'code':        forms.Textarea(attrs={'rows': 1, 'cols': 40, 'style': 'height: 40px; width: 100%;'})
                 }

    def __init__(self, *args, **kwargs):
        # Start by executing the standard handling
        super(SourceEditForm, self).__init__(*args, **kwargs)
        # Some fields are not required
        self.fields['url'].required = False
        self.fields['code'].required = False
        self.fields['profile_ta'].required = False
        self.fields['profile'].required = False
        self.fields['profilelist'].queryset = Profile.objects.all().order_by('user')
        # Set the initial value for the profile


class AuthorEditForm(forms.ModelForm):

    class Meta:
        model = Author
        fields = ['name', 'abbr']
        widgets={'name':      forms.TextInput(attrs={'placeholder': 'Name of this author', 'style': 'width: 100%;'}),
                 'abbr':     forms.TextInput(attrs={'placeholder': 'Abbreviation as e.g. used in Gryson', 'style': 'width: 100%;'})
                 }


class AuthorSearchForm(forms.ModelForm):
    author_ta = forms.CharField(label=_("Author"), required=False,
                widget=forms.TextInput(attrs={'class': 'typeahead searching authors input-sm', 'placeholder': 'Keyword(s)...', 'style': 'width: 100%;'}))
    authlist     = ModelMultipleChoiceField(queryset=None, required=False, 
                widget=AuthorWidget(attrs={'data-placeholder': 'Select multiple authors...', 'style': 'width: 100%;', 'class': 'searching'}))
    typeaheads = ["authors"]


    class Meta:
        ATTRS_FOR_FORMS = {'class': 'form-control'};

        model = Author
        fields = ('name',)
        widgets={'name':        forms.TextInput(attrs={'style': 'width: 100%;', 'class': 'searching'})
                 }
    def __init__(self, *args, **kwargs):
        # Start by executing the standard handling
        super(AuthorSearchForm, self).__init__(*args, **kwargs)
        # Some fields are not required
        self.fields['name'].required = False
        self.fields['authlist'].queryset = Author.objects.all().order_by('name')
        # Get the instance
        if 'instance' in kwargs:
            instance = kwargs['instance']


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
