"""
Definition of visualization views for the SEEKER app.
"""

from xml.etree.ElementInclude import include
from django.db import transaction
from django.db.models import Q, Prefetch, Count, F
from django.template.loader import render_to_string
from django.urls import reverse
import pandas as pd 
from sklearn.decomposition import PCA
from sklearn.preprocessing import StandardScaler
import json
import copy
import itertools

# ======= imports from my own application ======
from passim.utils import ErrHandle
from passim.basic.views import BasicPart, user_is_ingroup
from passim.seeker.models import get_crpp_date, get_current_datetime, process_lib_entries, adapt_search, get_searchable, get_now_time, \
    add_gold2equal, add_equal2equal, add_ssg_equal2equal, get_helptext, Information, Country, City, Author, Manuscript, \
    User, Group, Origin, SermonDescr, MsItem, SermonHead, SermonGold, SermonDescrKeyword, SermonDescrEqual, Nickname, NewsItem, \
    FieldChoice, SourceInfo, SermonGoldSame, SermonGoldKeyword, EqualGoldKeyword, Signature, Ftextlink, ManuscriptExt, \
    ManuscriptKeyword, Action, EqualGold, EqualGoldLink, Location, LocationName, LocationIdentifier, LocationRelation, LocationType, \
    ProvenanceMan, Provenance, Daterange, CollOverlap, BibRange, Feast, Comment, SermonEqualDist, \
    Project2, Basket, BasketMan, BasketGold, BasketSuper, Litref, LitrefMan, LitrefCol, LitrefSG, EdirefSG, Report, SermonDescrGold, \
    Visit, Profile, Keyword, SermonSignature, Status, Library, Collection, CollectionSerm, \
    CollectionMan, CollectionSuper, CollectionGold, UserKeyword, Template, ManuscriptCorpus, ManuscriptCorpusLock, \
    EqualGoldCorpus, EqualGoldCorpusItem, \
   LINK_EQUAL, LINK_PRT, LINK_BIDIR, LINK_PARTIAL, STYPE_IMPORTED, STYPE_EDITED, LINK_UNSPECIFIED
from passim.stylo.corpus import Corpus
from passim.stylo.analysis import bootstrapped_distance_matrices, hierarchical_clustering, distance_matrix
from passim.dct.models import SavedVis

# ======= from RU-Basic ========================
from passim.basic.views import BasicList, BasicDetails, make_search_list, add_rel_item, app_editor


COMMON_NAMES = ["Actibus", "Adiubante", "Africa", "Amen", "Andreas", "Apostolorum", "Apringio", "Augustinus", 
                "Austri", "Baptistae", "Beatum", "Christi", "Christo", "Christum", 
                "Christus", "Christus", "Chrsiti", "Cosmae", "Cui", "Dauid", "Dedicatur", "Dei", 
                "Deum", "Deus", "Dies", "Domenicae", "Domiani", "Domine", "Domini", "Dominico", "Domino", 
                "Dominum", "Dominus", "Ecce", "Ephesum", "Epiphaniae", "Eua", "Euangelista", 
                "Eusebii", "Eustochium", "Explicit", "Filio", "Fraternitatis", "Fulgentio", "Galilaea\u2026piscatores",
                "Herodes", "Iesse", "Iesu", "Iesu", "Iesum", "Iesus", "Ihesu", "In", "Ioannis", "Iohanne", 
                "Iohannem", "Iohannes", "Iohannis", "Ipse", "Ipsi", "Ipso", "Iudaea", "Iudaeis", "Lectis", 
                "Lucas", "Marcellino", "Maria", "Mariam", "Moysen", "Nam", "Naue", "Niniue", "Paschae", 
                "Patre", "Patrem", "Patre\u2026", "Patris", "Paula", "Pauli", "Paulino", 
                "Paulus", "Per", "Petri", "Petrus", "Possidius", "Praecursoris", "Praestante\u2026", "Primus", 
                "Qui", "Quid", "Quis", "Quod", "Remedia", "Rex", "Salomon", "Salomonem", "Saluator", 
                "Saluatoris", "Salvator", "Sancti", "Saulus", "Si", "Sicut", "Simon", "Sine", "Solomonis", 
                "Spiritu", "Spiritus", "Stephanus", "Testamenti", "Therasiae", "Thomam", "Thomas"]


def get_ssg_corpus(profile, instance):
    oErr = ErrHandle()
    lock_status = "new"
    ssg_corpus = None
    try:
        
        # Set the lock, or return if we are busy with this ssg_corpus
        ssg_corpus = EqualGoldCorpus.objects.filter(profile=profile, ssg=instance).last()
        if ssg_corpus != None:
            lock_status = ssg_corpus.status
            # Check the status
            if lock_status == "busy":
                # Already busy
                return context
        else:
            # Need to create a lock
            ssg_corpus = EqualGoldCorpus.objects.create(profile=profile, ssg=instance)
            lock_status = "busy"

        # Save the status
        ssg_corpus.status = lock_status
        ssg_corpus.save()

        if lock_status == "new":
            # Remove earlier corpora made by me based on this SSG
            EqualGoldCorpus.objects.filter(profile=profile, ssg=instance).delete()

            # Create a new one
            ssg_corpus = EqualGoldCorpus.objects.create(profile=profile, ssg=instance, status="busy")

    except:
        msg = oErr.get_error_message()
        oErr.DoError("get_ssg_corpus")       
    return ssg_corpus, lock_status

def get_ssg_sig(ssg_id):

    oErr = ErrHandle()
    sig = ""
    editype_preferences = ['gr', 'cl', 'ot']
    issue_375 = True
    try:
        for editype in editype_preferences:
            siglist = Signature.objects.filter(gold__equal__id=ssg_id, editype=editype).order_by('code').values('code')
            if len(siglist) > 0:
                sig = siglist[0]['code']
                break
        # We now have the most appropriate signature, or the empty string, if there is none
        # The folloing is old code, not quite clear why it was necessary
        if not issue_375 and ',' in sig:
            sig = sig.split(",")[0].strip()
    except:
        msg = oErr.get_error_message()
        oErr.DoError("get_ssg_sig")
    return sig

def get_ssg_passim(ssg_id, obj=None):
    oErr = ErrHandle()
    code = ""
    try:
        # Get the Passim Code
        if obj == None:
            obj = EqualGold.objects.filter(id=ssg_id).first()
        if obj.code == None:
            code = "eqg_{}".format(obj.id)
        elif " " in obj.code:
            code = obj.code.split(" ")[1]
        else:
            code = obj.code
    except:
        msg = oErr.get_error_message()
        oErr.DoError("get_ssg_passim")
    return code

