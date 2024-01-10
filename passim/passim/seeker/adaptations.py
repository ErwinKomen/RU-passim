"""
Adaptations of the database that are called up from the (list)views in the SEEKER app.
"""

from django.db import transaction
import re
import json
import os
import csv
import sqlite3
import pandas as pd
from unidecode import unidecode
from passim.settings import MEDIA_DIR

# ======= imports from my own application ======
from passim.utils import ErrHandle, RomanNumbers
from passim.basic.models import UserSearch
from passim.seeker.models import get_crpp_date, get_current_datetime, process_lib_entries, get_searchable, get_now_time, \
    add_gold2equal, add_equal2equal, add_ssg_equal2equal, get_helptext, Information, Country, City, Author, Manuscript, \
    User, Group, Origin, SermonDescr, MsItem, SermonHead, SermonGold, SermonDescrKeyword, SermonDescrEqual, Nickname, NewsItem, \
    SourceInfo, SermonGoldSame, SermonGoldKeyword, EqualGoldKeyword, Signature, Ftextlink, ManuscriptExt, \
    ManuscriptKeyword, Action, EqualGold, EqualGoldLink, Location, LocationName, LocationIdentifier, LocationRelation, LocationType, \
    ProvenanceMan, Provenance, Daterange, CollOverlap, BibRange, Feast, Comment, SermonEqualDist, \
    Basket, BasketMan, BasketGold, BasketSuper, Litref, LitrefMan, LitrefCol, LitrefSG, EdirefSG, Report, SermonDescrGold, \
    Visit, Profile, Keyword, SermonSignature, Status, Library, Collection, CollectionSerm, \
    CollectionMan, CollectionSuper, CollectionGold, UserKeyword, Template, \
    ManuscriptCorpus, ManuscriptCorpusLock, EqualGoldCorpus, SermonGoldExternal, \
    Codico, OriginCod, CodicoKeyword, ProvenanceCod, Project2, ManuscriptProject, SermonDescrProject, \
    CollectionProject, EqualGoldProject, OnlineSources, \
    ProjectApprover, ProjectEditor, ManuscriptExternal, SermonDescrExternal, \
    get_reverse_spec, LINK_EQUAL, LINK_PRT, LINK_BIDIR, LINK_PARTIAL, STYPE_IMPORTED, STYPE_EDITED, LINK_UNSPECIFIED, \
    EXTERNAL_HUWA_OPERA
from passim.reader.models import Edition, Literatur, OperaLit
from passim.reader.views import read_kwcategories


