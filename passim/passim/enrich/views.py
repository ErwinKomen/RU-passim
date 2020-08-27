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
from django.views.decorators.csrf import csrf_exempt
from django.views.generic.detail import DetailView
from django.views.generic.base import RedirectView
from django.views.generic import ListView, View

import json
import fnmatch
import os, csv
import random
import itertools as it
from io import StringIO
from datetime import datetime

# ======= imports from my own application ======
from passim.settings import APP_PREFIX, MEDIA_DIR
from passim.utils import ErrHandle
from passim.seeker.models import Information
from passim.enrich.models import Sentence, Speaker, Testunit, Participant, Testset, TestsetUnit
from passim.enrich.forms import TestunitForm, TestsetForm, SpeakerForm, SentenceForm

# ======= from RU-Basic ========================
from passim.basic.views import BasicList, BasicDetails, make_search_list, add_rel_item
from passim.seeker.views import BasicPart

# Global debugging 
bDebug = False

enrich_editor = "enrich_editor"

def enrich_experiment():
    """RUn a complete experiment"""

    sBack = "Experiment has started"
    oErr = ErrHandle()

    # Define the randomization method
    method = "pergroup"
    method = "stochastic"
    method = "quadro"

    # Other initialisations
    cnt_speakers = 78   # Number of speakers
    cnt_sentences = 48  # Number of sentences
    cnt_conditions = 2  # Number of ntype conditions
    cnt_groupsize = 6   # Number of speakers in one group
    cnt_maxspeaker = 12
    cnt_round = 4       # Number of rounds of testsets to be created
    cnt_sentpercond = cnt_sentences // cnt_conditions

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

            if method == "pergroup":
                # Simple testsets
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

            elif method == "quadro":
                # Divide groups of 4 titems of one author over testsets

                # Simple testsets
                for i in range(cnt_speakers * cnt_conditions): testsets.append([])
                idx_testset = 0

                # Prepare NP-type
                nptypes_odd = ['n', 'p']
                nptypes_even = ['p', 'n']

                # Iterate over random speakers
                lst_spk = [x.id for x in Speaker.objects.all()]
                random.shuffle(lst_spk)
                for idx_spk, spk in enumerate(lst_spk):
                    # Determine the order of NP type
                    nptypes = nptypes_odd if idx_spk % 2 == 0 else nptypes_even
                    for ntype in nptypes:
                        # Determine the set of speaker-nptype
                        lst_tunit = [x.id for x in Testunit.objects.filter(speaker__id=spk, ntype=ntype)]
                        # Shuffle these tunit items
                        random.shuffle(lst_tunit)
                        # Copy every four of them in consecutive testsets
                        number = len(lst_tunit) // 4
                        for idx in range(number):
                            start = idx * 4
                            for add in range(4):
                                testsets[idx_testset].append(lst_tunit[start+add])
                            # Go to the next testset
                            idx_testset += 1
                            if idx_testset >= len(testsets):
                                idx_testset = 0
                        
                # Shuffle each testset
                for testset in testsets:
                    random.shuffle(testset)
 
                # We now have 156 sets of 48 tunits: these are the testsets for this particular round
                with transaction.atomic():
                    for idx, testset in enumerate(testsets):
                        # Get the testset object for this round
                        tsobj = Testset.get_testset(round+1, idx+1)

                        # ========== DEBUG ===========
                        oErr.Status("round {} testset {}".format(round+1, idx+1))
                        # ============================

                        # Add testsets to this particular round
                        qs = Testunit.objects.filter(id__in=testset)
                        for tunit in qs:
                            # tunit.testsets.add(tsobj)
                            TestsetUnit.objects.create(testunit=tunit, testset=tsobj)

            elif method == "stochastic":
                # Smart testsets
                for i in range(cnt_speakers * cnt_conditions): 
                    oSet = dict(items=[], speaker=[], sentence={}, ntype=dict(n=0,p=0))
                    testsets.append(oSet)

                # Randomize the titems
                titems = [x for x in Testunit.objects.all()]
                random.shuffle(titems)

                # Walk all test unitsl
                for idx, tunit in enumerate(titems):
                    # ========== DEBUG ===========
                    if idx % 100 == 0:
                        oErr.Status("Round {}, Working on tunit={}".format(round+1, idx+1))
                    # ============================

                    tunit_id = tunit.id
                    speaker_id = tunit.speaker.id
                    sentence_id = tunit.sentence.id
                    ntype = tunit.ntype
                    # Find the first testset where this fits
                    bFound = False
                    bSentence = False
                    while not bFound:
                        for testset in testsets:
                            speakers = testset['speaker']
                            if len(speakers) < cnt_maxspeaker or speaker_id in speakers:
                                # Speakers are okay; get the number of sentence_id occurrances
                                num_sent_id = testset['sentence'].get(sentence_id, 0)
                                #sentences = testset['sentence']
                                #if bSentence or not sentence_id in sentences:
                                if num_sent_id < 2:
                                    # Sentences are okay
                                    ntype_n = testset['ntype']['n']
                                    ntype_p = testset['ntype']['p']
                                    if (ntype == "n" and ntype_n < cnt_sentpercond) or (ntype == "p" and ntype_p < cnt_sentpercond):
                                        # Ntype is okay - add it
                                        testset['items'].append(tunit_id)
                                        # Bookkeeping
                                        if speaker_id not in speakers:
                                            testset['speaker'].append(speaker_id)
                                        # if sentence_id not in sentences:
                                        testset['sentence'][sentence_id] = num_sent_id + 1
                                        testset['ntype'][ntype] += 1
                                        bFound = True
                                        break
                        if not bFound:
                            left_n = [x for x in testsets if x['ntype'][ntype] < 24]
                            left_sp = [x for x in left_n if len(x['speaker']) < 12 or speaker_id in x['speaker'] ]
                            left_snt = [x for x in left_sp if len(x['sentence']) < 48 or  sentence_id in x['sentence'] ]
                            bSentence = True
                # Shuffle each testset
                for testset in testsets:
                    random.shuffle(testset['items'])
 
                # We now have 156 sets of 48 tunits: these are the testsets for this particular round
                with transaction.atomic():
                    for idx, testset in enumerate(testsets):
                        # Get the testset object for this round
                        tsobj = Testset.get_testset(round+1, idx+1)

                        # ========== DEBUG ===========
                        # oErr.Status("round {} testset {}".format(round+1, idx+1))
                        # ============================

                        # Add testsets to this particular round
                        qs = Testunit.objects.filter(id__in=testset['items'])
                        for tunit in qs:
                            tunit.testsets.add(tsobj)


        # Set the message
        sBack = "Created {} testset rounds".format(cnt_round)
    except:
        msg = oErr.get_error_message()
        oErr.DoError("enrich_experiment")
        sBack = msg

    return sBack