def get_watermark():
    """Create and return a watermark"""

    oErr = ErrHandle()
    watermark_template = "seeker/passim_watermark.html"
    watermark = ""
    try:
            # create a watermark with the right datestamp
            context_wm = dict(datestamp=get_crpp_date(get_current_datetime(), True))
            watermark = render_to_string(watermark_template, context_wm)
    except:
        msg = oErr.get_error_message()
        oErr.DoError("get_watermark")
    # Return the result
    return watermark



class DrawPieChart(BasicPart):
    """Fetch data for a particular type of pie-chart for the home page
    
    Current types: 'sermo', 'super', 'manu'
    """

    pass


class EqualGoldOverlap(BasicPart):
    """Network of textual overlap between SSGs"""

    MainModel = EqualGold
    template_name = "dct/vis_details.html"

    def add_to_context(self, context):

        oErr = ErrHandle()
        spec_dict = {}
        link_dict = {}
        graph_template = 'seeker/super_graph_hist.html'

        try:
            # Check validity
            if not self.userpermissions("r"):
                # Don't do anything
                return context

            # Need to figure out who I am
            profile = Profile.get_user_profile(self.request.user.username)
            instance = self.obj

            # Define the linktype and spectype
            for obj in FieldChoice.objects.filter(field="seeker.spectype"):
                spec_dict[obj.abbr]= obj.english_name
            for obj in FieldChoice.objects.filter(field="seeker.linktype"):
                link_dict[obj.abbr]= obj.english_name

            # The networkslider determines whether we are looking for 1st degree, 2nd degree or more
            networkslider = self.qd.get("network_overlap_slider", "1")            
            if isinstance(networkslider, str):
                networkslider = int(networkslider)

            # Initializations
            ssg_link = {}
            bUseDirectionality = True

            # Read the table with links from SSG to SSG
            eqg_link = EqualGoldLink.objects.all().order_by('src', 'dst').values(
                'src', 'dst', 'spectype', 'linktype', 'alternatives', 'note')
            # Transform into a dictionary with src as key and list-of-dst as value
            for item in eqg_link:
                src = item['src']
                dst = item['dst']
                if bUseDirectionality:
                    spectype = item['spectype']
                    linktype = item['linktype']
                    note = item['note']
                    alternatives = item['alternatives']
                    if alternatives == None: alternatives = False
                    # Make room for the SRC if needed
                    if not src in ssg_link: ssg_link[src] = []
                    # Add this link to the list
                    oLink = {   'dst': dst, 
                                'note': note,
                                'spectype': "", 
                                'linktype': linktype,
                                'spec': "",
                                'link': link_dict[linktype],
                                'alternatives': alternatives}
                    if spectype != None:
                        oLink['spectype'] = spectype
                        oLink['spec'] = spec_dict[spectype]
                    ssg_link[src].append(oLink)
                else:
                    # Make room for the SRC if needed
                    if not src in ssg_link: ssg_link[src] = []
                    # Add this link to the list
                    ssg_link[src].append(dst)

            # Create the overlap network
            node_list, link_list, hist_set, max_value, max_group = self.do_overlap(ssg_link, networkslider)

            # Create the buttons for the historical collections
            hist_list=[{'id': k, 'name': v} for k,v in hist_set.items()]
            hist_list = sorted(hist_list, key=lambda x: x['name']);
            # Add to context!
            # context = dict(hist_list = hist_list)
            context['hist_list'] = hist_list
            hist_buttons = render_to_string(graph_template, context, self.request)

            # Add the information to the context in data
            context['data'] = dict(node_list=node_list, 
                                   link_list=link_list,
                                   watermark=get_watermark(),
                                   hist_set=hist_set,
                                   hist_buttons=hist_buttons,
                                   max_value=max_value,
                                   max_group=max_group,
                                   networkslider=networkslider,
                                   legend="AF overlap network")

            # Check if we have a 'savedvis' parameter
            savedvis_id = self.qd.get("savedvis")
            if not savedvis_id is None:
                # Get the saved visualization
                savedvis = SavedVis.objects.filter(id=savedvis_id).first()
                if not savedvis is None:
                    # Pass on the parameters
                    context['data']['options'] = savedvis.options
                    context['overlap_options'] = savedvis.options
                    context['visname'] = savedvis.name

            if self.method == "GET":
                # We need to return HTML
                self.rtype = "html"
                # TO be added for GET calls: backbutton, listview, params, topleftbuttons
                if context.get('object') == None:
                    context['object'] = instance
                context['backbutton'] = True
                context['listview'] = reverse('equalgold_details', kwargs={'pk': instance.id})
                # Also indicate that we only want the OVERLAP
                context['only_overlap'] = True

                # And then the actual overlap drawing
                context['equalgold_overlap'] = reverse("equalgold_overlap", kwargs={'pk': instance.id})
                context['after_details'] = render_to_string('dct/super_overlap.html', context, self.request)

            
        except:
            msg = oErr.get_error_message()
            oErr.DoError("EqualGoldOverlap/add_to_context")

        return context

    def do_overlap(self, ssg_link, degree, include_to_me=False):
        """Calculate the overlap network up until 'degree'"""

        def add_nodeset(ssg_id, group):
            node_key = ssg_id

            # ---------- DEBUG --------------
            if node_key == 4968:
                iStop = 1
            # -------------------------------

            # Possibly add the node to the set
            if not node_key in node_set:
                code_sig = get_ssg_sig(ssg_id)
                ssg = EqualGold.objects.filter(id=ssg_id).first()
                code_pas = get_ssg_passim(ssg_id, ssg)
                scount = ssg.scount

                # Get a list of the HCs that this SSG is part of
                hc_list = ssg.collections.filter(settype="hc").values("id", "name")
                hcs = []
                for oItem in hc_list:
                    id = oItem['id']
                    if not id in hist_set:
                        hist_set[id] = oItem['name']
                    hcs.append(id)

                node_value = dict(label=code_sig, id=ssg_id, group=group, 
                                  passim=code_pas, scount=scount, hcs=hcs)
                node_set[node_key] = node_value
                
        node_list = []
        link_list = []
        node_set = {}
        link_set = {}
        hist_set = {}
        max_value = 0
        max_group = 1
        oErr = ErrHandle()

        try:
            # Degree 0: direct contacts
            ssg_id = self.obj.id

            ssg_queue = [ ssg_id ]
            ssg_add = []
            group = 1
            degree -= 1
            while len(ssg_queue) > 0 and degree >= 0:
                # Get the next available node
                node_key = ssg_queue.pop()

                # Possibly add the node to the set
                add_nodeset(node_key, group)

                # Add links from this SSG to others
                if node_key in ssg_link:
                    dst_list = ssg_link[node_key]
                    for oDst in dst_list:
                        dst = oDst['dst']
                        # Add this one to the add list
                        ssg_add.append(dst)
                        link_key = "{}_{}".format(node_key, dst)
                        if not link_key in link_set:
                            oLink = dict(source=node_key,
                                         target=dst,
                                         spectype=oDst['spectype'],
                                         linktype=oDst['linktype'],
                                         spec=oDst['spec'],
                                         link=oDst['link'],
                                         alternatives = oDst['alternatives'],
                                         note=oDst['note'],
                                         value=0)
                            # Add the link to the set
                            link_set[link_key] = oLink
                            # Add the destination node to nodeset
                            add_nodeset(dst, group + 1)

                        # Increment the link value
                        link_set[link_key]['value'] += 1

                # Go to the next degree
                if len(ssg_queue) == 0 and degree >= 0:
                    # Decrement the degree
                    degree -= 1

                    group += 1
                    # Add the items from ssg_add into the queue
                    while len(ssg_add) > 0:
                        ssg_queue.append(ssg_add.pop())


            # Turn the sets into lists
            node_list = [v for k,v in node_set.items()]
            link_list = [v for k,v in link_set.items()]

            # Calculate max_value
            for oItem in link_list:
                value = oItem['value']
                if value > max_value: max_value = value
            for oItem in node_list:
                group = oItem['group']
                if group > max_group: max_group = group
            
        except:
            msg = oErr.get_error_message()
            oErr.DoError("EqualGoldOverlap/do_overlap")

        return node_list, link_list, hist_set, max_value, max_group


