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
from passim.basic.forms import BasicModelForm, BasicSimpleForm
from passim.stemma.models import *
from passim.seeker.models import Profile


# =============== WIDGETS ===============================================

class EqualGoldWidget(ModelSelect2Widget):
    model = EqualGold
    search_fields = [ 'code__icontains', 'author__name__icontains', 'srchincipit__icontains', 'srchexplicit__icontains', 'equal_goldsermons__siglist__icontains' ]
    addonly = False
    order = [F('code').asc(nulls_last=True), 'firstsig']
    exclude = None

    def label_from_instance(self, obj):
        # Provide a label as in SuperOneWidget
        sLabel = obj.get_label(do_incexpl = True)

        # Determine here what to return...
        return sLabel

    def get_queryset(self):
        if self.addonly:
            qs = EqualGold.objects.none()
        elif self.exclude == None:
            qs = EqualGold.objects.filter(moved__isnull=True, atype='acc').order_by(*self.order).distinct()
        else:
            qs = EqualGold.objects.filter(moved__isnull=True, atype='acc').exclude(id=self.exclude).order_by(*self.order).distinct()
        return qs

    def filter_queryset(self, term, queryset = None, **dependent_fields):
        term_for_now = ""
        qs = super(EqualGoldWidget, self).filter_queryset(term_for_now, queryset, **dependent_fields)
        
        # Check if this contains a string literal
        bAdapted = False
        if term.count('"') >= 2:
            # Need to look for a literal string
            arTerm = term.split('"')
            if len(arTerm) >= 3:
                # Behaviour from issue #432

                term_ordered = []

                # Take the literal term
                term_literal = arTerm[1]
                term_ordered.append(term_literal)

                # Also add the terms from [literal], but chunked (if they contain spaces)
                if term_literal.count(" ") > 1:
                    term_parts = term_literal.split()

                    # Take the last two and the before part together
                    term_ordered.append(" ".join(term_parts[-2:]))
                    if len(term_parts) > 3:
                        term_ordered.append(" ".join(term_parts[0:-2]))

                    # Take the first two and the remainder together
                    term_ordered.append(" ".join(term_parts[0:2]))
                    if len(term_parts) > 3:
                        term_ordered.append(" ".join(term_parts[2:]))

                # Take the part before
                term_before = arTerm[0].strip()
                term_ordered.append(term_before)

                # Take all the following terms together, joined by "
                term_after = '"'.join(arTerm[2:])
                term_ordered.append(term_after)

                # Build the combined condition
                if not term_ordered is None:
                    # Build up the cases last-to-first
                    case_list = []
                    counter = len(term_ordered)
                    for term in  term_ordered:
                        if term != "":
                            condition = Q(code__icontains=term) | Q(author__name__icontains=term) | \
                                Q(srchincipit__icontains=term) | Q(srchexplicit__icontains=term) | \
                                Q(equal_goldsermons__siglist__icontains=term)
                            case_list.append(When(condition, then=Value(counter)))
                            counter -= 1

                    qs = qs.annotate(
                        term_string_order=Case(
                            # When(condition_literal, then=Value(1)),
                            *case_list,
                            default=Value(0),
                            output_field=IntegerField()
                        ),
                    )

                    # Filter intelligently
                    qs = qs.filter(term_string_order__gte=1)
 
                    qs = qs.order_by("-term_string_order", "code", "id")
                    bAdapted = True

        if not bAdapted:
            qs = order_search(qs, term)

        # Return result
        return qs


class ProfileWidget(ModelSelect2MultipleWidget):
    model = Profile
    search_fields = [ 'user__username__icontains' ]

    def label_from_instance(self, obj):
        return obj.user.username

    def get_queryset(self):
        return Profile.objects.all().order_by('user__username').distinct()


class StemmaSetOneWidget(ModelSelect2Widget):
    model = StemmaSet
    search_fields = [ 'name__icontains' ]
    type = None
    qs = None

    def label_from_instance(self, obj):
        return obj.name

    def get_queryset(self):
        if self.qs is None:
            profile = self.attrs.pop('profile', '')
            qs = StemmaSet.objects.filter(profile=profile)
            self.qs = qs
        else:
            qs = self.qs
        return qs


# ================ FORMS ================================================

class StemmaSetForm(BasicModelForm):
    profileid = forms.CharField(required=False)
    ownlist  = ModelMultipleChoiceField(queryset=None, required=False, 
                widget=ProfileWidget(attrs={'data-placeholder': 'Select multiple profiles...', 'style': 'width: 100%;', 'class': 'searching'}))

    class Meta:
        model = StemmaSet
        fields = ['name', 'notes', 'scope']
        widgets={'name':    forms.TextInput(attrs={'style': 'width: 100%;', 'placeholder': 'The name of this stemma research set...'}),
                 'notes':   forms.Textarea(attrs={'rows': 1, 'cols': 40, 'style': 'height: 40px; width: 100%;',
                                                       'placeholder': 'Optionally add your own notes...'}),
                 'scope':       forms.Select(attrs={'style': 'width: 100%;'})
                 }

    def __init__(self, *args, **kwargs):
        # Obligatory for this type of form!!!
        self.username = kwargs.pop('username', "")
        self.team_group = kwargs.pop('team_group', "")
        self.userplus = kwargs.pop('userplus', "")
        # Start by executing the standard handling
        super(StemmaSetForm, self).__init__(*args, **kwargs)

        oErr = ErrHandle()
        try:
            username = self.username
            profile = Profile.get_user_profile(username)
            team_group = self.team_group

            # Some fields are not required
            self.fields['name'].required = False
            self.fields['notes'].required = False
            self.fields['scope'].required = False

            # Make sure the profile is set correctly
            self.fields['profileid'].initial = profile.id

            # Set queryset(s) - for details view
            self.fields['ownlist'].queryset = Profile.objects.all()
            
            # Get the instance
            if 'instance' in kwargs:
                instance = kwargs['instance']
                # Adapt the profile if this is needed
                self.fields['profileid'].initial = instance.profile.id

        except:
            msg = oErr.get_error_message()
            oErr.DoError("StemmaSetForm")
        return None


#class StemmaItemForm(BasicModelForm):
#    """Used for listview and details view of StemmaItem"""


#    class Meta:
#        model = StemmaItem
#        fields = ['name', 'notes']
#        widgets={'name':    forms.TextInput(attrs={'style': 'width: 100%;', 'placeholder': 'The name of this DCT...'}),
#                 'notes':   forms.Textarea(attrs={'rows': 1, 'cols': 40, 'style': 'height: 40px; width: 100%;',
#                                                       'placeholder': 'Optionally add your own notes...'})
#                 }

#    def __init__(self, *args, **kwargs):
#        # Obligatory for this type of form!!!
#        self.username = kwargs.pop('username', "")
#        self.team_group = kwargs.pop('team_group', "")
#        self.userplus = kwargs.pop('userplus', "")
#        # Start by executing the standard handling
#        super(StemmaItemForm, self).__init__(*args, **kwargs)

#        oErr = ErrHandle()
#        try:
#            # Some fields are not required
#            self.fields['name'].required = False
#            self.fields['notes'].required = False

#            # Get the instance
#            if 'instance' in kwargs:
#                instance = kwargs['instance']   

#        except:
#            msg = oErr.get_error_message()
#            oErr.DoError("SetDefForm")
#        return None


