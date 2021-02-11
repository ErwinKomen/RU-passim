# ======================================= TO BE REMOVED IN THE FUTURE ===========================================

#class LocationRelset(BasicPart):
#    """The set of provenances from one manuscript"""

#    MainModel = Location
#    template_name = 'seeker/location_relset.html'
#    title = "LocationRelations"
#    LrelFormSet = inlineformset_factory(Location, LocationRelation,
#                                         form=LocationRelForm, min_num=0,
#                                         fk_name = "contained",
#                                         extra=0, can_delete=True, can_order=False)
#    formset_objects = [{'formsetClass': LrelFormSet, 'prefix': 'lrel', 'readonly': False}]

#    def get_queryset(self, prefix):
#        qs = None
#        if prefix == "lrel":
#            # List the parent locations for this location correctly
#            qs = LocationRelation.objects.filter(contained=self.obj).order_by('container__name')
#        return qs

#    def before_save(self, prefix, request, instance = None, form = None):
#        has_changed = False
#        if prefix == "lrel":
#            # Get any selected partof location id
#            loc_id = form.cleaned_data['partof']
#            if loc_id != "":
#                # Check if a new relation should be made or an existing one should be changed
#                if instance.id == None:
#                    # Set the correct container
#                    location = Location.objects.filter(id=loc_id).first()
#                    instance.container = location
#                    has_changed = True
#                elif instance.container == None or instance.container.id == None or instance.container.id != int(loc_id):
#                    location = Location.objects.filter(id=loc_id).first()
#                    # Set the correct container
#                    instance.container = location
#                    has_changed = True
 
#        return has_changed


#class CollectionSermset(BasicPart):
#    """The set of sermons from the collection"""

#    MainModel = Collection
#    template_name = 'seeker/collection_sermset.html'
#    title = "CollectionsSermons"

#    def add_to_context(self, context):
        
#        # Pass on all the sermons from each Collection
#        col = self.obj.id #??
#        scol_list = []
#        for item in Collection.objects.filter(collection_id=col):
#            oAdd = {}
#            oAdd['title'] = item.title.id
#            # oAdd['title'] = item.reference.title

#            scol_list.append(oAdd)

#        context['scol_list'] = scol_list

#        return context


#class SermonLinkset(BasicPart):
#    """The set of links from one gold sermon"""

#    MainModel = SermonDescr
#    template_name = 'seeker/sermon_linkset.html'
#    title = "SermonLinkset"
#    StogFormSet = inlineformset_factory(SermonDescr, SermonDescrGold,
#                                         form=SermonDescrGoldForm, min_num=0,
#                                         fk_name = "sermon",
#                                         extra=0, can_delete=True, can_order=False)
#    formset_objects = [{'formsetClass': StogFormSet, 'prefix': 'stog', 'readonly': False, 'initial': [{'linktype': LINK_EQUAL }]}]

#    def add_to_context(self, context):
#        x = 1
#        #for fs in context['stog_formset']:
#        #    for form in fs:
#        #        gold = form['gold']
#        #        geq = gold.equal_goldsermons.all()
#        #        qs = geq
#        return context


#class SermonSignset(BasicPart):
#    """The set of signatures from one sermon (manifestation)"""

#    MainModel = SermonDescr
#    template_name = 'seeker/sermon_signset.html'
#    title = "SermonSignset"
#    SrmsignFormSet = inlineformset_factory(SermonDescr, SermonSignature,
#                                         form=SermonDescrSignatureForm, min_num=0,
#                                         fk_name = "sermon",
#                                         extra=0, can_delete=True, can_order=False)
#    formset_objects = [{'formsetClass': SrmsignFormSet, 'prefix': 'srmsign', 'readonly': False}]
    
#    def add_to_context(self, context):
#        context['edi_list'] = [{'type': 'gr', 'name': 'Gryson'},
#                               {'type': 'cl', 'name': 'Clavis'},
#                               {'type': 'ot', 'name': 'Other'}]
#        return context
    
    
#class SermonColset(BasicPart):
#    """The set of collections that the sermon is a part of"""
#    MainModel = SermonDescr
#    template_name = 'seeker/sermon_colset.html'
#    title = "SermonDescrCollections"
#    ScolFormSet = inlineformset_factory(SermonDescr, CollectionSerm,  
#                                        form = SermonDescrCollectionForm, min_num=0,
#                                        fk_name = "sermon", extra=0, can_delete=True, can_order=False)
#    formset_objects = [{'formsetClass': ScolFormSet, 'prefix': 'scol', 'readonly': False}]