class EqualGoldTrans(BasicPart):
    """Prepare for a network graph depicting transmission"""

    MainModel = EqualGold
    template_name = "dct/vis_details.html"

    def add_to_context(self, context):

        def add_to_dict(this_dict, item):
            if item != "":
                if not item in this_dict: 
                    this_dict[item] = 1
                else:
                    this_dict[item] += 1
                    
        oErr = ErrHandle()
        try:
            # Check validity
            if not self.userpermissions("r"):
                # Don't do anything
                return context

            # Need to figure out who I am
            profile = Profile.get_user_profile(self.request.user.username)
            instance = self.obj

            networkslider = self.qd.get("network_trans_slider", "1")            
            if isinstance(networkslider, str):
                networkslider = int(networkslider)

            # Get the 'manuscript-corpus': all manuscripts in which a sermon is that belongs to the same SSG
            manu_list = SermonDescrEqual.objects.filter(super=instance).distinct().values("manu_id")
            manu_dict = {}
            for idx, manu in enumerate(manu_list):
                manu_dict[manu['manu_id']] = idx + 1

            ssg_corpus, lock_status = get_ssg_corpus(profile, instance)

            if lock_status != "ready":

                # Create an EqualGoldCorpus based on the SSGs in these manuscripts
                ssg_list = SermonDescrEqual.objects.filter(manu__id__in=manu_list).order_by(
                    'super_id').distinct().values('super_id')
                ssg_list_id = [x['super_id'] for x in ssg_list]
                with transaction.atomic():
                    for ssg in EqualGold.objects.filter(id__in=ssg_list_id):
                        # Get the name of the author
                        authorname = "empty" if ssg.author==None else ssg.author.name
                        # Get the scount
                        scount = ssg.scount
                        # Create new ssg_corpus item
                        obj = EqualGoldCorpusItem.objects.create(
                            corpus=ssg_corpus, equal=ssg, 
                            authorname=authorname, scount=scount)

                # Add this list to the ssg_corpus
                ssg_corpus.status = "ready"
                ssg_corpus.save()

            node_list, link_list, author_list, max_value = self.do_manu_method(ssg_corpus, manu_list, networkslider)


            # Add the information to the context in data
            context['data'] = dict(node_list=node_list, 
                                   link_list=link_list,
                                   watermark=get_watermark(),
                                   author_list=author_list,
                                   max_value=max_value,
                                   networkslider=networkslider,
                                   legend="AF network")
            
            # Can remove the lock
            ssg_corpus.status = "ready"
            ssg_corpus.save()

            # Check if we have a 'savedvis' parameter
            savedvis_id = self.qd.get("savedvis")
            if not savedvis_id is None:
                # Get the saved visualization
                savedvis = SavedVis.objects.filter(id=savedvis_id).first()
                if not savedvis is None:
                    # Pass on the parameters
                    context['data']['options'] = savedvis.options
                    context['trans_options'] = savedvis.options
                    context['visname'] = savedvis.name

            if self.method == "GET":
                # We need to return HTML
                self.rtype = "html"
                # TO be added for GET calls: backbutton, listview, params, topleftbuttons
                if context.get('object') == None:
                    context['object'] = instance
                context['backbutton'] = True
                context['listview'] = reverse('equalgold_details', kwargs={'pk': instance.id})
                # Also indicate that we only want the OVERLAP
                context['only_transmission'] = True

                # And then the actual overlap drawing
                context['equalgold_trans'] = reverse("equalgold_trans", kwargs={'pk': instance.id})
                context['after_details'] = render_to_string('dct/super_trans.html', context, self.request)

            

        except:
            msg = oErr.get_error_message()
            oErr.DoError("EqualGoldTrans/add_to_context")

        return context

    def do_manu_method(self, ssg_corpus, manu_list, min_value):
        """Calculation like 'MedievalManuscriptTransmission' description
        
        The @min_value is the minimum link-value the user wants to see
        """

        oErr = ErrHandle()
        author_dict = {}
        node_list = []
        link_list = []
        max_value = 0       # Maximum number of manuscripts in which an SSG occurs
        max_scount = 1      # Maximum number of sermons associated with one SSG

        try:
            # Initializations
            ssg_dict = {}
            link_dict = {}
            scount_dict = {}
            node_listT = []
            link_listT = []
            node_set = {}       # Put the nodes in a set, with their SSG_ID as key
            title_set = {}      # Link from title to SSG_ID

            # Walk the ssg_corpus: each SSG is one 'text', having a title and a category (=author code)
            for idx, item in enumerate(EqualGoldCorpusItem.objects.filter(corpus=ssg_corpus).values(
                'authorname', 'scount', 'equal__code', 'equal__id')):
                # Determine the name for this row
                category = item['authorname']
                ssg_id = item['equal__id']
                code = item['equal__code']
                if code == None or code == "" or not " " in code or not "." in code:
                    title = "eqg{}".format(ssg_id)
                else:
                    title = code.split(" ")[1]
                # Get the Signature that is most appropriate
                sig = get_ssg_sig(ssg_id)

                # Add author to dictionary
                if not category in author_dict: author_dict[category] = 0
                author_dict[category] += 1
               
                # the scount and store it in a dictionary
                scount = item['scount']
                scount_dict[ssg_id] = scount
                if scount > max_scount:
                    max_scount = scount

                node_key = ssg_id
                node_value = dict(label=title, category=category, scount=scount, sig=sig, rating=0)
                if node_key in node_set:
                    oErr.Status("EqualGoldGraph/do_manu_method: attempt to add same title '{}' for {} and {}".format(
                        title, ssg_id, title_set[title]))
                else:
                    node_set[node_key] = node_value
                    title_set[title] = ssg_id

            # Create list of authors
            author_list = [dict(category=k, count=v) for k,v in author_dict.items()]
            author_list = sorted(author_list, key=lambda x: (-1 * x['count'], x['category'].lower()))

            # Create a dictionary of manuscripts, each having a list of SSG ids
            manu_set = {}
            for manu_item in manu_list:
                manu_id = manu_item["manu_id"]
                # Get a list of all SSGs in this manuscript
                ssg_list = SermonDescrEqual.objects.filter(manu__id=manu_id).order_by(
                    'super_id').distinct()
                # Add the SSG id list to the manuset
                manu_set[manu_id] = [x.super for x in ssg_list]

            # Create a list of edges based on the above
            link_dict = {}
            for manu_id, ssg_list in manu_set.items():
                # Only treat ssg_lists that are larger than 1
                if len(ssg_list) > 1:
                    # itertool.combinations creates all combinations of SSG to SSG in one manuscript
                    for subset in itertools.combinations(ssg_list, 2):
                        source = subset[0]
                        target = subset[1]
                        source_id = source.id
                        target_id = target.id
                        link_code = "{}_{}".format(source_id, target_id)
                        if link_code in link_dict:
                            oLink = link_dict[link_code]
                        else:
                            oLink = dict(source=source_id,
                                         target=target_id,
                                         value=0)
                            link_dict[link_code] = oLink
                        # Add 1
                        oLink['value'] += 1
                        if oLink['value'] > max_value:
                            max_value = oLink['value']
            # Turn the link_dict into a list
            # link_list = [v for k,v in link_dict.items()]
            
            # Only accept the links that have a value >= min_value
            node_dict = {}
            link_list = []
            for k, oItem in link_dict.items():
                if oItem['value'] >= min_value:
                    link_list.append(copy.copy(oItem))
                    # Take note of the nodes
                    src = oItem['source']
                    dst = oItem['target']

                    # Double check to see if both are in the node_set (they should be)
                    if not src in node_set:
                        # Issue a warning
                        oErr.DoError("EqualGoldTrans/do_manu_method WARNING: cannot find src ssg {} in [node_set]".format(src))
                    elif not dst in node_set:
                        # Issue a warning
                        oErr.DoError("EqualGoldTrans/do_manu_method WARNING: cannot find dst ssg {} in [node_set]".format(dst))
                    else:
                        # Now adapt the [node_dict]
                        if not src in node_dict: node_dict[src] = node_set[src]
                        if not dst in node_dict: node_dict[dst] = node_set[dst]
            # Walk the nodes
            node_list = []
            for ssg_id, oItem in node_dict.items():
                oItem['id'] = ssg_id
                oItem['scount'] = 100 * scount_dict[oItem['id']] / max_scount
                node_list.append(copy.copy(oItem))

 
        except:
            msg = oErr.get_error_message()
            oErr.DoError("EqualGoldTrans/do_manu_method")

        return node_list, link_list,  author_list, max_value


