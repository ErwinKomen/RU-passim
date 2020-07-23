"""
Definition of forms.
"""

from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.utils.translation import ugettext_lazy as _
from django.forms import ModelMultipleChoiceField, ModelChoiceField
from django.forms.widgets import *
from django.db.models import F
from django_select2.forms import Select2MultipleWidget, ModelSelect2MultipleWidget, ModelSelect2TagWidget, ModelSelect2Widget, HeavySelect2Widget
from passim.seeker.models import *

def init_choices(obj, sFieldName, sSet, use_helptext=True, maybe_empty=False, bUseAbbr=False, exclude=None):
    if (obj.fields != None and sFieldName in obj.fields):
        if bUseAbbr:
            obj.fields[sFieldName].choices = build_abbr_list(sSet, maybe_empty=maybe_empty, exclude=exclude)
        else:
            obj.fields[sFieldName].choices = build_choice_list(sSet, maybe_empty=maybe_empty)
        if use_helptext:
            obj.fields[sFieldName].help_text = get_help(sSet)

def user_is_in_team(username, team_group, userplus=None):
    bResult = False
    # Validate
    if username and team_group and username != "" and team_group != "":
        # First filter on owner
        owner = Profile.get_user_profile(username)
        # Now check for permissions
        bResult = (owner.user.groups.filter(name=team_group).first() != None)
        # If the user has no permission, perhaps he is a 'userplus'?
        if not bResult and userplus:
            bResult = (owner.user.groups.filter(name=userplus).first() != None)
    return bResult

CODE_TYPE = [('-', 'Irrelevant'), ('spe', 'Part of a Super Sermon Gold'), ('non', 'Loner: not part of a SSG')]


# ================= WIDGETS =====================================


class AuthorOneWidget(ModelSelect2Widget):
    model = Author
    search_fields = [ 'name__icontains']

    def label_from_instance(self, obj):
        return obj.name

    def get_queryset(self):
        return Author.objects.all().order_by('name').distinct()


class AuthorWidget(ModelSelect2MultipleWidget):
    model = Author
    search_fields = [ 'name__icontains']

    def label_from_instance(self, obj):
        return obj.name

    def get_queryset(self):
        return Author.objects.all().order_by('name').distinct()


class AutypeWidget(ModelSelect2Widget):
    model = FieldChoice
    search_fields = [ 'english_name__icontains']

    def label_from_instance(self, obj):
        return obj.english_name

    def get_queryset(self):
        return FieldChoice.objects.filter(field=CERTAINTY_TYPE).order_by("english_name")


class CityOneWidget(ModelSelect2Widget):
    model = Location
    search_fields = [ 'name__icontains' ]
    dependent_fields = {'lcity': 'lcity_manuscripts'}

    def label_from_instance(self, obj):
        return obj.name

    def get_queryset(self):
        loc_city = LocationType.objects.filter(name="city").first()
        return Location.objects.filter(loctype=loc_city).order_by('name').distinct()


class CodeWidget(ModelSelect2MultipleWidget):
    # PASSIM codes defined in EqualGold instances
    model = EqualGold
    search_fields = [ 'code__icontains' ]

    def label_from_instance(self, obj):
        return obj.code

    def get_queryset(self):
        return EqualGold.objects.filter(moved__isnull=True).order_by('code').distinct()


class CollectionWidget(ModelSelect2MultipleWidget):
    model = Collection
    search_fields = [ 'name__icontains' ]
    type = None

    def label_from_instance(self, obj):
        return "{} ({})".format( obj.name, obj.owner.user.username)

    def get_queryset(self):
        username = self.attrs.pop('username', '')
        team_group = self.attrs.pop('team_group', '')
        if self.type:
            qs = Collection.get_scoped_queryset(self.type, username, team_group)
        else:
            qs = Collection.get_scoped_queryset(None, username, team_group)
        return qs


class CollectionGoldWidget(CollectionWidget):
    """Like Collection, but then for: SermonGold"""
    type = "gold"


class CollectionManuWidget(CollectionWidget):
    """Like Collection, but then for: Manuscript"""
    type = "manu"


class CollectionSermoWidget(CollectionWidget):
    """Like Collection, but then for: Sermon"""
    type = "sermo"


class CollectionSuperWidget(CollectionWidget):
    """Like Collection, but then for: EqualGold = super sermon gold"""
    type = "super"


class CollOneWidget(ModelSelect2Widget):
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


class CollOneGoldWidget(CollOneWidget):
    """Like CollOne, but then for: SermonGold"""
    type = "gold"


class CollOneManuWidget(CollOneWidget):
    """Like CollOne, but then for: Manuscript"""
    type = "manu"


class CollOneSermoWidget(CollOneWidget):
    """Like CollOne, but then for: Sermon"""
    type = "sermo"


class CollOneSuperWidget(CollOneWidget):
    """Like CollOne, but then for: EqualGold = super sermon gold"""
    type = "super"


class CountryOneWidget(ModelSelect2Widget):
    model = Location
    search_fields = [ 'name__icontains' ]
    dependent_fields = {'lcountry': 'lcountry_manuscripts'}

    def label_from_instance(self, obj):
        return obj.name

    def get_queryset(self):
        loc_country = LocationType.objects.filter(name="country").first()
        return Location.objects.filter(loctype=loc_country).order_by('name').distinct()


class DaterangeWidget(ModelSelect2MultipleWidget):
    model = Daterange
    search_fields = [ 'yearstart__icontains', 'yearfinish__icontains' ]
    addonly = False

    def label_from_instance(self, obj):
        return "{}-{}".format(obj.yearstart, obj.yearfinish)

    def get_queryset(self):
        if self.addonly:
            qs = Daterange.objects.none()
        else:
            qs = Daterange.objects.all().order_by('yearstart').distinct()
        return qs


class EdirefSgWidget(ModelSelect2MultipleWidget):
    model = EdirefSG
    search_fields = [ 'reference__full__icontains' ]

    def label_from_instance(self, obj):
        # The label only gives the SHORT version!!
        return obj.get_short()

    def get_queryset(self):
        return EdirefSG.objects.all().order_by('reference__full', 'pages').distinct()


class EqualGoldMultiWidget(ModelSelect2MultipleWidget):
    model = EqualGold
    search_fields = ['code__icontains', 'id__icontains', 'author__name__icontains', 'equal_goldsermons__siglist__icontains']
    addonly = False

    def label_from_instance(self, obj):
        # sLabel = obj.get_label(do_incexpl = False)
        sLabel = obj.code
        return sLabel

    def get_queryset(self):
        if self.addonly:
            qs = EqualGold.objects.none()
        else:
            qs = EqualGold.objects.filter(code__isnull=False, moved__isnull=True).order_by('code').distinct()
        return qs


class EqualGoldLinkAddOnlyWidget(EqualGoldMultiWidget):
    model = EqualGoldLink
    search_fields = ['dst__code__icontains', 'dst__id__icontains', 'dst__author__name__icontains', 'dst__equal_goldsermons__siglist__icontains']
    addonly = True

    def label_from_instance(self, obj):
        sLabel = obj.get_label(do_incexpl = True)
        return sLabel

    def get_queryset(self):
        if self.addonly:
            qs = EqualGoldLink.objects.none()
        else:
            qs = EqualGoldLink.objects.all().order_by('dst__code', 'dst__firstsig').distinct()
        return qs


class EqualGoldWidget(ModelSelect2Widget):
    model = EqualGold
    search_fields = [ 'code__icontains', 'author__name__icontains', 'srchincipit__icontains', 'srchexplicit__icontains', 'equal_goldsermons__siglist__icontains' ]
    addonly = False
    order = [F('code').asc(nulls_last=True), 'firstsig']

    def label_from_instance(self, obj):
        # Determine the full text
        full = obj.get_text()
        # Determine here what to return...
        return full

    def get_queryset(self):
        if self.addonly:
            qs = EqualGold.objects.none()
        else:
            # qs = EqualGold.objects.all().order_by('code', 'firstsig').distinct()
            qs = EqualGold.objects.filter(moved__isnull=True).order_by(*self.order).distinct()
        return qs


class FtextlinkWidget(ModelSelect2MultipleWidget):
    model = Ftextlink
    search_fields = [ 'url__icontains' ]

    def label_from_instance(self, obj):
        # The label only gives the SHORT version!!
        return obj.url

    def get_queryset(self):
        return Ftextlink.objects.all().order_by('url').distinct()


class KeywordWidget(ModelSelect2MultipleWidget):
    model = Keyword
    search_fields = [ 'name__icontains' ]
    is_team = True

    def label_from_instance(self, obj):
        return obj.name

    def get_queryset(self):
        if self.is_team:
            qs = Keyword.objects.all().order_by('name').distinct()
        else:
            qs = Keyword.objects.exclude(visibility="edi").order_by('name').distinct()
        return qs


class KeywordAllWidget(KeywordWidget):
    is_team = False


class KeywordOneWidget(ModelSelect2Widget):
    model = Keyword
    search_fields = [ 'name__icontains' ]
    is_team = True

    def label_from_instance(self, obj):
        return obj.name

    def get_queryset(self):
        if self.is_team:
            qs = Keyword.objects.all().order_by('name').distinct()
        else:
            qs = Keyword.objects.exclude(visibility="edi").order_by('name').distinct()
        return qs


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


class LibraryOneWidget(ModelSelect2Widget):
    model = Library
    search_fields = [ 'name__icontains' ]
    dependent_fields = {'lcity': 'lcity', 'lcountry': 'lcountry'}

    def label_from_instance(self, obj):
        return obj.name

    def get_queryset(self):
        return Library.objects.all().order_by('name').distinct()

    def filter_queryset(self, term, queryset = None, **dependent_fields):
        response = super(LibraryOneWidget, self).filter_queryset(term, queryset, **dependent_fields)
        return response


class LitrefSgWidget(ModelSelect2MultipleWidget):
    model = LitrefSG
    search_fields = [ 'reference__full__icontains' ]

    def label_from_instance(self, obj):
        # The label only gives the SHORT version!!
        return obj.get_short()

    def get_queryset(self):
        return LitrefSG.objects.all().order_by('reference__full', 'pages').distinct()


class LitrefManWidget(ModelSelect2MultipleWidget):
    model = LitrefMan
    search_fields = [ 'reference__full__icontains' ]

    def label_from_instance(self, obj):
        # The label only gives the SHORT version!!
        return obj.get_short()

    def get_queryset(self):
        return LitrefMan.objects.all().order_by('reference__full', 'pages').distinct()


class LocationWidget(ModelSelect2MultipleWidget):
    model = Location
    search_fields = [ 'name__icontains']

    def label_from_instance(self, obj):
        sLabel = "{} ({})".format(obj.name, obj.loctype)
        # sLabel = obj.name
        return sLabel


class LocationOneWidget(ModelSelect2Widget):
    model = Location
    search_fields = [ 'name__icontains']

    def label_from_instance(self, obj):
        sLabel = "{} ({})".format(obj.name, obj.loctype)
        # sLabel = obj.name
        return sLabel

    def get_queryset(self):
        return Location.objects.all().order_by('name').distinct()


class ManuidWidget(ModelSelect2MultipleWidget):
    model = Manuscript
    search_fields = [ 'idno__icontains']

    def label_from_instance(self, obj):
        return obj.idno

    def get_queryset(self):
        return Manuscript.objects.filter(mtype='man').order_by('idno').distinct()


class ManuscriptExtWidget(ModelSelect2MultipleWidget):
    model = ManuscriptExt
    search_fields = [ 'url__icontains' ]
    addonly = False

    def label_from_instance(self, obj):
        return obj.url

    def get_queryset(self):
        if self.addonly:
            qs = ManuscriptExt.objects.none()
        else:
            qs = ManuscriptExt.objects.all().order_by('url').distinct()
        return qs        


