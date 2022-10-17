"""
Adaptations of the database that are called up from the (list)views in the SEEKER app.
"""

from django.db import transaction
import re
import json
import os
import csv
import pandas as pd
from passim.settings import MEDIA_DIR

# ======= imports from my own application ======
from passim.utils import ErrHandle
from passim.seeker.models import get_crpp_date, get_current_datetime, process_lib_entries, get_searchable, get_now_time, \
    add_gold2equal, add_equal2equal, add_ssg_equal2equal, get_helptext, Information, Country, City, Author, Manuscript, \
    User, Group, Origin, SermonDescr, MsItem, SermonHead, SermonGold, SermonDescrKeyword, SermonDescrEqual, Nickname, NewsItem, \
    SourceInfo, SermonGoldSame, SermonGoldKeyword, EqualGoldKeyword, Signature, Ftextlink, ManuscriptExt, \
    ManuscriptKeyword, Action, EqualGold, EqualGoldLink, Location, LocationName, LocationIdentifier, LocationRelation, LocationType, \
    ProvenanceMan, Provenance, Daterange, CollOverlap, BibRange, Feast, Comment, SermonEqualDist, \
    Basket, BasketMan, BasketGold, BasketSuper, Litref, LitrefMan, LitrefCol, LitrefSG, EdirefSG, Report, SermonDescrGold, \
    Visit, Profile, Keyword, SermonSignature, Status, Library, Collection, CollectionSerm, \
    CollectionMan, CollectionSuper, CollectionGold, UserKeyword, Template, \
    ManuscriptCorpus, ManuscriptCorpusLock, EqualGoldCorpus, \
    Codico, OriginCod, CodicoKeyword, ProvenanceCod, Project2, ManuscriptProject, SermonDescrProject, \
    CollectionProject, EqualGoldProject, OnlineSources, \
    get_reverse_spec, LINK_EQUAL, LINK_PRT, LINK_BIDIR, LINK_PARTIAL, STYPE_IMPORTED, STYPE_EDITED, LINK_UNSPECIFIED


adaptation_list = {
    "manuscript_list": ['sermonhierarchy', 'msitemcleanup', 'locationcitycountry', 'templatecleanup', 
                        'feastupdate', 'codicocopy', 'passim_project_name_manu', 'doublecodico',
                        'codico_origin', 'import_onlinesources', 'dateranges'],
    'sermon_list': ['nicknames', 'biblerefs', 'passim_project_name_sermo'],
    'sermongold_list': ['sermon_gsig'],
    'equalgold_list': ['author_anonymus', 'latin_names', 'ssg_bidirectional', 's_to_ssg_link', 
                       'hccount', 'scount', 'ssgcount', 'ssgselflink', 'add_manu', 'passim_code', 'passim_project_name_equal', 
                       'atype_def_equal', 'atype_acc_equal', 'passim_author_number'],
    'provenance_list': ['manuprov_m2m'],
    "collhist_list": ['passim_project_name_hc', 'coll_ownerless', 'litref_check']    
    }


def listview_adaptations(lv):
    """Perform adaptations specific for this listview"""

    oErr = ErrHandle()
    try:
        if lv in adaptation_list:
            for adapt in adaptation_list.get(lv):
                sh_done  = Information.get_kvalue(adapt)
                if sh_done == None or sh_done != "done":
                    # Do the adaptation, depending on what it is
                    method_to_call = "adapt_{}".format(adapt)
                    bResult, msg = globals()[method_to_call]()
                    if bResult:
                        # Success
                        Information.set_kvalue(adapt, "done")
    except:
        msg = oErr.get_error_message()
        oErr.DoError("listview_adaptations")

# =========== Part of manuscript_list ==================
def adapt_sermonhierarchy():
    # Perform adaptations
    bResult, msg = Manuscript.adapt_hierarchy()
    return bResult, msg

def adapt_dateranges():
    oErr = ErrHandle()
    bResult = True
    msg = ""

    try:
        with transaction.atomic():
            # Walk all manuscripts
            for manu in Manuscript.objects.all():
                yearstart = 0
                yearfinish = 3000
                # Find the best fit for the yearstart
                lst_dateranges = Daterange.objects.filter(codico__manuscript=manu).order_by('yearstart').values('yearstart')
                if len(lst_dateranges) > 0:
                    yearstart = lst_dateranges[0]['yearstart']
                # Find the best fit for the yearfinish
                lst_dateranges = Daterange.objects.filter(codico__manuscript=manu).order_by('-yearfinish').values('yearfinish')
                if len(lst_dateranges) > 0:
                    yearfinish = lst_dateranges[0]['yearfinish']
                bNeedSaving = False
                if yearstart != manu.yearstart:
                    manu.yearstart = yearstart
                    bNeedSaving = True
                if yearfinish != manu.yearfinish:
                    manu.yearfinish = yearfinish
                    bNeedSaving = True
                if bNeedSaving:
                    manu.save()
    except:
        bResult = False
        msg = oErr.get_error_message()
    return bResult, msg