class EqualGoldGraph(BasicPart):
    """Prepare for a network graph"""

    MainModel = EqualGold
    isRelevant = False      # See issue #549

    def add_to_context(self, context):
        def get_author(code):
            """Get the author id from the passim code"""
            author = 10000
            if "PASSIM" in code:
                author = int(code.replace("PASSIM", "").strip().split(".")[0])
            return author

        def add_to_dict(this_dict, item):
            if item != "":
                if not item in this_dict: 
                    this_dict[item] = 1
                else:
                    this_dict[item] += 1
                    
        oErr = ErrHandle()
        try:
            # Check validity
            if not self.userpermissions("r"):
                # Don't do anything
                return context

            if self.isRelevant:
                # Need to figure out who I am
                profile = Profile.get_user_profile(self.request.user.username)
                instance = self.obj

                networkslider = self.qd.get("networkslider", "1")            
                if isinstance(networkslider, str):
                    networkslider = int(networkslider)

                # Get the 'manuscript-corpus': the manuscripts in which the same kind of sermon like me is
                manu_list = SermonDescrEqual.objects.filter(super=instance).distinct().values("manu_id")
                manu_dict = {}
                for idx, manu in enumerate(manu_list):
                    manu_dict[manu['manu_id']] = idx + 1
                author_dict = {}

                lock_status = "new"
                # Set the lock, or return if we are busy with this ssg_corpus
                ssg_corpus = EqualGoldCorpus.objects.filter(profile=profile, ssg=instance).last()
                if ssg_corpus != None:
                    lock_status = ssg_corpus.status
                    # Check the status
                    if lock_status == "busy":
                        # Already busy
                        return context
                else:
                    # Need to create a lock
                    ssg_corpus = EqualGoldCorpus.objects.create(profile=profile, ssg=instance)
                    lock_status = "busy"

                # Save the status
                ssg_corpus.status = lock_status
                ssg_corpus.save()

                if lock_status == "new":
                    # Remove earlier corpora made by me based on this SSG
                    EqualGoldCorpus.objects.filter(profile=profile, ssg=instance).delete()

                    # Create a new one
                    ssg_corpus = EqualGoldCorpus.objects.create(profile=profile, ssg=instance, status="busy")

                if lock_status != "ready":

                    # Create an EqualGoldCorpus based on the SSGs in these manuscripts
                    ssg_list = SermonDescrEqual.objects.filter(manu__id__in=manu_list).order_by(
                        'super_id').distinct().values('super_id')
                    ssg_list_id = [x['super_id'] for x in ssg_list]
                    all_words = {}
                    with transaction.atomic():
                        for ssg in EqualGold.objects.filter(id__in=ssg_list_id):
                            # Add this item to the ssg_corpus
                            latin = {}
                            if ssg.incipit != None:
                                for item in ssg.srchincipit.replace(",", "").replace("…", "").split(" "): 
                                    add_to_dict(latin, item)
                                    add_to_dict(all_words, item)
                            if ssg.explicit != None:
                                for item in ssg.srchexplicit.replace(",", "").replace("…", "").split(" "): 
                                    add_to_dict(latin, item)
                                    add_to_dict(all_words, item)
                            # Get the name of the author
                            authorname = "empty" if ssg.author==None else ssg.author.name
                            # Get the scount
                            scount = ssg.scount
                            # Create new ssg_corpus item
                            obj = EqualGoldCorpusItem.objects.create(
                                corpus=ssg_corpus, words=json.dumps(latin), equal=ssg, 
                                authorname=authorname, scount=scount)

                    # What are the 100 MFWs in all_words?
                    mfw = [dict(word=k, count=v) for k,v in all_words.items()]
                    mfw_sorted = sorted(mfw, key = lambda x: -1 * x['count'])
                    mfw_cento = mfw_sorted[:100]
                    mfw = []
                    for item in mfw_cento: mfw.append(item['word'])
                    # Add this list to the ssg_corpus
                    ssg_corpus.mfw = json.dumps(mfw)
                    ssg_corpus.status = "ready"
                    ssg_corpus.save()

                node_list, link_list, max_value = self.do_manu_method(ssg_corpus, manu_list, networkslider)


                # Add the information to the context in data
                context['data'] = dict(node_list=node_list, 
                                       link_list=link_list,
                                       watermark=get_watermark(),
                                       max_value=max_value,
                                       networkslider=networkslider,
                                       legend="AF network")
            
                # Can remove the lock
                ssg_corpus.status = "ready"
                ssg_corpus.save()


        except:
            msg = oErr.get_error_message()
            oErr.DoError("EqualGoldGraph/add_to_context")

        return context

    def do_manu_method(self, ssg_corpus, manu_list, min_value):
        """Calculation like Manuscript_Transmission_Of_se172
        
        The @min_value is the minimum link-value the user wants to see
        """
        oErr = ErrHandle()
        node_list = []
        link_list = []
        max_value = 0       # Maximum number of manuscripts in which an SSG occurs
        max_scount = 1      # Maximum number of sermons associated with one SSG
        manu_count = []

        def get_nodes(crp):
            nodes = []
            for idx, item in enumerate(crp.target_ints):
                oNode = dict(group=item, author=crp.target_idx[item], id=crp.titles[idx])
                nodes.append(oNode)
            return nodes

        try:
            # Create a pystyl-corpus object (see above)
            sty_corpus = Corpus(texts=[], titles=[], target_ints=[], target_idx=[])

            ssg_dict = {}
            link_dict = {}
            scount_dict = {}
            node_listT = []
            link_listT = []

            # Initialize manu_count: the number of SSG co-occurring in N manuscripts
            for item in manu_list:
                manu_count.append(0)

            # Walk the ssg_corpus: each SSG is one 'text', having a title and a category (=author code)
            for idx, item in enumerate(EqualGoldCorpusItem.objects.filter(corpus=ssg_corpus).values(
                'words', 'authorname', 'scount', 'equal__code', 'equal__id')):
                # Determine the name for this row
                category = item['authorname']
                code = item['equal__code']
                if code == None or code == "" or not " " in code or not "." in code:
                    title = "eqg{}".format(item['equal__id'])
                else:
                    title = code.split(" ")[1]
                # The text = the words
                text = " ".join(json.loads(item['words']))
                
                # the scount and store it in a dictionary
                scount_dict[title] = item['scount']
                if item['scount'] > max_scount:
                    max_scount = item['scount']

                # Add the text to the corpus
                if title in sty_corpus.titles:
                    ssg_id = -1
                    bFound = False
                    for k,v in ssg_dict.items():
                        if v == title:
                            ssg_id = k
                            bFound = True
                            break
                    oErr.Status("EqualGoldGraph/do_manu_method: attempt to add same title '{}' for {} and {}".format(
                        title, ssg_id, item['equal__id']))
                else:
                    # Also make sure to buidl an SSG-dictionary
                    ssg_dict[item['equal__id']] = title

                    sty_corpus.add_text(text, title, category)

            # Get a list of nodes
            node_listT = get_nodes(sty_corpus)

            # Walk the manuscripts
            for manu_item in manu_list:
                manu_id = manu_item["manu_id"]
                # Get a list of all SSGs in this manuscript
                ssg_list = SermonDescrEqual.objects.filter(manu__id=manu_id).order_by(
                    'super_id').distinct().values('super_id')
                ssg_list_id = [x['super_id'] for x in ssg_list]
                # evaluate links between a source and target SSG
                for idx_s, source_id in enumerate(ssg_list_id):
                    # sanity check
                    if source_id in ssg_dict:
                        # Get the title of the source
                        source = ssg_dict[source_id]
                        for idx_t in range(idx_s+1, len(ssg_list_id)-1):
                            target_id = ssg_list_id[idx_t]
                            # Double check
                            if target_id in ssg_dict:
                                # Get the title of the target
                                target = ssg_dict[target_id]
                                # Retrieve or create a link from the link_listT
                                link_code = "{}_{}".format(source_id, target_id)
                                if link_code in link_dict:
                                    oLink = link_listT[link_dict[link_code]]
                                else:
                                    oLink = dict(source=source, source_id=source_id,
                                                 target=target, target_id=target_id,
                                                 value=0)
                                    link_listT.append(oLink)
                                    link_dict[link_code] = len(link_listT) - 1
                                # Now add to the value
                                oLink['value'] += 1
                                if oLink['value'] > max_value:
                                    max_value = oLink['value']
            
            # Only accept the links that have a value >= min_value
            node_dict = []
            for oItem in link_listT:
                if oItem['value'] >= min_value:
                    link_list.append(copy.copy(oItem))
                    # Take note of the nodes
                    src = oItem['source']
                    dst = oItem['target']
                    if not src in node_dict: node_dict.append(src)
                    if not dst in node_dict: node_dict.append(dst)
            # Walk the nodes
            for oItem in node_listT:
                if oItem['id'] in node_dict:
                    oItem['scount'] = 100 * scount_dict[oItem['id']] / max_scount
                    node_list.append(copy.copy(oItem))

 
        except:
            msg = oErr.get_error_message()
            oErr.DoError("do_hier_method1")

        return node_list, link_list, max_value
    