#    def before_save(self, prefix, request, instance = None, form = None):
#        has_changed = False
#        if prefix == "scol":
#            # Get the chosen collection
#            obj = form.cleaned_data['collection']
#            if obj == None:
#                # Get the value entered for the collection
#                col = form['name'].data
#                # Check if this is an existing collection
#                obj = Collection.objects.filter(name__iexact=col).first() # gaat dit goed
#                # Now set the instance value correctly
#                instance.collection = obj
#                has_changed = True

#        return has_changed


#class SermonKwset(BasicPart):
#    """The set of keywords from one sermon"""

#    MainModel = SermonDescr
#    template_name = 'seeker/sermon_kwset.html'
#    title = "SermonDescrKeywords"
#    SkwFormSet = inlineformset_factory(SermonDescr, SermonDescrKeyword,
#                                         form=SermonDescrKeywordForm, min_num=0,
#                                         fk_name = "sermon",
#                                         extra=0, can_delete=True, can_order=False)
#    formset_objects = [{'formsetClass': SkwFormSet, 'prefix': 'skw', 'readonly': False}]

#    def before_save(self, prefix, request, instance = None, form = None):
#        has_changed = False
#        if prefix == "skw":
#            # Get the chosen keyword
#            obj = form.cleaned_data['keyword']
#            if obj == None:
#                # Get the value entered for the keyword
#                kw = form['name'].data
#                # Check if this is an existing Keyword
#                obj = Keyword.objects.filter(name__iexact=kw).first()
#                if obj == None:
#                    # Create it
#                    obj = Keyword(name=kw.lower())
#                    obj.save()
#                # Now set the instance value correctly
#                instance.keyword = obj
#                has_changed = True

#        return has_changed
    

#class SermonEdiset(BasicPart):
#    """The set of editions from the gold-sermons related to me"""

#    MainModel = SermonDescr
#    template_name = 'seeker/sermon_ediset.html'
#    title = "SermonDescrEditions"

#    def add_to_context(self, context):

#        # Pass on all the linked-gold editions to the sermons
#        sedi_list = []
#        # Visit all linked gold sermons
#        for linked in SermonDescrGold.objects.filter(sermon=self.obj, linktype=LINK_EQUAL):
#            # Access the gold sermon
#            gold = linked.gold
            
#            # Get all the editions references of this gold sermon 
#            for item in EdirefSG.objects.filter(sermon_gold_id = gold):
                
#                oAdd = {}
#                oAdd['reference_id'] = item.reference.id
#                oAdd['short'] = item.reference.short
#                oAdd['reference'] = item.reference
#                oAdd['pages'] = item.pages
#                sedi_list.append(oAdd)
       
#        context['sedi_list'] = sedi_list

#        return context


#class SermonLitset(BasicPart):
#    """The set of literature references from SermonGold(s) and Manuscript passed over to each Sermon"""

#    MainModel = SermonDescr
#    template_name = 'seeker/sermon_litset.html'
#    title = "SermonDescrLiterature"
    
#    def add_to_context(self, context):
        
#        # Pass on all the literature from Manuscript to each of the Sermons of that Manuscript
               
#        # First the litrefs from the manuscript: 
#        manu = self.obj.manu
#        lref_list = []
#        for item in LitrefMan.objects.filter(manuscript=manu):
#            oAdd = {}
#            oAdd['reference_id'] = item.reference.id
#            oAdd['short'] = item.reference.short
#            oAdd['reference'] = item.reference
#            oAdd['pages'] = item.pages
#            lref_list.append(oAdd)
       
#        # Second the litrefs from the linked Gold sermons: 

#        for linked in SermonDescrGold.objects.filter(sermon=self.obj, linktype=LINK_EQUAL):
#            # Access the gold sermon
#            gold = linked.gold
#            # Get all the literature references of this gold sermon 
#            for item in LitrefSG.objects.filter(sermon_gold_id = gold):
                