def adapt_msitemcleanup():
    method = "UseAdaptations"
    method = "RemoveOrphans"
    oErr = ErrHandle()
    bResult = True
    msg = ""
    
    try:
        if method == "RemoveOrphans":
            # Walk all manuscripts
            for manu in Manuscript.objects.all():
                manu.remove_orphans()
        elif method == "UseAdaptations":
            # Perform adaptations
            del_id = []
            qs = MsItem.objects.annotate(num_heads=Count('itemheads')).annotate(num_sermons=Count('itemsermons'))
            for obj in qs.filter(num_heads=0, num_sermons=0):
                del_id.append(obj.id)
            # Remove them
            MsItem.objects.filter(id__in=del_id).delete()
    except:
        bResult = False
        msg = oErr.get_error_message()
    return bResult, msg

def adapt_locationcitycountry():
    oErr = ErrHandle()
    bResult = True
    msg = ""
    
    try:
        with transaction.atomic():
            for obj in Location.objects.all():
                bNeedSaving = False
                lcountry = obj.partof_loctype("country")
                lcity = obj.partof_loctype("city")
                if obj.lcountry == None and lcountry != None:
                    obj.lcountry = lcountry
                    bNeedSaving = True
                if obj.lcity == None and lcity != None:
                    obj.lcity = lcity
                    bNeedSaving = True
                if bNeedSaving:
                    obj.save()
    except:
        bResult = False
        msg = oErr.get_error_message()
    return bResult, msg

def adapt_templatecleanup():
    oErr = ErrHandle()
    bResult = True
    msg = ""
    
    try:
        # Get a list of all the templates and the manuscript id's in it
        template_manu_id = [x.manu.id for x in Template.objects.all().order_by('manu__id')]

        # Get all manuscripts that are supposed to be template, but whose ID is not in [templat_manu_id]
        qs_manu = Manuscript.objects.filter(mtype='tem').exclude(id__in=template_manu_id)

        # Remove these manuscripts (and their associated msitems, sermondescr, sermonhead
        qs_manu.delete()
    except:
        bResult = False
        msg = oErr.get_error_message()
    return bResult, msg

def adapt_feastupdate():
    oErr = ErrHandle()
    bResult = True
    msg = ""
    
    try:
        # Get a list of all the templates and the manuscript id's in it
        feast_lst = [x['feast'] for x in SermonDescr.objects.exclude(feast__isnull=True).order_by('feast').values('feast').distinct()]
        feast_set = {}
        # Create the feasts
        for feastname in feast_lst:
            obj = Feast.objects.filter(name=feastname).first()
            if obj == None:
                obj = Feast.objects.create(name=feastname)
            feast_set[feastname] = obj

        with transaction.atomic():
            for obj in SermonDescr.objects.filter(feast__isnull=False):
                obj.feast = feast_set[obj.feast]
                obj.save()
    except:
        bResult = False
        msg = oErr.get_error_message()
    return bResult, msg