class EqualGoldPca(BasicPart):
    """Principle component analysis of a set of SSGs"""

    MainModel = EqualGold

    def add_to_context(self, context):

        names_list = [x.lower() for x in COMMON_NAMES]

        def get_author(code):
            """Get the author id from the passim code"""
            author = 10000
            if "PASSIM" in code:
                author = int(code.replace("PASSIM", "").strip().split(".")[0])
            return author

        def add_to_dict(this_dict, item):
            if item != "":
                if not item in this_dict: 
                    this_dict[item] = 1
                else:
                    this_dict[item] += 1
                    
        oErr = ErrHandle()
        try:
            # Check validity
            if not self.userpermissions("r"):
                # Don't do anything
                return context

            # Need to figure out who I am
            profile = Profile.get_user_profile(self.request.user.username)
            instance = self.obj

            # Get the 'manuscript-corpus': the manuscripts in which the same kind of sermon like me is
            manu_list = SermonDescrEqual.objects.filter(super=instance).distinct().values("manu_id")
            manu_dict = {}
            for idx, manu in enumerate(manu_list):
                manu_dict[manu['manu_id']] = idx + 1
            author_dict = {}

            lock_status = "new"
            # Set the lock, or return if we are busy with this ssg_corpus
            ssg_corpus = EqualGoldCorpus.objects.filter(profile=profile, ssg=instance).last()
            if ssg_corpus != None:
                lock_status = ssg_corpus.status
                # Check the status
                if lock_status == "busy":
                    # Already busy
                    return context
            else:
                # Need to create a lock
                ssg_corpus = EqualGoldCorpus.objects.create(profile=profile, ssg=instance)
                lock_status = "busy"

            # Save the status
            ssg_corpus.status = lock_status
            ssg_corpus.save()

            if lock_status == "new":
                # Remove earlier corpora made by me based on this SSG
                EqualGoldCorpus.objects.filter(profile=profile, ssg=instance).delete()

                # Create a new one
                ssg_corpus = EqualGoldCorpus.objects.create(profile=profile, ssg=instance, status="busy")

            if lock_status != "ready":

                # Create an EqualGoldCorpus based on the SSGs in these manuscripts
                ssg_list = SermonDescrEqual.objects.filter(manu__id__in=manu_list).order_by(
                    'super_id').distinct().values('super_id')
                ssg_list_id = [x['super_id'] for x in ssg_list]
                all_words = {}
                with transaction.atomic():
                    for ssg in EqualGold.objects.filter(id__in=ssg_list_id):
                        # Add this item to the ssg_corpus
                        latin = {}
                        if ssg.incipit != None:
                            for item in ssg.srchincipit.replace(",", "").replace("…", "").split(" "): 
                                add_to_dict(latin, item)
                                add_to_dict(all_words, item)
                        if ssg.explicit != None:
                            for item in ssg.srchexplicit.replace(",", "").replace("…", "").split(" "): 
                                add_to_dict(latin, item)
                                add_to_dict(all_words, item)
                        # Get the name of the author
                        authorname = "empty" if ssg.author==None else ssg.author.name
                        # Create new ssg_corpus item
                        obj = EqualGoldCorpusItem.objects.create(
                            corpus=ssg_corpus, words=json.dumps(latin), equal=ssg, authorname=authorname)

                # What are the 100 MFWs in all_words?
                mfw = [dict(word=k, count=v) for k,v in all_words.items()]
                mfw_sorted = sorted(mfw, key = lambda x: -1 * x['count'])
                mfw_cento = mfw_sorted[:100]
                mfw = []
                for item in mfw_cento: mfw.append(item['word'])
                # Add this list to the ssg_corpus
                ssg_corpus.mfw = json.dumps(mfw)
                ssg_corpus.status = "ready"
                ssg_corpus.save()

            node_list, link_list, max_value = self.do_hier_method3(ssg_corpus, names_list)


            # Add the information to the context in data
            context['data'] = dict(node_list=node_list, 
                                   link_list=link_list,
                                   watermark=get_watermark(),
                                   max_value=max_value,
                                   legend="AF network")
            
            # Can remove the lock
            ssg_corpus.status = "ready"
            ssg_corpus.save()

        except:
            msg = oErr.get_error_message()
            oErr.DoError("EqualGoldPca/add_to_context")

        return context

    def do_hier_method3(self, ssg_corpus, names_list):
        """Calculate distance matrix with PYSTYL, do the rest myself"""
        oErr = ErrHandle()
        node_list = []
        link_list = []
        max_value = 0

        def dm_to_leo(matrix, crp):
            links = []
            i = 0
            maxv = 0
            for row_id, row in enumerate(matrix):
                # Calculate the link
                minimum = None
                min_id = -1
                for col_idx in range(row_id+1, len(row)-1):
                    value = row[col_idx]
                    if minimum == None:
                        if value > 0: minimum = value
                    elif value < minimum:
                        minimum = value
                        min_id = col_idx
                if minimum != None and min_id >=0:
                    # Create a link
                    oLink = dict(source_id=row_id, source = crp.titles[row_id],
                                 target_id=min_id, target = crp.titles[min_id],
                                 value=minimum)
                    links.append(oLink)
                    # Keep track of max_value
                    if minimum > maxv: 
                        maxv = minimum

            return links, maxv

        def get_nodes(crp):
            nodes = []
            for idx, item in enumerate(crp.target_ints):
                oNode = dict(group=item, author=crp.target_idx[item], id=crp.titles[idx], scount=5)
                nodes.append(oNode)
            return nodes

        do_example = False
        try:
            # Create a pystyl-corpus object (see above)
            sty_corpus = Corpus(texts=[], titles=[], target_ints=[], target_idx=[])

            ssg_dict = {}

            # Walk the ssg_corpus: each SSG is one 'text', having a title and a category (=author code)
            for idx, item in enumerate(EqualGoldCorpusItem.objects.filter(corpus=ssg_corpus).values(
                'words', 'authorname', 'equal__code', 'equal__id')):
                # Determine the name for this row
                category = item['authorname']
                code = item['equal__code']
                if code == None or code == "" or not " " in code or not "." in code:
                    title = "eqg{}".format(item['equal__id'])
                else:
                    title = code.split(" ")[1]
                # The text = the words
                text = " ".join(json.loads(item['words']))

                # Add the text to the corpus
                if title in sty_corpus.titles:
                    ssg_id = -1
                    bFound = False
                    for k,v in ssg_dict.items():
                        if v == title:
                            ssg_id = k
                            bFound = True
                            break
                    oErr.Status("EqualGoldGraph/do_manu_method: attempt to add same title '{}' for {} and {}".format(
                        title, ssg_id, item['equal__id']))
                else:
                    # Also make sure to buidl an SSG-dictionary
                    ssg_dict[item['equal__id']] = title

                    sty_corpus.add_text(text, title, category)

            # We now 'have' the corpus, so we can work with it...
            sty_corpus.preprocess(alpha_only=True, lowercase=True)
            sty_corpus.tokenize()
            
            # REmove the common names
            sty_corpus.remove_tokens(rm_tokens=names_list, rm_pronouns=False)

            # Vectorize the corpus
            sty_corpus.vectorize(mfi=200, ngram_type="word", ngram_size=1, vector_space="tf_std")

            # Get a list of nodes
            node_list = get_nodes(sty_corpus)

            # Create a distance matrix
            dm = distance_matrix(sty_corpus, "minmax")

            # Convert the distance matrix into a list of 'nearest links'
            link_list, max_value = dm_to_leo(dm, sty_corpus) 

            # Convert the cluster_tree into a node_list and a link_list (i.e. get the list of edges)
            iRead = 1

        except:
            msg = oErr.get_error_message()
            oErr.DoError("do_hier_method1")

        return node_list, link_list, max_value


