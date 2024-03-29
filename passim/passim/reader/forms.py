"""
Definition of forms.
"""

from django import forms
from django.forms.widgets import *
from django_select2.forms import Select2MultipleWidget, ModelSelect2MultipleWidget, ModelSelect2TagWidget, ModelSelect2Widget, HeavySelect2Widget

from passim.basic.forms import BasicModelForm, BasicSimpleForm


class UploadFileForm(BasicSimpleForm):
    """This is for uploading just one file"""

    file_source = forms.FileField(label="Specify which file should be loaded")

    def is_valid(self):
        # Do default is valid
        valid = super(UploadFileForm, self).is_valid()

        # If it's False, return
        if valid: 

            # Otherwise: try myself.
            cd = self.cleaned_data

            if not cd is None:
                for k,v in cd.items():
                    if isinstance(v,str) and "<script" in v:
                        # provide an appropriate warning message
                        valid = False
                        self.errors[k] = "Don't include JS in a text field"
                        # break
        # Return what we have
        return valid


class UploadFilesForm(BasicSimpleForm):
    """This is for uploading multiple files"""

    files_field = forms.FileField(label="Specify which file(s) should be loaded",
                                  widget=forms.ClearableFileInput(attrs={'multiple': True}))

    def is_valid(self):
        # Do default is valid
        valid = super(UploadFilesForm, self).is_valid()

        # If it's False, return
        if valid: 

            # Otherwise: try myself.
            cd = self.cleaned_data

            if not cd is None:
                for k,v in cd.items():
                    if isinstance(v,str) and "<script" in v:
                        # provide an appropriate warning message
                        valid = False
                        self.errors[k] = "Don't include JS in a text field"
                        # break
        # Return what we have
        return valid