def adapt_codicocopy(oStatus=None):
    """Create Codico's and copy Manuscript information to Codico"""
    oErr = ErrHandle()
    bResult = True
    msg = ""
    count_add = 0       # Codico layers added
    count_copy = 0      # Codico layers copied
    count_tem = 0       # Template codico changed
    oBack = dict(status="ok", msg="")

    try:
        # TODO: add code here and change to True
        bResult = False

        # Walk through all manuscripts (that are not templates)
        manu_lst = []
        for manu in Manuscript.objects.filter(mtype__iregex="man|tem"):
            # Check if this manuscript already has Codico's
            if manu.manuscriptcodicounits.count() == 0:
                # Note that Codico's must be made for this manuscript
                manu_lst.append(manu.id)
        # Status message
        oBack['total'] = "Manuscripts without codico: {}".format(len(manu_lst))
        if oStatus != None: oStatus.set("ok", oBack)
        # Create the codico's for the manuscripts
        with transaction.atomic():
            for idx, manu_id in enumerate(manu_lst):
                # Debugging message
                msg = "Checking manuscript {} of {}".format(idx+1, len(manu_lst))
                oErr.Status(msg)

                # Status message
                oBack['total'] = msg
                if oStatus != None: oStatus.set("ok", oBack)

                manu = Manuscript.objects.filter(id=manu_id).first()
                if manu != None:
                    bResult, msg = add_codico_to_manuscript(manu)
                    count_add += 1
        oBack['codico_added'] = count_add

        # Checking up on manuscripts that are imported (stype='imp') but whose Codico has not been 'fixed' yet
        manu_lst = Manuscript.objects.filter(stype="imp").exclude(itype="codico_copied")
        # Status message
        oBack['total'] = "Imported manuscripts whose codico needs checking: {}".format(len(manu_lst))
        if oStatus != None: oStatus.set("ok", oBack)
        with transaction.atomic():
            for idx, manu in enumerate(manu_lst):
                # Show what we are doing
                oErr.Status("Checking manuscript {} of {}".format(idx+1, len(manu_lst)))
                # Actually do it
                bResult, msg = add_codico_to_manuscript(manu)
                if bResult:
                    manu.itype = "codico_copied"
                    manu.save()
                    count_copy += 1
        oBack['codico_copied'] = count_copy

        # Adapt codico's for templates
        codico_name = "(No codicological definition for a template)" 
        with transaction.atomic():
            for codico in Codico.objects.filter(manuscript__mtype="tem"):
                # Make sure the essential parts are empty!!
                bNeedSaving = False
                if codico.name != codico_name : 
                    codico.name = codico_name
                    bNeedSaving = True
                if codico.notes != None: codico.notes = None ; bNeedSaving = True
                if codico.support != None: codico.support = None ; bNeedSaving = True
                if codico.extent != None: codico.extent = None ; bNeedSaving = True
                if codico.format != None: codico.format = None ; bNeedSaving = True
                if bNeedSaving:
                    codico.save()
                    count_tem += 1
        oBack['codico_template'] = count_tem

        if oStatus != None: oStatus.set("finished", oBack)

        # Note that we are indeed ready
        bResult = True
    except:
        msg = oErr.get_error_message()
        bResult = False
    return bResult, msg

def adapt_passim_project_name_manu(): 
    oErr = ErrHandle()
    bResult = True
    msg = ""
    name = "Passim"
    # Issue 412: give all items in the current database the Project name "Passim"
    # This means: Manuscript, SSG/AF, Historical collection
    # Sermon: NO, is done in a separate method
    try:
        # Iterate over all Manuscripts in the database:  
        for manu in Manuscript.objects.all():
            # Try to find if the project already exists:        
            projectfound = Project2.objects.filter(name__iexact = name).first()
            if projectfound == None:
                # If the project does not already exist, it needs to be added to the database
                project = Project2.objects.create(name = name)
                # And a link should be made between this new project and the manuscript
                ManuscriptProject.objects.create(project = project, manuscript = manu)
            else:               
                manuprojlink = ManuscriptProject.objects.filter(project = projectfound, manuscript = manu).first()
                if manuprojlink == None:
                    # If the project already exists, but not the link, than only a link should be 
                    # made between the manuscript and the project
                    ManuscriptProject.objects.create(project = projectfound, manuscript = manu)
                    #print(manu, projectfound)
            # When iterating over Manuscript, make sure to iterate over Sermons too, how to access them?
            # Sermons belong to 1 manu
            # take project of Manuscript, 
            # SermonDescrProject (project = projectmanu, sermon = sermon)


    except:
        bResult = False
        msg = oErr.get_error_message()
    return bResult, msg

def adapt_doublecodico():
    oErr = ErrHandle()
    bResult = True
    msg = ""
    name = "Passim"
    # Change the codicological unit for manuscripts that appear to have more than one
    try:
        codico_id = []

        # Walk all codicological units in order
        qs = Codico.objects.all().order_by('id')
        for codico in qs:
            # Get the manuscript for this codicological unit
            manuscript = codico.manuscript
            manu_other = []
            manu_codico = {}
            # Get all the MsItems for this codico
            for obj in codico.codicoitems.exclude(manu=manuscript).order_by('manu__id'):
                # Add the id of the corresponding manuscript
                manu_id = obj.manu.id
                if not manu_id in manu_other:
                    manu_other.append(manu_id)
                # Possibly get the relation from manuscript to the proper codico
                if not manu_id in manu_codico:
                    manu_codico[manu_id] = Codico.objects.filter(manuscript=obj.manu).first()
            if len(manu_other) > 0:
                # Move all the relevant MSitems to the proper Codico
                with transaction.atomic():
                    for manu_id in manu_other:
                        correct_codico = manu_codico[manu_id]
                        for obj in MsItem.objects.filter(codico=codico, manu_id=manu_id):
                            obj.codico = correct_codico
                            obj.save()

    except:
        bResult = False
        msg = oErr.get_error_message()
    return bResult, msg