#                oAdd = {}
#                oAdd['reference_id'] = item.reference.id
#                oAdd['short'] = item.reference.short
#                oAdd['reference'] = item.reference
#                oAdd['pages'] = item.pages
#                lref_list.append(oAdd)
                
#        # Set the sort order TH: werkt
#        lref_list = sorted(lref_list, key=lambda x: "{}_{}".format(x['short'].lower(), x['pages']))
                
#        # Remove duplicates 
#        unique_litref_list=[]
                
#        previous = None
#        for item in lref_list:
#            # Keep the first
#            if previous == None:
#                unique_litref_list.append(item)
#            # Try to compare current item to previous
#            elif previous != None:
#                # Are they the same?
#                if item['reference_id'] == previous['reference_id'] and \
#                    item['pages'] == previous['pages']:
#                    # They are the same, no need to copy
#                    pass
                            
#                # elif previous == None: 
#                #    unique_litref_list.append(item)
#                else:
#                    # Add this item to the new list
#                    unique_litref_list.append(item)

#            # assign previous
#            previous = item
                
#        litref_list = unique_litref_list
        
#        context['lref_list'] = litref_list
       
#        return context


#class ManuscriptProvset(BasicPart):
#    """The set of provenances from one manuscript"""

#    MainModel = Manuscript
#    template_name = 'seeker/manuscript_provset.html'
#    title = "ManuscriptProvenances"
#    MprovFormSet = inlineformset_factory(Manuscript, ProvenanceMan,
#                                         form=ManuscriptProvForm, min_num=0,
#                                         fk_name = "manuscript",
#                                         extra=0, can_delete=True, can_order=False)
#    formset_objects = [{'formsetClass': MprovFormSet, 'prefix': 'mprov', 'readonly': False}]

#    def get_queryset(self, prefix):
#        qs = None
#        if prefix == "mprov":
#            # List the provenances for this manuscript correctly
#            qs = ProvenanceMan.objects.filter(manuscript=self.obj).order_by('provenance__name')
#        return qs

#    def before_save(self, prefix, request, instance = None, form = None):
#        has_changed = False
#        if prefix == "mprov":
#            # First need to get a possible ID of the (new) location 
#            loc_id = form.cleaned_data['location']
#            # Check if a new provenance should be made
#            if instance.id == None or instance.provenance == None or instance.provenance.id == None or \
#               instance.provenance.location != None and instance.provenance.location.id != int(loc_id):
#                # Need to create a new provenance
#                name = form.cleaned_data['name']
#                note = form.cleaned_data['note']
#                # Create the new provenance
#                provenance = Provenance(name=name, note=note)

#                bCanSave = True
#                # Possibly add location
#                loc_name = form.cleaned_data['location_ta']
#                if loc_id != "":
#                    location = Location.objects.filter(id=loc_id).first()
#                    provenance.location = location
#                elif loc_name != "":
#                    # The user specified a new location, but we are not able to process it here
#                    # TODO: how do we signal to the user that he has to add a location elsewhere??
#                    bCanSave = False
#                    self.arErr.append("You are using a new location [{}]. Add it first, and then select it.".format(loc_name))

#                if bCanSave:
#                    # Save the new provenance
#                    provenance.save()
#                    instance.provenance = provenance

#                    # Make a new ProvenanceMan
#                    instance.manuscript = self.obj

#                    # Indicate that changes have been made
#                    has_changed = True
#            elif instance and instance.id and instance.provenance:
#                # Check for any other changes in existing stuff
#                provenance = instance.provenance
#                name = form.cleaned_data['name']
#                note = form.cleaned_data['note']
#                if provenance.name != name:
#                    # Change in name
#                    instance.provenance.name = name
#                    instance.provenance.save()
#                    has_changed = True
#                if provenance.note != note:
#                    # Change in note
#                    instance.provenance.note = note
#                    instance.provenance.save()
#                    has_changed = True

#        return has_changed
    

#class SermonGoldEdiset(BasicPart):
#    """The set of critical text editions from one gold sermon""" 

