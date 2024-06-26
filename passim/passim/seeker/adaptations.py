"""
Adaptations of the database that are called up from the (list)views in the SEEKER app.
"""

from tracemalloc import start
from unicodedata import category
from django.db import transaction
import re
import json
import os
import csv
import sqlite3
import pandas as pd
import copy
from unidecode import unidecode
from passim.settings import MEDIA_DIR, MEDIA_ROOT

# ======= imports from my own application ======
from passim.utils import ErrHandle, RomanNumbers
from passim.basic.models import UserSearch
from passim.seeker.models import ManuscriptSimilar, get_crpp_date, get_current_datetime, process_lib_entries, get_searchable, get_now_time, \
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
    CollectionProject, EqualGoldProject, OnlineSources, CollectionType, \
    ProjectApprover, ProjectEditor, ManuscriptExternal, SermonDescrExternal, \
    get_reverse_spec, LINK_EQUAL, LINK_PRT, LINK_BIDIR, LINK_PARTIAL, STYPE_IMPORTED, STYPE_EDITED, LINK_UNSPECIFIED, \
    EXTERNAL_HUWA_OPERA, excel_to_list
from passim.reader.models import Edition, Literatur, OperaLit
from passim.reader.views import read_kwcategories


adaptation_list = {
    "manuscript_list": [
        'sermonhierarchy', 'msitemcleanup', 'locationcitycountry', 'templatecleanup', 
        'feastupdate', 'codicocopy', 'passim_project_name_manu', 'doublecodico',
        'codico_origin', 'import_onlinesources', 'dateranges', 'huwaeditions',
        'supplyname', 'usersearch_params', 'huwamanudate', 'baddateranges', 'correctdateranges',
        'collectiontype', 'huwadoubles', 'manu_setlists', 'similars'], # 'sermonesdates',
    'sermon_list': ['nicknames', 'biblerefs', 'passim_project_name_sermo', 'huwainhalt',  'huwafolionumbers',
                    'projectorphans', 'codesort', 'siglists'],
    'sermongold_list': ['sermon_gsig', 'huwa_opera_import'],
    'equalgold_list': [
        'author_anonymus', 'latin_names', 'ssg_bidirectional', 's_to_ssg_link', 
        'hccount', 'scount', 'sgcount', 'ssgcount', 'ssgselflink', 'add_manu', 'passim_code', 'passim_project_name_equal', 
        'atype_def_equal', 'atype_acc_equal', 'passim_author_number', 'huwa_ssg_literature',
        'huwa_edilit_remove', 'searchable', 'af_stype'],
    'profile_list': ['projecteditors', 'projectdefaults'],
    'provenance_list': ['manuprov_m2m'],
    'keyword_list': ['kwcategories', 'kwtopics', 'kwtopicdist'],
    "collhist_list": ['passim_project_name_hc', 'coll_ownerless', 'litref_check', 'scope_hc',
                      'name_datasets', 'coll_setlists'],
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

                # Do not accept 3000
                if manu.yearfinish == 3000:
                    manu.yearfinish = yearstart
                    bNeedSaving = True
                    
                if bNeedSaving:
                    manu.save()
    except:
        bResult = False
        msg = oErr.get_error_message()
    return bResult, msg

def adapt_baddateranges():
    oErr = ErrHandle()
    bResult = True
    msg = ""
    lst_ranges = [ [100, 100], [9999, 9999], [1800, 2020] ]

    try:
        lst_delete = []
        for oRange in lst_ranges:
            yearstart = oRange[0]
            yearfinish = oRange[1]
            lst_ids = [x['id'] for x in Daterange.objects.filter(yearstart=yearstart, yearfinish=yearfinish).values('id')]
            for id_this in lst_ids:
                if not id_this in lst_delete:
                    lst_delete.append(id_this)
        # Do we have some ids?
        if len(lst_delete) > 0:
            # Remove them
            Daterange.objects.filter(id__in=lst_delete).delete()
            oErr.Status("adapt_baddaterange removed: {}".format(lst_delete))
    except:
        bResult = False
        msg = oErr.get_error_message()
    return bResult, msg

def adapt_correctdateranges():
    """Try to correct dateranges. Make use of preferential order.
    
    1 - daterange.years
    2 - codico.years
    3 - manuscript.years
    """

    def get_codico_years(oCodi):
        lBack = None
        codico_st = oCodi.get("yearstart")
        codico_fi = oCodi.get("yearfinish")
        if codico_st and codico_fi:
            if codico_fi > codico_st:
                if codico_st > 100 and codico_fi < 1900:
                    lBack = [codico_st, codico_fi]
        return lBack

    def get_manu_years(oCodi):
        lBack = None
        manu_st = oCodi.get("manuscript__yearstart")
        manu_fi = oCodi.get("manuscript__yearfinish")
        if manu_st and manu_fi:
            if manu_fi > manu_st:
                if manu_st > 100 and manu_fi < 1900:
                    lBack = [manu_st, manu_fi]
        return lBack

    def get_dr_years(lst_dr):
        # Get the first and last daterange years
        lBack = None
        if len(lst_dr) > 0:
            lBack = [lst_dr[0]['yearstart'], lst_dr.last()['yearfinish']]
        return lBack

    oErr = ErrHandle()
    bResult = True
    msg = ""

    try:
        # Walk all codicological units
        lst_codico = Codico.objects.all().values(
            'id', 'yearstart', 'yearfinish', 'manuscript__id', 'manuscript__yearstart', 'manuscript__yearfinish')
        for oCodico in lst_codico:
            # Extract the codico id
            codico_id = oCodico.get("id")
            manu_id = oCodico.get('manuscript__id')

            # Extract the dateranges for DR, Codico, Manuscript
            dr_yrs = get_dr_years(Daterange.objects.filter(codico__id = oCodico['id']).order_by(
                'yearstart', 'yearfinish').values('yearstart', 'yearfinish'))
            codico_yrs = get_codico_years(oCodico)
            manu_yrs = get_manu_years(oCodico)

            # Start testing...
            if dr_yrs is None:
                # There are no datarange years
                good_yrs = None
                if codico_yrs is None:
                    # Take the manuscript years as a starting point
                    if not manu_yrs is None:
                        # Create datarange from manuscript years
                        obj_dr = Daterange.objects.create(codico_id=codico_id, yearstart=manu_yrs[0], yearfinish=manu_yrs[1])
                        oErr.Status("Created daterange [{}-{}] for codico {} from manuscript".format(manu_yrs[0], manu_yrs[1], codico_id))
                        # Take over the daterange years
                        codico = Codico.objects.filter(id=codico_id).first()
                        codico.yearstart = manu_yrs[0]
                        codico.yearfinish = manu_yrs[1]
                        codico.save()
                        oErr.Status("Created codico {} years [{}-{}] from manuscript".format(codico_id, manu_yrs[0], manu_yrs[1]))
                else:
                    # Create datarange from codico
                    obj_dr = Daterange.objects.create(codico_id=codico_id, yearstart=codico_yrs[0], yearfinish=codico_yrs[1])
                    oErr.Status("Created daterange [{}-{}] for codico {} from codico".format(codico_yrs[0], codico_yrs[1], codico_id))

            elif codico_yrs is None:
                # Take over the daterange years
                codico = Codico.objects.filter(id=codico_id).first()
                codico.yearstart = dr_yrs[0]
                codico.yearfinish = dr_yrs[1]
                codico.save()
                oErr.Status("Created codico {} years [{}-{}] from daterange".format(codico_id, dr_yrs[0], dr_yrs[1]))
                # Double check the manuscript years
                if manu_yrs is None:
                    # Take over the daterange years
                    manu = codico.manuscript
                    manu.yearstart = dr_yrs[0]
                    manu.yearfinish = dr_yrs[1]
                    manu.save()
                    oErr.Status("Created manuscript {} years [{}-{}] from daterange".format(manu.id, dr_yrs[0], dr_yrs[1]))

            elif manu_yrs is None:
                # Getting here means that we have dr_yrs and codico_yrs
                manu = Manuscript.objects.filter(id=manu_id).first()
                manu.yearstart = dr_yrs[0]
                manu.yearfinish = dr_yrs[1]
                manu.save()
                oErr.Status("Created manuscript {} years [{}-{}] from daterange".format(manu.id, dr_yrs[0], dr_yrs[1]))

    except:
        bResult = False
        msg = oErr.get_error_message()
    return bResult, msg

def adapt_sermonesdates():
    oErr = ErrHandle()
    bResult = True
    msg = ""
    count_miss = 0
    count_hit = 0
    FILE_NAME = "check_dates_passim_2.xlsx"

    try:
        # Expected column names
        lExpected = ["first_line", "old_date", "new_dates", "shelfmark"]
        # Names of the fields in which these need to be transformed
        lField = ["first_line", "old_date", "new_dates", "shelfmark"]

        # Expected filename
        filename = os.path.abspath(os.path.join(MEDIA_DIR, "passim", FILE_NAME))
        oErr.Status("Reading file {}".format(filename))

        if not os.path.exists(filename):
            oErr.Status("Cannot find this file")
            bResult = False
            msg = "Cannot find file {}".format(filename)

        else:
            # Get the right dataset
            dataset = Collection.objects.filter(name__icontains="SERMONES FILE").first()

            # Convert the data into a list of objects
            bResult, lst_sermones, msg = excel_to_list(None, filename, lExpected, lField)

            if bResult and not dataset is None:

                # Create a dictionary mapping the shelfmark to the manuscript ID
                oManu = {x.manuscript.get_full_name() : x.manuscript.id for x in dataset.manuscript_col.all()}
                oManuFlat = {x.manuscript.get_full_name().replace(' ', '').lower() : x.manuscript.id for x in dataset.manuscript_col.all()}

                # Read the objects
                for oSermon in lst_sermones:
                    # Treat this sermon
                    old_date = oSermon.get("old_date")
                    new_dates = oSermon.get("new_dates")
                    shelfmark = oSermon.get("shelfmark")

                    # Figure out the dates
                    sDates = old_date if new_dates is None or new_dates == "" else new_dates
                    if sDates != "" and sDates != "?":
                        lDates = re.split(r'\,\s*', sDates)
                        lst_date = []
                        for sDate in lDates:
                            ardate = sDate.split("-")
                            if len(ardate) > 1:
                                lst_date.append(dict(yearstart = ardate[0], yearfinish = ardate[1]))
                            elif len(ardate) == 1:
                                lst_date.append(dict(yearstart = ardate[0], yearfinish = ardate[0]))

                        # Turn shelfmark into city/library/idno
                        manu_id = oManu.get(shelfmark)
                        if manu_id is None:
                            # Re-try using flat
                            manu_id = oManuFlat.get(shelfmark.replace(' ', '').lower())
                        if manu_id is None:
                            # Cannot find this one
                            oErr.Status("Cannot locate SERMONES shelfmark [{}]".format(shelfmark))
                            count_miss += 1
                        else:
                            # Get the right manuscript
                            manuscript = Manuscript.objects.filter(id=manu_id).first()
                            if manuscript is None:
                                oErr.Status("Cannot locate SERMONES manuscript [{}]".format(shelfmark))
                                count_miss += 1
                            else:
                                count_hit += 1
                                # Get the codico - assuming there is only one
                                codico = Codico.objects.filter(manuscript=manuscript).first()
                                # Review the dates
                                for oDate in lst_date:
                                    yearstart = oDate.get('yearstart')
                                    yearfinish = oDate.get('yearfinish')
                                    dr = Daterange.objects.filter(codico=codico, yearstart=yearstart, yearfinish=yearfinish).first()
                                    if dr is None:
                                        oErr.Status("Manu [{}]: adding daterange [{},{}]".format(shelfmark, yearstart, yearfinish))
                                        dr = Daterange.objects.create(codico=codico, yearstart=yearstart, yearfinish=yearfinish)
                            

                        # Check and adapt the dates

        # Give a report
        oErr.Status("sermonesdates: hit={} miss={}".format(count_hit, count_miss))
    except:
        bResult = False
        msg = oErr.get_error_message()
    return bResult, msg

def adapt_collectiontype():
    oErr = ErrHandle()
    bResult = True
    msg = ""
    oCtype = dict(sermo="Manifestation", super="Authority File", manu="Manuscript", gold="Sermon Gold")
    try:
        # Possibly fill the CollectionType table
        count = CollectionType.objects.count()
        if count == 0:
            for k,v in oCtype.items():
                obj = CollectionType.objects.create(name=k, full=v)
        # Get mapping from short name to id
        oCtypeMap = {}
        for obj in CollectionType.objects.all():
            oCtypeMap[obj.name] = obj
        # Make a link from every collection
        for obj in Collection.objects.all():
            # Get the type
            ctype = obj.type
            # Get the id of CollectionType
            typename = oCtypeMap[ctype]
            # Check if it is there
            if obj.typename is None or obj.typename.id != typename.id:
                obj.typename = typename
                obj.save()

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

def adapt_huwadoubles():
    """Try to combine HUWA-imported manuscripts that are the same (library/idno), but have different handschrift entries """

    oErr = ErrHandle()
    bResult = True
    bDebug = False
    msg = ""
    huwa_tables = ['handschrift']
    try:

        # Now try to calculate via the Passim way
        prj_huwa = Project2.objects.filter(name__icontains="huwa").first()
        qs = Manuscript.objects.filter(manuscript_proj__project=prj_huwa, 
                                       mtype="man", 
                                       library__isnull=False).exclude(idno="").order_by("library__id", "idno")
        q_len = qs.count()
        key = ""
        oManus = {}
        for obj in qs:
            key = "{}|{}".format(obj.library.id, obj.idno)
            if not key in oManus:
                oManus[key] = []
            oManus[key].append(obj.id)
            
        # Get all the manuscripts with the same shelfmark, occurring more than once
        lManuDouble = []
        iManuLongest = 0
        for key, lst_ids in oManus.items():
            lLength = len(lst_ids)
            if lLength > 1:
                lManuDouble.append(dict(key=key, manuids=lst_ids))
                if lLength > iManuLongest:
                    iManuLongest = lLength
        x = len(lManuDouble)


        # Read the HUWA database
        table_info = read_huwa()
        # (5) Load the tables that we need
        tables = get_huwa_tables(table_info, huwa_tables)
        # Get the table of handschrift
        lHandschrift = tables['handschrift']

        # Start a dictionary
        oCombi = {}
        oFaszikel = {}
        # Walk the handschrifts
        for oHandschrift in lHandschrift:
            externalid = oHandschrift.get("id") 
            # Get the library id and the signatur
            library_id = oHandschrift.get("bibliothek")
            signatur = oHandschrift.get("signatur")
            # Exclude empty signatur
            if not signatur is None: # and len(signatur.strip()) > 0 and not signatur[0] == "?":

                if "10440" in signatur:
                    iStop = 1

                # Combine into one key
                key = "{}|{}".format(library_id, signatur)
                if not key in oCombi:
                    oCombi[key] = []
                if not key in oFaszikel:
                    oFaszikel[key] = []

                # Add the externalid to the dictionary
                oCombi[key].append(externalid)

                # Also get the faszikel (codices) information
                faszikel_id = oHandschrift.get("faszikel")
                # And get the manuscript id
                manuscript = Manuscript.objects.filter(manuexternals__externalid=externalid).first()
                if not manuscript is None:
                    manuscriptid = manuscript.id
                    oFaszikel[key].append(dict(faszikel=faszikel_id, handschrift=externalid, manuscript=manuscriptid))
                else:
                    oErr.Status("Could not find manuscript for handschrift={} [{}]".format(externalid, key))

        # Get manuscripts with more than one differing faszikel
        lst_joinmanu = []
        lst_head = ["Key", "Handschr.Start", "Manuscript", "Handschrift", "Faszikel"]
        print("\t".join(lst_head))
        for key, lst_faszikel in oFaszikel.items():
            if "10440" in key:
                iStop = 1
            if len(lst_faszikel) > 1:
                # There are multiple handschrift items: do they have different faszikels?
                #if lst_faszikel[0] != lst_faszikel[-1]:
                if True:
                    # Figure out what the starting one is (the first one having 100)
                    start_id = -1
                    start_manu = -1
                    lst_f = []
                    for f in lst_faszikel:
                        if start_id < 0 and f['faszikel'] == 100:
                            start_id = f['handschrift']
                            start_manu = f['manuscript']
                        else:
                            lst_f.append(copy.copy(f))
                    # Sort the list of faszikel
                    lst_f_sorted = sorted(lst_f, key=lambda x:x['faszikel'])
                    # They potentiall differ: add to list
                    oJoin = dict(key=key, faszikels=lst_f_sorted, start=start_id, manu=start_manu)

                    # Check if the manuscript differs over de faszikels
                    manuid = start_manu
                    bSame = False
                    for oItem in lst_faszikel:
                        if oItem['manuscript'] == manuid:
                            bSame=True
                            exit
                    lst_cell = []
                    lst_cell.append("{}".format(key))
                    lst_cell.append("{}".format(start_id))
                    lst_cell.append("{}".format(start_manu))
                    lst_cell.append("{}".format(start_id))
                    lst_cell.append("{}".format("100"))
                    print("\t".join(lst_cell))
                    # Also just provide lines for a CSV
                    for oFaszikel in lst_f_sorted:
                        lst_cell = []
                        lst_cell.append("{}".format(key))
                        lst_cell.append("{}".format(start_id))
                        lst_cell.append("{}".format(oFaszikel['manuscript']))
                        lst_cell.append("{}".format(oFaszikel['handschrift']))
                        lst_cell.append("{}".format(oFaszikel['faszikel']))
                        print("\t".join(lst_cell))
                    lst_joinmanu.append(oJoin)

        lJoining = len(lst_joinmanu)
        print(lst_joinmanu)

        iStop = 1

        # Walk the manuscripts that can be joined, potentially...
        for oJoining in lst_joinmanu:
            # Get the manuscript associated with the start_id
            start_id = oJoining['start']
            lst_faszikel = oJoining['faszikels']
            key = oJoining['key']
            oErr.Status("Joining key={}".format(key))
            manuscript = Manuscript.objects.filter(manuexternals__externalid=start_id).first()
            order = 1
            if not manuscript is None:
                oErr.Status("Treating manuscript id={} - handschrift={}".format(manuscript.id, start_id))
                lst_delete = []
                # Walk all the faszikels
                for oFaszikel in lst_faszikel:
                    # Get the handschrift id
                    externalid = oFaszikel['handschrift']
                    # Find the codicological unit
                    codico = Codico.objects.filter(manuscript__manuexternals__externalid=externalid).first()
                    if not codico is None:
                        order += 1
                        old_manu_id = codico.manuscript.id
                        lst_delete.append(old_manu_id)
                        # debug
                        oErr.Status("Adding codico={} that was manuscript={}".format(codico.id, old_manu_id))
                        # Change to the new manuscript
                        codico.manuscript = manuscript
                        codico.order = order
                        codico.save()
                        # Make sure to change the MsItems connected to this one
                        for msitem in codico.codicoitems.all():
                            msitem.manu = manuscript
                            msitem.save()
                            # Walk the SermonDescr items
                            for serm in msitem.itemsermons.all():
                                serm.manu = manuscript
                                serm.save()
                        # Find the ManuscriptExternal item
                        obj = ManuscriptExternal.objects.filter(externalid=externalid, manu_id=old_manu_id).first()
                        if not obj is None:
                            # Set to the correct manuscript
                            obj.manu = manuscript
                            # Add the codico information
                            obj.externaltextid = "codico;{}".format(codico.id)
                            obj.save()

                # Is there anything to be deleted?
                if len(lst_delete) > 0:
                    # Remove the manuscripts
                    Manuscript.objects.filter(id__in=lst_delete).delete()

                    
        iStop = 1
    except:
        bResult = False
        msg = oErr.get_error_message()
        oErr.DoError("adaptations/adapt_huwadoubles")
    # Return the table that we found
    return bResult, msg

def adapt_manu_setlists():
    """Adapt the setlists from the point of view of manuscripts"""

    oErr = ErrHandle()
    bResult = True
    bDebug = False
    msg = ""
    try:
        lst_setlist = []
        lst_setlistid = []
        for manu in Manuscript.objects.filter(mtype='man'):
            for setlist in manu.manuscript_setlists.all():
                if not setlist.id in lst_setlistid:
                    lst_setlistid.append(setlist.id)
                    lst_setlist.append(setlist)

        # Now address all the setlists
        for setlist in lst_setlist:
            setlist.adapt_rset(rset_type = "adaptations manu")


        # Everything has been processed correctly now
        msg = "ok"
    except:
        bResult = False
        msg = oErr.get_error_message()
    return bResult, msg

def adapt_similars():
    """Fill the manuscript deduplications"""

    oErr = ErrHandle()
    bResult = True
    msg = ""
    DEDUPS_FILE = "manu_dedups.json"
    DEDUPS_FILE = "manuscript_duplicates_id.json"
    try:
        filename = os.path.abspath(os.path.join(MEDIA_ROOT, "passim", DEDUPS_FILE))
        if os.path.exists(filename):
            # Read the file
            with open(filename, "r") as f:
                lst_dedup = json.load(f)

            # Show where we are
            oErr.Status("Read adapt_similars file: {}".format(filename))

            # List of additions to be made
            lst_add = []
            count_del = 0

            # Simply delete all previous values
            ManuscriptSimilar.objects.all().delete()
            ## Get a list of current manuscriptIds addressed by ManuscriptSimilar
            #lst_current_ids = [x['src__id'] for x in ManuscriptSimilar.objects.all().values('src__id').distinct()]
            
            # walk through the similars
            for idx, oItem in enumerate(lst_dedup):
                if idx % 500 == 0:
                    print("adapt_similars: {}".format(idx))
                # Get the manuscript and the duplicate candicates
                manuscriptId = oItem.get("manuscriptId")
                duplicateCandidates = oItem.get("duplicateCandidates")
                if not manuscriptId is None and not duplicateCandidates is None:
                    ## Make sure to remove this id from the [lst_current_ids]
                    #if manuscriptId in lst_current_ids:
                    #    lst_current_ids.remove(manuscriptId)

                    # Get existing list of duplicateCandidates
                    oCurrent = { x['dst__id'] : x['id']
                                   for x in ManuscriptSimilar.objects.filter(src_id=manuscriptId).values("id", "dst__id")}
                    # (1) create a list of deletables
                    delete_id = []
                    for dst_id, sim_id in oCurrent.items():
                        if not dst_id in duplicateCandidates:
                            delete_id.append(sim_id)
                    # (2) Delete whatever needs to be deleted
                    if len(delete_id) > 0:
                        ManuscriptSimilar.objects.filter(id__in=delete_id).delete()
                        count_del += len(delete_id)
                    # Prepare an addition
                    for dst_id in duplicateCandidates:
                        if not dst_id in oCurrent.keys():
                            lst_add.append(dict(src_id=manuscriptId, dst_id=dst_id))

            # Add what needs to be added
            oErr.Status("Now adding {} items...".format(len(lst_add)))
            lst_added_src = []
            with transaction.atomic():
                for idx, oItem in enumerate(lst_add):
                    # Add the item
                    obj = ManuscriptSimilar.objects.create(src_id=oItem['src_id'], dst_id=oItem['dst_id'])
                    lst_added_src.append(oItem['src_id'])
            
            ## Anything left in [lst_current_ids]?
            #if len(lst_current_ids) > 0:
            #    lst_also_delete = []
            #    for manu_id in lst_current_ids:
            #        if not manu_id in lst_added_src:
            #            lst_also_delete.append(manu_id)
            #    ManuscriptSimilar.objects.filter(src__id__in=lst_also_delete).delete()
            #    count_del += len(lst_also_delete)
            # Show what has been deleted
            oErr.Status("Deleted [ManuscriptSimilar]: {}".format(count_del))
        else:
            # This should not be signed off yet
            bResult = False
            oErr.Status("Could not find adapt_similars file: {}".format(filename))
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
                    oErr.Status("adapt_huwainhalt/get_sermon too many sermons for inhalt={} opera={}, manu={}".format(inhaltid, opera, manu_id))
                    x = qs.last()
                else:
                    obj = qs.first()
            elif qs.count() == 0:
                oErr.Status("adapt_huwainhalt/get_sermon NO sermon for inhalt={} opera={}, manu={}".format(inhaltid, opera, manu_id))

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

    def get_locus_new(von_bis, von_rv, bis_f, bis_rv):
        sLocus = ""
        oErr = ErrHandle()
        try:
            html = []
            # Calculate from
            lst_from = []
            if not von_bis is None: lst_from.append(von_bis)
            if von_rv != "": lst_from.append("{}".format(von_rv))
            sFrom = "".join(lst_from)

            # Calculate until
            lst_until = []
            if not bis_f is None: lst_until.append(bis_f)
            if bis_rv != "": lst_until.append("{}".format(bis_rv))
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

    def get_sermon_new(oInhalt):
        """Get the correct sermon, based on inhalt"""

        obj = None
        oErr = ErrHandle()
        bProcessed = False
        ext_inhalt = "huwin"    # HUWA inhalt
        try:
            qs = SermonDescr.objects.none()
            manu_id = -1
            # First try to get it one way
            inhaltid = oInhalt.get("id")
            sermon_ids = [x['sermon__id'] for x in SermonDescrExternal.objects.filter(
                externaltype=ext_inhalt, externalid=inhaltid).values('sermon__id')]
            if len(sermon_ids) > 0:
                qs = SermonDescr.objects.filter(id__in=sermon_ids)
                bProcessed = True
            else:
                # Something is wrong!!
                oErr.Status("adapt_huwafolionumbers/get_sermon_new NO entry for inhalt={}".format(inhaltid))
            # Evaluate the outcome
            if qs.count() == 1:
                obj = qs.first()
            elif qs.count() > 1:
                # We need to specify an additional filter for locus
                qs = qs.filter(locus=sLocus)
                if qs.count() > 1:
                    oErr.Status("adapt_huwafolionumbers/get_sermon_new too many sermons for inhalt={}".format(inhaltid))
                    x = qs.last()
                else:
                    obj = qs.first()
            elif qs.count() == 0:
                oErr.Status("adapt_huwafolionumbers/get_sermon_new NO sermon for inhalt={}".format(inhaltid))

        except:
            msg = oErr.get_error_message()
            oErr.DoError("get_sermon_new")
        # Return our result
        return obj

    oErr = ErrHandle()
    oRom = RomanNumbers()
    bResult = True
    msg = ""
    huwa_tables = ['inhalt']
    lst_result = []
    try:
        # Read the HUWA database
        table_info = read_huwa()
        # (5) Load the tables that we need
        tables = get_huwa_tables(table_info, huwa_tables)

        # Walk the INHALT table
        lInhalt = tables['inhalt']
        len_inhalt = len(lInhalt)
        iCount = 0
        iNoNeed = 0
        for idx, oInhalt in enumerate(lInhalt):
            # Show where we are
            if (idx + 1) % 100 == 0:
                oErr.Status("Processing {}/{} changes: {} leaving: {}".format(
                    idx+1, len_inhalt, iCount, iNoNeed))

            bNeedAdaptation = False

            # Try to get the correct sermon
            sermon = get_sermon_new(oInhalt)

            # Do we have one?
            if not sermon is None:

                # Get the value of the von_rv field and the bis_rv field
                von_rv = str(oInhalt.get("von_rv", ""))
                bis_rv = str(oInhalt.get("bis_rv", ""))
            
                # Check if this needs treatment: length of von_rv or bis_rv is larger than 0
                if len(von_rv) > 1:
                    lst_von_bis = str(oInhalt.get("von_bis", "")).split(".")
                    von_bis = get_folio_number(lst_von_bis)
                    bNeedAdaptation = True
                else:
                    lst_von_bis = str(oInhalt.get("von_bis", "")).split(".")
                    von_bis = get_folio_number(lst_von_bis)
                    bNeedAdaptation = True

                if len(bis_rv) > 1:
                    lst_bis_f = str(oInhalt.get("bis_f", "")).split(".")
                    bis_f = get_folio_number(lst_bis_f)
                    bNeedAdaptation = True
                else:
                    lst_bis_f = str(oInhalt.get("bis_f", "")).split(".")
                    bis_f = get_folio_number(lst_bis_f)
                    bNeedAdaptation = True

                # Only perform adaptation if necessary
                if bNeedAdaptation:
                    # Calculate the locus as it should be set in MsItem
                    sLocus = get_locus_new(von_bis, von_rv, bis_f, bis_rv)

                    # We now have the locus: Check the PASSIM item
                    if sermon is None:
                        # Something went wrong
                        oErr.Status("Could not get sermon for handschrift={}, opera={}".format(handschrift, opera))
                    else:
                        # See if we need to change the locus
                        if sermon.locus != sLocus:
                            # Collect all changes that are needed
                            sermon.locus = sLocus
                            iCount += 1
                            oResult = dict(sermon_id=sermon.id, locus=sLocus)
                            lst_result.append(oResult)

                            # Be sure to save the sermon, when a change has occurred
                            sermon.save()
                        else:
                            # No need to change this one
                            iNoNeed += 1


        # Everything has been processed correctly now
        msg = "ok"
    except:
        bResult = False
        msg = oErr.get_error_message()
    return bResult, msg

def adapt_projectorphans():
    """Try to re-locate sermons that are project-less"""

    oErr = ErrHandle()
    bResult = True
    msg = ""
    iCount = 0
    iSermons = 0
    try:
        # Review all project-less sermons
        qs = SermonDescr.objects.filter(sermondescr_proj__isnull=True)
        iSermons = qs.count()
        with transaction.atomic():
            for obj in qs:
                # Get the manuscript
                manu = obj.msitem.codico.manuscript
                if not manu is None:
                    # Get the manuscript object count
                    for project in manu.projects.all():
                        # Add this sermon to the project
                        sermo_proj = SermonDescrProject.objects.create(sermon=obj, project=project)
                        iCount += 1

        # Give feedback
        oErr.Status("ProjectOrphans: {} sermons, {} repairs".format(iSermons, iCount))
        # Everything has been processed correctly now
        msg = "ok"
    except:
        bResult = False
        msg = oErr.get_error_message()
    return bResult, msg

def adapt_siglists():
    """Reset the siglist field contents"""

    oErr = ErrHandle()
    bResult = True
    msg = ""
    try:
        # Re-doc the siglist in all SermonDescr
        qs = SermonDescr.objects.all()
        iNumber = qs.count()
        count = 0
        with transaction.atomic():
            for obj in qs:
                count += 1
                obj.do_signatures()
                if count % 1000 == 0:
                    oErr.Status("adapt_siglists SermonDescr {} / {}".format(count, iNumber))

        # Re-doc the siglist in all SermonGold
        qs = SermonGold.objects.all()
        iNumber = qs.count()
        count = 0
        with transaction.atomic():
            for obj in qs:
                count += 1
                obj.do_signatures()
                if count % 1000 == 0:
                    oErr.Status("adapt_siglists SermonGold {} / {}".format(count, iNumber))

        # Everything has been processed correctly now
        msg = "ok"
    except:
        bResult = False
        msg = oErr.get_error_message()
    return bResult, msg

def adapt_codesort():
    """Set the codesort field contents"""

    oErr = ErrHandle()
    bResult = True
    msg = ""
    try:
        # Create [codesort] contents for model Signature
        qs = Signature.objects.all()
        with transaction.atomic():
            for obj in qs:
                obj.do_codesort()
        # Create [codesort] contents for model SermonSignature
        qs = SermonSignature.objects.all()
        with transaction.atomic():
            for obj in qs:
                obj.do_codesort()

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
        count_remove = 0
        count_add = 0
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
                    # debugging
                    oErr.Status("Could be removed id={}".format(item.id))
                    count_remove += 1
            else:
                # Add the obj to the list
                lst_link.append(obj)
        for obj in lst_link:
            # Find the reverse link
            reverse = EqualGoldLink.objects.filter(src=obj.dst, dst=obj.src)
            if reverse.count() == 0:
                # Create the reversal
                reverse = EqualGoldLink.objects.create(src=obj.dst, dst=obj.src, linktype=obj.linktype)
                count_add += 1

        oErr.Status("SSG bidirectional report: removable={} added={}".format(count_remove, count_add))
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

def adapt_name_datasets():

    oErr = ErrHandle()
    bResult = True
    msg = ""
    try:
        # Remove everything that has no owner
        qs = Collection.objects.filter(owner__isnull=True)
        if qs.count() > 0:
            # Signal
            oErr.Status("adapt_name_datasets: removing {} datasets without owner".format(qs.count()))
            qs.delete()
        # Walk through the remainder
        for coll in Collection.objects.filter(name__isnull=True):
            if coll.name is None:
                profile = coll.owner
                username = "Anonymous" if profile is None else profile.user.username
                # If this is a new one, just make sure it gets the right name
                if coll.type != "super":
                    name = "{}_{}_{}".format(username, coll.id, coll.type)                         
                else:
                    name = "{}_{}_{}".format(username, coll.id, "af")
                coll.name = name
                coll.save()

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

def adapt_coll_setlists():
    """Adapt the setlists from the point of view of collections"""

    oErr = ErrHandle()
    bResult = True
    bDebug = False
    msg = ""
    try:
        lst_setlist = []
        lst_setlistid = []
        for coll in Collection.objects.filter(type='super'):
            for setlist in coll.collection_setlists.all():
                if not setlist.id in lst_setlistid:
                    lst_setlistid.append(setlist.id)
                    lst_setlist.append(setlist)

        # Now address all the setlists
        for setlist in lst_setlist:
            setlist.adapt_rset(rset_type = "adaptations coll")


        # Everything has been processed correctly now
        msg = "ok"
    except:
        bResult = False
        msg = oErr.get_error_message()
    return bResult, msg

def adapt_af_stype():
    """Make sure the STYPE of Authority Files is set to [imp], if otherwise undefined"""

    oErr = ErrHandle()
    bResult = True
    bDebug = False
    msg = ""
    try:
        qs = EqualGold.objects.filter(stype="-")
        with transaction.atomic():
            for obj in qs:
                obj.stype = "imp"
                obj.save()
        # Everything has been processed correctly now
        msg = "ok"
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

def adapt_projectdefaults():
    """Make sure that project defaults are stored in ProjectEditors"""

    oErr = ErrHandle()
    bResult = True
    msg = ""
        
    try:
        # Set all projecteditor rights status fields to excl
        with transaction.atomic():
            for obj in ProjectEditor.objects.all():
                obj.status = "excl"
                obj.save()

        # There are no editors yet: copy them from ProjectApprover
        with transaction.atomic():
            for obj in ProjectApprover.objects.all():
                project = obj.project
                profile = obj.profile
                editor = ProjectEditor.objects.filter(project=project, profile=profile).first()
                if not editor is None:
                    # Carry over the 'status' setting from Approver to Editor
                    editor.status = obj.status
                    editor.save()
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

def adapt_kwtopics():
    """Make sure each keyword gets put into the correct category"""

    oErr = ErrHandle()
    bResult = True
    msg = ""
        
    try:
        # The list of topics
        lst_topic_v1 = [
            "Judgment and Justice", "The Shepherd and the Herd", "Law and Sin", "Christ and the Jewish People", 
            "The Tree and its Fruits", "Renewal in Christ, the House of God", "Idolatry, Paganism, Heresy", 
            "Hope, Faith, and Salvation", "Truth, Lies, Testimony", "Prophets and the Old Testament", 
            "Eternal Joy and Beatitude", "Sin, Penitence, and Mercy", "Wheat and Chaff, Weeds", 
            "Riches and Poverty", "Death, Resurrection, Eternal Life", "Via ad Patriam, Jesus the Way", 
            "Eucharist, Food and Drink, True Satiation", "Martyrdom and Sanctity", 
            "Conflict, Hatred, Bortherly Correction", "Christus Medicus", "John the Baptist, the Word of God", 
            "Vigil, Liturgy, Exordium", "Marriage and Chastity", "Paul and His Conversion", "Light and Darkness", 
            "Concupiscentia Carnis", "Love", "The Miraculous Fisherman", "Crucifixion, the Symbol of the Cross",
            "The Kingdom of Heaven", "Jewish History, Genealogy of Christ", "Noli me tangere", "The Yoke",
            "The Lord's Prayer", "Christ and the Church", "Earthly and Heavenly Riches", "Obedience and Orthodoxy",
            "Symbolic Meaning of Numbers", "Holy Spirit", "Prayer", "The Nature of God, Trinity",
            "Temptation and the Devil", "The Promis of Eternal Life", "The Father and the Son", "Exegesis", 
            "Timor Dei", "St. Peter", "Peace, Redemption, and the Haereditas Christi", 
            "Community, Christian and Pagan Customs", "Grace, Serving the Lord", "Nativity, Mary", "Good and Evil", 
            "Pride and Humility"]
        lst_topic = [
            "The Promise of Eternal Life", "The Shepherd and the Herd", 
            "Christ as the Head of the Church, Ascension, Symbol of the Cross", "John the Baptist, the Word of God", 
            "Obedience and Orthodoxy", "The Law, the Ten Commandments", "Via ad Patriam, Jesus the Way", 
            "Light and Darkness", "Death and the Mortal Flesh", "Sin, Confession, and Penitence", 
            "Eucharist, Food and Drink, True Satiation", "Temptation and the Devil", "Prayer", "Vigil, Resurrection", 
            "Wisdom, Revelation", "Earthly and Heavenly Riches", "Joy in the Lord, Liturgy", "Concupiscentia Carnis", 
            "Faith and Charity", "The Tree and its Fruits", "Riches and Poverty", "Conflict, Hatred, Bortherly Correction", 
            "Prophets and the Old Testament", "Judgment", "Love", "Nativity, Mary", "The Father and the Son, Trinity", 
            "Renewal in Christ the Foundation", "Truth, Lies, Testimony", "St. Peter", "Justice, Grace, Retribution", 
            "Martyrdom and Sanctity", "Symbolic Meaning of Numbers", "Marriage and Chastity", "Tribulation and Felicity", 
            "The Word of God, Seeing and Hearing", "Good and Evil", "Creation", "Wheat and Chaff, Weeds", 
            "Holy Spirit, Unity of the Church", "Water, Stream?", "Christus Medicus", "The Yoke", "Peace, Unity of the Church",
            "Idolatry, Paganism, Heresy", "Christ as King, The Miraculous Fisherman", "Epiphany (and blindness of Jews)", 
            "Paul and His Conversion", "Noli me tangere", "Pride and Humility", "Exegetical motif ", 
            "Timor Dei", "The Lord's Prayer"]

        # Remove previous topics
        Keyword.objects.filter(category="top").delete()

        # Add the new topics
        for idx, topic in enumerate(lst_topic):
            sTopic = "Topic {}: {}".format(idx+1, topic)
            obj = Keyword.objects.create(name=sTopic, category="top")

        # Show all the keywords that were missed
        oErr.Status("Added topic-cateogry keywords: {}".format(lst_topic))
    except:
        bResult = False
        msg = oErr.get_error_message()
    return bResult, msg

def adapt_kwtopicdist():
    """Read the topic distribution and add the correct topic keywords"""

    def best_topics(line):
        """Get the best five topics from the line"""
        oErr = ErrHandle
        lBack = []
        try:
            # Extract list of topics
            lst_topic_list = [ dict(topic=k, v=v) for k,v in line.items() if "Topic" in k]

            # Sort the topic list
            lst_topic_list.sort(key=lambda x: x['v'], reverse=True)

            # Return the first five
            lBack = lst_topic_list[0:5]
        except:
            lBack = []
            msg = oErr.get_error_message()
        return lBack

    oErr = ErrHandle()
    bResult = False
    msg = ""
    lst_line = []
    lst_missing = []
    filename = "doc_topic_dist_full_sermons.csv"
        
    try:
        # First make sure the correct topic keywords are there
        # bResult, msg = adapt_kwtopics()

        # Locate the topic distribution file
        file = os.path.abspath(os.path.join(MEDIA_ROOT, "passim", filename))
        # Try to read it
        if os.path.exists(file):
            # Read it
            with open(file, mode="r") as f:
                csv_file = csv.DictReader(f)
                for line in csv_file:
                    lst_line.append(line)

            # Prepare a dictionary of all topics
            topic_keyword = {}
            for num in range(1, 54):
                sName = "Topic {}:".format(num)
                obj = Keyword.objects.filter(category="top", name__icontains=sName).first()
                if obj is None:
                    iStop = 1
                else:
                    topic_keyword[sName] = obj

            # Read through the file
            for idx, line in enumerate(lst_line):
                file_id = line.get("file_id")
                sig = file_id.replace("_", " ")
                obj = Signature.objects.filter(code__iexact=sig).first()
                if obj is None:
                    lst_missing.append(file_id)
                    print("Cannot find item {}, signature={}".format(idx, sig))
                else:
                    # Try to find the AF
                    gold = obj.gold
                    if gold is None:
                        print("Cannot find gold for item {}, signature={}".format(idx, sig))
                    else:
                        af = gold.equal
                        if af is None:
                            print("Cannot find AF for item {}, signature={}".format(idx, sig))
                        else:
                            # We have the authority file: get the five highest scoring topics
                            lTopics = best_topics(line)
                            # Add these topics to the AF
                            for oTopic in lTopics:
                                sName = "{}:".format(oTopic['topic'])
                                kw = topic_keyword[sName]
                                af.keywords.add(kw)
                            oErr.Status("Added topics to AF {}".format(af.id))
            # Indicate that all went wel
            bResult = True


        else:
            # Could not read it
            oErr.Status("Cannot find topic dist file: {}".format(file))

        # Show all the keywords that were missed
        oErr.Status("Added topic keywords to AFs.")
    except:
        bResult = False
        msg = oErr.get_error_message()
    return bResult, msg