def user_is_ingroup(request, sGroup):
    # Is this user part of the indicated group?
    user = User.objects.filter(username=request.user.username).first()

    # Only look at group if the user is known
    if user == None:
        glist = []
    else:
        glist = [x.name for x in user.groups.all()]

        # Only needed for debugging
        if bDebug:
            ErrHandle().Status("User [{}] is in groups: {}".format(user, glist))
    # Evaluate the list
    bIsInGroup = (sGroup in glist)
    return bIsInGroup

@csrf_exempt
def get_testsets(request):
    """Get a list of testunits per testset of one round"""

    oErr = ErrHandle()
    try:
        data = 'fail'
        qd = request.GET if request.method == "GET" else request.POST
        if request.is_ajax():
            round = qd.get("round", "")
            lstQ = []
            lstQ.append(Q(testset__round=round))
            items = TestsetUnit.objects.filter(*lstQ).order_by("testset__number").values(
                'testset__round', 'testset__number', 'testunit__speaker__name', 
                'testunit__sentence__name', 'testunit__ntype')
            results = []
            for idx, obj in enumerate(items):
                number = obj.get('testset__number')           
                speaker = obj.get('testunit__speaker__name')  
                sentence = obj.get('testunit__sentence__name')
                ntype = "Lom" if obj.get('testunit__ntype') == "n" else "Nat"
                co_json = {'idx': idx+1, 'testset': number, 'speaker': speaker, 'sentence': sentence, 'ntype': ntype }
                results.append(co_json)
            data = json.dumps(results)
        else:
            data = "Request is not ajax"
    except:
        msg = oErr.get_error_message()
        data = "error: {}".format(msg)
    mimetype = "application/json"
    return HttpResponse(data, mimetype)



class SpeakerEdit(BasicDetails):
    """Details view of Speaker"""

    model = Speaker
    mForm = SpeakerForm
    prefix = "spk"
    title = "Speaker"
    rtype = "json"
    mainitems = []

    def add_to_context(self, context, instance):
        """Add to the existing context"""

        # Define the main items to show and edit
        context['mainitems'] = [
            {'type': 'plain', 'label': "Id",    'value': instance.id},
            {'type': 'plain', 'label': "Name:", 'value': instance.name, 'field_key': 'name'} 
            ]
        context['is_enrich_editor'] = user_is_ingroup(self.request, enrich_editor)
        # Return the context we have made
        return context


class SpeakerDetails(SpeakerEdit):
    """Like Speaker Edit, but then html output"""
    rtype = "html"


class SpeakerListView(BasicList):
    """List Speakers"""

    model = Speaker
    listform = SpeakerForm
    prefix = "spk"
    new_button = False              # Don't allow adding new speakers right now     
    order_cols = ['id', 'name']
    order_default = order_cols
    order_heads = [
        {'name': 'Id',      'order': 'o=1', 'type': 'int', 'field': 'id',   'linkdetails': True},
        {'name': 'Name',    'order': 'o=2', 'type': 'str', 'field': 'name', 'linkdetails': True, 'main': True}]

    def add_to_context(self, context, initial):
        context['is_enrich_editor'] = user_is_ingroup(self.request, enrich_editor)
        return context