#    MainModel = SermonGold
#    template_name = 'seeker/sermongold_ediset.html'
#    title = "SermonGoldEditions"
#    GediFormSet = inlineformset_factory(SermonGold, EdirefSG,
#                                         form = SermonGoldEditionForm, min_num=0,
#                                         fk_name = "sermon_gold",
#                                         extra=0, can_delete=True, can_order=False)
#    formset_objects = [{'formsetClass': GediFormSet, 'prefix': 'gedi', 'readonly': False}]

#    def get_queryset(self, prefix):
#        qs = None
#        if prefix == "gedi":
#            # List the editions for this SermonGold correctly
#            qs = EdirefSG.objects.filter(sermon_gold=self.obj).order_by('reference__short')
#        return qs
   
#    def before_save(self, prefix, request, instance = None, form = None):
#        has_changed = False
#        # Check if a new litref should be processed
#        litref_id = form.cleaned_data['litref']
#        if litref_id != "":
#            if instance.id == None or instance.reference == None or instance.reference.id == None or \
#                instance.reference.id != int(litref_id):
#                # Find the correct litref
#                litref = Litref.objects.filter(id=litref_id).first()
#                if litref != None:
#                    # Adapt the value of the instance 
#                    instance.reference = litref
#                    has_changed = True
            
#        return has_changed  
    

#class ManuscriptLitset(BasicPart):
#    """The set of literature references from one manuscript"""

#    MainModel = Manuscript
#    template_name = 'seeker/manuscript_litset.html'
#    title = "ManuscriptLiterature"
#    MlitFormSet = inlineformset_factory(Manuscript, LitrefMan,
#                                         form = ManuscriptLitrefForm, min_num=0,
#                                         fk_name = "manuscript",
#                                         extra=0, can_delete=True, can_order=False)
#    formset_objects = [{'formsetClass': MlitFormSet, 'prefix': 'mlit', 'readonly': False}]

#    def get_queryset(self, prefix):
#        qs = None
#        if prefix == "mlit":
#            # List the litrefs for this manuscript correctly
#            qs = LitrefMan.objects.filter(manuscript=self.obj).order_by('reference__short')
#        return qs

#    def before_save(self, prefix, request, instance = None, form = None):
#        has_changed = False
#        # Check if a new reference should be processed
#        litref_id = form.cleaned_data['litref']
#        if litref_id != "":
#            if instance.id == None or instance.reference == None or instance.reference.id == None or \
#                instance.reference.id != int(litref_id):
#                # Find the correct litref
#                litref = Litref.objects.filter(id=litref_id).first()
#                if litref != None:
#                    # Adapt the value of the instance 
#                    instance.reference = litref
#                    has_changed = True
            
#        return has_changed


#class ManuscriptExtset(BasicPart):
#    """The set of provenances from one manuscript"""

#    MainModel = Manuscript
#    template_name = 'seeker/manuscript_extset.html'
#    title = "ManuscriptExternalLinks"
#    MextFormSet = inlineformset_factory(Manuscript, ManuscriptExt,
#                                         form=ManuscriptExtForm, min_num=0,
#                                         fk_name = "manuscript",
#                                         extra=0, can_delete=True, can_order=False)
#    formset_objects = [{'formsetClass': MextFormSet, 'prefix': 'mext', 'readonly': False}]

#    def get_queryset(self, prefix):
#        qs = None
#        if prefix == "mext":
#            # List the external links for this manuscript correctly
#            qs = ManuscriptExt.objects.filter(manuscript=self.obj).order_by('url')
#        return qs

#    def before_save(self, prefix, request, instance = None, form = None):
#        has_changed = False
#        # NOTE: no drastic things here yet
#        return has_changed

    
#class ManuscriptKwset(BasicPart):
#    """The set of keywords from one manuscript"""

#    MainModel = Manuscript
#    template_name = 'seeker/manuscript_kwset.html'
#    title = "ManuscriptKeywords"
#    MkwFormSet = inlineformset_factory(Manuscript, ManuscriptKeyword,
#                                         form=ManuscriptKeywordForm, min_num=0,
#                                         fk_name = "manuscript",
#                                         extra=0, can_delete=True, can_order=False)
#    formset_objects = [{'formsetClass': MkwFormSet, 'prefix': 'mkw', 'readonly': False}]