def add_codico_to_manuscript(manu):
    """Check if a manuscript has a Codico, and if not create it"""

    def get_number(items, bFirst):
        """Extract the first or last consecutive number from the string"""

        number = -1
        if len(items) > 0:
            if bFirst:
                # Find the first number
                for sInput in items:
                    arNumber = re.findall(r'\d+', sInput)
                    if len(arNumber) > 0:
                        number = int(arNumber[0])
                        break
            else:
                # Find the last number
                for sInput in reversed(items):
                    arNumber = re.findall(r'\d+', sInput)
                    if len(arNumber) > 0:
                        number = int(arNumber[-1])
                        break

        return number
    
    oErr = ErrHandle()
    bResult = False
    msg = ""
    try:
        # Check if the codico exists
        codi = Codico.objects.filter(manuscript=manu).first()
        if codi == None:
            # Get first and last sermons and then their pages
            items = [x['itemsermons__locus'] for x in manu.manuitems.filter(itemsermons__locus__isnull=False).order_by(
                'order').values('itemsermons__locus')]
            if len(items) > 0:
                pagefirst = get_number(items, True)
                pagelast = get_number(items, False)
            else:
                pagefirst = 1
                pagelast = 1
            # Create the codico
            codi = Codico.objects.create(
                name=manu.name, support=manu.support, extent=manu.extent,
                format=manu.format, order=1, pagefirst=pagefirst, pagelast=pagelast,
                origin=manu.origin, manuscript=manu
                )
        else:
            # Possibly copy stuff from manu to codi
            bNeedSaving = False
            if codi.name == "SUPPLY A NAME" and manu.name != "":
                codi.name = manu.name ; bNeedSaving = True
            if codi.support == None and manu.support != None:
                codi.support = manu.support ; bNeedSaving = True
            if codi.extent == None and manu.extent != None:
                codi.extent = manu.extent ; bNeedSaving = True
            if codi.format == None and manu.format != None:
                codi.format = manu.format ; bNeedSaving = True
            if codi.order == 0:
                codi.order = 1 ; bNeedSaving = True
            if codi.origin == None and manu.origin != None:
                codi.origin = manu.origin ; bNeedSaving = True
            # Possibly save changes
            if bNeedSaving:
                codi.save()
        # Copy provenances
        if codi.codico_provenances.count() == 0:
            for mp in manu.manuscripts_provenances.all():
                obj = ProvenanceCod.objects.filter(
                    provenance=mp.provenance, codico=codi, note=mp.note).first()
                if obj == None:
                    obj = ProvenanceCod.objects.create(
                        provenance=mp.provenance, codico=codi, note=mp.note)

        # Copy keywords
        if codi.codico_kw.count() == 0:
            for mk in manu.manuscript_kw.all():
                obj = CodicoKeyword.objects.filter(
                    codico=codi, keyword=mk.keyword).first()
                if obj == None:
                    obj = CodicoKeyword.objects.create(
                        codico=codi, keyword=mk.keyword)

        ## Copy date ranges
        #if codi.codico_dateranges.count() == 0:
        #    for md in manu.manuscript_dateranges.all():
        #        if md.codico_id == None or md.codico_id == 0 or md.codico == None or md.codic.id != codi.id:
        #            md.codico = codi
        #            md.save()

        # Tie all MsItems that need be to the Codico
        for msitem in manu.manuitems.all().order_by('order'):
            if msitem.codico_id == None or msitem.codico == None or msitem.codico.id != codi.id:
                msitem.codico = codi
                msitem.save()
        bResult = True
    except:
        msg = oErr.get_error_message()
        oErr.DoError("add_codico_to_manuscript")
        bResult = False
    return bResult, msg

def adapt_daterange_codico():
    oErr = ErrHandle()
    bResult = True
    msg = ""
    try:
        # Check all date ranges, that they are connected to a Codico (instead of manuscript)
        qs = Daterange.objects.filter(codico__isnull=True)
        for obj in qs:
            # Get the correct codico from the manuscript
            codico = obj.manuscript.manuscriptcodicounits.first()
            if codico is None:
                oErr.Status("Cannot find a CODICO for manuscript {}".format(obj.manuscript.id))
            else:
                # Set the right codico
                obj.codico = codico
                obj.save()
        # Getting here means that all went well
        bResult = True
    except:
        msg = oErr.get_error_message()
        oErr.DoError("add_codico_to_manuscript")
        bResult = False
    return bResult, msg

def adapt_codico_origin():
    oErr = ErrHandle()
    bResult = True
    msg = ""
    name = "Passim"
    # Issue #427:
    #   Create one OriginCod object for each Origin that is part of a Codico
    #   Then set the 'origin' field of that Codico to None
    try:
        qs = Codico.objects.all()
        lst_codico = []
        with transaction.atomic():
            for codico in qs:
                # Does this one have an origin set?
                if not codico.origin is None:
                    # Check if an appropriate OriginCod is already there
                    obj = OriginCod.objects.filter(codico=codico).first()
                    if obj is None:
                        # Create one
                        obj = OriginCod.objects.create(codico=codico, origin=codico.origin)
                    lst_codico.append(codico)
        # Set the 'origin' field to none
        with transaction.atomic():
            for codico in lst_codico:
                codico.origin = None
                codico.save()
 

    except:
        bResult = False
        msg = oErr.get_error_message()
    return bResult, msg

