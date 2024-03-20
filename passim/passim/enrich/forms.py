"""
Definition of forms.
"""

from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.utils.translation import gettext_lazy as _
from django.forms import ModelMultipleChoiceField, ModelChoiceField
from django.forms.widgets import *
from django.db.models import F

from passim.enrich.models import *
from passim.basic.forms import BasicModelForm, BasicSimpleForm


class SpeakerForm(BasicModelForm):

    class Meta:
        model = Speaker
        fields = ['name']
        widgets = {'name':  forms.TextInput(attrs={'style': 'width: 100%;', 
                                                   'placeholder': 'Name or number (code) of speaker used in filename...'})}


class SentenceForm(BasicModelForm):

    class Meta:
        model = Sentence
        fields = ['name']
        widgets = {'name':  forms.TextInput(attrs={'style': 'width: 100%;', 
                                                   'placeholder': 'Name or code of sentence used in filename...'})}


class TestunitForm(BasicModelForm):

    class Meta:
        model = Testunit
        fields = ['speaker', 'sentence', 'ntype']


class TestsetForm(BasicModelForm):

    class Meta:
        model = Testset
        fields = ['round', 'number']