#    def before_save(self, prefix, request, instance = None, form = None):
#        has_changed = False
#        if prefix == "mkw":
#            # Get the chosen keyword
#            obj = form.cleaned_data['keyword']
#            if obj == None:
#                # Get the value entered for the keyword
#                kw = form['name'].data
#                # Check if this is an existing Keyword
#                obj = Keyword.objects.filter(name__iexact=kw).first()
#                if obj == None:
#                    # Create it
#                    obj = Keyword(name=kw.lower())
#                    obj.save()
#                # Now set the instance value correctly
#                instance.keyword = obj
#                has_changed = True

#        return has_changed


#class SermonGoldSignset(BasicPart):
#    """The set of signatures from one gold sermon"""

#    MainModel = SermonGold
#    template_name = 'seeker/sermongold_signset.html'
#    title = "SermonGoldSignset"
#    GsignFormSet = inlineformset_factory(SermonGold, Signature,
#                                         form=SermonGoldSignatureForm, min_num=0,
#                                         fk_name = "gold",
#                                         extra=0, can_delete=True, can_order=False)
#    formset_objects = [{'formsetClass': GsignFormSet, 'prefix': 'gsign', 'readonly': False}]
    
#    def add_to_context(self, context):
#        context['edi_list'] = [{'type': 'gr', 'name': 'Gryson'},
#                               {'type': 'cl', 'name': 'Clavis'},
#                               {'type': 'ot', 'name': 'Other'}]
#        return context


#class SermonGoldKwset(BasicPart):
#    """The set of keywords from one gold sermon"""

#    MainModel = SermonGold
#    template_name = 'seeker/sermongold_kwset.html'
#    title = "SermonGoldKeywords"
#    GkwFormSet = inlineformset_factory(SermonGold, SermonGoldKeyword,
#                                         form=SermonGoldKeywordForm, min_num=0,
#                                         fk_name = "gold",
#                                         extra=0, can_delete=True, can_order=False)
#    formset_objects = [{'formsetClass': GkwFormSet, 'prefix': 'gkw', 'readonly': False}]

#    def before_save(self, prefix, request, instance = None, form = None):
#        has_changed = False
#        if prefix == "gkw":
#            # Get the chosen keyword
#            obj = form.cleaned_data['keyword']
#            if obj == None:
#                # Get the value entered for the keyword
#                kw = form['name'].data
#                # Check if this is an existing Keyword
#                obj = Keyword.objects.filter(name__iexact=kw).first()
#                if obj == None:
#                    # Create it
#                    obj = Keyword(name=kw.lower())
#                    obj.save()
#                # Now set the instance value correctly
#                instance.keyword = obj
#                has_changed = True

#        return has_changed


#class SermonGoldFtxtset(BasicPart):
#    """The set of critical text editions from one gold sermon"""

#    MainModel = SermonGold
#    template_name = 'seeker/sermongold_ftxtset.html'
#    title = "SermonGoldFulltextLinks"
#    GftextFormSet = inlineformset_factory(SermonGold, Ftextlink,
#                                         form=SermonGoldFtextlinkForm, min_num=0,
#                                         fk_name = "gold",
#                                         extra=0, can_delete=True, can_order=False)
#    formset_objects = [{'formsetClass': GftextFormSet, 'prefix': 'gftxt', 'readonly': False}]


#class SermonGoldLitset(BasicPart):
#    """The set of literature references from one SermonGold"""

#    MainModel = SermonGold
#    template_name = 'seeker/sermongold_litset.html'
#    title = "SermonGoldLiterature"
#    SGlitFormSet = inlineformset_factory(SermonGold, LitrefSG, form=SermonGoldLitrefForm, 
#                                         min_num=0, fk_name = "sermon_gold",
#                                         extra=0, can_delete=True, can_order=False)
#    formset_objects = [{'formsetClass': SGlitFormSet, 'prefix': 'sglit', 'readonly': False}]

#    def get_queryset(self, prefix):
#        qs = LitrefSG.objects.none()
#        if prefix == "sglit":
#            # List the litrefs for this SermonGold correctly
#            qs = LitrefSG.objects.filter(sermon_gold=self.obj).order_by('reference__short')
#        return qs

