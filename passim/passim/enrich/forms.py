"""
Definition of forms.
"""

from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.utils.translation import ugettext_lazy as _
from django.forms import ModelMultipleChoiceField, ModelChoiceField
from django.forms.widgets import *
from django.db.models import F
from passim.enrich.models import *


class TestunitForm(forms.ModelForm):

    class Meta:
        model = Testunit
        fields = ['speaker', 'sentence', 'ntype']


class TestsetForm(forms.ModelForm):

    class Meta:
        model = Testset
        fields = ['round', 'number']

