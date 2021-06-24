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
                        'feastupdate', 'codicocopy'],
    'sermon_list': ['nicknames', 'biblerefs'],
    'sermongold_list': ['sermon_gsig'],
    'equalgold_list': ['author_anonymus', 'latin_names', 'ssg_bidirectional', 's_to_ssg_link', 
                       'hccount', 'scount', 'ssgcount', 'ssgselflink', 'add_manu', 'passim_code'],
    'provenance_list': ['manuprov_m2m']
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

def adapt_codicocopy(oStatus=None):
    """Create Codico's and copy Manuscript information to Codico"""
    oErr = ErrHandle()
    bResult = True
    msg = ""
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
        oBack['total'] = "Got a list of manuscripts: {}".format(len(manu_lst))
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

        if oStatus != None: oStatus.set("finished", oBack)

        # Note that we are indeed ready
        bResult = True
    except:
        msg = oErr.get_error_message()
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

        # Copy date ranges
        if codi.codico_dateranges.count() == 0:
            for md in manu.manuscript_dateranges.all():
                if md.codico_id == None or md.codico_id == 0 or md.codico == None or md.codic.id != codi.id:
                    md.codico = codi
                    md.save()

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
        for obj in EqualGold.objects.all():
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