#    def before_save(self, prefix, request, instance = None, form = None):
#        has_changed = False
#        # Check if a new reference should be processed
#        litref_id = form.cleaned_data['litref']
#        if litref_id != "":
#            if instance.id == None or instance.reference == None or instance.reference.id == None or \
#                instance.reference.id != int(litref_id):
#                # Find the correct litref
#                litref = Litref.objects.filter(id=litref_id).first()
#                if litref != None:
#                    # Adapt the value of the instance 
#                    instance.reference = litref
#                    has_changed = True
            
#        return has_changed


#class EqualGoldEqualset(BasicPart):
#    """The set of gold sermons that are part of one SSG = EqualGold object"""

#    MainModel = EqualGold
#    template_name = 'seeker/super_eqset.html'
#    title = "SuperSermonGoldEqualset"
#    SSGeqFormSet = inlineformset_factory(EqualGold, SermonGold, 
#                                         form=EqualGoldForm, min_num=0,
#                                         fk_name = "equal",
#                                         extra=0, can_delete=True, can_order=False)
#    formset_objects = [{'formsetClass': SSGeqFormSet, 'prefix': 'ssgeq', 'readonly': False}]

#    def get_queryset(self, prefix):
#        qs = None
#        if prefix == "ssgeq":
#            # Get all SermonGold instances with the same EqualGold
#            #  (those are all SermonGold instances that have a FK linking to me)
#            qs = self.obj.equal_goldsermons.all()
#        return qs

#    def get_instance(self, prefix):
#        if prefix == "ssgeq" or "ssgeq" in prefix:
#            return self.obj
#        else:
#            return self.obj

#    def process_formset(self, prefix, request, formset):
#        if prefix == "ssgeq":
#            for form in formset:
#                # Check if this has an instance
#                if form.instance == None or form.instance.id == None:
#                    # This has no SermonGold instance: retrieve it from the 'gold' value
#                    if 'gold' in form.fields:
#                        gold_id = form['gold'].data
#                        if gold_id != "":
#                            gold = SermonGold.objects.filter(id=gold_id).first()
#                            form.instance = gold
#                    # This has no SermonGold instance: retrieve it from the 'gold' value
#                    elif 'newgold' in form.fields:
#                        gold_id = form['newgold'].data
#                        if gold_id != "":
#                            gold = SermonGold.objects.filter(id=gold_id).first()
#                            form.instance = gold
#        # No return value needed
#        return True

#    #def remove_from_eqset(self, instance):
#    #    # In fact, a new 'EqualGold' instance must be created
#    #    geq = instance.equal.create_new()
#    #    # Set the SermonGold instance to this new equality set
#    #    instance.equal = geq
#    #    instance.save()
#    #    # Check if we need to retain any partial or other links
#    #    gdkeep = [x for x in self.qd if "gdkeep-" in x]
#    #    for keep in gdkeep:
#    #        eqgl = EqualGoldLink.objects.filter(id=self.qd[keep]).first()
#    #        # Create a new link
#    #        lnk = EqualGoldLink(src=geq, dst=eqgl.dst, linktype=eqgl.linktype)
#    #        lnk.save()
#    #    # Return positively
#    #    return True

#    def before_delete(self, prefix = None, instance = None):
#        """Check if moving of non-equal links should take place"""

#        ## NOTE: this is already part of a transaction.atomic() area!!!
#        #bDoDelete = True
#        #if prefix != None and prefix == "ssgeq" and instance != None:
#        #    # No actual deletion of anything should take place...
#        #    bDoDelete = False
#        #    # Perform the operation
#        #    self.remove_from_eqset(instance)
#        return bDoDelete

#    def before_save(self, prefix, request, instance = None, form = None):
#        # Use [self.gold] to communicate with [after_save()]

#        bNeedSaving = False
#        if prefix == "ssgeq":
#            self.gold = None
#            if 'gold' in form.cleaned_data:
#                # Get the form's 'gold' value
#                gold_id = form.cleaned_data['gold']
#                if gold_id != "":
#                    # Find the gold to attach to
#                    gold = SermonGold.objects.filter(id=gold_id).first()
#                    if gold != None and gold.id != instance.id:
#                        self.gold = gold
#            elif 'newgold' in form.cleaned_data:
#                # Get the form's 'gold' value
#                gold_id = form.cleaned_data['newgold']
#                if gold_id != "":
#                    # Find the gold that should link to equal
#                    gold = SermonGold.objects.filter(id=gold_id).first()
#                    if gold != None and gold.id != instance.id:
#                        self.gold = gold
#        return bNeedSaving