# =========== Part of sermon_list ==================
def adapt_nicknames():
    oErr = ErrHandle()
    bResult = True
    msg = ""
    
    try:
        # Perform adaptations
        bResult, msg = SermonDescr.adapt_nicknames()
    except:
        bResult = False
        msg = oErr.get_error_message()
    return bResult, msg

def adapt_biblerefs():
    oErr = ErrHandle()
    bResult = True
    msg = ""
    
    try:
        # Remove any previous BibRange objects
        BibRange.objects.all().delete()
        # Perform adaptations
        for sermon in SermonDescr.objects.exclude(bibleref__isnull=True).exclude(bibleref__exact=''):
            sermon.do_ranges(force=True)

    except:
        bResult = False
        msg = oErr.get_error_message()
    return bResult, msg

def adapt_passim_project_name_sermo():
    oErr = ErrHandle()
    bResult = True
    msg = ""
   # name = "Passim"
    # Issue 412: give all items in the current database the Project name "Passim"
    # aanpassen, moet via MsItems
         
    try:
        # Iterate over all Manuscripts in the database:  
        idx = 0
        count = Manuscript.objects.count()
        with transaction.atomic():
            for manu in Manuscript.objects.all():    
                idx += 1
                print("Manuscript number {} of {}".format(idx, count))  
                # Create empty list of projects for each manuscript 
                project_list = []
                # Find all project names linked to this manuscript
                for mp in ManuscriptProject.objects.filter(manuscript = manu):
                    # Add the projects to the list
                    project_list.append(mp.project) 
       
                # Now iterate over the sermons that are part of the manuscript                    
                for sermon in SermonDescr.objects.filter(msitem__manu = manu):              
                    # And iterate over the project list taken from the manuscript
                    for project in project_list:
                        #print(project.name)
                        # Get the name of the project
                        name_project = project.name
                        # Find out of the project already exists TH: this step is not necessary or is it?
                        projectfound = Project2.objects.filter(name__iexact = name_project).first()
                        # Test if the project has already been linked to the sermon 
                        sermoprojlink = SermonDescrProject.objects.filter(sermon = sermon, project = projectfound).first()
                        # If this is not the case then a link must be made between the sermon and the project
                        if sermoprojlink == None: 
                            SermonDescrProject.objects.create(project = projectfound, sermon = sermon)
                   
       
    except:
        bResult = False
        msg = oErr.get_error_message()
    return bResult, msg

# =========== Part of sermongold_list ==================
def adapt_sermon_gsig():
    oErr = ErrHandle()
    bResult = True
    msg = ""
    
    try:
        # Perform adaptations
        bResult = SermonSignature.adapt_gsig()

    except:
        bResult = False
        msg = oErr.get_error_message()
    return bResult, msg

# =========== Part of equalgold_list ==================
def adapt_author_anonymus():
    oErr = ErrHandle()
    bResult = True
    msg = ""
    
    try:
        # Get all SSGs with anyonymus
        with transaction.atomic():
            ano = "anonymus"
            qs = EqualGold.objects.filter(Q(author__name__iexact=ano))
            for ssg in qs:
                ssg.save()
    except:
        bResult = False
        msg = oErr.get_error_message()
    return bResult, msg

def adapt_latin_names():
    oErr = ErrHandle()
    bResult = True
    msg = ""    
    re_pattern = r'^\s*(?:\b[A-Z][a-zA-Z]+\b\s*)+(?=[_])'
    re_name = r'^[A-Z][a-zA-Z]+\s*'

    def add_names(main_list, fragment):
        oErr = ErrHandle()
        try:
            for sentence in fragment.replace("_", "").split("."):
                # WOrk through non-initial words
                words = re.split(r'\s+', sentence)
                for word in words[1:]:
                    if re.match(re_name, word):
                        if not word in main_list:
                            main_list.append(word)
        except:
            msg = oErr.get_error_message()
            oErr.DoError("add_names")

    try:
        # Start list of common names
        common_names = []
        # Walk all SSGs that are not templates
        with transaction.atomic():
            incexpl_list = EqualGold.objects.values('incipit', 'explicit')
            for incexpl in incexpl_list:
                # Treat incipit and explicit
                inc = incexpl['incipit']
                if inc != None: add_names(common_names, inc)
                expl = incexpl['explicit']
                if expl != None:  add_names(common_names, expl)
            # TRansform word list
            names_list = sorted(common_names)
            oErr.Status("Latin common names: {}".format(json.dumps(names_list)))
    except:
        bResult = False
        msg = oErr.get_error_message()
    return bResult, msg

