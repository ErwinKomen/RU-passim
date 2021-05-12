"""
Adaptations of the database that are called up from the (list)views in the SEEKER app.
"""

from django.db import transaction
import re

# ======= imports from my own application ======
from passim.utils import ErrHandle
from passim.seeker.models import get_crpp_date, get_current_datetime, process_lib_entries, get_searchable, get_now_time, \
    add_gold2equal, add_equal2equal, add_ssg_equal2equal, get_helptext, Information, Country, City, Author, Manuscript, \
    User, Group, Origin, SermonDescr, MsItem, SermonHead, SermonGold, SermonDescrKeyword, SermonDescrEqual, Nickname, NewsItem, \
    SourceInfo, SermonGoldSame, SermonGoldKeyword, EqualGoldKeyword, Signature, Ftextlink, ManuscriptExt, \
    ManuscriptKeyword, Action, EqualGold, EqualGoldLink, Location, LocationName, LocationIdentifier, LocationRelation, LocationType, \
    ProvenanceMan, Provenance, Daterange, CollOverlap, BibRange, Feast, Comment, SermonEqualDist, \
    Project, Basket, BasketMan, BasketGold, BasketSuper, Litref, LitrefMan, LitrefCol, LitrefSG, EdirefSG, Report, SermonDescrGold, \
    Visit, Profile, Keyword, SermonSignature, Status, Library, Collection, CollectionSerm, \
    CollectionMan, CollectionSuper, CollectionGold, UserKeyword, Template, \
    ManuscriptCorpus, ManuscriptCorpusLock, EqualGoldCorpus, \
    Codico, CodicoKeyword, ProvenanceCod, \
    get_reverse_spec, LINK_EQUAL, LINK_PRT, LINK_BIDIR, LINK_PARTIAL, STYPE_IMPORTED, STYPE_EDITED, LINK_UNSPECIFIED


adaptation_list = {
    "manuscript_list": ['sermonhierarchy', 'msitemcleanup', 'locationcitycountry', 'templatecleanup', 
                        'feastupdate', 'codicocopy']
    }


def listview_adaptations(lv):
    """Perform adaptations specific for this listview"""

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

def adapt_sermonhierarchy():
    # Perform adaptations
    bResult, msg = Manuscript.adapt_hierarchy()
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

def adapt_codicocopy():
    """Create Codico's and copy Manuscript information to Codico"""
    oErr = ErrHandle()
    bResult = True
    msg = ""

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
    
    try:
        # TODO: add code here and change to True
        bResult = False

        # Walk through all manuscripts (that are not templates)
        manu_lst = []
        for manu in Manuscript.objects.filter(mtype="man"):
            # Check if this manuscript already has Codico's
            if manu.manuscriptcodicounits.count() == 0:
                # Note that Codico's must be made for this manuscript
                manu_lst.append(manu.id)
        # Create the codico's for the manuscripts
        with transaction.atomic():
            for idx, manu_id in enumerate(manu_lst):
                oErr.Status("Doing {} of {}".format(idx+1, len(manu_lst)))
                if manu_id == 1686: 
                    iStop = 1
                manu = Manuscript.objects.filter(id=manu_id).first()
                if manu != None:
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
                    # Copy provenances
                    if codi.codico_provenances.count() == 0:
                        for mp in manu.manuscripts_provenances.all():
                            obj = ProvenanceCod.objects.create(
                                provenance=mp.provenance, codico=codi, note=mp.note)

                    # Copy keywords
                    if codi.codico_kw.count() == 0:
                        for mk in manu.manuscript_kw.all():
                            obj = CodicoKeyword.objects.create(
                                codico=codi, keyword=mk.keyword)

                    # Copy date ranges
                    if codi.codico_dateranges.count() == 0:
                        for md in manu.manuscript_dateranges.all():
                            md.codico = codi
                            md.save()

        # Note that we are indeed ready
        bResult = True
    except:
        msg = oErr.get_error_message()
        bResult = False
    return bResult, msg


# ===================== MANUSCRIPT LISTVIEW ===============
        ## Check if signature adaptation is needed
        #sh_done = Information.get_kvalue("sermonhierarchy")
        #if sh_done == None or sh_done == "":
        #    # Perform adaptations
        #    bResult, msg = Manuscript.adapt_hierarchy()
        #    if bResult:
        #        # Success
        #        Information.set_kvalue("sermonhierarchy", "done")

        ## Check if MsItem cleanup is needed
        #sh_done = Information.get_kvalue("msitemcleanup")
        #if sh_done == None or sh_done == "":
        #    method = "UseAdaptations"
        #    method = "RemoveOrphans"

        #    if method == "RemoveOrphans":
        #        # Walk all manuscripts
        #        for manu in Manuscript.objects.all():
        #            manu.remove_orphans()
        #    elif method == "UseAdaptations":
        #        # Perform adaptations
        #        del_id = []
        #        qs = MsItem.objects.annotate(num_heads=Count('itemheads')).annotate(num_sermons=Count('itemsermons'))
        #        for obj in qs.filter(num_heads=0, num_sermons=0):
        #            del_id.append(obj.id)
        #        # Remove them
        #        MsItem.objects.filter(id__in=del_id).delete()
        #        # Success
        #        Information.set_kvalue("msitemcleanup", "done")

        ## Check if adding [lcity] and [lcountry] to locations is needed
        #sh_done = Information.get_kvalue("locationcitycountry")
        #if sh_done == None or sh_done == "":
        #    with transaction.atomic():
        #        for obj in Location.objects.all():
        #            bNeedSaving = False
        #            lcountry = obj.partof_loctype("country")
        #            lcity = obj.partof_loctype("city")
        #            if obj.lcountry == None and lcountry != None:
        #                obj.lcountry = lcountry
        #                bNeedSaving = True
        #            if obj.lcity == None and lcity != None:
        #                obj.lcity = lcity
        #                bNeedSaving = True
        #            if bNeedSaving:
        #                obj.save()
        #    # Success
        #    Information.set_kvalue("locationcitycountry", "done")

        ## Remove all 'template' manuscripts that are not in the list of templates
        #sh_done = Information.get_kvalue("templatecleanup")
        #if sh_done == None or sh_done == "":
        #    # Get a list of all the templates and the manuscript id's in it
        #    template_manu_id = [x.manu.id for x in Template.objects.all().order_by('manu__id')]

        #    # Get all manuscripts that are supposed to be template, but whose ID is not in [templat_manu_id]
        #    qs_manu = Manuscript.objects.filter(mtype='tem').exclude(id__in=template_manu_id)

        #    # Remove these manuscripts (and their associated msitems, sermondescr, sermonhead
        #    qs_manu.delete()

        #    # Success
        #    Information.set_kvalue("templatecleanup", "done")

        ## Remove all 'template' manuscripts that are not in the list of templates
        #sh_done = Information.get_kvalue("feastupdate")
        #if sh_done == None or sh_done == "":
        #    # Get a list of all the templates and the manuscript id's in it
        #    feast_lst = [x['feast'] for x in SermonDescr.objects.exclude(feast__isnull=True).order_by('feast').values('feast').distinct()]
        #    feast_set = {}
        #    # Create the feasts
        #    for feastname in feast_lst:
        #        obj = Feast.objects.filter(name=feastname).first()
        #        if obj == None:
        #            obj = Feast.objects.create(name=feastname)
        #        feast_set[feastname] = obj

        #    with transaction.atomic():
        #        for obj in SermonDescr.objects.filter(feast__isnull=False):
        #            obj.feast = feast_set[obj.feast]
        #            obj.save()

        #    # Success
        #    Information.set_kvalue("feastupdate", "done")
