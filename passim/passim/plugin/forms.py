"""
Definition of forms.
"""

from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.utils.translation import gettext_lazy as _
from django.forms import ModelMultipleChoiceField, ModelChoiceField
from django.forms.widgets import *
from django_select2.forms import Select2MultipleWidget, ModelSelect2MultipleWidget, ModelSelect2Widget

# From my own application
from passim.utils import ErrHandle
from passim.basic.forms import BasicModelForm, BasicSimpleForm
from passim.seeker.models import Signature, Manuscript
from passim.plugin.models import Highlight, SermonsDistance, SeriesDistance, BoardDataset, Dimension, \
    ClMethod, Highlight


# =============== WIDGETS ===============================================

class BoardDatasetOneWidget(ModelSelect2Widget):
    model = BoardDataset
    search_fields = [ 'name__icontains' ]

    def label_from_instance(self, obj):
        return obj.name

    def get_queryset(self):
        qs = BoardDataset.objects.all().order_by('name')
        return qs


class SermonsDistanceOneWidget(ModelSelect2Widget):
    model = SermonsDistance
    search_fields = [ 'name__icontains' ]

    def label_from_instance(self, obj):
        return obj.name

    def get_queryset(self):
        qs = SermonsDistance.objects.all().order_by('name')
        return qs


class SeriesDistanceOneWidget(ModelSelect2Widget):
    model = SeriesDistance
    search_fields = [ 'name__icontains' ]

    def label_from_instance(self, obj):
        return obj.name

    def get_queryset(self):
        qs = SeriesDistance.objects.all().order_by('name')
        return qs


class DimensionOneWidget(ModelSelect2Widget):
    model = Dimension
    search_fields = [ 'name__icontains' ]

    def label_from_instance(self, obj):
        return obj.name

    def get_queryset(self):
        qs = Dimension.objects.all().order_by('name')
        return qs


class ClMethodOneWidget(ModelSelect2Widget):
    model = ClMethod
    search_fields = [ 'name__icontains' ]

    def label_from_instance(self, obj):
        return obj.name

    def get_queryset(self):
        qs = ClMethod.objects.all().order_by('name')
        return qs


class HighlightWidget(ModelSelect2MultipleWidget):
    model = Highlight
    search_fields = [ 'name__icontains' ]

    def label_from_instance(self, obj):
        return obj.name

    def get_queryset(self):
        qs = Highlight.objects.all().order_by('name')
        return qs


class SignatureWidget(ModelSelect2MultipleWidget):
    # NOTE: only use the [Signature] table - don't use [SermonSignature]
    model = Signature
    search_fields = [ 'code__icontains' ]

    def label_from_instance(self, obj):
        return obj.code

    def get_queryset(self):
        return Signature.objects.all().order_by('code').distinct()


class ManuidOneWidget(ModelSelect2Widget):
    model = Manuscript
    search_fields = [ 'idno__icontains', 'lcity__name__icontains', 'library__name__icontains']

    def label_from_instance(self, obj):
        return obj.get_full_name()

    def get_queryset(self):
        qs = self.queryset
        if qs == None:
            qs = Manuscript.objects.filter(mtype='man').order_by('lcity__name', 'library__name', 'idno').distinct()
        return qs





# ================ FORMS ================================================

class BoardForm(BasicSimpleForm):
    """Form to facilitate selecting a savegroup"""

    dataset = ModelChoiceField(label="Dataset", queryset=None, required=False,
            widget=BoardDatasetOneWidget(attrs={'data-minimum-input-length': 0, 'data-placeholder': 'Select a dataset...', 'style': 'width: 100%;'}))
    sermdist = ModelChoiceField(label="Sermons distance", queryset=None, required=False,
            widget=SermonsDistanceOneWidget(attrs={'data-minimum-input-length': 0, 'data-placeholder': 'Select a sermons distance...', 'style': 'width: 100%;'}))
    serdist = ModelChoiceField(label="Series distance", queryset=None, required=False,
            widget=SeriesDistanceOneWidget(attrs={'data-minimum-input-length': 0, 'data-placeholder': 'Select a series distance...', 'style': 'width: 100%;'}))
    sermons = ModelMultipleChoiceField(label="Sermons", queryset=None, required=False,
            widget=SignatureWidget(attrs={'data-minimum-input-length': 0, 'data-placeholder': 'Select multiple sermons (Gryson, Clavis)...', 'style': 'width: 100%;', 'class': 'searching'}))
    anchorman = ModelChoiceField(label="Anchor manuscript", queryset=None, required=False,
                 widget=ManuidOneWidget(attrs={'data-minimum-input-length': 0, 'data-placeholder': 'Select one manuscript...', 'style': 'width: 100%;'}))
    umap_dim = ModelChoiceField(label="UMAP dimension", queryset=None, required=False,
            widget=DimensionOneWidget(attrs={'data-minimum-input-length': 0, 'data-placeholder': 'Select a dimension...', 'style': 'width: 100%;'}))
    cl_method = ModelChoiceField(label="Clustering method", queryset=None, required=False,
            widget=ClMethodOneWidget(attrs={'data-minimum-input-length': 0, 'data-placeholder': 'Select a clustering method...', 'style': 'width: 100%;'}))
    highlights = ModelMultipleChoiceField(label="Highlights", queryset=None, required=False,
            widget=HighlightWidget(attrs={'data-minimum-input-length': 0, 'data-placeholder': 'Select multiple highlights...', 'style': 'width: 100%;', 'class': 'searching'}))


    def __init__(self, *args, **kwargs):
        # Start by executing the standard handling
        super(BoardForm, self).__init__(*args, **kwargs)

        oErr = ErrHandle()
        try:
            # Fill in the querysets
            self.fields['dataset'].queryset = BoardDataset.objects.all().order_by('name')
            self.fields['sermdist'].queryset = SermonsDistance.objects.all().order_by('name')
            self.fields['serdist'].queryset = SeriesDistance.objects.all().order_by('name')
            self.fields['umap_dim'].queryset = Dimension.objects.all().order_by('name')
            self.fields['sermons'].queryset = Signature.objects.all().order_by('code')
            self.fields['anchorman'].queryset = Manuscript.objects.filter(mtype='man').order_by('idno')
            self.fields['cl_method'].queryset = ClMethod.objects.all().order_by('name')
            self.fields['highlights'].queryset = Highlight.objects.all().order_by('name')

            # Set initial values
            if BoardDataset.objects.all().count() > 0:
                self.fields['dataset'].initial = BoardDataset.objects.first()
            # Initial sermons distance: uniform
            sermdist = SermonsDistance.objects.filter(name__iexact="uniform").first()
            if not sermdist is None:
                self.fields['sermdist'].initial = sermdist
            # Initial series distance: birnbaum
            serdist = SeriesDistance.objects.filter(name__iexact="birnbaum").first()
            if not serdist is None:
                self.fields['serdist'].initial = serdist
            # Initial target dimension
            dimension = Dimension.objects.filter(name__iexact="2d").first()
            if not dimension is None:
                self.fields['umap_dim'].initial = dimension

            # Initial clustering method
            cl_method = ClMethod.objects.filter(abbr="ward").first()
            if not cl_method is None:
                self.fields['cl_method'].initial = cl_method

        except:
            msg = oErr.get_error_message()
            oErr.DoError("BoardForm")