class EqualGoldAttr(BasicPart):
    """Division of attributed authors in manuscripts related to this SSG"""

    MainModel = EqualGold

    def add_to_context(self, context):
     
        oErr = ErrHandle()
        try:
            # Check validity
            if not self.userpermissions("r"):
                # Don't do anything
                return context

            # Need to figure out who I am
            profile = Profile.get_user_profile(self.request.user.username)
            instance = self.obj

            # Get a list of SermonDescr linking to this EqualGold
            # NEW: exclude templates
            qs = SermonDescrEqual.objects.filter(super=instance).exclude(sermon__mtype="tem")
            count_sermon = qs.count()
            # Only continue if there are some results
            if count_sermon > 0:
                # Get all the attributed authors
                lst_attr_author = [x['sermon__author__name'] for x in qs.filter(sermon__author__isnull=False).values('sermon__author__name')]
                # Create a list of the individual ones
                lst_unique = sorted(list(set(lst_attr_author)))
                # Create a list of numbers
                lst_data = []
                attr_total = 0
                for attr_name in lst_unique:
                    attr_count = qs.filter(sermon__author__name=attr_name).count()
                    author = qs.filter(sermon__author__name=attr_name).first().sermon.author
                    url = reverse("author_details", kwargs={'pk': author.id})
                    oData = dict(name=attr_name, value=attr_count, total=count_sermon, url=url)
                    lst_data.append(oData)
                    attr_total += attr_count
                # Add the number of unidentified authors
                other_count = count_sermon - attr_total
                if other_count > 0:
                    lst_data.append(dict(name="not applicable", value=other_count, total=count_sermon, url=None))

                context['data'] = dict(attr_author=lst_data)
        except:
            msg = oErr.get_error_message()
            oErr.DoError("EqualGoldAttr/add_to_context")

        return context