class SentenceEdit(BasicDetails):
    """Details view of Sentence"""

    model = Sentence
    mForm = SentenceForm
    prefix = "spk"
    title = "Sentence"
    rtype = "json"
    mainitems = []

    def add_to_context(self, context, instance):
        """Add to the existing context"""

        # Define the main items to show and edit
        context['mainitems'] = [
            {'type': 'plain', 'label': "Id",    'value': instance.id},
            {'type': 'plain', 'label': "Name:", 'value': instance.name, 'field_key': 'name'} 
            ]
        context['is_enrich_editor'] = user_is_ingroup(self.request, enrich_editor)
        # Return the context we have made
        return context


class SentenceDetails(SentenceEdit):
    """Like Sentence Edit, but then html output"""
    rtype = "html"


class SentenceListView(BasicList):
    """List Sentences"""

    model = Sentence
    listform = SentenceForm
    prefix = "spk"
    new_button = False              # Don't allow adding new speakers right now     
    order_cols = ['id', 'name']
    order_default = order_cols
    order_heads = [
        {'name': 'Id',      'order': 'o=1', 'type': 'int', 'field': 'id',   'linkdetails': True},
        {'name': 'Name',    'order': 'o=2', 'type': 'str', 'field': 'name', 'linkdetails': True, 'main': True}]

    def add_to_context(self, context, initial):
        context['is_enrich_editor'] = user_is_ingroup(self.request, enrich_editor)
        return context


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
            {'type': 'safe',  'label': "N-Type:",       'value': instance.get_ntype_html(), },
            {'type': 'plain', 'label': "Test units:",   'value': instance.get_testsets() },
            {'type': 'safe',  'label': "Filename:",     'value': instance.get_filename_html() } 
            ]
        context['is_enrich_editor'] = user_is_ingroup(self.request, enrich_editor)
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
        context['is_enrich_editor'] = user_is_ingroup(self.request, enrich_editor)
        return context


class TestunitRunView(TestunitListView):
    """RUnning the experiment"""

    report = ""

    def initializations(self):
        self.report = enrich_experiment();
        self.redirectpage = reverse('testunit_list')
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
        context['is_enrich_editor'] = user_is_ingroup(self.request, enrich_editor)
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
    downloads = [{"label": "Excel", "dtype": "xlsx", "url": 'testset_results'},
                 {"label": "csv (tab-separated)", "dtype": "csv", "url": 'testset_results'},
                 {"label": None},
                 {"label": "json", "dtype": "json", "url": 'testset_results'}]

    def get_field_value(self, instance, custom):
        sBack = ""
        sTitle = ""
        if custom == "size":
            sBack = instance.testset_testunits.count()

        return sBack, sTitle

    def add_to_context(self, context, initial):
        context['is_enrich_editor'] = user_is_ingroup(self.request, enrich_editor)
        return context


class TestsetDownload(BasicPart):
    MainModel = Testset
    template_name = "seeker/download_status.html"
    action = "download"
    dtype = "csv"       # downloadtype

    def custom_init(self):
        """Calculate stuff"""
        
        dt = self.qd.get('downloadtype', "")
        if dt != None and dt != '':
            self.dtype = dt

    def get_queryset(self, prefix):

        # Construct the QS
        qs = TestsetUnit.objects.all().order_by('testset__round', 'testset__number').values(
            'testset__round', 'testset__number', 'testunit__speaker__name', 
            'testunit__sentence__name', 'testunit__ntype')

        return qs

    def get_data(self, prefix, dtype):
        """Gather the data as CSV, including a header line and comma-separated"""

        # Initialize
        lData = []
        sData = ""

        if dtype == "json":
            # Loop over all round/number combinations (testsets)
            for obj in self.get_queryset(prefix):
                round = obj.get('testset__round')                # obj.testset.round
                number = obj.get('testset__number')             # obj.testset.number
                speaker = obj.get('testunit__speaker__name')    # obj.testunit.speaker.name
                sentence = obj.get('testunit__sentence__name')  # obj.testunit.sentence.name
                ntype = obj.get('testunit__ntype')              # obj.testunit.ntype
                row = dict(round=round, testset=number, speaker=speaker,
                    sentence=sentence, ntype=ntype)
                lData.append(row)
            # convert to string
            sData = json.dumps(lData, indent=2)
        else:
            # Create CSV string writer
            output = StringIO()
            delimiter = "\t" if dtype == "csv" else ","
            csvwriter = csv.writer(output, delimiter=delimiter, quotechar='"')
            # Headers
            headers = ['round', 'testset', 'speaker', 'sentence', 'ntype']
            csvwriter.writerow(headers)
            for obj in self.get_queryset(prefix):
                round = obj.get('testset__round')                # obj.testset.round
                number = obj.get('testset__number')             # obj.testset.number
                speaker = obj.get('testunit__speaker__name')    # obj.testunit.speaker.name
                sentence = obj.get('testunit__sentence__name')  # obj.testunit.sentence.name
                ntype = obj.get('testunit__ntype')              # obj.testunit.ntype
                row = [round, number, speaker, sentence, ntype]
                csvwriter.writerow(row)

            # Convert to string
            sData = output.getvalue()
            output.close()

        return sData