class OriginOneWidget(ModelSelect2Widget):
    model = Origin
    search_fields = [ 'name__icontains']

    def label_from_instance(self, obj):
        # sLabel = "{} ({})".format(obj.name, obj.loctype)
        sLabel = obj.name
        return sLabel

    def get_queryset(self):
        return Location.objects.all().order_by('name').distinct()


class ProjectOneWidget(ModelSelect2Widget):
    model = Project
    search_fields = [ 'name__icontains' ]

    def label_from_instance(self, obj):
        return obj.name

    def get_queryset(self):
        return Project.objects.all().order_by('name').distinct()


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


class ProfileOneWidget(ModelSelect2Widget):
    model = Profile
    search_fields = [ 'user__username__icontains' ]

    def label_from_instance(self, obj):
        return obj.user.username

    def get_queryset(self):
        return Profile.objects.all().order_by('user__username').distinct()


class ProvenanceWidget(ModelSelect2MultipleWidget):
    model = Provenance
    search_fields = [ 'name__icontains' ]
    addonly = False

    def label_from_instance(self, obj):
        return obj.name

    def get_queryset(self):
        if self.addonly:
            qs = Provenance.objects.none()
        else:
            qs = Provenance.objects.all().order_by('name').distinct()
        return qs        


class SermonDescrGoldWidget(ModelSelect2MultipleWidget):
    model = SermonDescrGold
    add_only = False
    search_fields = ['sermon__siglist__icontains',      'sermon__author__name__icontains', 
                     'sermon__srchincipit__icontains',  'sermon__srchexplicit__icontains' ]

    def label_from_instance(self, obj):
        # Determine the full text
        full = obj.get_label(do_incexpl=False)
        # Determine here what to return...
        return full

    def get_queryset(self):
        # return SermonDescrGold.objects.all().order_by('linktype', 'sermon__author__name', 'sermon__siglist').distinct()
        if self.add_only:
            qs = SermonDescrGold.objects.none()
        else:
            qs = SermonDescrGold.unique_list()
        return qs


class SermonDescrGoldAddOnlyWidget(SermonDescrGoldWidget):
    add_only = True


class SermonDescrSuperWidget(ModelSelect2MultipleWidget):
    model = SermonDescrEqual
    add_only = False
    search_fields = ['sermon__siglist__icontains',      'sermon__author__name__icontains', 
                     'super__author__name__icontains', 'super__code__icontains',
                     'super__srchincipit__icontains',  'super__srchexplicit__icontains' ]

    def label_from_instance(self, obj):
        # Determine the full text
        full = obj.get_label(do_incexpl=False)
        # Determine here what to return...
        return full

    def get_queryset(self):
        if self.add_only:
            qs = SermonDescrEqual.objects.none()
        else:
            qs = SermonDescrEqual.unique_list()
        return qs


class SermonDescrSuperAddOnlyWidget(SermonDescrSuperWidget):
    add_only = True


class SermonGoldOneWidget(ModelSelect2Widget):
    model = SermonGold
    search_fields = [ 'siglist__icontains', 'author__name__icontains', 'srchincipit__icontains', 'srchexplicit__icontains' ]

    def label_from_instance(self, obj):
        # Determine the full text
        full = obj.get_label(do_incexpl=True)
        # Determine here what to return...
        return full

    def get_queryset(self):
        return SermonGold.objects.all().order_by('siglist').distinct()


class SermonGoldWidget(ModelSelect2MultipleWidget):
    model = SermonGold
    search_fields = [ 'siglist__icontains', 'author__name__icontains', 'srchincipit__icontains', 'srchexplicit__icontains' ]

    def label_from_instance(self, obj):
        # Determine the full text
        full = obj.get_label(do_incexpl=True)
        # Determine here what to return...
        return full

    def get_queryset(self):
        return SermonGold.objects.all().order_by('siglist').distinct()


class ManualSignatureWidget(ModelSelect2MultipleWidget):
    # NOTE: experimental
    model = SermonSignature
    search_fields = [ 'code__icontains' ]

    def label_from_instance(self, obj):
        return obj.code

    def get_queryset(self):
        return SermonSignatureSignature.objects.all().order_by('code').distinct()


class SignatureWidget(ModelSelect2MultipleWidget):
    # NOTE: only use the [Signature] table - don't use [SermonSignature]
    model = Signature
    search_fields = [ 'code__icontains' ]

    def label_from_instance(self, obj):
        return obj.code

    def get_queryset(self):
        return Signature.objects.all().order_by('code').distinct()


class SignatureOneWidget(ModelSelect2Widget):
    model = Signature
    search_fields = [ 'code__icontains' ]
    editype = None

    def label_from_instance(self, obj):
        return obj.code

    def get_queryset(self):
        if self.editype == None:
            qs = Signature.objects.all().order_by('code').distinct()
        else:
            qs = Signature.objects.filter(editype=self.editype).order_by('code').distinct()
        return qs


class SignatureGrysonWidget(SignatureOneWidget):
    editype = "gr"


class SignatureClavisWidget(SignatureOneWidget):
    editype = "cl"


class SignatureOtherWidget(SignatureOneWidget):
    editype = "ot"


class StypeWidget(ModelSelect2MultipleWidget):
    model = FieldChoice
    search_fields = [ 'english_name__icontains']

    def label_from_instance(self, obj):
        return obj.english_name

    def get_queryset(self):
        return FieldChoice.objects.filter(field=STATUS_TYPE).order_by("english_name")


class SuperOneWidget(ModelSelect2Widget):
    model = EqualGold
    search_fields = ['code__icontains', 'id__icontains', 'author__name__icontains', 
                     'srchincipit__icontains', 'srchexplicit__icontains',
                     'equal_goldsermons__siglist__icontains']

    def label_from_instance(self, obj):
        sLabel = obj.get_label(do_incexpl = True)
        #sLabel = obj.code
        #if sLabel == None:
        #    sLabel = "ssg id {}".format(obj.id)
        #elif obj.author != None:
        #    sLabel = "{} {}".format(sLabel, obj.author.name)
        return sLabel

    def get_queryset(self):
        return EqualGold.objects.filter(moved__isnull=True).order_by('code', 'id').distinct()



# ================= FORMS =======================================

class PassimModelForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        self.username = kwargs.pop('username', "")
        self.team_group = kwargs.pop('team_group', "")
        self.userplus = kwargs.pop('userplus', "")
        # Start by executing the standard handling
        super(PassimModelForm, self).__init__(*args, **kwargs)


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


class SearchManuForm(PassimModelForm):
    """Manuscript search form"""

    manuidlist  = ModelMultipleChoiceField(queryset=None, required=False, 
                            widget=ManuidWidget(attrs={'data-placeholder': 'Select multiple manuscript identifiers...', 'style': 'width: 100%;'}))

    stypelist   = ModelMultipleChoiceField(queryset=None, required=False, 
                            widget=StypeWidget(attrs={'data-placeholder': 'Select multiple status types...', 'style': 'width: 100%;'}))

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
    passimlist  = ModelMultipleChoiceField(queryset=None, required=False, 
                    widget=EqualGoldMultiWidget(attrs={'data-placeholder': 'Select multiple passim codes...', 'style': 'width: 100%;', 
                                                       'class': 'searching'}))
    passimcode  = forms.CharField(label=_("Passim code"), required=False, 
                widget=forms.TextInput(attrs={'class': 'searching', 'style': 'width: 100%;', 'placeholder': 'Passim code. Use wildcards, e.g: *002.*, *003'}))
    collist_m =  ModelMultipleChoiceField(queryset=None, required=False)
    collist_s =  ModelMultipleChoiceField(queryset=None, required=False)
    collist_sg =  ModelMultipleChoiceField(queryset=None, required=False)
    collist_ssg =  ModelMultipleChoiceField(queryset=None, required=False)
    collection_m = forms.CharField(label=_("Collection m"), required=False,
                widget=forms.TextInput(attrs={'class': 'typeahead searching collections input-sm', 'placeholder': 'Collection(s)...', 'style': 'width: 100%;'}))
    collection_s = forms.CharField(label=_("Collection s"), required=False,
                widget=forms.TextInput(attrs={'class': 'typeahead searching collections input-sm', 'placeholder': 'Collection(s)...', 'style': 'width: 100%;'}))
    collection_sg = forms.CharField(label=_("Collection sg"), required=False,
                widget=forms.TextInput(attrs={'class': 'typeahead searching collections input-sm', 'placeholder': 'Collection(s)...', 'style': 'width: 100%;'}))
    collection_ssg = forms.CharField(label=_("Collection ssg"), required=False,
                widget=forms.TextInput(attrs={'class': 'typeahead searching collections input-sm', 'placeholder': 'Collection(s)...', 'style': 'width: 100%;'}))
    collone     = ModelChoiceField(queryset=None, required=False, 
                widget=CollOneManuWidget(attrs={'data-placeholder': 'Select one collection...', 'style': 'width: 100%;', 'class': 'searching'}))
    typeaheads = ["countries", "cities", "libraries", "origins", "locations", "signatures", "keywords", "collections", "manuidnos", "gldsiggrysons", "gldsigclavises"]

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
        oErr = ErrHandle()
        try:
            username = self.username
            team_group = self.team_group
            # NONE of the fields are required in the SEARCH form!
            self.fields['stype'].required = False
            self.fields['name'].required = False
            self.fields['yearstart'].required = False
            self.fields['yearfinish'].required = False
            self.fields['manuidlist'].queryset = Manuscript.objects.filter(mtype='man').order_by('idno')
            self.fields['siglist'].queryset = Signature.objects.all().order_by('code')
            self.fields['kwlist'].queryset = Keyword.get_scoped_queryset(username, team_group)
            self.fields['prjlist'].queryset = Project.objects.all().order_by('name')
            self.fields['stypelist'].queryset = FieldChoice.objects.filter(field=STATUS_TYPE).order_by("english_name")
            self.fields['passimlist'].queryset = EqualGold.objects.filter(code__isnull=False, moved__isnull=True).order_by('code')

            # Set the widgets correctly
            self.fields['collist_m'].widget = CollectionManuWidget( attrs={'username': username, 'team_group': team_group,
                        'data-placeholder': 'Select multiple manuscript collections...', 'style': 'width: 100%;', 'class': 'searching'})
            self.fields['collist_s'].widget = CollectionSermoWidget( attrs={'username': username, 'team_group': team_group,
                        'data-placeholder': 'Select multiple manuscript collections...', 'style': 'width: 100%;', 'class': 'searching'})
            self.fields['collist_sg'].widget = CollectionGoldWidget( attrs={'username': username, 'team_group': team_group,
                        'data-placeholder': 'Select multiple manuscript collections...', 'style': 'width: 100%;', 'class': 'searching'})
            self.fields['collist_ssg'].widget = CollectionSuperWidget( attrs={'username': username, 'team_group': team_group,
                        'data-placeholder': 'Select multiple manuscript collections...', 'style': 'width: 100%;', 'class': 'searching'})

            # Note: the collection filters must use the SCOPE of the collection
            self.fields['collist_m'].queryset = Collection.get_scoped_queryset('manu', username, team_group)
            self.fields['collist_s'].queryset = Collection.get_scoped_queryset('sermo', username, team_group)
            self.fields['collist_sg'].queryset = Collection.get_scoped_queryset('gold', username, team_group)
            self.fields['collist_ssg'].queryset = Collection.get_scoped_queryset('super', username, team_group)
            #self.fields['collist_m'].queryset = Collection.objects.filter(type='manu').order_by('name')
            #self.fields['collist_s'].queryset = Collection.objects.filter(type='sermo').order_by('name')
            #self.fields['collist_sg'].queryset = Collection.objects.filter(type='gold').order_by('name')
            #self.fields['collist_ssg'].queryset = Collection.objects.filter(type='super').order_by('name')

            # The CollOne information is needed for the basket (add basket to collection)
            prefix = "manu"
            self.fields['collone'].queryset = Collection.objects.filter(type=prefix).order_by('name')

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
        except:
            msg = oErr.get_error_message()
            oErr.DoError("SearchManuForm-init")
        return None