def adapt_ssg_bidirectional():
    oErr = ErrHandle()
    bResult = True
    msg = ""
    
    try:
        # Put all links in a list
        lst_link = []
        lst_remove = []
        lst_reverse = []
        for obj in EqualGoldLink.objects.filter(linktype__in=LINK_BIDIR):
            # Check for any other eqg-links with the same source
            lst_src = EqualGoldLink.objects.filter(src=obj.src, dst=obj.dst).exclude(id=obj.id)
            if lst_src.count() > 0:
                # Add them to the removal
                for item in lst_src:
                    lst_remove.append(item)
            else:
                # Add the obj to the list
                lst_link.append(obj)
        for obj in lst_link:
            # Find the reverse link
            reverse = EqualGoldLink.objects.filter(src=obj.dst, dst=obj.src)
            if reverse.count() == 0:
                # Create the reversal
                reverse = EqualGoldLink.objects.create(src=obj.dst, dst=obj.src, linktype=obj.linktype)
    except:
        bResult = False
        msg = oErr.get_error_message()
    return bResult, msg

def adapt_s_to_ssg_link():
    oErr = ErrHandle()
    bResult = True
    msg = ""
    
    try:
        qs = SermonDescrEqual.objects.all()
        with transaction.atomic():
            for obj in qs:
                obj.linktype = LINK_UNSPECIFIED
                obj.save()
    except:
        bResult = False
        msg = oErr.get_error_message()
    return bResult, msg

def adapt_hccount():
    oErr = ErrHandle()
    bResult = True
    msg = ""
    
    try:
        # Walk all SSGs
        with transaction.atomic():
            for ssg in EqualGold.objects.all():
                hccount = ssg.collections.filter(settype="hc").count()
                if hccount != ssg.hccount:
                    ssg.hccount = hccount
                    ssg.save()
    except:
        bResult = False
        msg = oErr.get_error_message()
    return bResult, msg

def adapt_scount():
    oErr = ErrHandle()
    bResult = True
    msg = ""
    
    try:
        # Walk all SSGs
        with transaction.atomic():
            for ssg in EqualGold.objects.all():
                scount = ssg.equalgold_sermons.count()
                if scount != ssg.scount:
                    ssg.scount = scount
                    ssg.save()
    except:
        bResult = False
        msg = oErr.get_error_message()
    return bResult, msg

def adapt_ssgcount():
    oErr = ErrHandle()
    bResult = True
    msg = ""
    
    try:
        # Walk all SSGs
        with transaction.atomic():
            for ssg in EqualGold.objects.all():
                ssgcount = ssg.relations.count()
                if ssgcount != ssg.ssgcount:
                    ssg.ssgcount = ssgcount
                    ssg.save()
    except:
        bResult = False
        msg = oErr.get_error_message()
    return bResult, msg

def adapt_ssgselflink():
    oErr = ErrHandle()
    bResult = True
    msg = ""
    
    try:
        # Walk all SSGs
        with transaction.atomic():
            must_delete = []
            # Walk all SSG links
            for ssglink in EqualGoldLink.objects.all():
                # Is this a self-link?
                if ssglink.src == ssglink.dst:
                    # Add it to must_delete
                    must_delete.append(ssglink.id)
            # Remove all self-links
            EqualGoldLink.objects.filter(id__in=must_delete).delete()
    except:
        bResult = False
        msg = oErr.get_error_message()
    return bResult, msg

def adapt_add_manu():
    oErr = ErrHandle()
    bResult = True
    msg = ""
    
    try:
        # Walk all SSGs
        with transaction.atomic():
            # Walk all SSG links
            for link in SermonDescrEqual.objects.all():
                # Get the manuscript for this sermon
                manu = link.sermon.msitem.manu
                # Add it
                link.manu = manu
                link.save()
    except:
        bResult = False
        msg = oErr.get_error_message()
    return bResult, msg

def adapt_passim_code():
    oErr = ErrHandle()
    bResult = True
    msg = ""
    
    try:
        # Walk all SSGs
        need_correction = {}
        for obj in EqualGold.objects.all().order_by("-id"):
            code = obj.code
            if code != None and code != "ZZZ_DETERMINE":
                count = EqualGold.objects.filter(code=code).count()
                if count > 1:
                    oErr.Status("Duplicate code={} id={}".format(code, obj.id))
                    if code in need_correction:
                        need_correction[code].append(obj.id)
                    else:                            
                        need_correction[code] = [obj.id]
        oErr.Status(json.dumps(need_correction))
        for k,v in need_correction.items():
            code = k
            ssg_list = v
            for ssg_id in ssg_list[:-1]:
                oErr.Status("Changing CODE for id {}".format(ssg_id))
                obj = EqualGold.objects.filter(id=ssg_id).first()
                if obj != None:
                    obj.code = None
                    obj.number = None
                    obj.save()
                    oErr.Status("Re-saved id {}, code is now: {}".format(obj.id, obj.code))

    except:
        bResult = False
        msg = oErr.get_error_message()
    return bResult, msg