adaptation_list = {
    "manuscript_list": [
        'sermonhierarchy', 'msitemcleanup', 'locationcitycountry', 'templatecleanup', 
        'feastupdate', 'codicocopy', 'passim_project_name_manu', 'doublecodico',
        'codico_origin', 'import_onlinesources', 'dateranges', 'huwaeditions',
        'supplyname', 'usersearch_params', 'huwamanudate'],
    'sermon_list': ['nicknames', 'biblerefs', 'passim_project_name_sermo', 'huwainhalt'], #, 'huwafolionumbers'],
    'sermongold_list': ['sermon_gsig', 'huwa_opera_import'],
    'equalgold_list': [
        'author_anonymus', 'latin_names', 'ssg_bidirectional', 's_to_ssg_link', 
        'hccount', 'scount', 'sgcount', 'ssgcount', 'ssgselflink', 'add_manu', 'passim_code', 'passim_project_name_equal', 
        'atype_def_equal', 'atype_acc_equal', 'passim_author_number', 'huwa_ssg_literature',
        'huwa_edilit_remove', 'searchable'],
    'profile_list': ['projecteditors'],
    'provenance_list': ['manuprov_m2m'],
    'keyword_list': ['kwcategories'],
    "collhist_list": ['passim_project_name_hc', 'coll_ownerless', 'litref_check', 'scope_hc'],
    'onlinesources_list': ['unicode_name_online', 'unicode_name_litref'],    
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

def adapt_supplyname():
    """Convert SUPPLY A NAME to an empty string"""

    oErr = ErrHandle()
    bResult = True
    msg = ""
    try:
        # Walk all codico's
        with transaction.atomic():
            for codico in Codico.objects.all():
                if codico.name == "SUPPLY A NAME":
                    codico.name = ""
                    codico.save()
        # Walk all manuscripts
        with transaction.atomic():
            for manu in Manuscript.objects.all():
                if manu.name == "SUPPLY A NAME":
                    manu.name = ""
                    manu.save()

    except:
        msg = oErr.get_error_message()
        oErr.DoError("adapt_supplyname")
        bResult = False
    return bResult, msg

def adapt_usersearch_params():
    """Convert SUPPLY A NAME to an empty string"""

    oErr = ErrHandle()
    bResult = True
    msg = ""
    try:
        # Walk all UserSearch objects
        with transaction.atomic():
            for obj in UserSearch.objects.all():
                # Get the 'params' string
                sParams = obj.params
                if sParams != "":
                    oParams = json.loads(sParams)
                    # Check if this is a dictionary or a list
                    if isinstance(oParams, list):
                        # It is a list - transform it
                        oParams = dict(param_list = oParams, qfilter = [])
                        obj.params = json.dumps(oParams)
                        # Now save it
                        obj.save()

    except:
        msg = oErr.get_error_message()
        oErr.DoError("adapt_usersearch_params")
        bResult = False
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

def read_huwa_edilit():
    """Load the JSON that specifies the inter-SSG relations according to Opera id's """

    oErr = ErrHandle()
    lst_edilit = []
    try:
        edilit_json = os.path.abspath(os.path.join(MEDIA_DIR, "passim", "huwa_edilit.json"))
        if os.path.exists(edilit_json):
            with open(edilit_json, "r", encoding="utf-8") as f:
                lst_edilit = json.load(f)
        else:
            # Just issue a warning
            oErr.Status("WARNING: cannot find file {}".format(edilit_json))
    except:
        msg = oErr.get_error_message()
        oErr.DoError("adaptations.read_huwa_edilit")
    # Return the table that we found
    return lst_edilit

def adapt_huwaeditions():
    """See the reader app. This basically loads a JSON into the Huwa [Edition] and [Literatur] tables"""

    oErr = ErrHandle()
    bResult = True
    bDebug = False
    msg = ""
    specification = ['title', 'literaturtitel', 'pp', 'year', 'band', 'reihetitel', 'reihekurz']
    attrs = ['seiten', 'seitenattr', 'bis', 'bisattr', 'titel']

    try:
        # Read the HUWA edilit
        lst_edilit = read_huwa_edilit()
        # Process this table
        for oEdition in lst_edilit:
            # Get the obligatory opera id and then the huwatable and huwaid
            opera_id = oEdition.get("opera")        # This is for table [Edition]
            huwatable = oEdition.get("huwatable")   # This is for table [Literatur]
            huwaid = oEdition.get("huwaid")         # This is for table [Literatur]

            # Get the optional edition id
            edition_id = oEdition.get("edition")    # This is for table [Edition]

            # Other stuff for table [Edition]
            oPages = oEdition.get("pages")

            # Sanity check
            if not huwaid is None and not opera_id is None:
                # ================ DEBUG ==================
                if not edition_id is None and edition_id == 82:
                    iStop = 1
                # Show where we are
                if bDebug:
                    oErr.Status("HuwaTable {} Id {}".format(huwatable, huwaid))
                # =========================================

                # First check for the entry into [Literatur] - has that already been processed?
                lit = Literatur.objects.filter(huwaid=huwaid, huwatable=huwatable).first()
                if lit is None:
                    # It needs to be created
                    lit = Literatur.objects.create(huwaid=huwaid, huwatable=huwatable)
                    # Add the other optional elements
                    for sField in specification:
                        value = oEdition.get(sField)
                        if not value is None and value != "":
                            setattr(lit, sField, value)
                    # Look for location stuff
                    oLocation = oEdition.get("location")
                    if not oLocation is None:
                        # Get the handle to the location
                        lit.set_location(oLocation)

                    # Look for author stuff
                    oAuthor = oEdition.get("author")
                    if not oAuthor is None:
                        # Get the handle to the author
                        lit.set_author(oAuthor)

                    # Now make sure to save the adapted object
                    lit.save()

                # Further action depends on whether this is an [edition] or not
                if edition_id is None:
                    # This is not an edition, but bloomfield, stegmueller etc
                    operalit = OperaLit.objects.filter(operaid=opera_id, literatur=lit).first()
                    if operalit is None:
                        # It should be created
                        operalit = OperaLit.objects.create(operaid=opera_id, literatur=lit)
                else:
                    # This is an edition, so it should be processed into Edition

                    # Check if this is not yet processed
                    edition = Edition.objects.filter(editionid=edition_id, operaid=opera_id, literatur=lit).first()
                    if edition is None:
                        # This has not been read
                        edition = Edition.objects.create(editionid=edition_id, operaid=opera_id, literatur=lit)

                        # Walk through any loci
                        lst_loci = oEdition.get("loci", [])
                        for oLoci in lst_loci:
                            # Add this locus to the edition
                            edition.add_locus(oLoci)

                    # Walk through any [siglen]
                    lst_siglen = oEdition.get("siglen", [])
                    for oSiglen in lst_siglen:
                        # Add this siglen to the edition
                        edition.add_siglen(oSiglen)

                    # Walk through any [siglen_edd]
                    lst_siglen_edd = oEdition.get("siglen_edd", [])
                    for oSiglenEdd in lst_siglen_edd:
                        # Add this siglen to the edition
                        edition.add_siglen_edd(oSiglenEdd)

                    # Check for 'seiten' etc
                    for k,v in oPages.items():
                        if getattr(edition, k) is None and not v is None:
                            setattr(edition, k, v)
                    edition.save()
            else:
                # This is a bad entry. Double check
                bDoubleCheck = True
        # We have now processed all elements in [edilit]
        msg = "ok"
    except:
        bResult = False
        msg = oErr.get_error_message()
    return bResult, msg

def read_huwa():
    oErr = ErrHandle()
    table_info = {}
    try:
        # Get the location of the HUWA database
        huwa_db = os.path.abspath(os.path.join(MEDIA_DIR, "passim", "huwa_database_for_PASSIM.db"))
        with sqlite3.connect(huwa_db) as db:
            standard_fields = ['erstdatum', 'aenddatum', 'aenderer', 'bemerkungen', 'ersteller']

            cursor = db.cursor()
            db_results = cursor.execute("SELECT name FROM sqlite_master WHERE type='table';").fetchall()
            tables = [x[0] for x in db_results]

            count_tbl = len(tables)

            # Walk all tables
            for table_name in tables:
                oInfo = {}
                # Find out what fields this table has
                db_results = cursor.execute("PRAGMA table_info('{}')".format(table_name)).fetchall()
                fields = []
                for field in db_results:
                    field_name = field[1]
                    fields.append(field_name)

                    field_info = dict(type=field[2],
                                        not_null=(field[3] == 1),
                                        default=field[4])
                    oInfo[field_name] = field_info
                oInfo['fields'] = fields
                oInfo['links'] = []

                # Read the table
                table_contents = cursor.execute("SELECT * FROM {}".format(table_name)).fetchall()
                oInfo['contents'] = table_contents

                table_info[table_name] = oInfo

            # Close the database again
            cursor.close()
    except:
        msg = oErr.get_error_message()
        oErr.DoError("read_huwa")
    # Return the table that we found
    return table_info

def get_huwa_tables(table_info, lst_names):
    """Read all tables in [lst_names] from [table_info]"""

    oErr = ErrHandle()
    oTables = {}
    try:
        for sName in lst_names:
            oTable = table_info[sName]
            lFields = oTable['fields']
            lContent = oTable['contents']
            lTable = []
            for lRow in lContent:
                oNew = {}
                for idx, oPart in enumerate(lRow):
                    oNew[lFields[idx]] = oPart
                lTable.append(oNew)
            oTables[sName] = lTable
    except:
        msg = oErr.get_error_message()
        oErr.DoError("get_huwa_tables")

    return oTables

def adapt_huwamanudate():
    """Adapt the daterange table and date fields in Codico and Manuscript for those that have been read fromHUWA"""

    oErr = ErrHandle()
    bResult = True
    bDebug = False
    msg = ""
    huwa_tables = ['handschrift']
    try:
        # Read the HUWA database
        table_info = read_huwa()
        # (5) Load the tables that we need
        tables = get_huwa_tables(table_info, huwa_tables)
        # Get the table of handschrift
        lHandschrift = tables['handschrift']

        # Walk the handschrift table
        with transaction.atomic():
            for oHandschrift in lHandschrift:
                externalid = oHandschrift.get("id") 
                # Get the century information
                saeculum = oHandschrift.get("saeculum")
                if not saeculum is None:
                    # Get the Manuscript, Codico and Daterange (in Passim)
                    external = ManuscriptExternal.objects.filter(externalid=externalid).first()
                    if not external is None:
                        # Get the manuscript, codico and daterang
                        manu = external.manu
                        codico = manu.manuscriptcodicounits.first()
                        daterange = codico.codico_dateranges.first()
                        # We now have a number
                        saeculum= int(saeculum)
                        # Action depends in the particular number
                        if saeculum == 100 and not daterange is None:
                            # This needs special treatment: 
                            # 1 - either remove the manuscript info
                            # 2 - or set it to 1000-1600 to indicate we don't really know
                            yearstart = 900
                            yearfinish = 1600
                            # Remove the daterange
                            daterange.delete()
                            # Set the values in codico and manu
                            codico.yearstart = yearstart
                            codico.yearfinish = yearfinish
                            manu.yearstart = yearstart
                            manu.yearfinish = yearfinish
                            # Save them
                            codico.save()
                            manu.save()
                        elif not daterange is None and saeculum > 0:
                            # Calculate the proper daterange
                            yearstart = (saeculum - 1) * 100
                            yearfinish = yearstart + 99
                            # Do we need changing?
                            if daterange.yearstart != yearstart or daterange.yearfinish != yearfinish:
                                # Set the daterange, codico and manu
                                daterange.yearstart = yearstart
                                daterange.yearfinish = yearfinish
                                codico.yearstart = yearstart
                                codico.yearfinish = yearfinish
                                manu.yearstart = yearstart
                                manu.yearfinish = yearfinish
                                # Save them
                                daterange.save()
                                codico.save()
                                manu.save()

        # Everything has been processed correctly now
        msg = "ok"
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

def adapt_huwainhalt():
    """Adapt the LOCI (folio numbers) of the sermons that have been read fromHUWA"""

    def get_locus_org(oInhalt):
        """Get a complete LOCUS string combining von_bis, von_rv and bis_f, bis_rv"""

        sBack = ""
        oErr = ErrHandle()
        oRom = RomanNumbers()
        try:
            lst_von_bis = str(oInhalt.get("von_bis", "")).split(".")
            von_rv = str(oInhalt.get("von_rv", ""))
            lst_bis_f = str(oInhalt.get("bis_f", "")).split(".")
            bis_rv = str(oInhalt.get("bis_rv", ""))

            von_bis = None if int(lst_von_bis[0]) == 0 else lst_von_bis[0]
            bis_f = None if int(lst_bis_f[0]) == 0 else lst_bis_f[0]

            # Treat negative numbers (see issue #532)
            if not von_bis is None and re.match(r'-\d+', von_bis):
                order_num = int(von_bis)
                if order_num < -110: order_num = -110
                if order_num < 0:
                    # Add 110 + 1 and turn into romans
                    von_bis = oRom.intToRoman(order_num+110+1)
            if not bis_f is None and re.match(r'-\d+', bis_f):
                order_num = int(bis_f)
                if order_num < -110: order_num = -110
                if order_num < 0:
                    # Add 110 + 1 and turn into romans
                    bis_f = oRom.intToRoman(order_num+110+1)

            html = []
            # Calculate from
            lst_from = []
            if von_rv != "": lst_from.append(von_rv)
            if not von_bis is None: lst_from.append(von_bis)
            sFrom = "".join(lst_from)

            # Calculate until
            lst_until = []
            if bis_rv != "": lst_until.append(bis_rv)
            if not bis_f is None: lst_until.append(bis_f)
            sUntil = "".join(lst_until)

            # Combine the two
            if sFrom == sUntil:
                sBack = sFrom
            else:
                sBack = "{}-{}".format(sFrom, sUntil)

        except:
            msg = oErr.get_error_message()
            oErr.DoError("get_locus")

        return sBack

    def get_manuscript_id(handschrift):
        """Get the correct manuscript, based on handschrift"""

        obj = None
        oErr = ErrHandle()
        try:
            manuext = [x['manu__id'] for x in ManuscriptExternal.objects.filter(externalid=handschrift).values('manu__id')]
            if len(manuext) > 0:
                obj = manuext[0]
                if len(manuext) > 1:
                    iStop = 1
                    oErr.Status("get_manuscript_id: more than one candidate for handschrift [{}]".format(handschrift))
        except:
            msg = oErr.get_error_message()
            oErr.DoError("get_manuscript")
        # Return our result
        return obj

    def get_sermon_org(oInhalt, sLocus, lResults):
        """Get the correct sermon, based on opera and manuscript"""

        obj = None
        oErr = ErrHandle()
        bProcessed = False
        ext_inhalt = "huwin"    # HUWA inhalt
        ext_opera = "huwop"     # HUWA opera
        try:
            manu_id = -1
            # First try to get it one way
            inhaltid = oInhalt.get("id")
            sermon_ids = [x['sermon__id'] for x in SermonDescrExternal.objects.filter(
                externaltype=ext_inhalt, externalid=inhaltid).values('sermon__id')]
            if len(sermon_ids) > 0:
                qs = SermonDescr.objects.filter(id__in=sermon_ids)
                bProcessed = True
            else:
                handschrift = oInhalt.get("handschrift")
                opera = oInhalt.get("opera")
                manu_id = get_manuscript_id( handschrift)
                # There could be a number of sermons with this opera
                sermon_ids = [x['sermon__id'] for x in SermonDescrExternal.objects.filter(
                    externaltype=ext_opera, externalid=opera).values('sermon__id')]

                # Now find the correct one
                manu_sermons = [x['id'] for x in SermonDescr.objects.filter(msitem__codico__manuscript__id=manu_id).values('id')]
                lst_ids = [x for x in sermon_ids if x in manu_sermons]

                qs = SermonDescr.objects.filter(id__in=lst_ids)
            # Evaluate the outcome
            if qs.count() == 1:
                obj = qs.first()
            elif qs.count() > 1:
                # We need to specify an additional filter for locus
                qs = qs.filter(locus=sLocus)
                if qs.count() > 1:
                    oErr.Status("adapt_huwafolionumbers/get_sermon too many sermons for opera={}, manu={}".format(opera, manu_id))
                    x = qs.last()
                else:
                    obj = qs.first()
            elif qs.count() == 0:
                oErr.Status("adapt_huwafolionumbers/get_sermon NO sermon for opera={}, manu={}".format(opera, manu_id))

            if not obj is None and not bProcessed:
                # Add in results
                oResult = dict(externalid=inhaltid, externaltype=ext_inhalt, sermonid=obj.id)
                lResults.append(oResult)

        except:
            msg = oErr.get_error_message()
            oErr.DoError("get_sermon_org")
        # Return our result
        return obj


    oErr = ErrHandle()
    oRom = RomanNumbers()
    bResult = True
    msg = ""
    ext_inhalt = "huwin" 
    huwa_tables = ['inhalt']
    try:
        # Read the HUWA database
        table_info = read_huwa()
        # (5) Load the tables that we need
        tables = get_huwa_tables(table_info, huwa_tables)

        lResults = []

        # Walk the INHALT table
        lInhalt = tables['inhalt']
        len_inhalt = len(lInhalt)
        iCount = 0
        for idx, oInhalt in enumerate(lInhalt):
            # Show where we are
            if idx % 1000 == 0: 
                oErr.Status("Huwa Inhalt {}/{} ".format(idx+1, len_inhalt))
            bNeedAdaptation = False

            # Get the original locus
            sLocus = get_locus_org(oInhalt)

            # Try to get the correct sermon
            sermon = get_sermon_org(oInhalt, sLocus, lResults)

        # Go over the results and store them
        if len(lResults) > 0:
            with transaction.atomic():
                for oResult in lResults:
                    inhaltid= oResult.get("inhaltid")
                    sermonid = oResult.get("sermonid")
                    # Add this link into SermonDescrExternal
                    srm_ext = SermonDescrExternal.objects.create(externalid=inhaltid, externaltype=ext_inhalt, sermon_id=sermonid)


        # Everything has been processed correctly now
        msg = "ok"
    except:
        bResult = False
        msg = oErr.get_error_message()
    return bResult, msg

def adapt_huwafolionumbers():
    """Adapt the LOCI (folio numbers) of the sermons that have been read fromHUWA"""

    def get_folio_number(lst_folio_num):
        oErr = ErrHandle()
        oRom = RomanNumbers()
        try:
            folio_num = None if int(lst_folio_num[0]) == 0 else lst_folio_num[0]
            # Treat negative numbers (see issue #532)
            if not folio_num is None and re.match(r'-\d+', folio_num):
                order_num = int(folio_num)
                if order_num < -110: order_num = -110
                if order_num < 0:
                    # Add 110 + 1 and turn into romans
                    folio_num = oRom.intToRoman(order_num+110+1)
        except:
            msg = oErr.get_error_message()
            oErr.DoError("get_folio_number")
        # Return our result
        return folio_num

    def get_locus_org(oInhalt):
        """Get a complete LOCUS string combining von_bis, von_rv and bis_f, bis_rv"""

        sBack = ""
        oErr = ErrHandle()
        oRom = RomanNumbers()
        try:
            lst_von_bis = str(oInhalt.get("von_bis", "")).split(".")
            von_rv = str(oInhalt.get("von_rv", ""))
            lst_bis_f = str(oInhalt.get("bis_f", "")).split(".")
            bis_rv = str(oInhalt.get("bis_rv", ""))

            von_bis = None if int(lst_von_bis[0]) == 0 else lst_von_bis[0]
            bis_f = None if int(lst_bis_f[0]) == 0 else lst_bis_f[0]

            # Treat negative numbers (see issue #532)
            if not von_bis is None and re.match(r'-\d+', von_bis):
                order_num = int(von_bis)
                if order_num < -110: order_num = -110
                if order_num < 0:
                    # Add 110 + 1 and turn into romans
                    von_bis = oRom.intToRoman(order_num+110+1)
            if not bis_f is None and re.match(r'-\d+', bis_f):
                order_num = int(bis_f)
                if order_num < -110: order_num = -110
                if order_num < 0:
                    # Add 110 + 1 and turn into romans
                    bis_f = oRom.intToRoman(order_num+110+1)

            html = []
            # Calculate from
            lst_from = []
            if von_rv != "": lst_from.append(von_rv)
            if not von_bis is None: lst_from.append(von_bis)
            sFrom = "".join(lst_from)

            # Calculate until
            lst_until = []
            if bis_rv != "": lst_until.append(bis_rv)
            if not bis_f is None: lst_until.append(bis_f)
            sUntil = "".join(lst_until)

            # Combine the two
            if sFrom == sUntil:
                sBack = sFrom
            else:
                sBack = "{}-{}".format(sFrom, sUntil)

        except:
            msg = oErr.get_error_message()
            oErr.DoError("get_locus")

        return sBack

    def get_locus_new(von_bis, von_rv, bis_f, bis_rv):
        sLocus = ""
        oErr = ErrHandle()
        try:
            html = []
            # Calculate from
            lst_from = []
            if not von_bis is None: lst_from.append(von_bis)
            if von_rv != "": lst_from.append(".{}".format(von_rv))
            sFrom = "".join(lst_from)

            # Calculate until
            lst_until = []
            if not bis_f is None: lst_until.append(bis_f)
            if bis_rv != "": lst_until.append(".{}".format(bis_rv))
            sUntil = "".join(lst_until)

            # Combine the two
            if sFrom == sUntil:
                sLocus = sFrom
            else:
                sLocus = "{}-{}".format(sFrom, sUntil)

        except:
            msg = oErr.get_error_message()
            oErr.DoError("get_locus")
        # Return our result
        return sLocus

    def get_manuscript_id(handschrift):
        """Get the correct manuscript, based on handschrift"""

        obj = None
        oErr = ErrHandle()
        try:
            manuext = [x['manu__id'] for x in ManuscriptExternal.objects.filter(externalid=handschrift).values('manu__id')]
            if len(manuext) > 0:
                obj = manuext[0]
                if len(manuext) > 1:
                    iStop = 1
                    oErr.Status("get_manuscript_id: more than one candidate for handschrift [{}]".format(handschrift))
        except:
            msg = oErr.get_error_message()
            oErr.DoError("get_manuscript")
        # Return our result
        return obj

    def get_sermon_org(oInhalt, sLocus):
        """Get the correct sermon, based on opera and manuscript"""

        obj = None
        oErr = ErrHandle()
        bProcessed = False
        ext_inhalt = "huwin"    # HUWA inhalt
        ext_opera = "huwop"     # HUWA opera
        try:
            manu_id = -1
            # First try to get it one way
            inhaltid = oInhalt.get("id")
            sermon_ids = [x['sermon__id'] for x in SermonDescrExternal.objects.filter(
                externaltype=ext_inhalt, externalid=inhaltid).values('sermon__id')]
            if len(sermon_ids) > 0:
                qs = SermonDescr.objects.filter(id__in=sermon_ids)
                bProcessed = True
            else:
                handschrift = oInhalt.get("handschrift")
                opera = oInhalt.get("opera")
                manu_id = get_manuscript_id( handschrift)
                # There could be a number of sermons with this opera
                sermon_ids = [x['sermon__id'] for x in SermonDescrExternal.objects.filter(
                    externaltype=ext_opera, externalid=opera).values('sermon__id')]
                # Now find the correct one
                # qs = SermonDescr.objects.filter(id__in=sermon_ids, msitem__codico__manuscript__id=manu_id)
                #lst_ids = [x for x in sermon_ids if SermonDescr.objects.filter(id=x, msitem__codico__manuscript__id=manu_id).count() > 0]

                manu_sermons = [x['id'] for x in SermonDescr.objects.filter(msitem__codico__manuscript__id=manu_id).values('id')]
                lst_ids = [x for x in sermon_ids if x in manu_sermons]

                #lst_ids = []
                #for sermon_id in sermon_ids:
                #    if SermonDescr.objects.filter(id=sermon_id, msitem__codico__manuscript__id=manu_id).count() > 0:
                #        lst_ids.append(sermon_id)
                qs = SermonDescr.objects.filter(id__in=lst_ids)
            # Evaluate the outcome
            if qs.count() == 1:
                obj = qs.first()
            elif qs.count() > 1:
                # We need to specify an additional filter for locus
                qs = qs.filter(locus=sLocus)
                if qs.count() > 1:
                    oErr.Status("adapt_huwafolionumbers/get_sermon too many sermons for opera={}, manu={}".format(opera, manu_id))
                    x = qs.last()
                else:
                    obj = qs.first()
            elif qs.count() == 0:
                oErr.Status("adapt_huwafolionumbers/get_sermon NO sermon for opera={}, manu={}".format(opera, manu_id))

            if not obj is None and not bProcessed:
                # Add this link into SermonDescrExternal
                srm_ext = SermonDescrExternal.objects.create(externalid=inhaltid, externaltype=ext_inhalt, sermon=obj)

        except:
            msg = oErr.get_error_message()
            oErr.DoError("get_sermon_org")
        # Return our result
        return obj

    def get_sermon(opera, manu_id):
        """Get the correct sermon, based on opera and manuscript"""

        obj = None
        oErr = ErrHandle()
        try:
            # There could be a number of sermons with this opera
            sermon_ids = [x['sermon__id'] for x in SermonDescrExternal.objects.filter(externalid=opera).values('sermon__id')]
            # Now find the correct one
            qs = SermonDescr.objects.filter(id__in=sermon_ids, msitem__codico__manuscript__id=manu_id)
            if qs.count() == 1:
                obj = qs.first()
            elif qs.count() > 1:
                oErr.Status("adapt_huwafolionumbers/get_sermon too many sermons for opera={}, manu={}".format(opera, manu_id))
                x = qs.last()
            elif qs.count() == 0:
                oErr.Status("adapt_huwafolionumbers/get_sermon NO sermon for opera={}, manu={}".format(opera, manu_id))
        except:
            msg = oErr.get_error_message()
            oErr.DoError("get_sermon")
        # Return our result
        return obj

    oErr = ErrHandle()
    oRom = RomanNumbers()
    bResult = True
    bInhalt = True
    msg = ""
    huwa_tables = ['inhalt']
    try:
        # Read the HUWA database
        table_info = read_huwa()
        # (5) Load the tables that we need
        tables = get_huwa_tables(table_info, huwa_tables)

        # Walk the INHALT table
        lInhalt = tables['inhalt']
        len_inhalt = len(lInhalt)
        iCount = 0
        for idx, oInhalt in enumerate(lInhalt):
            # Show where we are
            oErr.Status("Processing {}/{} changes: {}".format(idx+1, len_inhalt, iCount))

            bNeedAdaptation = False

            # Get the original locus
            sLocus = get_locus_org(oInhalt)

            # Try to get the correct sermon
            sermon = get_sermon_org(oInhalt, sLocus)

            if not bInhalt:

                # Get the value of the von_rv field and the bis_rv field
                von_rv = str(oInhalt.get("von_rv", ""))
                bis_rv = str(oInhalt.get("bis_rv", ""))
            
                # Check if this needs treatment: length of von_rv or bis_rv is larger than 0
                if len(von_rv) > 1:
                    lst_von_bis = str(oInhalt.get("von_bis", "")).split(".")
                    von_bis = get_folio_number(lst_von_bis)
                    bNeedAdaptation = True

                if len(bis_rv) > 1:
                    lst_bis_f = str(oInhalt.get("bis_f", "")).split(".")
                    bis_f = get_folio_number(lst_bis_f)
                    bNeedAdaptation = True

                # Only perform adaptation if necessary
                if bNeedAdaptation:
                    # Calculate the locus as it should be set in MsItem
                    sLocus = get_locus_new(von_bis, von_rv, bis_f, bis_rv)

                    ## Get the correct PASSIM item, by looking at:
                    ## - 'opera'       -> SermonDescrExternal > SermonDescr
                    ## - 'handschrift' -> ManuscriptExternal  > Manuscript
                    #handschrift = oInhalt.get("handschrift")
                    #opera = oInhalt.get("opera")
                    #manuscript_id = get_manuscript_id( handschrift)
                    #sermon = get_sermon( opera , manuscript_id)

                    # We now have the locus: Check the PASSIM item
                    if sermon is None:
                        # Something went wrong
                        oErr.Status("Could not get sermon for handschrift={}, opera={}".format(handschrift, opera))
                    else:
                        # See if we need to change the locus
                        if sermon.locus != sLocus:
                            sermon.locus = sLocus
                            sermon.save()
                            iCount += 1


        # Everything has been processed correctly now
        msg = "ok"
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

def adapt_huwa_opera_import():
    oErr = ErrHandle()
    bResult = True
    msg = ""
    # Specific Report items that need to be processed
    report_id = [32, 34]
    
    try:
        # Process report items
        for report in Report.objects.filter(id__in=report_id):
            # Get the contents as a data object
            oData = json.loads(report.contents)
            # Get the list of objects that have been read
            lst_read = oData.get("read")
            # Walk through this list looking for gold/opera matches
            for oItem in lst_read:
                gold_id = oItem.get("gold")
                opera_id = oItem.get("opera")
                if not gold_id is None and not opera_id is None and isinstance(gold_id, int) and isinstance(opera_id, int):
                    # We have a match!! - Check if it is already in SermonGoldExternal
                    obj = SermonGoldExternal.objects.filter(gold_id=gold_id, externalid=opera_id).first()
                    if obj is None:
                        # Check if the gold is still there
                        gold = SermonGold.objects.filter(id=gold_id).first()
                        if not gold is None:
                            # Create it
                            obj = SermonGoldExternal.objects.create(gold=gold, externalid=opera_id, externaltype = EXTERNAL_HUWA_OPERA)
                            print("Created SermonGoldExternal opera={} gold={}".format(opera_id, gold_id))
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

def adapt_sgcount():
    oErr = ErrHandle()
    bResult = True
    msg = ""
    
    try:
        # Walk all SSGs
        with transaction.atomic():
            for ssg in EqualGold.objects.all():
                ssg.set_sgcount()
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

def adapt_huwa_ssg_literature():
    """Issue #587: add editions and literature to HUWA SSGs"""

    oErr = ErrHandle()
    bResult = True
    msg = ""
    try:
        pass
    except:
        bResult = False
        msg = oErr.get_error_message()
    return bResult, msg

def adapt_huwa_edilit_remove():
    """Clear contents of field [edilit] from SG and from SSG"""

    oErr = ErrHandle()
    bResult = True
    msg = ""
    try:
        # (1) SG
        with transaction.atomic():
            for obj in SermonGold.objects.all():
                if not obj.edinote is None:
                    obj.edinote = ""
                    obj.edinote = None
                    obj.save()
        # (1) SSG
        with transaction.atomic():
            for obj in EqualGold.objects.all():
                if not obj.edinote is None:
                    obj.edinote = ""
                    obj.edinote = None
                    obj.save()
    except:
        bResult = False
        msg = oErr.get_error_message()
    return bResult, msg

def adapt_searchable():
    # Issue #522: mono-projectal SSGs must have atype 'acc'
    oErr = ErrHandle()
    bResult = True
    msg = ""
    fields_sermondescr = ['incipit', 'explicit', 'fulltext', 'title', 'subtitle', 'sectiontitle']
    fields_equalgold = ['incipit', 'explicit', 'fulltext']
    fields_sermongold = ['incipit', 'explicit']

    def adapt_value(obj, field):
        # Need to know the name of the [srch] field
        srchfield = "srch{}".format(field)         
        # Get current value of that srch-field           
        srch_current = getattr(obj, srchfield)
        if srch_current is None: srch_current = ""
        # Get value as it should be
        srch_new = get_searchable(getattr(obj, field))
        # Compare and correct
        if srch_current != srch_new:
            setattr(obj, srchfield, srch_new)
            obj.save()

    try:
        # Process SermonDescr
        with transaction.atomic():
            for obj in SermonDescr.objects.all():
                for field in fields_sermondescr:
                    # Adapt value if needed
                    adapt_value(obj, field)

        # Process EqualGold
        with transaction.atomic():
            for obj in EqualGold.objects.all():
                for field in fields_equalgold:
                    # Adapt value if needed
                    adapt_value(obj, field)

        # Process SermonGold
        with transaction.atomic():
            for obj in SermonGold.objects.all():
                for field in fields_sermongold:
                    # Adapt value if needed
                    adapt_value(obj, field)

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


def adapt_scope_hc():
    """One-time change scope of HCs to public"""

    oErr = ErrHandle()
    bResult = True
    msg = ""
    name = "Passim"
    try:
        with transaction.atomic():
            qs = Collection.objects.filter(settype="hc")
            for obj_coll in qs:
                if obj_coll.scope != "publ":
                    obj_coll.scope = "publ"
                    obj_coll.save()
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


# ========== Part of profile_list ======================
def adapt_projecteditors():
    """Make sure that project approvers are also in the list of project editors"""

    oErr = ErrHandle()
    bResult = True
    msg = ""
        
    try:
        # Check if there are any editors already
        count = ProjectEditor.objects.count()
        if count == 0:
            # There are no editors yet: copy them from ProjectApprover
            for obj in ProjectApprover.objects.all():
                project = obj.project
                profile = obj.profile
                editor = ProjectEditor.objects.create(project=project, profile=profile)
    except:
        bResult = False
        msg = oErr.get_error_message()
    return bResult, msg


# ========== Part of onlinesources_list ======================

def adapt_unicode_name_online():
    """Make sure that sortname is filled with the unicode version of name in OnlineSources"""

    oErr = ErrHandle()
    bResult = True
    msg = ""
    try: 
        # Iterate over all objects in the OnlineSources table
        for obj in OnlineSources.objects.all():           
            name = obj.name
            # Decode the unicode
            name_dec = unidecode(name)
            # Store the new version
            obj.sortname = name_dec
            obj.save()

    except:
        bResult = False
        msg = oErr.get_error_message()
    return bResult, msg


def adapt_unicode_name_litref():
    """Make sure that sortname is filled with the unicode version of short in Litref"""

    oErr = ErrHandle()
    bResult = True
    msg = ""
    try: 
        # Iterate over all objects in the OnlineSources table
        for obj in Litref.objects.all():           
            short = obj.short
            # Decode the unicode
            short_dec = unidecode(short)
            print(short, "  ",  short_dec)            
            # Store the new version
            obj.sortref = short_dec
            obj.save()

    except:
        bResult = False
        msg = oErr.get_error_message()
    return bResult, msg





# ========== Part of keyword_list ======================
def adapt_kwcategories():
    """Make sure each keyword gets put into the correct category"""

    def get_kw_cat(lst_kwcat, sKeyword):
        sBack = None

        # Look at the LC variant
        lower_kw = sKeyword.lower()
        # Get the category of the keyword
        for oItem in lst_kwcat:
            # Get the keyword
            item_kw = oItem.get("Keyword").lower()
            # Check if this is a :* kw or not
            if ":*" in item_kw:
                # Check the matching part
                kw_length = len(item_kw) - 1
                if item_kw[:kw_length] == lower_kw[:kw_length]:
                    # Found it: get the category
                    sBack = oItem.get("kwcat")
                    break
            else:
                # expecting coincidence
                if item_kw == lower_kw:
                    # Found it: get the category
                    sBack = oItem.get("kwcat")
                    break
        # DOuble check
        if sBack is None:
            iStop = 1
        # Return what we found
        return sBack

    oErr = ErrHandle()
    bResult = True
    msg = ""
        
    try:
        # Read the kwcat JSON
        lst_kwcat = read_kwcategories()
        lst_missed = []

        # Check if there are any editors already
        qs = Keyword.objects.all()
        for obj in qs:
            # Get the current keyword and its category
            sKeyword = obj.name
            sCurrentCat = obj.category
            # Get the category that this should have
            sFutureCat = get_kw_cat(lst_kwcat, sKeyword)
            if sFutureCat is None:
                # Add the kw to the dictionary with missed keywords
                lst_missed.append(sKeyword)
            elif sCurrentCat != sFutureCat:
                # CHange it
                obj.category = sFutureCat
                obj.save()
        # Show all the keywords that were missed
        oErr.Status("Missed keywords: {}".format(lst_missed))
    except:
        bResult = False
        msg = oErr.get_error_message()
    return bResult, msg