class SermonForm(PassimModelForm):
    # Helper fields for SermonDescr fields
    stypelist   = ModelMultipleChoiceField(queryset=None, required=False, 
                    widget=StypeWidget(attrs={'data-placeholder': 'Select multiple status types...', 'style': 'width: 100%;'}))
    authorname  = forms.CharField(label=_("Author"), required=False, 
                    widget=forms.TextInput(attrs={'class': 'typeahead searching authors input-sm', 'placeholder': 'Authors using wildcards...', 'style': 'width: 100%;'}))
    authorlist  = ModelMultipleChoiceField(queryset=None, required=False, 
                    widget=AuthorWidget(attrs={'data-placeholder': 'Select multiple authors...', 'style': 'width: 100%;', 'class': 'searching'}))
    manuidno    = forms.CharField(label=_("Manuscript"), required=False,
                    widget=forms.TextInput(attrs={'class': 'typeahead searching manuidnos input-sm', 'placeholder': 'Shelfmarks using wildcards...', 'style': 'width: 100%;'}))
    manuidlist  = ModelMultipleChoiceField(queryset=None, required=False, 
                    widget=ManuidWidget(attrs={'data-placeholder': 'Select multiple manuscript identifiers...', 'style': 'width: 100%;'}))
    signature   = forms.CharField(label=_("Signature"), required=False,
                    widget=forms.TextInput(attrs={'class': 'typeahead searching srmsignatures input-sm', 'placeholder': 'Signatures (Gryson, Clavis) using wildcards...', 'style': 'width: 100%;'}))
    signatureid = forms.CharField(label=_("Signature ID"), required=False)
    siglist     = ModelMultipleChoiceField(queryset=None, required=False, 
                    widget=SignatureWidget(attrs={'data-placeholder': 'Select multiple signatures (Gryson, Clavis)...', 'style': 'width: 100%;', 'class': 'searching'}))
    siglist_a = ModelMultipleChoiceField(queryset=None, required=False, 
                    widget=SignatureWidget(attrs={'data-placeholder': 'Select multiple signatures (Gryson, Clavis)...', 'style': 'width: 100%;', 'class': 'searching'}))
    siglist_m = ModelMultipleChoiceField(queryset=None, required=False, 
                    widget=ManualSignatureWidget(attrs={'data-placeholder': 'Select multiple signatures (Gryson, Clavis)...', 'style': 'width: 100%;', 'class': 'searching'}))
    keyword = forms.CharField(label=_("Keyword"), required=False,
                widget=forms.TextInput(attrs={'class': 'typeahead searching keywords input-sm', 'placeholder': 'Keyword(s)...', 'style': 'width: 100%;'}))
    kwlist     = ModelMultipleChoiceField(queryset=None, required=False, 
                widget=KeywordWidget(attrs={'data-placeholder': 'Select multiple keywords...', 'style': 'width: 100%;', 'class': 'searching'}))
    ukwlist     = ModelMultipleChoiceField(queryset=None, required=False, 
                widget=KeywordWidget(attrs={'data-placeholder': 'Select multiple user-keywords...', 'style': 'width: 100%;', 'class': 'searching'}))
    superlist = ModelMultipleChoiceField(queryset=None, required=False,
                widget=SermonDescrSuperAddOnlyWidget(attrs={'data-placeholder': 'Add links with the green "+" sign...', 
                                                  'placeholder': 'Linked super sermons gold...', 'style': 'width: 100%;', 'class': 'searching'}))
    passimlist  = ModelMultipleChoiceField(queryset=None, required=False, 
                    widget=EqualGoldMultiWidget(attrs={'data-placeholder': 'Select multiple passim codes...', 'style': 'width: 100%;', 
                                                       'class': 'searching'}))
    passimcode  = forms.CharField(label=_("Passim code"), required=False, 
                widget=forms.TextInput(attrs={'class': 'searching', 'style': 'width: 100%;', 'placeholder': 'Passim code. Use wildcards, e.g: *002.*, *003'}))

    collist_m =  ModelMultipleChoiceField(queryset=None, required=False)
    collist_s =  ModelMultipleChoiceField(queryset=None, required=False)
    collist_sg =  ModelMultipleChoiceField(queryset=None, required=False)
    collist_ssg =  ModelMultipleChoiceField(queryset=None, required=False)
    collection_m = forms.CharField(label=_("Collection m"), required=False,
                widget=forms.TextInput(attrs={'class': 'typeahead searching collections input-sm', 'placeholder': 'Collection(s)...', 'style': 'width: 100%;'}))
    collection_s = forms.CharField(label=_("Collection s"), required=False,
                widget=forms.TextInput(attrs={'class': 'typeahead searching collections input-sm', 'placeholder': 'Collection(s)...', 'style': 'width: 100%;'}))
    collection_sg = forms.CharField(label=_("Collection sg"), required=False,
                widget=forms.TextInput(attrs={'class': 'typeahead searching collections input-sm', 'placeholder': 'Collection(s)...', 'style': 'width: 100%;'}))
    collection_ssg = forms.CharField(label=_("Collection ssg"), required=False,
                widget=forms.TextInput(attrs={'class': 'typeahead searching collections input-sm', 'placeholder': 'Collection(s)...', 'style': 'width: 100%;'}))
    collone     = ModelChoiceField(queryset=None, required=False, 
                widget=CollOneSermoWidget(attrs={'data-placeholder': 'Select one collection...', 'style': 'width: 100%;', 'class': 'searching'}))
   
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
    autype      = forms.ChoiceField(label=_("Author certainty type"), required=False,
                     widget=forms.Select(attrs={'class': 'input-sm', 'placeholder': 'Author certainty level...',  'style': 'width: 100%;'}))
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
        fields = ['title', 'subtitle', 'author', 'locus', 'incipit', 'explicit', 'quote', 'manu', 'mtype',
                  'feast', 'bibleref', 'bibnotes', 'additional', 'note', 'stype', 'sectiontitle', 'postscriptum']
        widgets={'title':       forms.Textarea(attrs={'rows': 1, 'cols': 40, 'style': 'height: 40px; width: 100%;', 'class': 'searching'}),
                 'sectiontitle':    forms.TextInput(attrs={'style': 'width: 100%;', 'class': 'searching'}),
                 'subtitle':    forms.TextInput(attrs={'style': 'width: 100%;', 'class': 'searching'}),
                 'author':      AuthorOneWidget(attrs={'data-placeholder': 'Select one author...', 'style': 'width: 100%;', 'class': 'searching'}),
                 # forms.TextInput(attrs={'style': 'width: 100%;'}),
                 'nickname':    forms.TextInput(attrs={'style': 'width: 100%;'}),
                 'locus':       forms.TextInput(attrs={'style': 'width: 100%;', 'class': 'searching'}),
                 'bibnotes':    forms.TextInput(attrs={'placeholder': 'Bibliography notes...', 'style': 'width: 100%;', 'class': 'searching'}),
                 'feast':       forms.TextInput(attrs={'style': 'width: 100%;', 'class': 'searching'}),

                 'incipit':     forms.TextInput(attrs={'class': 'typeahead searching srmincipits input-sm', 'placeholder': 'Incipit...', 'style': 'width: 100%;'}),
                 'explicit':    forms.TextInput(attrs={'class': 'typeahead searching srmexplicits input-sm', 'placeholder': 'Explicit...', 'style': 'width: 100%;'}),
                 'stype':       forms.Select(attrs={'style': 'width: 100%;'}),

                 # larger areas
                 'postscriptum':       forms.Textarea(attrs={'rows': 1, 'cols': 40, 'style': 'height: 40px; width: 100%;', 'class': 'searching'}),
                 'quote':       forms.Textarea(attrs={'rows': 1, 'cols': 40, 'style': 'height: 40px; width: 100%;', 'class': 'searching'}),
                 'bibleref':    forms.Textarea(attrs={'rows': 1, 'cols': 40, 'style': 'height: 40px; width: 100%;', 'class': 'searching'}),
                 'additional':  forms.Textarea(attrs={'rows': 1, 'cols': 40, 'style': 'height: 40px; width: 100%;', 'class': 'searching'}),
                 'note':        forms.Textarea(attrs={'rows': 1, 'cols': 40, 'style': 'height: 40px; width: 100%;', 'class': 'searching'}),
                 }

    def __init__(self, *args, **kwargs):
        # Start by executing the standard handling
        super(SermonForm, self).__init__(*args, **kwargs)
        oErr = ErrHandle()
        try:
            username = self.username
            team_group = self.team_group
            profile = Profile.get_user_profile(username)

            # Some fields are not required
            self.fields['autype'].required = False
            init_choices(self, 'autype', CERTAINTY_TYPE, bUseAbbr=True)
            self.fields['manu'].required = False
            self.fields['stype'].required = False
            self.fields['mtype'].required = False
            self.fields['stypelist'].queryset = FieldChoice.objects.filter(field=STATUS_TYPE).order_by("english_name")
            self.fields['manuidlist'].queryset = Manuscript.objects.filter(mtype='man').order_by('idno')
            self.fields['authorlist'].queryset = Author.objects.all().order_by('name')
            # self.fields['kwlist'].queryset = Keyword.objects.all().order_by('name')
            self.fields['kwlist'].queryset = Keyword.get_scoped_queryset(username, team_group)
            self.fields['ukwlist'].queryset = Keyword.get_scoped_queryset(username, team_group)
            if user_is_in_team(username, team_group):
                self.fields['kwlist'].widget.is_team = True
                self.fields['ukwlist'].widget.is_team = True
            else:
                self.fields['kwlist'].widget.is_team = False
                self.fields['ukwlist'].widget.is_team = False
            # Note: what we show the user is the set of GOLD-signatures
            self.fields['siglist'].queryset = Signature.objects.all().order_by('code')
            self.fields['siglist_a'].queryset = Signature.objects.all().order_by('code')
            self.fields['siglist_m'].queryset = SermonSignature.objects.all().order_by('code')
            # The available Sermondescr-Equal list
            # self.fields['goldlist'].queryset = SermonDescrGold.objects.none()
            self.fields['superlist'].queryset = SermonDescrEqual.objects.none()
            self.fields['passimlist'].queryset = EqualGold.objects.filter(code__isnull=False, moved__isnull=True).order_by('code')

            # Set the widgets correctly
            self.fields['collist_m'].widget = CollectionManuWidget( attrs={'username': username, 'team_group': team_group,
                        'data-placeholder': 'Select multiple manuscript collections...', 'style': 'width: 100%;', 'class': 'searching'})
            self.fields['collist_s'].widget = CollectionSermoWidget( attrs={'username': username, 'team_group': team_group,
                        'data-placeholder': 'Select multiple sermon manifestation collections...', 'style': 'width: 100%;', 'class': 'searching'})
            self.fields['collist_sg'].widget = CollectionGoldWidget( attrs={'username': username, 'team_group': team_group,
                        'data-placeholder': 'Select multiple sermon gold collections...', 'style': 'width: 100%;', 'class': 'searching'})
            self.fields['collist_ssg'].widget = CollectionSuperWidget( attrs={'username': username, 'team_group': team_group,
                        'data-placeholder': 'Select multiple super sermon gold collections...', 'style': 'width: 100%;', 'class': 'searching'})

            # Note: the collection filters must use the SCOPE of the collection
            self.fields['collist_m'].queryset = Collection.get_scoped_queryset('manu', username, team_group)
            self.fields['collist_s'].queryset = Collection.get_scoped_queryset('sermo', username, team_group)
            self.fields['collist_sg'].queryset = Collection.get_scoped_queryset('gold', username, team_group)
            self.fields['collist_ssg'].queryset = Collection.get_scoped_queryset('super', username, team_group)

            # The CollOne information is needed for the basket (add basket to collection)
            prefix = "sermo"
            self.fields['collone'].queryset = Collection.objects.filter(type=prefix).order_by('name')

            # For searching/listing
            self.fields['mtype'].initial = "man"

            # Get the instance
            if 'instance' in kwargs:
                instance = kwargs['instance']
                # If there is an instance, then check the author specification
                sAuthor = "" if not instance.author else instance.author.name

                if instance.get_manuscript():
                    self.fields['manu'].queryset = Manuscript.objects.filter(id=instance.get_manuscript().id)

                ## If there is an instance, then check the nickname specification
                #sNickName = "" if not instance.nickname else instance.nickname.name
                self.fields['authorname'].initial = sAuthor
                self.fields['authorname'].required = False
                # Set initial values for lists, where appropriate. NOTE: need to have the initial ID values
                self.fields['kwlist'].initial = [x.pk for x in instance.keywords.all().order_by('name')]
                self.fields['ukwlist'].initial = [x.keyword.pk for x in instance.sermo_userkeywords.filter(profile=profile).order_by('keyword__name')]

                # Determine the initial collections
                self.fields['collist_m'].initial = [x.pk for x in instance.collections.filter(type='manu').order_by('name')]
                self.fields['collist_s'].initial = [x.pk for x in instance.collections.filter(type='sermo').order_by('name')]
                self.fields['collist_sg'].initial = [x.pk for x in instance.collections.filter(type='gold').order_by('name')]
                self.fields['collist_ssg'].initial = [x.pk for x in instance.collections.filter(type='super').order_by('name')]

                # Note: what we *show* are the signatures that have actually been copied -- the SERMON signatures
                self.fields['siglist'].initial = [x.pk for x in instance.signatures.all().order_by('-editype', 'code')]

                # Note: this is the list of links between SermonDesrc-Gold
                self.fields['superlist'].initial = [x.pk for x in instance.sermondescr_super.all().order_by('linktype', 'sermon__author__name', 'sermon__siglist')]

                # Make sure the initial superlist captures exactly what we have
                self.fields['superlist'].queryset = SermonDescrEqual.objects.filter(Q(id__in = self.fields['superlist'].initial))

                self.fields['autype'].initial = instance.autype

                iStop = 1
        except:
            msg = oErr.get_error_message()
            oErr.DoError("SermonForm-init")
        return None


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
        fields = ['name', 'visibility']
        widgets={'name':        forms.TextInput(attrs={'style': 'width: 100%;', 'class': 'searching'}),
                 'visibility':  forms.Select(attrs={'class': 'input-sm', 'placeholder': 'Visibility type...',  'style': 'width: 100%;'})
                 }

    def __init__(self, *args, **kwargs):
        # Start by executing the standard handling
        super(KeywordForm, self).__init__(*args, **kwargs)
        # Some fields are not required
        self.fields['name'].required = False
        self.fields['visibility'].required = False
        self.fields['kwlist'].queryset = Keyword.objects.all().order_by('name')
        # Initialize choices for linktype
        init_choices(self, 'vistype', VISIBILITY_TYPE, bUseAbbr=True, use_helptext=False)
        # Get the instance
        if 'instance' in kwargs:
            instance = kwargs['instance']
            self.fields['visibility'].initial = instance.visibility