def adapt_passim_author_number():
    oErr = ErrHandle()
    bResult = True
    msg = ""
    
    try:
        # (3) Get the author id for 'Undecided'
        undecided = Author.objects.filter(name__iexact="undecided").first()
        undecided_id = undecided.id

        # Walk all SSGs and save those whose .number is none
        qs = EqualGold.objects.filter(author__isnull=False, number__isnull=True).exclude(author=undecided).order_by('author_id')
        for obj in qs:
            # Double checking
            if not obj.author is None and obj.number is None and not obj.author.id == undecided_id:
                # Re-saving means getting a legitimate number
                obj.save()

        # Walk all SSGs whose [code] is null, but have a number
        qs = EqualGold.objects.filter(author__isnull=False, code__isnull=True, number__isnull=False)
        with transaction.atomic():
            for obj in qs:
                # Reset the number to none
                obj.number = None
                obj.save()

    except:
        bResult = False
        msg = oErr.get_error_message()
    return bResult, msg


def adapt_passim_project_name_equal():
    oErr = ErrHandle()
    bResult = True
    msg = ""
    name = "Passim"
    # Issue 412: give all items in the current database the Project name "Passim"
    # This means: Manuscript, SSG/AF, Historical collection

    try:
        # Iterate over all SSGs/AFs in the database:  
        for equal in EqualGold.objects.all():     
            # Try to find if the project already exists:        
            projectfound = Project2.objects.filter(name__iexact = name).first()
            if projectfound == None:
                # If the project does not already exist, it needs to be added to the database
                project = Project2.objects.create(name = name)
                # And a link should be made between this new project and the SSG/AF
                EqualGoldProject.objects.create(project = project, equal = equal)
            else:               
                equalprojlink = EqualGoldProject.objects.filter(project = projectfound, equal = equal).first()
                if equalprojlink == None:
                    # If the project already exists, but not the link, than only a link should be 
                    # made between the collection and the project
                    EqualGoldProject.objects.create(project = projectfound, equal = equal)
                    print(equal, projectfound)
    except:
        bResult = False
        msg = oErr.get_error_message()
    return bResult, msg

def adapt_atype_def_equal():
    # NEW ISSUE #492 change def in atype EqualGold model
    oErr = ErrHandle()
    bResult = True
    msg = ""
    code = "acc"
    try:
        with transaction.atomic():
            # Iterate over all SSGs/AFs in the database:  
            for equal in EqualGold.objects.all():
                bNeedSaving = False
                # if atype is def
                if equal.atype == "def":            
                    equal.atype = code             
                    bNeedSaving = True
                if bNeedSaving:
                    equal.save()
                    #print(equal.atype)    
                        
    except:
        bResult = False
        msg = oErr.get_error_message()
    return bResult, msg

def adapt_atype_acc_equal():
    # Issue #522: mono-projectal SSGs must have atype 'acc'
    oErr = ErrHandle()
    bResult = True
    msg = ""
    code = "acc"
    try:
        with transaction.atomic():
            # Iterate over all SSGs/AFs in the database:  
            for equal in EqualGold.objects.all():
                bNeedSaving = False
                # if atype is def
                if equal.atype == "def":  
                    # How many projects are connected to this SSG?
                    count = equal.projects.count()
                    if count <= 1:
                        equal.atype = code             
                        bNeedSaving = True
                if bNeedSaving:
                    equal.save()
                        
    except:
        bResult = False
        msg = oErr.get_error_message()
    return bResult, msg


# =========== Part of provenance_list ==================
def adapt_manuprov_m2m():
    oErr = ErrHandle()
    bResult = True
    msg = ""
    
    try:
        # Issue #289: back to m2m connection
        prov_changes = 0
        prov_added = 0
        # Keep a list of provenance id's that may be kept
        keep_id = []

        # Remove all previous ProvenanceMan connections
        ProvenanceMan.objects.all().delete()
        # Get all the manuscripts
        for manu in Manuscript.objects.all():
            # Treat all the M2O provenances for this manuscript
            for prov in manu.manuprovenances.all():
                # Get the *name* and the *loc* for this prov
                name = prov.name
                loc = prov.location
                note = prov.note
                # Get the very *first* provenance with name/loc
                firstprov = Provenance.objects.filter(name__iexact=name, location=loc).first()
                if firstprov == None:
                    # Create one
                    firstprov = Provenance.objects.create(name=name, location=loc)
                keep_id.append(firstprov.id)
                # Add the link
                link = ProvenanceMan.objects.create(manuscript=manu, provenance=firstprov, note=note)
        # Walk all provenances to remove the unused ones
        delete_id = []
        for prov in Provenance.objects.all().values('id'):
            if not prov['id'] in keep_id:
                delete_id.append(prov['id'])
        oErr.Status("Deleting provenances: {}".format(len(delete_id)))
        Provenance.objects.filter(id__in=delete_id).delete()

        # Success
        oErr.Status("adapt_manuprov_m2m: {} changes, {} additions".format(prov_changes, prov_added))
    except:
        bResult = False
        msg = oErr.get_error_message()
    return bResult, msg

