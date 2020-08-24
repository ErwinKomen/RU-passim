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
from passim.enrich.models import Sentence, Speaker, Testunit, Participant, Testset
from passim.enrich.forms import TestunitForm, TestsetForm

# ======= from RU-Basic ========================
from passim.basic.views import BasicList, BasicDetails, make_search_list, add_rel_item

# Global debugging 
bDebug = False

def enrich_experiment():
    """RUn a complete experiment"""

    sBack = "Experiment has started"
    oErr = ErrHandle()
    cnt_speakers = 78   # Number of speakers
    cnt_sentences = 48  # Number of sentences
    cnt_conditions = 2  # Number of ntype conditions
    cnt_groupsize = 6   # Number of speakers in one group
    cnt_round = 4       # Number of rounds of testsets to be created

    # How many testunit items are needed per combination of SpeakerGroup + Ntype?
    cnt_pertestset = cnt_sentences // (cnt_conditions + 12 // cnt_groupsize )
    try:
        # Remove all previous participant-testunit combinations
        with transaction.atomic():
            for obj in Testset.objects.all():
                obj.testset_testunits.clear()
        sBack = "Previous testset-testunit combinations have been removed"

        # Create testset for each round
        for round in range(cnt_round):

            # Create test-sets: each testset must contain cnt_sentences 
            testsets = []
            for i in range(cnt_speakers * cnt_conditions): testsets.append([])

            # Create sets of [cnt_groupsize] speakers
            speaker_group = []
            cnt_speakergroup = cnt_speakers // cnt_groupsize
            spk = [x.id for x in Speaker.objects.all()]
            random.shuffle(spk)
            for spk_idx in range(cnt_speakergroup):
                start = spk_idx * cnt_groupsize
                end = start + cnt_groupsize
                oSet = spk[start:end]
                speaker_group.append(oSet)

            # Create speakergroup-pn-sets
            idx_testset = 0
            for sg_id, speaker_ids in enumerate(speaker_group):
                for ntype in ['n', 'p']:
                    # Get all the tunits for this combination of speaker/ntype
                    qs = Testunit.objects.filter(speaker__id__in=speaker_ids, ntype=ntype)

                    # ========== DEBUG ===========
                    #if qs.count() != 288:
                    #    iStop = 1
                    # ============================

                    # Walk them and increment their count
                    tunits = []
                    with transaction.atomic():
                        for obj in qs:
                            obj.count = obj.count + 1
                            tunits.append(obj.id)

                    # Create one list of tunit ids
                    tunits = [x.id for x in qs]
                    random.shuffle(tunits)

                    # Divide this combination of SpeakerGroup + Ntype over the testsets
                    idx_chunk = 0
                    while idx_chunk + cnt_pertestset <= len(tunits):
                        # copy a chunk to the next testset
                        testset = testsets[idx_testset]
                        for idx in range(cnt_pertestset):
                            # ========== DEBUG ===========
                            # oErr.Status("adding tunit item {} of {}".format(idx_chunk+idx, qs.count()))
                            # ============================

                            testset.append( tunits[idx_chunk + idx])
                        # Go to the next testset
                        idx_testset += 1
                        if idx_testset >= len(testsets): 
                            idx_testset = 0

                        # Next chunk 
                        idx_chunk += cnt_pertestset

            # Shuffle each testset
            for testset in testsets:
                random.shuffle(testset)
 
            # We now have 156 sets of 48 tunits: these are the testsets for this particular round
            with transaction.atomic():
                for idx, testset in enumerate(testsets):
                    # Get the testset object for this round
                    tsobj = Testset.get_testset(round+1, idx+1)

                    # ========== DEBUG ===========
                    # oErr.Status("round {} testset {}".format(round+1, idx+1))
                    # ============================

                    # Add testsets to this particular round
                    qs = Testunit.objects.filter(id__in=testset)
                    for tunit in qs:
                        tunit.testsets.add(tsobj)

        # Set the message
        sBack = "Created {} testset rounds".format(cnt_round)
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
            {'type': 'plain', 'label': "Test units:",   'value': instance.get_testsets() }
 
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


class TestsetEdit(BasicDetails):
    """Details view of Testset"""

    model = Testset
    mForm = TestsetForm
    prefix = "tset"
    title = "Test set Edit"
    rtype = "json"
    mainitems = []

    def add_to_context(self, context, instance):
        """Add to the existing context"""

        # Define the main items to show and edit
        context['mainitems'] = [
            {'type': 'plain', 'label': "Round",       'value': instance.round},
            {'type': 'plain', 'label': "Number:",     'value': instance.number} 
            ]
        # Return the context we have made
        return context


class TestsetDetails(TestsetEdit):
    """Like Testset Edit, but then html output"""
    rtype = "html"

    def add_to_context(self, context, instance):
        # First get the 'standard' context from TestsetEdit
        context = super(TestsetDetails, self).add_to_context(context, instance)

        context['sections'] = []

        # Lists of related objects
        related_objects = []
        resizable = True
        index = 1
        sort_start = '<span class="sortable"><span class="fa fa-sort sortshow"></span>&nbsp;'
        sort_end = '</span>'

        # List of Testunits contained in this testset
        testunits = dict(title="Test units in this testset", prefix="tunit")
        if resizable: testunits['gridclass'] = "resizable"

        rel_list =[]
        for item in instance.testset_testunits.all().order_by('speaker', 'ntype', 'sentence'):
            url = reverse('testunit_details', kwargs={'pk': item.id})
            rel_item = []

            # S: Order in Manuscript
            add_rel_item(rel_item, index, False, align="right")
            index += 1

            # Speaker
            add_rel_item(rel_item, item.speaker.name, False, main=True, link=url)

            # Ntype
            add_rel_item(rel_item, item.get_ntype_display(), False, link=url)

            # Sentence
            add_rel_item(rel_item, item.sentence.name, False, link=url)

            # Add this line to the list
            rel_list.append(rel_item)

        testunits['rel_list'] = rel_list

        testunits['columns'] = [
            '#',
            '{}<span>Speaker</span>{}'.format(sort_start, sort_end), 
            '{}<span title="Ntype is either [P]lain or Lomdard [N]oise">Ntype</span>{}'.format(sort_start, sort_end), 
            '{}<span>Sentence</span>{}'.format(sort_start, sort_end)
            ]
        related_objects.append(testunits)

        # Add all related objects to the context
        context['related_objects'] = related_objects

        # Return the context we have made
        return context


class TestsetListView(BasicList):
    """List Testunits"""

    model = Testset
    listform = TestsetForm
    prefix = "tset"
    new_button = False      
    order_cols = ['round', 'number', 'testset_testunits__count']
    order_default = order_cols
    order_heads = [
        {'name': 'Round',     'order': 'o=1', 'type': 'int', 'field': 'round', 'linkdetails': True},
        {'name': 'Number',    'order': 'o=2', 'type': 'int', 'field': 'number', 'main': True, 'linkdetails': True},
        {'name': 'Size',      'order': 'o=3', 'type': 'int', 'custom': 'size', 'linkdetails': True}]

    def get_field_value(self, instance, custom):
        sBack = ""
        sTitle = ""
        if custom == "size":
            sBack = instance.testset_testunits.count()

        return sBack, sTitle