class UserKeywordForm(forms.ModelForm):
    """User Keyword list"""

    profilelist = ModelMultipleChoiceField(queryset=None, required=False, 
                widget=ProfileWidget(attrs={'data-placeholder': 'Select multiple users...', 'style': 'width: 100%;', 'class': 'searching'}))
    kwlist     = ModelMultipleChoiceField(queryset=None, required=False, 
                widget=KeywordWidget(attrs={'data-placeholder': 'Select multiple keywords...', 'style': 'width: 100%;', 'class': 'searching'}))

    class Meta:
        ATTRS_FOR_FORMS = {'class': 'form-control'};

        model = UserKeyword
        fields = ['keyword', 'profile', 'type']
        widgets={'keyword': KeywordOneWidget(attrs={'data-placeholder': 'Select one keyword...', 'style': 'width: 100%;'}),
                 'profile': ProfileOneWidget(attrs={'data-placeholder': 'Select one user profile...', 'style': 'width: 100%;'}),
                 'type':    forms.Select(attrs={'class': 'input-sm', 'placeholder': 'Item type...',  'style': 'width: 100%;'})
                 }

    def __init__(self, *args, **kwargs):
        # Start by executing the standard handling
        super(UserKeywordForm, self).__init__(*args, **kwargs)
        # Some fields are not required
        self.fields['keyword'].required = False
        self.fields['profile'].required = False
        self.fields['type'].required = False

        self.fields['kwlist'].queryset = Keyword.objects.all().order_by('name')
        self.fields['profilelist'].queryset = Profile.objects.all().order_by('user__username')
        # Initialize choices for the type
        init_choices(self, 'type', COLLECTION_TYPE, bUseAbbr=True, use_helptext=False)
        # Get the instance
        if 'instance' in kwargs:
            instance = kwargs['instance']
            self.fields['keyword'].initial = instance.keyword
            self.fields['profile'].initial = instance.profile
            self.fields['type'].initial = instance.type


class ProvenanceForm(forms.ModelForm):
    """Provenance list"""

    class Meta:
        ATTRS_FOR_FORMS = {'class': 'form-control'};

        model = Provenance
        fields = ['name', 'location', 'note']
        widgets={'name':    forms.TextInput(attrs={'style': 'width: 100%;', 'class': 'searching', 'placeholder': 'Name for this provenance'}),
                 'location': LocationOneWidget(attrs={'data-placeholder': 'Select one location...', 'style': 'width: 100%;'}),
                 'note':    forms.Textarea(attrs={'rows': 1, 'cols': 40, 'style': 'height: 40px; width: 100%;', 
                                                      'class': 'searching', 'placeholder': 'Notes on this provenance...'})
                 }

    def __init__(self, *args, **kwargs):
        # Start by executing the standard handling
        super(ProvenanceForm, self).__init__(*args, **kwargs)

        # Some fields are not required
        self.fields['name'].required = False
        self.fields['location'].required = False
        self.fields['note'].required = False

        # Get the instance
        if 'instance' in kwargs:
            instance = kwargs['instance']



class ProfileForm(forms.ModelForm):
    """Profile list and details"""


    class Meta:
        ATTRS_FOR_FORMS = {'class': 'form-control'};

        model = Profile
        fields = ['user', 'ptype', 'affiliation']
        widgets={'user':        forms.TextInput(attrs={'style': 'width: 100%;', 'class': 'searching'}),
                 'ptype':       forms.Select(attrs={'class': 'input-sm', 'placeholder': 'User profile status...',  'style': 'width: 100%;'}),
                 'affiliation': forms.Textarea(attrs={'rows': 1, 'cols': 40, 'style': 'height: 40px; width: 100%;', 
                                                      'class': 'searching', 'placeholder': 'List all affiliation details...'}),
                 }

    def __init__(self, *args, **kwargs):
        # Start by executing the standard handling
        super(ProfileForm, self).__init__(*args, **kwargs)

        # Some fields are not required
        self.fields['user'].required = False
        self.fields['ptype'].required = False
        self.fields['affiliation'].required = False
        # Initialize choices for linktype
        init_choices(self, 'ptype', PROFILE_TYPE, bUseAbbr=True, use_helptext=False)
        # Get the instance
        if 'instance' in kwargs:
            instance = kwargs['instance']
            self.fields['ptype'].initial = instance.ptype
            self.fields['user'].initial = instance.user
            self.fields['user'].queryset = User.objects.filter(id=instance.user.id)

    def clean_user(self):
        data = self.cleaned_data.get("user")
        if data == None:
            data = self.fields['user'].initial
        return data
    

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


class CollectionForm(PassimModelForm):
    """Collection list"""

    collection_ta = forms.CharField(label=_("Collection"), required=False,
                widget=forms.TextInput(attrs={'class': 'typeahead searching collections input-sm', 'placeholder': 'Collection(s)...', 'style': 'width: 100%;'}))
    collist     = ModelMultipleChoiceField(queryset=None, required=False, 
                widget=CollectionWidget(attrs={'data-placeholder': 'Select multiple collections...', 'style': 'width: 100%;', 'class': 'searching'}))
    collist_m =  ModelMultipleChoiceField(queryset=None, required=False)
    collist_s =  ModelMultipleChoiceField(queryset=None, required=False, 
                widget=CollectionSermoWidget(attrs={'data-placeholder': 'Select multiple sermon collections...', 'style': 'width: 100%;', 'class': 'searching'}))
    collist_sg =  ModelMultipleChoiceField(queryset=None, required=False, 
                widget=CollectionGoldWidget(attrs={'data-placeholder': 'Select multiple gold sermon collections...', 'style': 'width: 100%;', 'class': 'searching'}))
    collist_ssg =  ModelMultipleChoiceField(queryset=None, required=False, 
                widget=CollectionSuperWidget(attrs={'data-placeholder': 'Select multiple super sg collections...', 'style': 'width: 100%;', 'class': 'searching'}))
    collone     = ModelChoiceField(queryset=None, required=False, 
                widget=CollOneWidget(attrs={'data-placeholder': 'Select one collection...', 'style': 'width: 100%;', 'class': 'searching'}))
    ownlist     = ModelMultipleChoiceField(queryset=None, required=False, 
                widget=ProfileWidget(attrs={'data-placeholder': 'Select multiple profiles...', 'style': 'width: 100%;', 'class': 'searching'}))
    typeaheads = ["collections"]

    class Meta:
        ATTRS_FOR_FORMS = {'class': 'form-control'};

        model = Collection
        fields = ['name', 'owner', 'descrip', 'readonly', 'url', 'type', 'scope']
        widgets={'name':        forms.TextInput(attrs={'style': 'width: 100%;', 'class': 'searching'}), 
                 'owner':       forms.TextInput(attrs={'style': 'width: 100%;'}),
                 'descrip':     forms.Textarea(attrs={'rows': 1, 'cols': 40, 'style': 'height: 40px; width: 100%;', 'class': 'searching'}),
                 'readonly':    forms.CheckboxInput(),
                 'url':         forms.TextInput(attrs={'style': 'width: 100%;'}),
                 'scope':       forms.Select(attrs={'style': 'width: 100%;'})
                 }

    def __init__(self, *args, **kwargs):
        # Start by executing the standard handling
        super(CollectionForm, self).__init__(*args, **kwargs)
        username = self.username
        team_group = self.team_group
        # Get the prefix
        prefix = "any" if 'prefix' not in kwargs else kwargs['prefix']
        # Some fields are not required
        self.fields['name'].required = False
        self.fields['owner'].required = False
        self.fields['descrip'].required = False
        self.fields['readonly'].required = False
        self.fields['type'].required = False
        self.fields['scope'].required = False
        self.fields['url'].required = False
        self.fields['collone'].required = False

        # Set the widgets correctly
        self.fields['collist_m'].widget = CollectionManuWidget( attrs={'username': username, 'team_group': team_group,
                    'data-placeholder': 'Select multiple manuscript collections...', 'style': 'width: 100%;', 'class': 'searching'})
        self.fields['collist_s'].widget = CollectionSermoWidget( attrs={'username': username, 'team_group': team_group,
                    'data-placeholder': 'Select multiple manuscript collections...', 'style': 'width: 100%;', 'class': 'searching'})
        self.fields['collist_sg'].widget = CollectionGoldWidget( attrs={'username': username, 'team_group': team_group,
                    'data-placeholder': 'Select multiple manuscript collections...', 'style': 'width: 100%;', 'class': 'searching'})
        self.fields['collist_ssg'].widget = CollectionSuperWidget( attrs={'username': username, 'team_group': team_group,
                    'data-placeholder': 'Select multiple manuscript collections...', 'style': 'width: 100%;', 'class': 'searching'})

        if prefix == "any":
            self.fields['collist'].queryset = Collection.objects.all().order_by('name')
            self.fields['collone'].queryset = Collection.objects.all().order_by('name')
        else:
            type = prefix.split("-")[0]
            # self.fields['collist'].queryset = Collection.objects.filter(type=type).order_by('name')
            self.fields['collist'].queryset = Collection.get_scoped_queryset('', username, team_group)
            self.fields['collone'].queryset = Collection.objects.filter(type=type).order_by('name')

            # Note: the collection filters must use the SCOPE of the collection
            self.fields['collist_m'].queryset = Collection.get_scoped_queryset('manu', username, team_group)
            self.fields['collist_s'].queryset = Collection.get_scoped_queryset('sermo', username, team_group)
            self.fields['collist_sg'].queryset = Collection.get_scoped_queryset('gold', username, team_group)
            self.fields['collist_ssg'].queryset = Collection.get_scoped_queryset('super', username, team_group)
            

            # Set the initial type
            self.fields['type'].initial = type
            self.initial['type'] = type
        self.fields['ownlist'].queryset = Profile.objects.all()
        # Get the instance
        if 'instance' in kwargs:
            instance = kwargs['instance']