class EqualGoldOrigin(BasicPart):
    """Division of origin locations in manuscripts' codicological units related to this SSG"""

    MainModel = EqualGold

    def add_to_context(self, context):
     
        oErr = ErrHandle()
        try:
            # Check validity
            if not self.userpermissions("r"):
                # Don't do anything
                return context

            # Need to figure out who I am
            profile = Profile.get_user_profile(self.request.user.username)
            instance = self.obj

            # Get a list of SermonDescr linking to this EqualGold
            qs_codico = [x.sermon.msitem.codico for x in SermonDescrEqual.objects.filter(super=instance).exclude(sermon__mtype="tem").order_by(
                'sermon__msitem__codico__id')]
            if len(qs_codico) > 0:
                # Get to the origins and distill countries
                lst_country = []
                for obj in qs_codico:
                    lcountry = "no origin defined"
                    for origin in obj.origins.all():
                        location = origin.location
                        if not location is None:
                            if location.loctype.name == "country":
                                lcountry = location.name
                            elif not location.lcountry is None:
                                lcountry = location.lcountry.name
                            else:
                                lcountry = "Country of location: {}".format( location.name)
                        else:
                            lcountry = "Country of origin: {}".format( origin.name)
                    lst_country.append(lcountry)
                # Get the unique countries
                lst_unique = sorted(list(set(lst_country)))

                # Create a list of numbers
                lst_data = []
                count_total = len(lst_country)
                for country_name in lst_unique:
                    country_count = lst_country.count(country_name)
                    url = ""
                    oData = dict(name=country_name, value=country_count, total=count_total, url=url)
                    lst_data.append(oData)


                context['data'] = dict(origin_country=lst_data)
        except:
            msg = oErr.get_error_message()
            oErr.DoError("EqualGoldOrigin/add_to_context")

        return context


class EqualGoldChrono(BasicPart):
    """Division date ranges in sermons' codicological units related to this SSG"""

    MainModel = EqualGold

    def add_to_context(self, context):
     
        oErr = ErrHandle()
        try:
            # Check validity
            if not self.userpermissions("r"):
                # Don't do anything
                return context

            # Need to figure out who I am
            profile = Profile.get_user_profile(self.request.user.username)
            instance = self.obj

            # Other initializations

            # Get a list of SermonDescr linking to this EqualGold
            qs_codico = [x['sermon__msitem__codico__id'] for x in SermonDescrEqual.objects.filter(super=instance).exclude(
                sermon__mtype="tem").order_by('sermon__msitem__codico__id').values('sermon__msitem__codico__id')]
            if len(qs_codico) > 0:
                # Get to the date ranges
                weight_year = {}
                # Get the overall minimum and maximum year
                qExcl = ( Q(codico__yearstart=0) & Q(codico__yearfinish__gte=2000) ) | ( Q(codico__yearstart=100) & Q(codico__yearfinish=100) )
                qs = Daterange.objects.exclude(qExcl).filter(codico__id__in=qs_codico)
                if qs.count() > 0:
                    # Note min_year and max_year
                    min_year = qs.order_by('yearstart').first().yearstart
                    max_year = qs.order_by('-yearfinish').first().yearfinish

                    # Initialize dictionary of cumulative weight
                    for year in range(min_year, max_year + 1): 
                        weight_year[year] = 0
                
                for obj in qs_codico:
                    # Filter out two "no date" scenario's:
                    # 1 - min_year '0', max_year >= 2000
                    # 2 - min_year/max_year '100'
                    # Note the number of date-ranges for this codico
                    qExcl = ( Q(yearstart=0) & Q(yearfinish__gte=2000) ) | ( Q(yearstart=100) & Q(yearfinish=100) )
                    # qs = obj.codico_dateranges.exclude(qExcl)
                    qs = Daterange.objects.filter(codico_id=obj).exclude(qExcl)
                    num_dr = qs.count()

                    # We can only continue if there are *any* datings
                    if num_dr > 0:
                        # Go through each date-range
                        for oDr in qs.values('yearstart', 'yearfinish'):
                            yearstart = oDr.get('yearstart', -1)
                            yearfinish = oDr.get('yearfinish', -1)
                            if yearstart < 0 or yearfinish < 0:
                                # We have a problem
                                iStop = 1
                                pass
                            else:
                                #yearstart = min(min_year, yearstart)
                                #yearfinish = max(max_year, yearfinish)
                                # Calculate the weight
                                weight = 1 / (num_dr * (yearfinish - yearstart + 1) )
                                # Add the weight to all relevant years
                                for year in range(yearstart, yearfinish + 1):
                                    weight_year[year] += weight
                
                # Turn this into an ordered list
                lst_data = [dict(date=x[0], value=x[1]) for x in sorted(weight_year.items())]

                # The data expected is: date (year), value (our cumulative weight)
                context['data'] = dict(codico_chrono=lst_data)
        except:
            msg = oErr.get_error_message()
            oErr.DoError("EqualGoldChrono/add_to_context")

        return context