# =========== Part of collhist_list ==================
def adapt_passim_project_name_hc(): 
    oErr = ErrHandle()
    bResult = True
    msg = ""
    name = "Passim"
    # Issue 412: give all items in the current database the Project name "Passim"
    # This means: Manuscript, SSG/AF, Historical collection

    # Ok, eigenlijk alleen de hc collections:
    # settype == "hc"

    try:
        # Iterate over all Collections in the database:  
        for coll in Collection.objects.all():     
            # Try to find if the project already exists:        
            projectfound = Project2.objects.filter(name__iexact = name).first()
            if projectfound == None:
                # If the project does not already exist, it needs to be added to the database
                project = Project2.objects.create(name = name)
                # And a link should be made between this new project and the collection
                # Only when the collection is an Historical Collection"
                if coll.settype == "hc":
                    CollectionProject.objects.create(project = project, collection = coll)
            else:               
                collprojlink = CollectionProject.objects.filter(project = projectfound, collection = coll).first()
                if collprojlink == None:
                    # If the project already exists, but not the link, than only a link should be 
                    # made between the collection and the project
                    # Only when the collection is an Historical Collection"
                    if coll.settype == "hc":
                        CollectionProject.objects.create(project = projectfound, collection = coll)
                        print(coll.name, projectfound)    
    except:
        bResult = False
        msg = oErr.get_error_message()
    return bResult, msg

def adapt_coll_ownerless():
    """Find collections without owner and delete these"""
    oErr = ErrHandle()
    bResult = True
    msg = ""
    name = "Passim"
    try:
        qs = Collection.objects.filter(owner__isnull=True)
        qs.delete()
    except:
        bResult = False
        msg = oErr.get_error_message()
    return bResult, msg

def adapt_litref_check():
    """Remove identical literature references per collection"""

    oErr = ErrHandle()
    bResult = True
    msg = ""
    name = "Passim"
    try:
        qs = Collection.objects.all()
        for obj_coll in qs:
            # Look for literatur references
            lst_unique = []
            lst_delete = []
            for obj_litrefcol in obj_coll.collection_litrefcols.all():
                # Get the litref ID and the pages
                litref_id = obj_litrefcol.reference.id
                pages = obj_litrefcol.pages
                # Check if this is already in there
                bFound = False
                for oUnique in lst_unique:
                    if oUnique['litref'] == litref_id and oUnique['pages'] == pages:
                        bFound = True
                        lst_delete.append(obj_litrefcol.id)
                        break
                # If it is not found
                if not bFound:
                    lst_unique.append(dict(litref=litref_id, pages=pages))
            # Anything deletable?
            if len(lst_delete) > 0:
                print("adapt_litref_check: removing LitrefCol ids: {}".format(lst_delete))
                LitrefCol.objects.filter(id__in=lst_delete).delete()
    except:
        bResult = False
        msg = oErr.get_error_message()
    return bResult, msg


# =========== Part of literature_list ==================
def adapt_import_onlinesources(): 
    oErr = ErrHandle()
    bResult = True
    msg = ""
        
    try:
        # Import online_sources.csv that holds the names and URLs of the online sources used in PASSIM
        filename = os.path.abspath(os.path.join(MEDIA_DIR, 'online_sources.csv'))
        # Open the file...
        with open(filename, encoding='utf-8') as f:            
            # ...and read the file...
            reader = csv.reader(f, dialect='excel', delimiter=';') 
            
            # Transpose the result     
            name, url = zip(*reader)

            # Make lists of the tuples
            name_list = list(name)
            url_list = list(url)
            
            # Delete the first records in order to 
            # get rid of the fieldnames 
            name_list.pop(0)
            url_list.pop(0)
            
            # Iterate over the two combined lists:
            for name, url in zip(name_list, url_list):                
                print(name, url)
                # Store the records in the OnlineCourses table:
                OnlineSources.objects.create(name = name, url = url)               
                            
    except:
        bResult = False
        msg = oErr.get_error_message()
    return bResult, msg