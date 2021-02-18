"""
Definition of visualization views for the SEEKER app.
"""

from django.db import transaction
from django.db.models import Q, Prefetch, Count, F
import pandas as pd 
from sklearn.decomposition import PCA
from sklearn.preprocessing import StandardScaler
import json
import copy
import itertools

# ======= imports from my own application ======
from passim.utils import ErrHandle
from passim.basic.views import BasicPart
from passim.seeker.models import get_crpp_date, get_current_datetime, process_lib_entries, adapt_search, get_searchable, get_now_time, \
    add_gold2equal, add_equal2equal, add_ssg_equal2equal, get_helptext, Information, Country, City, Author, Manuscript, \
    User, Group, Origin, SermonDescr, MsItem, SermonHead, SermonGold, SermonDescrKeyword, SermonDescrEqual, Nickname, NewsItem, \
    SourceInfo, SermonGoldSame, SermonGoldKeyword, EqualGoldKeyword, Signature, Ftextlink, ManuscriptExt, \
    ManuscriptKeyword, Action, EqualGold, EqualGoldLink, Location, LocationName, LocationIdentifier, LocationRelation, LocationType, \
    ProvenanceMan, Provenance, Daterange, CollOverlap, BibRange, Feast, Comment, SermonEqualDist, \
    Project, Basket, BasketMan, BasketGold, BasketSuper, Litref, LitrefMan, LitrefCol, LitrefSG, EdirefSG, Report, SermonDescrGold, \
    Visit, Profile, Keyword, SermonSignature, Status, Library, Collection, CollectionSerm, \
    CollectionMan, CollectionSuper, CollectionGold, UserKeyword, Template, ManuscriptCorpus, ManuscriptCorpusLock, \
    EqualGoldCorpus, EqualGoldCorpusItem, \
   LINK_EQUAL, LINK_PRT, LINK_BIDIR, LINK_PARTIAL, STYPE_IMPORTED, STYPE_EDITED, LINK_UNSPECIFIED
from passim.stylo.corpus import Corpus
from passim.stylo.analysis import bootstrapped_distance_matrices, hierarchical_clustering, distance_matrix

# ======= from RU-Basic ========================
from passim.basic.views import BasicList, BasicDetails, make_search_list, add_rel_item


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


class DrawPieChart(BasicPart):
    """Fetch data for a particular type of pie-chart for the home page
    
    Current types: 'sermo', 'super', 'manu'
    """

    pass


class EqualGoldTrans(BasicPart):
    """Prepare for a network graph"""


    MainModel = EqualGold

    def add_to_context(self, context):

        def add_to_dict(this_dict, item):
            if item != "":
                if not item in this_dict: 
                    this_dict[item] = 1
                else:
                    this_dict[item] += 1
                    
        oErr = ErrHandle()
        try:
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

            # author_dict = {}

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
                        ## Add author to dictionary
                        #if not authorname in author_dict: author_dict[authorname] = 0
                        #author_dict[authorname] += 1

                # Add this list to the ssg_corpus
                ssg_corpus.status = "ready"
                ssg_corpus.save()
                ## Create list of authors
                #author_list = [dict(category=k, count=v) for k,v in author_dict.items()]
                #author_list = sorted(author_list, key=lambda x: (-1 * x['count'], x['category'].lower()))

            node_list, link_list, author_list, max_value = self.do_manu_method(ssg_corpus, manu_list, networkslider)


            # Add the information to the context in data
            context['data'] = dict(node_list=node_list, 
                                   link_list=link_list,
                                   author_list=author_list,
                                   max_value=max_value,
                                   networkslider=networkslider,
                                   legend="SSG network")
            
            # Can remove the lock
            ssg_corpus.status = "ready"
            ssg_corpus.save()


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
                sig_obj = Signature.objects.filter(gold__equal__id=ssg_id).order_by('-editype', 'code').first()
                sig = "" if sig_obj == None else sig_obj.code

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
            oErr.DoError("do_manu_method")

        return node_list, link_list,  author_list, max_value


class EqualGoldGraph(BasicPart):
    """Prepare for a network graph"""

    MainModel = EqualGold

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
                                   max_value=max_value,
                                   networkslider=networkslider,
                                   legend="SSG network")
            
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
                    # Get the title of the source
                    source = ssg_dict[source_id]
                    for idx_t in range(idx_s+1, len(ssg_list_id)-1):
                        target_id = ssg_list_id[idx_t]
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
                                   max_value=max_value,
                                   legend="SSG network")
            
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