#    def after_save(self, prefix, instance = None, form = None):
#        # The instance here is the geq-instance, so an instance of SermonGold
#        # Now make sure all related material is updated

#        if self.gold == None:
#            # Add this gold sermon to the equality group of the target
#            added, lst_res = add_gold2equal(instance, self.obj)
#        else:
#            # The user wants to change the gold-sermon inside the equality set: 
#            # (1) Keep track of the current equality set
#            eqset = self.obj
#            # (2) Remove [instance] from the equality set
#            self.remove_from_eqset(instance)
#            # (3) Add [gold] to the current equality set
#            added, lst_res = add_gold2equal(self.gold, eqset)
#            # (4) Save changes to the instance
#            self.obj.save()
#            # bNeedSaving = True
#        return True

#    def add_to_context(self, context):
#        # Get the EqualGold instances to which I am associated
#        context['associations'] = self.obj.equalgold_src.all()

#        return context

    
#class EqualGoldLinkset(BasicPart):
#    """The set of EqualGold instances that link to an EqualGold one, but that are not 'equal' """

#    MainModel = EqualGold
#    template_name = 'seeker/super_linkset.html'
#    title = "EqualGoldLinkset"
#    SSGlinkFormSet = inlineformset_factory(EqualGold, EqualGoldLink,
#                                         form=EqualGoldLinkForm, min_num=0,
#                                         fk_name = "src",
#                                         extra=0, can_delete=True, can_order=False)
#    formset_objects = [{'formsetClass': SSGlinkFormSet, 'prefix': 'ssglink', 'readonly': False, 'initial': [{'linktype': LINK_EQUAL }], 'clean': True}]

#    def clean(self, formset, prefix):
#        # Clean method
#        if prefix == "ssglink":
#            # Iterate over all forms and get the destinations
#            lDstList = []
#            for form in formset.forms:
#                dst = form.cleaned_data['dst']
#                if dst == None:
#                    dst = form.cleaned_data['newsuper']
#                # Check if we have a destination
#                if dst != None:
#                    # Check if it is already in the list
#                    if dst in lDstList:
#                        # Something is wrong: double desination
#                        self.arErr.append("A target Super Sermon Gold can only be used once")
#                        return False
#                    # Add it to the list
#                    lDstList.append(dst)
#        return True

#    def process_formset(self, prefix, request, formset):
#        if prefix == "ssglink":
#            # Check the forms in the formset, and set the correct 'dst' values where possible
#            for form in formset:
#                if 'gold' in form.changed_data and 'dst' in form.fields and 'gold' in form.fields:
#                    gold_id = form['gold'].data
#                    dst_id = form['dst'].data
#                    if gold_id != None and gold_id != "":
#                        gold = SermonGold.objects.filter(id=gold_id).first()
#                        if gold != None:
#                            # Gaat niet: form['dst'].data = gold.equal
#                            #            form['dst'].data = gold.equal.id
#                            #            form.fields['dst'].initial = gold.equal.id
#                            form.instance.dst = gold.equal
#                # end if
#        # No need to return a value
#        return True

#    def before_delete(self, prefix = None, instance = None):
#        id = instance.id
#        return True

#    def before_save(self, prefix, request, instance = None, form = None):
#        bNeedSaving = False
#        if prefix == "ssglink":
#            if 'target_list' in form.cleaned_data:
#                # Get the one single destination id number
#                dst = form.cleaned_data['target_list']
#                if dst != None:
#                    # Fill in the destination
#                    instance.dst = dst
#                    bNeedSaving = True
#        return bNeedSaving

#    def after_save(self, prefix, instance = None, form = None):
#        # The instance here is the glink-instance, so an instance of EqualGoldLink
#        # Now make sure all related material is updated

#        added, lst_res = add_ssg_equal2equal(self.obj, instance.dst, instance.linktype)
#        return True