class SermonDescrSignatureForm(forms.ModelForm):
    """The link between SermonDescr and manually identified Signature"""

    class Meta:
        ATTRS_FOR_FORMS = {'class': 'form-control'};

        model = SermonSignature
        fields = ['sermon', 'gsig', 'code', 'editype']
        widgets={'editype':     forms.Select(attrs={'style': 'width: 100%;'}),
                 'code':        forms.TextInput(attrs={'class': 'typeahead searching signaturetype input-sm', 
                                                       'placeholder': 'Signature...', 'style': 'width: 100%;'})
                 }

    def __init__(self, *args, **kwargs):
        # Start by executing the standard handling
        super(SermonDescrSignatureForm, self).__init__(*args, **kwargs)
        # Initialize choices for editype
        init_choices(self, 'editype', EDI_TYPE, bUseAbbr=True)
        # Set some parameters to optional for best processing
        self.fields['code'].required = False
        self.fields['editype'].required = False
        self.fields['gsig'].required = False


class SermonDescrGoldForm(forms.ModelForm):
    #newlinktype = forms.Select(label=_("Linktype"), required=False, help_text="editable", 
    #           widget=forms.TextInput(attrs={'class': 'input-sm', 'placeholder': 'Type of link...',  'style': 'width: 100%;'}))
    newlinktype = forms.ChoiceField(label=_("Linktype"), required=False, help_text="editable", 
               widget=forms.Select(attrs={'class': 'input-sm', 'placeholder': 'Type of link...',  'style': 'width: 100%;'}))
    newgold  = forms.CharField(label=_("Sermon Gold"), required=False, help_text="editable", 
                widget=SermonGoldOneWidget(attrs={'data-placeholder': 'Select links...', 
                                                  'placeholder': 'Select a sermon gold...', 'style': 'width: 100%;', 'class': 'searching'}))

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
        init_choices(self, 'newlinktype', LINK_TYPE, bUseAbbr=True, use_helptext=False)
        # Set the keyword to optional for best processing
        self.fields['newlinktype'].required = False
        self.fields['newgold'].required = False
        self.fields['gold'].required = False
        self.fields['linktype'].required = False
        # Initialize queryset
        self.fields['newgold'].queryset = SermonGold.objects.order_by('author__name', 'siglist')
        # Get the instance
        if 'instance' in kwargs:
            instance = kwargs['instance']
            if instance != None:
                #  NOTE: the following has no effect because we use bound fields
                #       self.fields['linktype'].initial = instance.linktype
                #       self.fields['dst'].initial = instance.dst

                # Make sure we exclude the instance from the queryset
                self.fields['newgold'].queryset = self.fields['newgold'].queryset.exclude(id=instance.id).order_by('author__name', 'siglist')


class SermonDescrSuperForm(forms.ModelForm):
    newlinktype = forms.ChoiceField(label=_("Linktype"), required=False, #help_text="editable", 
               widget=forms.Select(attrs={'class': 'input-sm', 'placeholder': 'Type of link...',  'style': 'width: 100%;', 'tdstyle': 'width: 100px;'}))
    newsuper    = forms.CharField(label=_("Sermon Gold"), required=False, help_text="editable", 
                widget=SuperOneWidget(attrs={'data-placeholder': 'Select links...', 
                                                  'placeholder': 'Select a super sermon gold...', 'style': 'width: 100%;', 'class': 'searching'}))

    class Meta:
        ATTRS_FOR_FORMS = {'class': 'form-control'};

        model = SermonDescrEqual
        fields = ['sermon', 'linktype', 'super' ]
        widgets={'linktype':    forms.Select(attrs={'style': 'width: 100%;'})
                 }

    def __init__(self, *args, **kwargs):
        # Start by executing the standard handling
        super(SermonDescrSuperForm, self).__init__(*args, **kwargs)
        # Initialize choices for linktype
        init_choices(self, 'linktype', LINK_TYPE, bUseAbbr=True)
        init_choices(self, 'newlinktype', LINK_TYPE, bUseAbbr=True, use_helptext=False)
        # Set the keyword to optional for best processing
        self.fields['newlinktype'].required = False
        self.fields['newsuper'].required = False
        self.fields['super'].required = False
        self.fields['linktype'].required = False
        self.fields['newlinktype'].initial = "uns"
        # Initialize queryset
        self.fields['newsuper'].queryset = EqualGold.objects.filter(moved__isnull=True).order_by('code', 'author__name', 'id')
        # Get the instance
        if 'instance' in kwargs:
            instance = kwargs['instance']
            if instance != None:
                #  NOTE: the following has no effect because we use bound fields
                #       self.fields['linktype'].initial = instance.linktype
                #       self.fields['dst'].initial = instance.dst

                # Make sure we exclude the instance from the queryset
                self.fields['newsuper'].queryset = self.fields['newsuper'].queryset.exclude(id=instance.id).order_by('code', 'author__name', 'id')


class SermonDescrKeywordForm(forms.ModelForm):
    newkw  = forms.CharField(label=_("Keyword (new)"), required=False, help_text="editable", 
               widget=forms.TextInput(attrs={'class': 'input-sm', 'placeholder': 'Keyword...',  'style': 'width: 100%;'}))
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
        self.fields['newkw'].required = False
        self.fields['keyword'].required = False
        # Get the instance
        if 'instance' in kwargs:
            instance = kwargs['instance']
            # Check if the initial name should be added
            if instance.keyword != None:
                kw = instance.keyword.name
                self.fields['name'].initial = kw