# ============================= downloads ==========================================================


class CollectionDownload(BasicPart):
    """Facilitate downloading datasets to some extent"""

    MainModel = Collection
    template_name = "seeker/download_status.html"
    action = "download"         # This is purely a download function
    dtype = "csv"               # downloadtype
    spec_download = True        # Indicate that we should use the [specification]
    downloadname = "Dataset"    # Part of the name of the downloaded dataset
    model = None                # This is assigned the correct model, depending on the 

    def custom_init(self):
        """Calculate stuff"""
        
        oErr = ErrHandle()
        oModel = dict(manu=Manuscript, sermo=SermonDescr, gold=SermonGold, super=EqualGold)
        oAbbr = dict(manu="ms", sermo="mf", gold="sg", super="af")
        try:
            # Process the downloadtype or dtype - but actually irrelevant
            dt = self.qd.get('downloadtype', "")
            if dt is None or dt == "":
                dt = self.qd.get("dtype")
            if dt != None and dt != '':
                self.dtype = dt

            # Find out who I am and set my [model]
            instance = self.obj
            # What type am I?
            coltype = instance.type
            # Set model, depending on coltype
            cls_this = oModel.get(coltype)
            if not cls_this is None:
                self.model = cls_this
            sAbbr = oAbbr.get(coltype)
            if sAbbr is None: sAbbr = ""

            # Adapt my downloadname to include the dataset id etc
            sDate = get_current_datetime().strftime("%Y-%m-%dT%H:%M:%S")
            self.downloadname = "Dataset_{}{}-{}".format(sAbbr, instance.id, sDate)
        except:
            msg = oErr.get_error_message()
            oErr.DoError("CollectionDownload/custom_init")

    def add_to_context(self, context):
        # Provide search URL and search name
        return context

    def get_queryset(self, prefix):
        """The queryset closely follows issue #716
        
        The list of M/S/SG/SSG is given, depending on the collection type
        This goes via:
          M   CollectionMan
          S   CollectionSerm
          SG  CollectionGold
          SSG CollectionSuper
        """

        def may_download(qs, size, lst_contains, is_editor, my_projects, lst_bad=[]):
            """Determine if someone may actually download"""

            oErr = ErrHandle()
            bResult = False
            max_for_user = 1000
            try:
                # size = len(qs)  # qs.count()
                if size < max_for_user:
                    bResult = True
                else:
                    # Is this an editor?
                    if is_editor:
                        # Check for overal appliance
                        iBad = 0
                        for item in lst_contains:
                            if not item in my_projects:
                                iBad += 1
                                lst_bad.append(item)
                        if iBad == 0:
                            bResult = True
                    else:
                        # since this is not an editor and the number is higher than [max_for_user]; deny
                        pass
            except:
                msg = oErr.get_error_message()
                oErr.DoError("may_download")
            return bResult

        oErr = ErrHandle()
        qs = None
        lst_item = []
        lst_forb = []
        max_number = None
        my_projects = None
        is_editor = False
        str_warning = '<h3>ERROR</h3><p>Regular users can only download datasets of max. 1000 items.</p> \
            <p>If you would like access to a larger dataset within PASSIM, \
            please contact the <a href="mailto:{}">moderator</a></p>'
        str_moderator = "shariboodts"
        try:
            user = self.request.user
            if not user is None:
                # Find out who this is
                profile = user.user_profiles.first()
                # Get the projects I am part of
                my_projects = [ x['id'] for x in profile.editprojects.all().values('id')]
                
                # Get the Collection object
                instance = self.obj
                if instance is None:
                    # There is no object specified
                    pass
                else:
                    # There is an object, so figure out what this is
                    scope = instance.scope      # I.e: priv, team, publ
                    coltype = instance.type     # I.e: sermo, gold, manu, super
                    settype = instance.settype  # I.e: pd, hc

                    # Figure out whether this user is allowed to download how much
                    is_editor = user_is_ingroup(self.request, app_editor)
                    has_permission = False

                    # Get a list of all the relevant objects
                    if coltype == "manu":
                        # Get all the items in this collection
                        qs = instance.manuscript_col.order_by('order')
                        size = qs.count()
                        prj_ids = [x['manuscript__projects'] for x in qs.values('manuscript__projects').distinct()]
                        has_permission = may_download(qs, size, prj_ids, is_editor, my_projects, lst_forb)
                        if has_permission:
                            qs = [x.manuscript for x in qs]
                        else:
                            qs = Manuscript.objects.none()
                    elif coltype == "sermo":
                        # Get all the items in this collection
                        qs = instance.sermondescr_col.order_by('order')
                        size = qs.count()
                        prj_ids = [x['sermon__projects'] for x in qs.values('sermon__projects').distinct()]
                        has_permission = may_download(qs, size, prj_ids, is_editor, my_projects, lst_forb)
                        if has_permission:
                            qs = [x.sermon for x in qs]
                        else:
                            qs = SermonDescr.objects.none()
                    elif coltype == "gold":
                        # Get all the items in this collection
                        qs = instance.gold_col.order_by('order')
                        size = qs.count()
                        prj_ids = [x['gold__projects'] for x in qs.values('gold__projects').distinct()]
                        has_permission = may_download(qs, size, prj_ids, is_editor, my_projects, lst_forb)
                        if has_permission:
                            qs = [x.gold for x in qs]
                        else:
                            qs = SermonGold.objects.none()
                    elif coltype == "super":
                        # Get all the items in this collection
                        qs = instance.super_col.order_by('order')
                        size = qs.count()
                        prj_ids = [x['super__projects'] for x in instance.super_col.all().values('super__projects').distinct()]
                        has_permission = may_download(qs, size, prj_ids, is_editor, my_projects, lst_forb)
                        if has_permission:
                            qs = [x.super for x in qs]
                        else:
                            qs = EqualGold.objects.none()

                    if not has_permission:
                        # Get the moderator's email address
                        mod = Profile.objects.filter(user__username=str_moderator).first()
                        email = mod.user.email
                        self.arErr.append(str_warning.format(email))
                        if len(lst_forb) > 0:
                            # Figure out which projects this are
                            lHtml = [x['name'] for x in Project2.objects.filter(id__in=lst_forb).values('name')]
                            self.arErr.append("<p>Collection contains data from projects you have no permission for:</p><ul>")
                            for sName in lHtml:
                                self.arErr.append("<li><code>{}</code></li>".format(sName))
                            self.arErr.append("</ul>")

        except:
            msg = oErr.get_error_message()
            oErr.DoError("CollectionDownload/get_queryset")

        return qs



