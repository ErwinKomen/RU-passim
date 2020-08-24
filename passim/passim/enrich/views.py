"""
Definition of views for the ENRICH app.
"""

from django.apps import apps
from django.contrib.auth.models import User, Group
from django.urls import reverse
from django.db import transaction
from django.db.models import Q, Prefetch, Count, F
from django.db.models.functions import Lower
from django.db.models.query import QuerySet 
from django.http import HttpRequest, HttpResponse, HttpResponseRedirect, JsonResponse, FileResponse
from django.shortcuts import get_object_or_404, render, redirect
from django.template.loader import render_to_string
from django.views.generic.detail import DetailView
from django.views.generic.base import RedirectView
from django.views.generic import ListView, View

import json
import fnmatch
import os
import random
import itertools as it
from datetime import datetime

# ======= imports from my own application ======
from passim.settings import APP_PREFIX, MEDIA_DIR
from passim.utils import ErrHandle
from passim.seeker.models import Information
from passim.enrich.models import Sentence, Speaker, Testunit, Participant
from passim.enrich.forms import TestunitForm

# ======= from RU-Basic ========================
from passim.basic.views import BasicList, BasicDetails, make_search_list

# Global debugging 
bDebug = False

def enrich_experiment():
    """RUn a complete experiment"""

    sBack = "Experiment has started"
    oErr = ErrHandle()
    try:
        # Remove all previous participant-testunit combinations
        with transaction.atomic():
            for obj in Participant.objects.all():
                obj.participant_testunits.clear()
        sBack = "Previous participant-testunit combinations have been removed"

        # Create 13 sets of 6 speakers
        speaker_six = []
        spk = [x.id for x in Speaker.objects.all()]
        random.shuffle(spk)
        for spk_idx in range(13):
            start = spk_idx * 6
            end = start + 6
            oSet = spk[start:end]
            speaker_six.append(oSet)

        # Create 78 (!) speaker sets of 12 speakers
        lst_combi = [x for x in it.combinations(speaker_six, 2)]
        speaker_twelve = []
        for item in lst_combi: speaker_twelve.append(item[0] + item[1])
        # Note: speaker_twelve now contains 78 different sets of 12 speakers

        # Iterate over the speaker_twelve sets
        pms = []
        for speaker_ids in speaker_twelve:
            condition_sets = {}
            # Iterate over the two conditions
            for ntype in ['n', 'p']:
                # Get all the tunits for this combination of speaker/ntype
                qs = Testunit.objects.filter(speaker__id__in=speaker_ids, ntype=ntype)
                # Walk them and increment their count
                tunits = []
                with transaction.atomic():
                    for obj in qs:
                        obj.count = obj.count + 1
                        tunits.append(obj.id)

                # Create lists of tunit ids
                tunits = [x.id for x in qs]
                random.shuffle(tunits)
                condition_sets[ntype] = tunits
            # Create 24 lists of 48 tunits
            for idx in range(24):
                start = idx * 24
                end = start + 24
                # Get 24 'n' and 24 'p'
                oSet = condition_sets['p'][start:end] + condition_sets['p'][start:end]
                random.shuffle(oSet)
                pms.append(oSet)
        # We now have 156 sets of 48 tunits
        iStop = 1
        x = len(pms)

        # Set the message
    except:
        msg = oErr.get_error_message()
        oErr.DoError("enrich_experiment")
        sBack = msg

    return sBack

class TestunitEdit(BasicDetails):
    """Details view of Testunit"""

    model = Testunit
    mForm = TestunitForm
    prefix = "tunit"
    title = "Test unit Edit"
    rtype = "json"
    mainitems = []

    def add_to_context(self, context, instance):
        """Add to the existing context"""

        # Define the main items to show and edit
        context['mainitems'] = [
            {'type': 'plain', 'label': "Speaker",       'value': instance.speaker.name},
            {'type': 'plain', 'label': "Sentence:",     'value': instance.sentence.name, },
            {'type': 'plain', 'label': "N-Type:",       'value': instance.get_ntype_display(), },
 
            ]
        # Return the context we have made
        return context


class TestunitDetails(TestunitEdit):
    """Like Testunit Edit, but then html output"""
    rtype = "html"


class TestunitListView(BasicList):
    """List Testunits"""

    model = Testunit
    listform = TestunitForm
    prefix = "tunit"
    new_button = True      
    order_cols = ['speaker__name', 'sentence__name', 'ntype']
    order_default = order_cols
    order_heads = [
        {'name': 'Speaker',     'order': 'o=1', 'type': 'str', 'custom': 'speaker', 'default': "(unnamed)", 'linkdetails': True},
        {'name': 'Sentence',    'order': 'o=2', 'type': 'str', 'custom': 'sentence', 'main': True, 'linkdetails': True},
        {'name': 'N-type',      'order': 'o=3', 'type': 'str', 'custom': 'ntype', 'linkdetails': True}]
    custombuttons = [{"name": "experiment", "title": "Experiment", 
                      "icon": "music", "template_name": "enrich/experiment.html" }]

    def initializations(self):
        if Information.get_kvalue("enrich-speakers") != "done":
            # Create speakers: 78
            with transaction.atomic():
                for idx in range(78):
                    num = str(idx+1).zfill(2)
                    name = "speaker_{}".format(num)
                    obj = Speaker.objects.create(name=name)
            Information.set_kvalue("enrich-speakers", "done")

        if Information.get_kvalue("enrich-sentences") != "done":
            # Create sentences: 48
            with transaction.atomic():
                for idx in range(48):
                    num = str(idx+1).zfill(2)
                    name = "sentence_{}".format(num)
                    obj = Sentence.objects.create(name=name)
            Information.set_kvalue("enrich-sentences", "done")

        if Information.get_kvalue("enrich-tunits") != "done":
            # Create test units
            with transaction.atomic():
                for ntype in ['n', 'p']:
                    for speaker in Speaker.objects.all():
                        for sentence in Sentence.objects.all():
                            obj = Testunit.objects.create(sentence=sentence, speaker=speaker, ntype=ntype)
            Information.set_kvalue("enrich-tunits", "done")

        return None

    def get_field_value(self, instance, custom):
        sBack = ""
        sTitle = ""
        if custom == "speaker":
            sBack = instance.speaker.name
        elif custom == "sentence":
            sBack = instance.sentence.name
        elif custom == "ntype":
            sBack = instance.get_ntype_display()

        return sBack, sTitle

    def add_to_context(self, context, initial):
        ## Add a button to start experiment
        #template_name = "enrich/experiment.html"
        #context['after_details'] = render_to_string(template_name, context, self.request)
        return context


class TestunitRunView(TestunitListView):
    """RUnning the experiment"""

    report = ""

    def initializations(self):
        self.report = enrich_experiment();
        return None

    def add_to_context(self, context, initial):
        context['after_details'] = self.report
        return context