class SermonGoldForm(PassimModelForm):
    stypelist   = ModelMultipleChoiceField(queryset=None, required=False, 
                widget=StypeWidget(attrs={'data-placeholder': 'Select multiple status types...', 'style': 'width: 100%;'}))
    authorname  = forms.CharField(label=_("Author"), required=False, 
                widget=forms.TextInput(attrs={'class': 'typeahead searching authors input-sm', 'placeholder': 'Author...', 'style': 'width: 100%;'}))
    signature   = forms.CharField(label=_("Signature"), required=False,
                widget=forms.TextInput(attrs={'class': 'typeahead searching signatures input-sm', 'placeholder': 'Signature/code (Gryson, Clavis)...', 'style': 'width: 100%;'}))
    signatureid = forms.CharField(label=_("Signature ID"), required=False)
    siglist     = ModelMultipleChoiceField(queryset=None, required=False, 
                widget=SignatureWidget(attrs={'data-placeholder': 'Select multiple signatures (Gryson, Clavis)...', 'style': 'width: 100%;', 'class': 'searching'}))
    codelist    = ModelMultipleChoiceField(queryset=None, required=False, 
                widget=CodeWidget(attrs={'data-placeholder': 'Select multiple Passim Codes...', 'style': 'width: 100%;', 'class': 'searching'}))
    codetype  = forms.ChoiceField(label=_("Passim code type"), required=False, 
                widget=forms.Select(attrs={'class': 'input-sm', 'placeholder': 'Type of Passim code...',  'style': 'width: 100%;', 'tdstyle': 'width: 150px;'}))
    codename  = forms.CharField(label=_("Passim code"), required=False, 
                widget=forms.TextInput(attrs={'class': 'searching input-sm', 'placeholder': 'Passim code...', 'style': 'width: 100%;'}))
    keyword    = forms.CharField(label=_("Keyword"), required=False,
                widget=forms.TextInput(attrs={'class': 'typeahead searching keywords input-sm', 'placeholder': 'Keyword(s)...', 'style': 'width: 100%;'}))
    kwlist     = ModelMultipleChoiceField(queryset=None, required=False, 
                widget=KeywordWidget(attrs={'data-placeholder': 'Select multiple keywords...', 'style': 'width: 100%;', 'class': 'searching'}))
    ukwlist     = ModelMultipleChoiceField(queryset=None, required=False, 
                widget=KeywordWidget(attrs={'data-placeholder': 'Select multiple user-keywords...', 'style': 'width: 100%;', 'class': 'searching'}))
    kwnew       = forms.CharField(label=_("New keyword"), required=False, 
                widget=forms.TextInput(attrs={'placeholder': 'Keyword...', 'style': 'width: 100%;'}))
    authorlist  = ModelMultipleChoiceField(queryset=None, required=False, 
                widget=AuthorWidget(attrs={'data-placeholder': 'Select multiple authors...', 'style': 'width: 100%;', 'class': 'searching'}))
    edilist     = ModelMultipleChoiceField(queryset=None, required=False, 
                widget=EdirefSgWidget(attrs={'data-placeholder': 'Select multiple editions...', 'style': 'width: 100%;', 'class': 'searching'}))
    litlist     = ModelMultipleChoiceField(queryset=None, required=False, 
                widget=LitrefSgWidget(attrs={'data-placeholder': 'Select multiple literature references...', 'style': 'width: 100%;', 'class': 'searching'}))
    ftxtlist    = ModelMultipleChoiceField(queryset=None, required=False,
                widget=FtextlinkWidget(attrs={'data-placeholder': 'Select links to full texts...', 'style': 'width: 100%;', 'class': 'searching'}))
    collist_m =  ModelMultipleChoiceField(queryset=None, required=False)
    collist_s =  ModelMultipleChoiceField(queryset=None, required=False)
    collist_sg =  ModelMultipleChoiceField(queryset=None, required=False)
    collist_ssg =  ModelMultipleChoiceField(queryset=None, required=False)
    collection_m = forms.CharField(label=_("Collection m"), required=False,
                widget=forms.TextInput(attrs={'class': 'typeahead searching collections input-sm', 'placeholder': 'Collection(s)...', 'style': 'width: 100%;'}))
    collection_s = forms.CharField(label=_("Collection s"), required=False,
                widget=forms.TextInput(attrs={'class': 'typeahead searching collections input-sm', 'placeholder': 'Collection(s)...', 'style': 'width: 100%;'}))
    collection_sg = forms.CharField(label=_("Collection sg"), required=False,
                widget=forms.TextInput(attrs={'class': 'typeahead searching collections input-sm', 'placeholder': 'Collection(s)...', 'style': 'width: 100%;'}))
    collection_ssg = forms.CharField(label=_("Collection ssg"), required=False,
                widget=forms.TextInput(attrs={'class': 'typeahead searching collections input-sm', 'placeholder': 'Collection(s)...', 'style': 'width: 100%;'}))
    collone     = ModelChoiceField(queryset=None, required=False, 
                widget=CollOneGoldWidget(attrs={'data-placeholder': 'Select one collection...', 'style': 'width: 100%;', 'class': 'searching'}))
    typeaheads = ["authors", "signatures", "keywords", "gldincipits", "gldexplicits"]

    class Meta:
        ATTRS_FOR_FORMS = {'class': 'form-control'};

        model = SermonGold
        fields = ['author', 'incipit', 'explicit', 'bibliography', 'stype', 'srchincipit', 'srchexplicit', 'equal' ]
        widgets={'author':      AuthorOneWidget(attrs={'data-placeholder': 'Select one author...', 'style': 'width: 100%;', 'class': 'searching'}),
                 'incipit':     forms.TextInput(attrs={'class': 'typeahead searching gldincipits input-sm', 'placeholder': 'Incipit...', 'style': 'width: 100%;'}),
                 'explicit':    forms.TextInput(attrs={'class': 'typeahead searching gldexplicits input-sm', 'placeholder': 'Explicit...', 'style': 'width: 100%;'}),
                 'bibliography':forms.Textarea(attrs={'rows': 2, 'cols': 40, 'style': 'height: 80px; width: 100%; font-family: monospace', 'class': 'searching'}),
                 'equal':       SuperOneWidget(attrs={'data-placeholder': 'Select one Super Sermon Gold...', 'style': 'width: 100%;', 'class': 'searching'}),
                 'stype':       forms.Select(attrs={'style': 'width: 100%;'})
                 }

    def __init__(self, *args, **kwargs):
        # Start by executing the standard handling
        super(SermonGoldForm, self).__init__(*args, **kwargs)
        oErr = ErrHandle()
        try:
            username = self.username        # kwargs.pop('username', "")
            team_group = self.team_group    # kwargs.pop('team_group', "")
            userplus = self.userplus
            profile = Profile.get_user_profile(username)
            # Some fields are not required
            self.fields['stype'].required = False
            self.fields['codename'].required = False
            self.fields['codetype'].required = False

            # Choice field initialization
            self.fields['codetype'].choices = CODE_TYPE

            # Determine the querysets
            self.fields['stypelist'].queryset = FieldChoice.objects.filter(field=STATUS_TYPE).order_by("english_name")
            self.fields['siglist'].queryset = Signature.objects.all().order_by('code')
            self.fields['codelist'].queryset = EqualGold.objects.filter(moved__isnull=True).order_by('code').distinct()
            self.fields['kwlist'].queryset = Keyword.get_scoped_queryset(username, team_group, userplus)
            self.fields['ukwlist'].queryset = Keyword.get_scoped_queryset(username, team_group, userplus)
            self.fields['authorlist'].queryset = Author.objects.all().order_by('name')
            self.fields['edilist'].queryset = EdirefSG.objects.all().order_by('reference__full', 'pages').distinct()
            self.fields['litlist'].queryset = LitrefSG.objects.all().order_by('reference__full', 'pages').distinct()
            self.fields['ftxtlist'].queryset = Ftextlink.objects.all().order_by('url')

            # Set the widgets correctly
            self.fields['collist_m'].widget = CollectionManuWidget( attrs={'username': username, 'team_group': team_group,
                        'data-placeholder': 'Select multiple manuscript collections...', 'style': 'width: 100%;', 'class': 'searching'})
            self.fields['collist_s'].widget = CollectionSermoWidget( attrs={'username': username, 'team_group': team_group,
                        'data-placeholder': 'Select multiple manuscript collections...', 'style': 'width: 100%;', 'class': 'searching'})
            self.fields['collist_sg'].widget = CollectionGoldWidget( attrs={'username': username, 'team_group': team_group,
                        'data-placeholder': 'Select multiple manuscript collections...', 'style': 'width: 100%;', 'class': 'searching'})
            self.fields['collist_ssg'].widget = CollectionSuperWidget( attrs={'username': username, 'team_group': team_group,
                        'data-placeholder': 'Select multiple manuscript collections...', 'style': 'width: 100%;', 'class': 'searching'})

            if user_is_in_team(username, team_group, userplus):
                self.fields['kwlist'].widget.is_team = True
                self.fields['ukwlist'].widget.is_team = True
            else:
                self.fields['kwlist'].widget.is_team = False
                self.fields['ukwlist'].widget.is_team = False

            # Note: the collection filters must use the SCOPE of the collection
            self.fields['collist_m'].queryset = Collection.get_scoped_queryset('manu', username, team_group)
            self.fields['collist_s'].queryset = Collection.get_scoped_queryset('sermo', username, team_group)
            self.fields['collist_sg'].queryset = Collection.get_scoped_queryset('gold', username, team_group)
            self.fields['collist_ssg'].queryset = Collection.get_scoped_queryset('super', username, team_group)

            # The CollOne information is needed for the basket (add basket to collection)
            prefix = "gold"
            self.fields['collone'].queryset = Collection.objects.filter(type=prefix).order_by('name')
        
            # Get the instance
            if 'instance' in kwargs:
                instance = kwargs['instance']
                # If there is an instance, then check the author specification
                sAuthor = "" if not instance.author else instance.author.name
                self.fields['authorname'].initial = sAuthor
                self.fields['authorname'].required = False
                # Set initial values for lists, where appropriate. NOTE: need to have the initial ID values
                self.fields['kwlist'].initial = [x.pk for x in instance.keywords.all().order_by('name')]
                self.fields['ukwlist'].initial = [x.keyword.pk for x in instance.gold_userkeywords.filter(profile=profile).order_by('keyword__name')]
                self.fields['siglist'].initial = [x.pk for x in instance.goldsignatures.all().order_by('-editype', 'code')]
                self.fields['edilist'].initial = [x.pk for x in instance.sermon_gold_editions.all().order_by('reference__full', 'pages')]
                self.fields['litlist'].initial = [x.pk for x in instance.sermon_gold_litrefs.all().order_by('reference__full', 'pages')]
                self.fields['collist_sg'].initial = [x.pk for x in instance.collections.all().order_by('name')]
                self.fields['ftxtlist'].initial = [x.pk for x in instance.goldftxtlinks.all().order_by('url')]
        except:
            msg = oErr.get_error_message()
            oErr.DoError("SermonGoldForm-init")
        return None

    def clean(self):
        cleaned_data = super(SermonGoldForm, self).clean()
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
    newgold = ModelChoiceField(queryset=None, required=False,
                widget=SermonGoldOneWidget(attrs={'data-placeholder': 'Select one sermon gold...', 'style': 'width: 100%;', 'class': 'searching'}))
    gold = forms.CharField(label=_("Destination gold sermon"), required=True)
    
    class Meta:
        ATTRS_FOR_FORMS = {'class': 'form-control'};

        model = EqualGold
        fields = [ ]

    def __init__(self, *args, **kwargs):
        # Start by executing the standard handling
        super(EqualGoldForm, self).__init__(*args, **kwargs)

        # Set the keyword to optional for best processing
        self.fields['newgold'].required = False
        self.fields['gold'].required = False

        # Initialize queryset
        self.fields['newgold'].queryset = SermonGold.objects.order_by('author__name', 'siglist')
    

class SuperToGoldForm(forms.ModelForm):
    newgold = ModelChoiceField(queryset=None, required=False,
                widget=SermonGoldOneWidget(attrs={'data-placeholder': 'Select one sermon gold...', 'style': 'width: 100%;', 'class': 'searching'}))
    gold = forms.CharField(label=_("Destination gold sermon"), required=True)
    
    class Meta:
        ATTRS_FOR_FORMS = {'class': 'form-control'};

        model = SermonDescr
        fields = [ ]

    def __init__(self, *args, **kwargs):
        # Start by executing the standard handling
        super(SuperToGoldForm, self).__init__(*args, **kwargs)

        # Set the keyword to optional for best processing
        self.fields['newgold'].required = False
        self.fields['gold'].required = False

        # Initialize queryset
        self.fields['newgold'].queryset = SermonGold.objects.order_by('author__name', 'siglist')
    

class SuperSermonGoldForm(PassimModelForm):
    stypelist   = ModelMultipleChoiceField(queryset=None, required=False, 
                widget=StypeWidget(attrs={'data-placeholder': 'Select multiple status types...', 'style': 'width: 100%;'}))
    authorname = forms.CharField(label=_("Author"), required=False, 
                widget=forms.TextInput(attrs={'class': 'typeahead searching authors input-sm', 'placeholder': 'Author...', 'style': 'width: 100%;'}))
    authorlist  = ModelMultipleChoiceField(queryset=None, required=False, 
                widget=AuthorWidget(attrs={'data-placeholder': 'Select multiple authors...', 'style': 'width: 100%;', 'class': 'searching'}))
    signature = forms.CharField(label=_("Signature"), required=False,
                widget=forms.TextInput(attrs={'class': 'typeahead searching signatures input-sm', 'placeholder': 'Signature/code (Gryson, Clavis)...', 'style': 'width: 100%;'}))
    signatureid = forms.CharField(label=_("Signature ID"), required=False)
    siglist     = ModelMultipleChoiceField(queryset=None, required=False, 
                widget=SignatureWidget(attrs={'data-placeholder': 'Select multiple signatures (Gryson, Clavis)...', 'style': 'width: 100%;', 'class': 'searching'}))
    goldlist    = ModelMultipleChoiceField(queryset=None, required=False, 
                widget=SermonGoldWidget(attrs={'data-placeholder': 'Select multiple Sermons Gold...', 
                                                'data-allow-clear': 'false', 'style': 'width: 100%;', 'class': 'searching'}))
    superlist   = ModelMultipleChoiceField(queryset=None, required=False, 
                widget=EqualGoldLinkAddOnlyWidget(attrs={'data-placeholder': 'Use the + sign to add links...', 
                                                         'data-allow-clear': 'false', 'style': 'width: 100%;', 'class': 'searching'}))
    passimlist  = ModelMultipleChoiceField(queryset=None, required=False, 
                    widget=EqualGoldMultiWidget(attrs={'data-placeholder': 'Select multiple passim codes...', 'style': 'width: 100%;', 
                                                       'class': 'searching'}))
    kwlist     = ModelMultipleChoiceField(queryset=None, required=False, 
                widget=KeywordWidget(attrs={'data-placeholder': 'Select multiple keywords...', 'style': 'width: 100%;', 'class': 'searching'}))
    ukwlist     = ModelMultipleChoiceField(queryset=None, required=False, 
                widget=KeywordWidget(attrs={'data-placeholder': 'Select multiple user-keywords...', 'style': 'width: 100%;', 'class': 'searching'}))

    collist_m   = ModelMultipleChoiceField(queryset=None, required=False)
    collist_s   = ModelMultipleChoiceField(queryset=None, required=False)
    collist_sg  = ModelMultipleChoiceField(queryset=None, required=False)
    collist_ssg = ModelMultipleChoiceField(queryset=None, required=False)
    collection_m = forms.CharField(label=_("Collection m"), required=False,
                widget=forms.TextInput(attrs={'class': 'typeahead searching collections input-sm', 'placeholder': 'Collection(s)...', 'style': 'width: 100%;'}))
    collection_s = forms.CharField(label=_("Collection s"), required=False,
                widget=forms.TextInput(attrs={'class': 'typeahead searching collections input-sm', 'placeholder': 'Collection(s)...', 'style': 'width: 100%;'}))
    collection_sg = forms.CharField(label=_("Collection sg"), required=False,
                widget=forms.TextInput(attrs={'class': 'typeahead searching collections input-sm', 'placeholder': 'Collection(s)...', 'style': 'width: 100%;'}))
    collection_ssg = forms.CharField(label=_("Collection ssg"), required=False,
                widget=forms.TextInput(attrs={'class': 'typeahead searching collections input-sm', 'placeholder': 'Collection(s)...', 'style': 'width: 100%;'}))
    collone     = ModelChoiceField(queryset=None, required=False, 
                widget=CollOneSuperWidget(attrs={'data-placeholder': 'Select one collection...', 'style': 'width: 100%;', 'class': 'searching'}))
    typeaheads = ["authors", "gldincipits", "gldexplicits", "signatures"]   # Add [signatures] because of select_gold

    class Meta:
        ATTRS_FOR_FORMS = {'class': 'form-control'};

        model = EqualGold
        fields = ['author', 'incipit', 'explicit', 'code', 'number', 'stype']
        widgets={'author':      AuthorOneWidget(attrs={'data-placeholder': 'Select one author...', 'style': 'width: 100%;', 'class': 'searching'}),
                 'code':        forms.TextInput(attrs={'class': 'searching', 'style': 'width: 100%;', 
                                                       'placeholder': 'Passim code. Use wildcards, e.g: *002.*, *003'}),
                 'number':      forms.TextInput(attrs={'class': 'searching', 'style': 'width: 100%;', 'data-placeholder': 'Author number'}),
                 'incipit':     forms.TextInput(attrs={'class': 'typeahead searching gldincipits input-sm', 'placeholder': 'Incipit...', 'style': 'width: 100%;'}),
                 'explicit':    forms.TextInput(attrs={'class': 'typeahead searching gldexplicits input-sm', 'placeholder': 'Explicit...', 'style': 'width: 100%;'}),
                 'stype':       forms.Select(attrs={'style': 'width: 100%;'})
                 }

    def __init__(self, *args, **kwargs):
        # Start by executing the standard handling
        super(SuperSermonGoldForm, self).__init__(*args, **kwargs)
        oErr = ErrHandle()
        try:
            username = self.username
            team_group = self.team_group
            profile = Profile.get_user_profile(username)
            # Some fields are not required
            self.fields['authorname'].required = False
            self.fields['stype'].required = False

            # Initialize querysets
            self.fields['stypelist'].queryset = FieldChoice.objects.filter(field=STATUS_TYPE).order_by("english_name")
            self.fields['authorlist'].queryset = Author.objects.all().order_by('name')
            self.fields['siglist'].queryset = Signature.objects.all().order_by('code')
            self.fields['goldlist'].queryset = SermonGold.objects.all().order_by('siglist')
            self.fields['superlist'].queryset = EqualGoldLink.objects.none()
            self.fields['passimlist'].queryset = EqualGold.objects.filter(code__isnull=False, moved__isnull=True).order_by('code')
            # self.fields['superlist'].queryset = EqualGold.objects.all().order_by('code', 'author__name', 'number')
            self.fields['kwlist'].queryset = Keyword.get_scoped_queryset(username, team_group)
            self.fields['ukwlist'].queryset = Keyword.get_scoped_queryset(username, team_group)

            # Set the widgets correctly
            self.fields['collist_m'].widget = CollectionManuWidget( attrs={'username': username, 'team_group': team_group, 'data-allow-clear': 'false',
                        'data-placeholder': 'Select multiple manuscript collections...', 'style': 'width: 100%;', 'class': 'searching'})
            self.fields['collist_s'].widget = CollectionSermoWidget( attrs={'username': username, 'team_group': team_group, 'data-allow-clear': 'false',
                        'data-placeholder': 'Select multiple manuscript collections...', 'style': 'width: 100%;', 'class': 'searching'})
            self.fields['collist_sg'].widget = CollectionGoldWidget( attrs={'username': username, 'team_group': team_group, 'data-allow-clear': 'false',
                        'data-placeholder': 'Select multiple manuscript collections...', 'style': 'width: 100%;', 'class': 'searching'})
            self.fields['collist_ssg'].widget = CollectionSuperWidget( attrs={'username': username, 'team_group': team_group, 'data-allow-clear': 'false',
                        'data-placeholder': 'Select multiple manuscript collections...', 'style': 'width: 100%;', 'class': 'searching'})

            if user_is_in_team(username, team_group):
                self.fields['kwlist'].widget.is_team = True
                self.fields['ukwlist'].widget.is_team = True
            else:
                self.fields['kwlist'].widget.is_team = False
                self.fields['ukwlist'].widget.is_team = False

            # Note: the collection filters must use the SCOPE of the collection
            self.fields['collist_m'].queryset = Collection.get_scoped_queryset('manu', username, team_group)
            self.fields['collist_s'].queryset = Collection.get_scoped_queryset('sermo', username, team_group)
            self.fields['collist_sg'].queryset = Collection.get_scoped_queryset('gold', username, team_group)
            self.fields['collist_ssg'].queryset = Collection.get_scoped_queryset('super', username, team_group)

            # The CollOne information is needed for the basket (add basket to collection)
            prefix = "super"
            self.fields['collone'].queryset = Collection.objects.filter(type=prefix).order_by('name')
        
           # Get the instance
            if 'instance' in kwargs:
                instance = kwargs['instance']
                # If there is an instance, then check the author specification
                sAuthor = "" if not instance.author else instance.author.name
                self.fields['authorname'].initial = sAuthor
                self.fields['collist_ssg'].initial = [x.pk for x in instance.collections.all().order_by('name')]
                self.fields['goldlist'].initial = [x.pk for x in instance.equal_goldsermons.all().order_by('siglist')]
                self.fields['kwlist'].initial = [x.pk for x in instance.keywords.all().order_by('name')]
                self.fields['ukwlist'].initial = [x.keyword.pk for x in instance.super_userkeywords.filter(profile=profile).order_by('keyword__name')]
                self.fields['superlist'].initial = [x.pk for x in instance.equalgold_src.all().order_by('dst__code', 'dst__author__name', 'dst__number')]
                self.fields['superlist'].queryset = EqualGoldLink.objects.filter(Q(id__in=self.fields['superlist'].initial))
                qs = instance.equalgold_dst.all()
        except:
            msg = oErr.get_error_message()
            oErr.DoError("SuperSermonGoldForm-init")
        # We are okay
        return None

    def clean_author(self):
        """Possibly determine the author if not known"""

        do_remove = False
        
        author = self.cleaned_data.get("author", None)
        if not author:
            authorname = self.cleaned_data.get("authorname", None)
            if authorname:
                # Figure out what the author is
                author = Author.objects.filter(name=authorname).first()
        if self.instance and self.instance.author and author:
            authornameLC = self.instance.author.name.lower()
            if self.instance.author.id != author.id:
                if do_remove:
                    # Need to remove all SSG that have me as 'moved
                    qs = EqualGold.objects.filter(moved=self.instance)
                    qs.delete()
                # Determine what to do in terms of 'moved'.
                if authornameLC != "undecided":
                    # Create a copy of the object I used to be
                    moved = EqualGold.create_moved(self.instance)
                    # NOTE: no need to move all Gold Sermons that were pointing to me -- they stay with the 'new' me
                else:
                    # We are moving from "undecided" to another name
                    # NOTE: not yet implemented. Is this needed??
                    pass
        return author


class EqualGoldLinkForm(forms.ModelForm):
    newlinktype = forms.ChoiceField(label=_("Linktype"), required=False, help_text="editable", 
                widget=forms.Select(attrs={'class': 'input-sm', 'placeholder': 'Type of link...',  'style': 'width: 100%;', 'tdstyle': 'width: 150px;'}))
    newsuper = ModelChoiceField(queryset=None, required=False, help_text="editable",
                widget=EqualGoldWidget(attrs={'data-placeholder': 'Select one super sermon gold...', 'style': 'width: 100%;', 'class': 'searching select2-ssg'}))
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
        init_choices(self, 'linktype', LINK_TYPE, bUseAbbr=True, exclude=['eqs'])
        init_choices(self, 'newlinktype', LINK_TYPE, bUseAbbr=True, exclude=['eqs'], use_helptext=False)
        # Make sure to set required and optional fields
        self.fields['linktype'].required = False
        self.fields['newlinktype'].required = False
        self.fields['dst'].required = False
        self.fields['newsuper'].required = False
        self.fields['newsuper'].queryset = EqualGold.objects.filter(moved__isnull=True).order_by('code')
        # self.fields['target_list'].queryset = EqualGold.objects.none()
        # Get the instance
        if 'instance' in kwargs:
            instance = kwargs['instance']
            if instance != None:
                #  NOTE: the following has no effect because we use bound fields
                #       self.fields['linktype'].initial = instance.linktype
                #       self.fields['dst'].initial = instance.dst

                self.fields['newsuper'].queryset = EqualGold.objects.filter(moved__isnull=True).exclude(id=instance.id).order_by('code')

        # REturn nothing
        return None

    def clean(self):
        # Run any super class cleaning
        cleaned_data = super(EqualGoldLinkForm, self).clean()

        # Get the source
        src = cleaned_data.get("src")
        if src != None:
            # Any new destination is added in target_list
            dst = cleaned_data.get("newsuper")
            if dst != None:
                # WE have a DST, now check how many links there are with this one
                existing = src.relations.filter(id=dst.id)
                if existing.count() > 0:
                    # This combination already exists
                    raise forms.ValidationError(
                            "This Super Sermon Gold is already linked"
                        )


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
        self.fields['gold'].required = False
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
    newcol = forms.CharField(label=_("Collection (new)"), required=False, help_text="editable", 
               widget=forms.TextInput(attrs={'class': 'input-sm', 'placeholder': 'Collection...',  'style': 'width: 100%;'}))
    # typeaheads = ["collections"]
    
    class Meta:
        ATTRS_FOR_FORMS = {'class': 'form-control'};

        model = CollectionSerm
        fields = ['sermon', 'collection']

    def __init__(self, *args, **kwargs):
        # Start by executing the standard handling
        super(SermonDescrCollectionForm, self).__init__(*args, **kwargs)
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

                
class SermonGoldLitrefForm(forms.ModelForm):
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
        # EK: Added for Sermon Gold new approach 
        self.fields['newpages'].required = False
        self.fields['oneref'].required = False
        self.fields['oneref'].queryset = Litref.objects.exclude(full="").order_by('full')
        # Get the instance
        if 'instance' in kwargs:
            instance = kwargs['instance']
            # Check if the initial reference should be added
            if instance.reference != None:
                self.fields['litref_ta'].initial = instance.reference.get_full()

    def clean(self):
        cleaned_data = super(SermonGoldLitrefForm, self).clean()
        litref = cleaned_data.get("litref")
        oneref = cleaned_data.get("oneref")
        reference = cleaned_data.get("reference")
        if reference == None and (litref == None or litref == "") and (oneref == None or oneref == ""):
            #litref_ta = cleaned_data.get("litref_ta")
            #obj = Litref.objects.filter(full=litref_ta).first()
            #if obj == None:
            raise forms.ValidationError("Cannot find the reference. Make sure to select it. If it is not available, add it in Zotero and import it in Passim")


class ManuscriptProvForm(forms.ModelForm):
    name = forms.CharField(label=_("Name"), required=False, help_text="editable",
                           widget=forms.TextInput(attrs={'placeholder': 'Name...',  'style': 'width: 100%;'}))
    note = forms.CharField(label=_("Note"), required=False, help_text="editable",
                           widget = forms.Textarea(attrs={'placeholder': 'Note (optional)...',  'rows': 1, 'cols': 40, 'style': 'height: 40px; width: 100%;'}))
    location = forms.ModelChoiceField(queryset=None, required=False, help_text="editable",
                           widget = LocationOneWidget(attrs={'data-placeholder': 'Select a location...', 'style': 'width: 100%;', 'class': 'searching'}))
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
        self.fields['location'].queryset = Location.objects.all().order_by('name')
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
        # EK: Added for Sermon Gold new approach 
        self.fields['newpages'].required = False
        self.fields['oneref'].required = False
        self.fields['oneref'].queryset = Litref.objects.exclude(full="").order_by('full')
        # Get the instance
        if 'instance' in kwargs:
            instance = kwargs['instance']
            # Check if the initial reference should be added
            if instance.reference != None:
                self.fields['litref_ta'].initial = instance.reference.get_full()

    def clean(self):
        cleaned_data = super(ManuscriptLitrefForm, self).clean()
        litref = cleaned_data.get("litref")
        oneref = cleaned_data.get("oneref")
        reference = cleaned_data.get("reference")
        if reference == None and (litref == None or litref == "") and (oneref == None or oneref == ""):
            #litref_ta = cleaned_data.get("litref_ta")
            #obj = Litref.objects.filter(full=litref_ta).first()
            #if obj == None:
            raise forms.ValidationError("Cannot find the reference. Make sure to select it. If it is not available, add it in Zotero and import it in Passim")


class ManuscriptExtForm(forms.ModelForm):
    newurl = forms.CharField(label=_("URL (new)"), required=False, help_text="editable", 
               widget=forms.TextInput(attrs={'class': 'input-sm', 'placeholder': 'URL...',  'style': 'width: 100%;'}))

    class Meta:
        ATTRS_FOR_FORMS = {'class': 'form-control'};

        model = ManuscriptExt
        fields = ['url']
        widgets={'url':     forms.TextInput(attrs={'placeholder': 'External link (URL)...', 'style': 'width: 100%;'})
                 }

    def __init__(self, *args, **kwargs):
        # Start by executing the standard handling
        super(ManuscriptExtForm, self).__init__(*args, **kwargs)

        self.fields['url'].required = False
        self.fields['newurl'].required = False
        # Get the instance
        if 'instance' in kwargs:
            instance = kwargs['instance']


class ManuscriptKeywordForm(forms.ModelForm):
    name = forms.CharField(label=_("Keyword"), required=False, 
                           widget=forms.TextInput(attrs={'class': 'typeahead searching keywords input-sm', 'placeholder': 'Keyword...',  'style': 'width: 100%;'}))
    newkw = forms.CharField(label=_("Keyword (new)"), required=False, help_text="editable", 
               widget=forms.TextInput(attrs={'class': 'input-sm', 'placeholder': 'Keyword...',  'style': 'width: 100%;'}))
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
        self.fields['name'].required = False
        self.fields['newkw'].required = False
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
    newurl  = forms.CharField(label=_("Full text link"), required=False, help_text="editable", 
               widget=forms.TextInput(attrs={'class': 'input-sm', 'placeholder': 'URL to full text...',  'style': 'width: 100%;'}))

    class Meta:
        ATTRS_FOR_FORMS = {'class': 'form-control'};

        model = Ftextlink
        fields = ['url', 'gold']
        widgets={'url':     forms.URLInput(attrs={'placeholder': 'Full text URLs...', 'style': 'width: 100%;'})
                 }

    def __init__(self, *args, **kwargs):
        # Start by executing the standard handling
        super(SermonGoldFtextlinkForm, self).__init__(*args, **kwargs)
        # Set the keyword to optional for best processing
        self.fields['url'].required = False
        self.fields['newurl'].required = False
        self.fields['gold'].required = False


class ManuscriptForm(PassimModelForm):
    country_ta  = forms.CharField(label=_("Country"), required=False, 
                widget=forms.TextInput(attrs={'class': 'typeahead searching countries input-sm', 'placeholder': 'Country...', 'style': 'width: 100%;'}))
    city_ta     = forms.CharField(label=_("City"), required=False, 
                widget=forms.TextInput(attrs={'class': 'typeahead searching cities input-sm', 'placeholder': 'City...',  'style': 'width: 100%;'}))
    libname_ta  = forms.CharField(label=_("Library"), required=False, 
                widget=forms.TextInput(attrs={'class': 'typeahead searching libraries input-sm', 'placeholder': 'Name of library...',  'style': 'width: 100%;'}))
    origname_ta = forms.CharField(label=_("Origin"), required=False, 
                widget=forms.TextInput(attrs={'class': 'typeahead searching origins input-sm', 'placeholder': 'Origin...',  'style': 'width: 100%;'}))
    origone     = ModelChoiceField(queryset=None, required=False,
                widget=OriginOneWidget(attrs={'data-placeholder': 'Select an origin...', 'style': 'width: 100%;', 'class': 'searching'}))
    collection  = forms.CharField(label=_("Collection"), required=False,
                widget=forms.TextInput(attrs={'class': 'searching input-sm', 'placeholder': 'Collection(s)...', 'style': 'width: 100%;'}))
    collist     = ModelMultipleChoiceField(queryset=None, required=False, 
                widget=CollectionManuWidget(attrs={'data-placeholder': 'Select multiple collections...', 'style': 'width: 100%;', 'class': 'searching'}))
    kwlist      = ModelMultipleChoiceField(queryset=None, required=False, 
                widget=KeywordWidget(attrs={'data-placeholder': 'Select multiple keywords...', 'style': 'width: 100%;', 'class': 'searching'}))
    ukwlist      = ModelMultipleChoiceField(queryset=None, required=False, 
                widget=KeywordWidget(attrs={'data-placeholder': 'Select multiple user-keywords...', 'style': 'width: 100%;', 'class': 'searching'}))
    litlist     = ModelMultipleChoiceField(queryset=None, required=False, 
                widget=LitrefManWidget(attrs={'data-placeholder': 'Select multiple literature references...', 'style': 'width: 100%;', 'class': 'searching'}))
    provlist    = ModelMultipleChoiceField(queryset=None, required=False, 
                widget=ProvenanceWidget(attrs={'data-placeholder': 'Select multiple provenances...', 'style': 'width: 100%;', 'class': 'searching'}))
    extlist     = ModelMultipleChoiceField(queryset=None, required=False, 
                widget=ManuscriptExtWidget(attrs={'data-placeholder': 'Select multiple external links...', 'style': 'width: 100%;', 'class': 'searching'}))
    datelist    = ModelMultipleChoiceField(queryset=None, required=False, 
                widget=DaterangeWidget(attrs={'data-placeholder': 'Use the "+" sign to add dates...', 'style': 'width: 100%;', 'class': 'searching'}))
    typeaheads = ["countries", "cities", "libraries", "origins", "manuidnos"]
    action_log = ['name', 'library', 'lcity', 'lcountry', 'idno', 
                  'origin', 'url', 'support', 'extent', 'format', 'stype', 'project',
                  'ukwlist', 'kwlist', 'listlist', 'collist', 'provlist', 'extlist', 'datelist']
    exclude = ['country_ta', 'city_ta', 'libname_ta', 'origname_ta']

    class Meta:
        ATTRS_FOR_FORMS = {'class': 'form-control'};

        model = Manuscript
        fields = ['name', 'library', 'lcity', 'lcountry', 'idno', # 'yearstart', 'yearfinish', 
                  'origin', 'url', 'support', 'extent', 'format', 'stype', 'project']
        widgets={'library':     LibraryOneWidget(attrs={'data-placeholder': 'Select a library...', 'style': 'width: 100%;', 'class': 'searching'}),
                 'lcity':       CityOneWidget(attrs={'data-placeholder': 'Select a city...', 'style': 'width: 100%;', 'class': 'searching'}),
                 'lcountry':    CountryOneWidget(attrs={'data-placeholder': 'Select a country...', 'style': 'width: 100%;', 'class': 'searching'}),
                 'name':        forms.TextInput(attrs={'style': 'width: 100%;'}),
                 #'yearstart':   forms.TextInput(attrs={'style': 'width: 40%;'}),
                 #'yearfinish':  forms.TextInput(attrs={'style': 'width: 40%;'}),
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
        oErr = ErrHandle()
        try:
            username = self.username
            team_group = self.team_group
            profile = Profile.get_user_profile(username)
            # Some fields are not required
            self.fields['stype'].required = False
            #self.fields['yearstart'].required = False
            #self.fields['yearfinish'].required = False
            self.fields['name'].required = False
            self.fields['lcity'].required = False
            self.fields['lcountry'].required = False
            self.fields['litlist'].queryset = LitrefMan.objects.all().order_by('reference__full', 'pages').distinct()
            self.fields['kwlist'].queryset = Keyword.get_scoped_queryset(username, team_group)
            self.fields['ukwlist'].queryset = Keyword.get_scoped_queryset(username, team_group)

            if user_is_in_team(username, team_group):
                self.fields['kwlist'].widget.is_team = True
                self.fields['ukwlist'].widget.is_team = True
            else:
                self.fields['kwlist'].widget.is_team = False
                self.fields['ukwlist'].widget.is_team = False

            # Note: the collection filters must use the SCOPE of the collection
            self.fields['collist'].queryset = Collection.get_scoped_queryset('manu', username, team_group)

            self.fields['origone'].queryset = Origin.objects.all().order_by('name')

            # Some lists need to be initialized to NONE:
            self.fields['provlist'].queryset = Provenance.objects.none()
            self.fields['extlist'].queryset = ManuscriptExt.objects.none()
            self.fields['datelist'].queryset = Daterange.objects.none()

            self.fields['provlist'].widget.addonly = True
            self.fields['extlist'].widget.addonly = True
            self.fields['datelist'].widget.addonly = True
        
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

                    # New method
                    # self.fields['library'].initial = 
                # Look after origin
                origin = instance.origin
                self.fields['origname_ta'].initial = "" if origin == None else origin.name
                self.fields['origone'].initial = None if origin == None else origin.id
                self.fields['collist'].initial = [x.pk for x in instance.collections.all().order_by('name')]
                self.fields['litlist'].initial = [x.pk for x in instance.manuscript_litrefs.all().order_by('reference__full', 'pages')]
                self.fields['kwlist'].initial = [x.pk for x in instance.keywords.all().order_by('name')]
                self.fields['ukwlist'].initial = [x.keyword.pk for x in instance.manu_userkeywords.filter(profile=profile).order_by('keyword__name')]

                self.fields['provlist'].initial = [x.pk for x in instance.provenances.all()]
                self.fields['extlist'].initial = [x.pk for x in instance.manuscriptexternals.all()]
                self.fields['datelist'].initial = [x.pk for x in instance.manuscript_dateranges.all()]

                # The manuscriptext and the provenance should *just* contain what they have (no extension here)
                self.fields['provlist'].queryset = Provenance.objects.filter(id__in=self.fields['provlist'].initial)
                self.fields['extlist'].queryset = ManuscriptExt.objects.filter(id__in=self.fields['extlist'].initial)
                self.fields['datelist'].queryset = Daterange.objects.filter(id__in=self.fields['datelist'].initial)

        except:
            msg = oErr.get_error_message()
            oErr.DoError("manuscriptForm")
        return None


class TemplateForm(PassimModelForm):
    profileid = forms.CharField(required=False)

    class Meta:
        ATTRS_FOR_FORMS = {'class': 'form-control'};

        model = Template
        fields = ['name', 'description']
        widgets={'name':        forms.TextInput(attrs={'style': 'width: 100%;'}),
                 'description': forms.Textarea(attrs={'rows': 1, 'cols': 40, 'style': 'height: 40px; width: 100%;'}),
                 }

    def __init__(self, *args, **kwargs):
        # Start by executing the standard handling
        super(TemplateForm, self).__init__(*args, **kwargs)
        oErr = ErrHandle()
        try:
            username = self.username
            team_group = self.team_group
            profile = Profile.get_user_profile(username)
            # Make sure the profile is set correctly
            self.fields['profileid'].initial = profile.id

            # Some fields are not required
            self.fields['name'].required = False
            self.fields['description'].required = False

            # Get the instance
            if 'instance' in kwargs:
                instance = kwargs['instance']
                # Adapt the profile if this is needed
                self.fields['profileid'].initial = instance.profile.id
        except:
            msg = oErr.get_error_message()
            oErr.DoError("TemplateForm")
        return None


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
    newstart    = forms.CharField(required=False, help_text='editable', 
                widget=forms.TextInput(attrs={'class': 'input-sm', 'placeholder': 'Start...',  'style': 'width: 100%;'}))
    newfinish   = forms.CharField(required=False, help_text='editable', 
                widget=forms.TextInput(attrs={'class': 'input-sm', 'placeholder': 'Finish...',  'style': 'width: 100%;'}))
    oneref      = forms.ModelChoiceField(queryset=None, required=False, help_text="editable", 
                widget=LitrefWidget(attrs={'data-placeholder': 'Select one reference...', 'style': 'width: 100%;', 'class': 'searching'}))
    newpages    = forms.CharField(label=_("Page range"), required=False, help_text="editable", 
                widget=forms.TextInput(attrs={'class': 'input-sm', 'placeholder': 'Page range...',  'style': 'width: 100%;'}))
    action_log = ['yearstart', 'yearfinish', 'pages', 'reference']
    exclude = []    # ['newstart', 'newfinish', 'oneref', 'newpages']

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
        self.fields['yearstart'].required = False
        self.fields['yearfinish'].required = False
        self.fields['reference'].required = False
        self.fields['pages'].required = False
        self.fields['newpages'].required = False
        self.fields['oneref'].required = False
        self.fields['oneref'].queryset = Litref.objects.exclude(full="").order_by('full')
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
