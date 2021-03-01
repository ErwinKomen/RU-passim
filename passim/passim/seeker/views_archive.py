


# ======================================= TO BE REMOVED IN THE FUTURE ===========================================

#class SourceDetailsView_ORG(PassimDetails):
#    model = SourceInfo
#    mForm = SourceEditForm
#    template_name = 'seeker/source_details.html'
#    prefix = 'source'
#    prefix_type = "simple"
#    basic_name = 'source'
#    title = "SourceDetails"
#    rtype = "html"

#    def after_new(self, form, instance):
#        """Action to be performed after adding a new item"""

#        self.afternewurl = reverse('source_list')
#        if instance != None:
#            # Make sure we do a page redirect
#            self.newRedirect = True
#            self.redirectpage = reverse('source_details', kwargs={'pk': instance.id})
#        return True, "" 

#    def add_to_context(self, context, instance):
#        context['is_app_editor'] = user_is_ingroup(self.request, app_editor)
#        # Process this visit and get the new breadcrumbs object
#        prevpage = reverse('source_list')
#        context['prevpage'] = prevpage
#        crumbs = []
#        crumbs.append(['Sources', prevpage])
#        current_name = "Source details"
#        if instance:
#            current_name = "Source {} {}".format(instance.collector, get_crpp_date(instance.created))
#        context['breadcrumbs'] = get_breadcrumbs(self.request, current_name, True, crumbs)
#        return context

#    def before_save(self, form, instance):
#        if form != None:
#            # Search the user profile
#            profile = Profile.get_user_profile(self.request.user.username)
#            form.instance.profile = profile
#        return True, ""


#class SourceEdit_ORG(BasicPart):
#    """The details of one manuscript"""

#    MainModel = SourceInfo
#    template_name = 'seeker/source_edit.html'
#    title = "SourceInfo" 
#    afternewurl = ""
#    # One form is attached to this 
#    prefix = "source"
#    form_objects = [{'form': SourceEditForm, 'prefix': prefix, 'readonly': False}]

#    def custom_init(self):
#        """Adapt the prefix for [sermo] to fit the kind of prefix provided by PassimDetails"""

#        return True

#    def add_to_context(self, context):

#        # Get the instance
#        instance = self.obj

#        # Not sure if this is still needed
#        context['msitem'] = instance

#        afternew =  reverse('source_list')
#        if 'afternewurl' in self.qd:
#            afternew = self.qd['afternewurl']
#        context['afternewurl'] = afternew
#        # Define where to go to after deletion
#        context['afterdelurl'] = reverse('source_list')

#        return context

#    def after_save(self, prefix, instance = None, form = None):

#        # There's is no real return value needed here 
#        return True



#class SermonGoldSelect(BasicPart):
#    """Facilitate searching and selecting one gold sermon"""

#    MainModel = SermonGold
#    template_name = "seeker/sermongold_select.html"

#    # Pagination
#    paginate_by = paginateSelect
#    page_function = "ru.passim.seeker.gold_page"
#    form_div = "select_gold_button" 
#    entrycount = 0
#    qs = None

#    # One form is attached to this 
#    source_id = None
#    prefix = 'gsel'
#    form_objects = [{'form': SelectGoldForm, 'prefix': prefix, 'readonly': True}]

#    def get_instance(self, prefix):
#        instance = None
#        if prefix == "gsel":
#            # The instance is the SRC of a link
#            instance = self.obj
#        return instance

#    def add_to_context(self, context):
#        """Anything that needs adding to the context"""

#        # If possible add source_id
#        if 'source_id' in self.qd:
#            self.source_id = self.qd['source_id']
#        context['source_id'] = self.source_id
        
#        # Pagination
#        self.do_pagination('gold')
#        context['object_list'] = self.page_obj
#        context['page_obj'] = self.page_obj
#        context['page_function'] = self.page_function
#        context['formdiv'] = self.form_div
#        context['entrycount'] = self.entrycount

#        # Add the result to the context
#        context['results'] = self.qs
#        context['authenticated'] = user_is_authenticated(self.request)
#        context['is_app_uploader'] = user_is_ingroup(self.request, app_uploader)
#        context['is_app_editor'] = user_is_ingroup(self.request, app_editor)

#        # Return the updated context
#        return context

#    def do_pagination(self, prefix):
#        # We need to calculate the queryset immediately
#        self.get_queryset(prefix)

#        # Paging...
#        page = self.qd.get('page')
#        page = 1 if page == None else int(page)
#        # Create a list [page_obj] that contains just these results
#        paginator = Paginator(self.qs, self.paginate_by)
#        self.page_obj = paginator.page(page)        

#    def get_queryset(self, prefix):
#        qs = SermonGold.objects.none()
#        if prefix == "gold":
#            # Get the cleaned data
#            oFields = None
#            if 'cleaned_data' in self.form_objects[0]:
#                oFields = self.form_objects[0]['cleaned_data']
#            qs = SermonGold.objects.none()
#            if oFields != None and self.request.method == 'POST':
#                # There is valid data to search with
#                lstQ = []

#                # (1) Check for author name -- which is in the typeahead parameter
#                if 'author' in oFields and oFields['author'] != "" and oFields['author'] != None: 
#                    val = oFields['author']
#                    lstQ.append(Q(author=val))
#                elif 'authorname' in oFields and oFields['authorname'] != ""  and oFields['authorname'] != None: 
#                    val = adapt_search(oFields['authorname'])
#                    lstQ.append(Q(author__name__iregex=val))

#                # (2) Process incipit
#                if 'incipit' in oFields and oFields['incipit'] != "" and oFields['incipit'] != None: 
#                    val = adapt_search(oFields['incipit'])
#                    lstQ.append(Q(srchincipit__iregex=val))

#                # (3) Process explicit
#                if 'explicit' in oFields and oFields['explicit'] != "" and oFields['explicit'] != None: 
#                    val = adapt_search(oFields['explicit'])
#                    lstQ.append(Q(srchexplicit__iregex=val))

#                # (4) Process signature
#                if 'signature' in oFields and oFields['signature'] != "" and oFields['signature'] != None: 
#                    val = adapt_search(oFields['signature'])
#                    lstQ.append(Q(goldsignatures__code__iregex=val))

#                # Calculate the final qs
#                if len(lstQ) == 0:
#                    # Show everything excluding myself
#                    qs = SermonGold.objects.all()
#                else:
#                    # Make sure to exclude myself, and then apply the filter
#                    qs = SermonGold.objects.filter(*lstQ)

#                # Always exclude the source
#                if self.source_id != None:
#                    qs = qs.exclude(id=self.source_id)

#                sort_type = "fast_and_easy"

#                if sort_type == "pythonic":
#                    # Sort the python way
#                    qs = sorted(qs, key=lambda x: x.get_sermon_string())
#                elif sort_type == "too_much":
#                    # Make sure sorting is done correctly
#                    qs = qs.order_by('signature__code', 'author__name', 'incipit', 'explicit')
#                elif sort_type == "fast_and_easy":
#                    # Sort fast and easy
#                    qs = qs.order_by('author__name', 'siglist', 'incipit', 'explicit')
            
#            self.entrycount = qs.count()
#            self.qs = qs
#        # Return the resulting filtered and sorted queryset
#        return qs



#class LibraryEdit_ORG(BasicPart):
#    """The details of one library"""

#    MainModel = Library
#    template_name = 'seeker/library_edit.html'  
#    title = "Library" 
#    afternewurl = ""
#    # One form is attached to this 
#    prefix = "lib"
#    form_objects = [{'form': LibraryForm, 'prefix': prefix, 'readonly': False}]

#    def before_save(self, prefix, request, instance = None, form = None):
#        bNeedSaving = False
#        if prefix == "lib":
#            # Check whether the location has changed
#            if 'location' in form.changed_data:
#                # Get the new location
#                location = form.cleaned_data['location']
#                if location != None:
#                    # Get the hierarchy including myself
#                    hierarchy = location.hierarchy()
#                    for item in hierarchy:
#                        if item.loctype.name == "city":
#                            instance.lcity = item
#                            bNeedSaving = True
#                        elif item.loctype.name == "country":
#                            instance.lcountry = item
#                            bNeedSaving = True
#            pass

#        return bNeedSaving

#    def add_to_context(self, context):

#        # Get the instance
#        instance = self.obj

#        if instance != None:
#            pass

#        afternew =  reverse('library_list')
#        if 'afternewurl' in self.qd:
#            afternew = self.qd['afternewurl']
#        context['afternewurl'] = afternew

#        return context



#class LocationListView_ORG(ListView):
#    """Listview of locations"""

#    model = Location
#    paginate_by = 15
#    template_name = 'seeker/location_list.html'
#    entrycount = 0

#    def get_context_data(self, **kwargs):
#        # Call the base implementation first to get a context
#        context = super(LocationListView_ORG, self).get_context_data(**kwargs)

#        # Get parameters
#        initial = self.request.GET

#        # Determine the count 
#        context['entrycount'] = self.entrycount # self.get_queryset().count()

#        # Set the prefix
#        context['app_prefix'] = APP_PREFIX

#        # Get parameters for the search
#        initial = self.request.GET
#        # The searchform is just a list form, but filled with the 'initial' parameters
#        context['searchform'] = LocationForm(initial)

#        # Make sure the paginate-values are available
#        context['paginateValues'] = paginateValues

#        if 'paginate_by' in initial:
#            context['paginateSize'] = int(initial['paginate_by'])
#        else:
#            context['paginateSize'] = paginateSize

#        # Set the title of the application
#        context['title'] = "Passim location info"

#        # Check if user may upload
#        context['is_authenticated'] = user_is_authenticated(self.request)
#        context['is_app_uploader'] = user_is_ingroup(self.request, app_uploader)
#        context['is_app_editor'] = user_is_ingroup(self.request, app_editor)

#        # Process this visit and get the new breadcrumbs object
#        prevpage = reverse('home')
#        context['prevpage'] = prevpage
#        context['breadcrumbs'] = get_breadcrumbs(self.request, "Locations", True)

#        # Return the calculated context
#        return context

#    def get_paginate_by(self, queryset):
#        """
#        Paginate by specified value in default class property value.
#        """
#        return self.paginate_by
  
#    def get_queryset(self):
#        # Get the parameters passed on with the GET or the POST request
#        get = self.request.GET if self.request.method == "GET" else self.request.POST
#        get = get.copy()
#        self.get = get

#        lstQ = []

#        # Check for author [name]
#        if 'name' in get and get['name'] != '':
#            val = adapt_search(get['name'])
#            # Search in both the name field
#            lstQ.append(Q(name__iregex=val))

#        # Check for location type
#        if 'loctype' in get and get['loctype'] != '':
#            val = get['loctype']
#            # Search in both the name field
#            lstQ.append(Q(loctype=val))

#        # Calculate the final qs
#        qs = Location.objects.filter(*lstQ).order_by('name').distinct()

#        # Determine the length
#        self.entrycount = len(qs)

#        # Return the resulting filtered and sorted queryset
#        return qs


#class LocationDetailsView_ORG(PassimDetails):
#    model = Location
#    mForm = LocationForm
#    template_name = 'seeker/location_details.html'
#    prefix = 'loc'
#    prefix_type = "simple"
#    title = "LocationDetails"
#    rtype = "html"

#    def after_new(self, form, instance):
#        """Action to be performed after adding a new item"""

#        self.afternewurl = reverse('location_list')
#        return True, "" 

#    def add_to_context(self, context, instance):
#        # Add the list of relations in which I am contained
#        contained_locations = []
#        if instance != None:
#            contained_locations = instance.hierarchy(include_self=False)
#        context['contained_locations'] = contained_locations

#        # The standard information
#        context['is_app_editor'] = user_is_ingroup(self.request, app_editor)
#        # Process this visit and get the new breadcrumbs object
#        prevpage = reverse('location_list')
#        crumbs = []
#        crumbs.append(['Locations', prevpage])
#        current_name = "Location details"
#        if instance:
#            current_name = "Location [{}]".format(instance.name)
#        context['prevpage'] = prevpage
#        context['breadcrumbs'] = get_breadcrumbs(self.request, current_name, True, crumbs)
#        return context


#class LocationEdit_ORG(BasicPart):
#    """The details of one location"""

#    MainModel = Location
#    template_name = 'seeker/location_edit.html'  
#    title = "Location" 
#    afternewurl = ""
#    # One form is attached to this 
#    prefix = "loc"
#    form_objects = [{'form': LocationForm, 'prefix': prefix, 'readonly': False}]
#    stype_edi_fields = ['name', 'loctype', 'lcity', 'lcountry']

#    def before_save(self, prefix, request, instance = None, form = None):
#        bNeedSaving = False
#        if prefix == "loc":
#            pass

#        return bNeedSaving

#    def after_save(self, prefix, instance = None, form = None):
#        bStatus = True
#        if prefix == "loc":
#            # Check if there is a locationlist
#            if 'locationlist' in form.cleaned_data:
#                locationlist = form.cleaned_data['locationlist']

#                # Get all the containers inside which [instance] is contained
#                current_qs = Location.objects.filter(container_locrelations__contained=instance)
#                # Walk the new list
#                for item in locationlist:
#                    #if item.id not in current_ids:
#                    if item not in current_qs:
#                        # Add it to the containers
#                        LocationRelation.objects.create(contained=instance, container=item)
#                # Update the current list
#                current_qs = Location.objects.filter(container_locrelations__contained=instance)
#                # Walk the current list
#                remove_list = []
#                for item in current_qs:
#                    if item not in locationlist:
#                        # Add it to the list of to-be-fremoved
#                        remove_list.append(item.id)
#                # Remove them from the container
#                if len(remove_list) > 0:
#                    LocationRelation.objects.filter(contained=instance, container__id__in=remove_list).delete()

#        return bStatus

#    def add_to_context(self, context):

#        # Get the instance
#        instance = self.obj

#        if instance != None:
#            pass

#        afternew =  reverse('location_list')
#        if 'afternewurl' in self.qd:
#            afternew = self.qd['afternewurl']
#        context['afternewurl'] = afternew

#        return context

#    def action_add(self, instance, details, actiontype):
#        """User can fill this in to his/her liking"""
#        passim_action_add(self, instance, details, actiontype)



#class BasicPart(View):
#    """This is my own versatile handling view.

#    Note: this version works with <pk> and not with <object_id>
#    """

#    # Initialisations
#    arErr = []              # errors   
#    template_name = None    # The template to be used
#    template_err_view = None
#    form_validated = True   # Used for POST form validation
#    savedate = None         # When saving information, the savedate is returned in the context
#    add = False             # Are we adding a new record or editing an existing one?
#    obj = None              # The instance of the MainModel
#    action = ""             # The action to be undertaken
#    MainModel = None        # The model that is mainly used for this form
#    form_objects = []       # List of forms to be processed
#    formset_objects = []    # List of formsets to be processed
#    previous = None         # Return to this
#    bDebug = False          # Debugging information
#    redirectpage = ""       # Where to redirect to
#    data = {'status': 'ok', 'html': ''}       # Create data to be returned    
    
#    def post(self, request, pk=None):
#        # A POST request means we are trying to SAVE something
#        self.initializations(request, pk)
#        # Initialize typeahead list
#        lst_typeahead = []

#        # Explicitly set the status to OK
#        self.data['status'] = "ok"
        
#        if self.checkAuthentication(request):
#            # Build the context
#            context = dict(object_id = pk, savedate=None)
#            context['authenticated'] = user_is_authenticated(request)
#            context['is_app_uploader'] = user_is_ingroup(request, app_uploader)
#            context['is_app_editor'] = user_is_ingroup(request, app_editor)

#            # Action depends on 'action' value
#            if self.action == "":
#                if self.bDebug: self.oErr.Status("ResearchPart: action=(empty)")
#                # Walk all the forms for preparation of the formObj contents
#                for formObj in self.form_objects:
#                    # Are we SAVING a NEW item?
#                    if self.add:
#                        # We are saving a NEW item
#                        formObj['forminstance'] = formObj['form'](request.POST, prefix=formObj['prefix'])
#                        formObj['action'] = "new"
#                    else:
#                        # We are saving an EXISTING item
#                        # Determine the instance to be passed on
#                        instance = self.get_instance(formObj['prefix'])
#                        # Make the instance available in the form-object
#                        formObj['instance'] = instance
#                        # Get an instance of the form
#                        formObj['forminstance'] = formObj['form'](request.POST, prefix=formObj['prefix'], instance=instance)
#                        formObj['action'] = "change"

#                # Initially we are assuming this just is a review
#                context['savedate']="reviewed at {}".format(get_current_datetime().strftime("%X"))

#                # Iterate again
#                for formObj in self.form_objects:
#                    prefix = formObj['prefix']
#                    # Adapt if it is not readonly
#                    if not formObj['readonly']:
#                        # Check validity of form
#                        if formObj['forminstance'].is_valid() and self.is_custom_valid(prefix, formObj['forminstance']):
#                            # Save it preliminarily
#                            instance = formObj['forminstance'].save(commit=False)
#                            # The instance must be made available (even though it is only 'preliminary')
#                            formObj['instance'] = instance
#                            # Perform actions to this form BEFORE FINAL saving
#                            bNeedSaving = formObj['forminstance'].has_changed()
#                            if self.before_save(prefix, request, instance=instance, form=formObj['forminstance']): bNeedSaving = True
#                            if formObj['forminstance'].instance.id == None: bNeedSaving = True
#                            if bNeedSaving:
#                                # Perform the saving
#                                instance.save()
#                                # Log the SAVE action
#                                details = {'id': instance.id}
#                                if formObj['forminstance'].changed_data != None:
#                                    details['changes'] = action_model_changes(formObj['forminstance'], instance)
#                                if 'action' in formObj: details['savetype'] = formObj['action']
#                                Action.add(request.user.username, self.MainModel.__name__, instance.id, "save", json.dumps(details))
#                                # Set the context
#                                context['savedate']="saved at {}".format(get_current_datetime().strftime("%X"))
#                                # Put the instance in the form object
#                                formObj['instance'] = instance
#                                # Store the instance id in the data
#                                self.data[prefix + '_instanceid'] = instance.id
#                                # Any action after saving this form
#                                self.after_save(prefix, instance=instance, form=formObj['forminstance'])
#                            # Also get the cleaned data from the form
#                            formObj['cleaned_data'] = formObj['forminstance'].cleaned_data
#                        else:
#                            self.arErr.append(formObj['forminstance'].errors)
#                            self.form_validated = False
#                            formObj['cleaned_data'] = None
#                    else:
#                        # Form is readonly

#                        # Check validity of form
#                        if formObj['forminstance'].is_valid() and self.is_custom_valid(prefix, formObj['forminstance']):
#                            # At least get the cleaned data from the form
#                            formObj['cleaned_data'] = formObj['forminstance'].cleaned_data

#                            # x = json.dumps(sorted(self.qd.items(), key=lambda kv: kv[0]), indent=2)
#                    # Add instance to the context object
#                    context[prefix + "Form"] = formObj['forminstance']
#                    # Get any possible typeahead parameters
#                    lst_form_ta = getattr(formObj['forminstance'], "typeaheads", None)
#                    if lst_form_ta != None:
#                        for item in lst_form_ta:
#                            lst_typeahead.append(item)
#                # Walk all the formset objects
#                for formsetObj in self.formset_objects:
#                    prefix  = formsetObj['prefix']
#                    if self.can_process_formset(prefix):
#                        formsetClass = formsetObj['formsetClass']
#                        form_kwargs = self.get_form_kwargs(prefix)
#                        if self.add:
#                            # Saving a NEW item
#                            if 'initial' in formsetObj:
#                                formset = formsetClass(request.POST, request.FILES, prefix=prefix, initial=formsetObj['initial'], form_kwargs = form_kwargs)
#                            else:
#                                formset = formsetClass(request.POST, request.FILES, prefix=prefix, form_kwargs = form_kwargs)
#                        else:
#                            # Saving an EXISTING item
#                            instance = self.get_instance(prefix)
#                            qs = self.get_queryset(prefix)
#                            if qs == None:
#                                formset = formsetClass(request.POST, request.FILES, prefix=prefix, instance=instance, form_kwargs = form_kwargs)
#                            else:
#                                formset = formsetClass(request.POST, request.FILES, prefix=prefix, instance=instance, queryset=qs, form_kwargs = form_kwargs)
#                        # Process all the forms in the formset
#                        self.process_formset(prefix, request, formset)
#                        # Store the instance
#                        formsetObj['formsetinstance'] = formset
#                        # Make sure we know what we are dealing with
#                        itemtype = "form_{}".format(prefix)
#                        # Adapt the formset contents only, when it is NOT READONLY
#                        if not formsetObj['readonly']:
#                            # Is the formset valid?
#                            if formset.is_valid():
#                                # Possibly handle the clean() for this formset
#                                if 'clean' in formsetObj:
#                                    # Call the clean function
#                                    self.clean(formset, prefix)
#                                has_deletions = False
#                                if len(self.arErr) == 0:
#                                    # Make sure all changes are saved in one database-go
#                                    with transaction.atomic():
#                                        # Walk all the forms in the formset
#                                        for form in formset:
#                                            # At least check for validity
#                                            if form.is_valid() and self.is_custom_valid(prefix, form):
#                                                # Should we delete?
#                                                if 'DELETE' in form.cleaned_data and form.cleaned_data['DELETE']:
#                                                    # Check if deletion should be done
#                                                    if self.before_delete(prefix, form.instance):
#                                                        # Log the delete action
#                                                        details = {'id': form.instance.id}
#                                                        Action.add(request.user.username, itemtype, form.instance.id, "delete", json.dumps(details))
#                                                        # Delete this one
#                                                        form.instance.delete()
#                                                        # NOTE: the template knows this one is deleted by looking at form.DELETE
#                                                        has_deletions = True
#                                                else:
#                                                    # Check if anything has changed so far
#                                                    has_changed = form.has_changed()
#                                                    # Save it preliminarily
#                                                    sub_instance = form.save(commit=False)
#                                                    # Any actions before saving
#                                                    if self.before_save(prefix, request, sub_instance, form):
#                                                        has_changed = True
#                                                    # Save this construction
#                                                    if has_changed and len(self.arErr) == 0: 
#                                                        # Save the instance
#                                                        sub_instance.save()
#                                                        # Adapt the last save time
#                                                        context['savedate']="saved at {}".format(get_current_datetime().strftime("%X"))
#                                                        # Log the delete action
#                                                        details = {'id': sub_instance.id}
#                                                        if form.changed_data != None:
#                                                            details['changes'] = action_model_changes(form, sub_instance)
#                                                        Action.add(request.user.username, itemtype,sub_instance.id, "save", json.dumps(details))
#                                                        # Store the instance id in the data
#                                                        self.data[prefix + '_instanceid'] = sub_instance.id
#                                                        # Any action after saving this form
#                                                        self.after_save(prefix, sub_instance)
#                                            else:
#                                                if len(form.errors) > 0:
#                                                    self.arErr.append(form.errors)
                                
#                                    # Rebuild the formset if it contains deleted forms
#                                    if has_deletions or not has_deletions:
#                                        # Or: ALWAYS
#                                        if qs == None:
#                                            formset = formsetClass(prefix=prefix, instance=instance, form_kwargs=form_kwargs)
#                                        else:
#                                            formset = formsetClass(prefix=prefix, instance=instance, queryset=qs, form_kwargs=form_kwargs)
#                                        formsetObj['formsetinstance'] = formset
#                            else:
#                                # Iterate over all errors
#                                for idx, err_this in enumerate(formset.errors):
#                                    if '__all__' in err_this:
#                                        self.arErr.append(err_this['__all__'][0])
#                                    elif err_this != {}:
#                                        # There is an error in item # [idx+1], field 
#                                        problem = err_this 
#                                        for k,v in err_this.items():
#                                            fieldName = k
#                                            errmsg = "Item #{} has an error at field [{}]: {}".format(idx+1, k, v[0])
#                                            self.arErr.append(errmsg)

#                            # self.arErr.append(formset.errors)
#                    else:
#                        formset = []
#                    # Get any possible typeahead parameters
#                    lst_formset_ta = getattr(formset.form, "typeaheads", None)
#                    if lst_formset_ta != None:
#                        for item in lst_formset_ta:
#                            lst_typeahead.append(item)
#                    # Add the formset to the context
#                    context[prefix + "_formset"] = formset
#            elif self.action == "download":
#                # We are being asked to download something
#                if self.dtype != "":
#                    plain_type = ["xlsx", "csv", "excel"]
#                    # Initialise return status
#                    oBack = {'status': 'ok'}
#                    sType = "csv" if (self.dtype == "xlsx") else self.dtype

#                    # Get the data
#                    sData = ""
#                    if self.dtype != "excel":
#                        sData = self.get_data('', self.dtype)
#                    # Decode the data and compress it using gzip
#                    bUtf8 = (self.dtype != "db")
#                    bUsePlain = (self.dtype in plain_type)

#                    # Create name for download
#                    # sDbName = "{}_{}_{}_QC{}_Dbase.{}{}".format(sCrpName, sLng, sPartDir, self.qcTarget, self.dtype, sGz)
#                    modelname = self.MainModel.__name__
#                    obj_id = "n" if self.obj == None else self.obj.id
#                    extension = "xlsx" if self.dtype == "excel" else self.dtype
#                    sDbName = "passim_{}_{}.{}".format(modelname, obj_id, extension)
#                    sContentType = ""
#                    if self.dtype == "csv":
#                        sContentType = "text/tab-separated-values"
#                    elif self.dtype == "json":
#                        sContentType = "application/json"
#                    elif self.dtype == "xlsx" or self.dtype == "excel":
#                        sContentType = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
#                    elif self.dtype == "hist-svg":
#                        sContentType = "application/svg"
#                        sData = self.qd['downloaddata']
#                        # Set the filename correctly
#                        sDbName = "passim_{}_{}.svg".format(modelname, obj_id)
#                    elif self.dtype == "hist-png":
#                        sContentType = "image/png"
#                        # Read the base64 encoded part
#                        sData = self.qd['downloaddata']
#                        arPart = sData.split(";")
#                        if len(arPart) > 1:
#                            dSecond = arPart[1]
#                            # Strip off preceding base64 part
#                            sData = dSecond.replace("base64,", "")
#                            # Convert string to bytestring
#                            sData = sData.encode()
#                            # Decode base64 into binary
#                            sData = base64.decodestring(sData)
#                            # Set the filename correctly
#                            sDbName = "passim_{}_{}.png".format(modelname, obj_id)

#                    # Excel needs additional conversion
#                    if self.dtype == "xlsx":
#                        # Convert 'compressed_content' to an Excel worksheet
#                        response = HttpResponse(content_type=sContentType)
#                        response['Content-Disposition'] = 'attachment; filename="{}"'.format(sDbName)    
#                        response = csv_to_excel(sData, response)
#                    elif self.dtype == "excel":
#                        # Convert 'compressed_content' to an Excel worksheet
#                        response = HttpResponse(content_type=sContentType)
#                        response['Content-Disposition'] = 'attachment; filename="{}"'.format(sDbName)    
#                        response = self.get_data('', self.dtype, response)
#                    else:
#                        response = HttpResponse(sData, content_type=sContentType)
#                        response['Content-Disposition'] = 'attachment; filename="{}"'.format(sDbName)    

#                    # Continue for all formats
                        
#                    # return gzip_middleware.process_response(request, response)
#                    return response
#            elif self.action == "delete":
#                # The user requests this to be deleted
#                if self.before_delete():
#                    # Log the delete action
#                    details = {'id': self.obj.id}
#                    Action.add(request.user.username, self.MainModel.__name__, self.obj.id, "delete", json.dumps(details))
#                    # We have permission to delete the instance
#                    self.obj.delete()
#                    context['deleted'] = True

#            # Allow user to add to the context
#            context = self.add_to_context(context)
            
#            # Possibly add data from [context.data]
#            if 'data' in context:
#                for k,v in context['data'].items():
#                    self.data[k] = v

#            # First look at redirect page
#            self.data['redirecturl'] = ""
#            if self.redirectpage != "":
#                self.data['redirecturl'] = self.redirectpage
#            # Check if 'afternewurl' needs adding
#            # NOTE: this should only be used after a *NEW* instance has been made -hence the self.add check
#            if 'afternewurl' in context and self.add:
#                self.data['afternewurl'] = context['afternewurl']
#            else:
#                self.data['afternewurl'] = ""
#            if 'afterdelurl' in context:
#                self.data['afterdelurl'] = context['afterdelurl']

#            # Make sure we have a list of any errors
#            error_list = [str(item) for item in self.arErr]
#            context['error_list'] = error_list
#            context['errors'] = json.dumps( self.arErr)
#            if len(self.arErr) > 0:
#                # Indicate that we have errors
#                self.data['has_errors'] = True
#                self.data['status'] = "error"
#            else:
#                self.data['has_errors'] = False
#            # Standard: add request user to context
#            context['requestuser'] = request.user

#            # Set any possible typeaheads
#            self.data['typeaheads'] = lst_typeahead

#            # Get the HTML response
#            if len(self.arErr) > 0:
#                if self.template_err_view != None:
#                     # Create a list of errors
#                    self.data['err_view'] = render_to_string(self.template_err_view, context, request)
#                else:
#                    self.data['error_list'] = error_list
#                    self.data['errors'] = self.arErr
#                self.data['html'] = ''
#                # We may not redirect if there is an error!
#                self.data['redirecturl'] = ''
#            elif self.action == "delete":
#                self.data['html'] = "deleted" 
#            elif self.template_name != None:
#                # In this case reset the errors - they should be shown within the template
#                sHtml = render_to_string(self.template_name, context, request)
#                sHtml = treat_bom(sHtml)
#                self.data['html'] = sHtml
#            else:
#                self.data['html'] = 'no template_name specified'

#            # At any rate: empty the error basket
#            self.arErr = []
#            error_list = []

#        else:
#            self.data['html'] = "Please log in before continuing"

#        # Return the information
#        return JsonResponse(self.data)
        
#    def get(self, request, pk=None): 
#        self.data['status'] = 'ok'
#        # Perform the initializations that need to be made anyway
#        self.initializations(request, pk)
#        # Initialize typeahead list
#        lst_typeahead = []

#        # Continue if authorized
#        if self.checkAuthentication(request):
#            context = dict(object_id = pk, savedate=None)
#            context['prevpage'] = self.previous
#            context['authenticated'] = user_is_authenticated(request)
#            context['is_app_uploader'] = user_is_ingroup(request, app_uploader)
#            context['is_app_editor'] = user_is_ingroup(request, app_editor)
#            # Walk all the form objects
#            for formObj in self.form_objects:        
#                # Used to populate a NEW research project
#                # - CREATE a NEW research form, populating it with any initial data in the request
#                initial = dict(request.GET.items())
#                if self.add:
#                    # Create a new form
#                    formObj['forminstance'] = formObj['form'](initial=initial, prefix=formObj['prefix'])
#                else:
#                    # Used to show EXISTING information
#                    instance = self.get_instance(formObj['prefix'])
#                    # We should show the data belonging to the current Research [obj]
#                    formObj['forminstance'] = formObj['form'](instance=instance, prefix=formObj['prefix'])
#                # Add instance to the context object
#                context[formObj['prefix'] + "Form"] = formObj['forminstance']
#                # Get any possible typeahead parameters
#                lst_form_ta = getattr(formObj['forminstance'], "typeaheads", None)
#                if lst_form_ta != None:
#                    for item in lst_form_ta:
#                        lst_typeahead.append(item)
#            # Walk all the formset objects
#            for formsetObj in self.formset_objects:
#                formsetClass = formsetObj['formsetClass']
#                prefix  = formsetObj['prefix']
#                form_kwargs = self.get_form_kwargs(prefix)
#                if self.add:
#                    # - CREATE a NEW formset, populating it with any initial data in the request
#                    initial = dict(request.GET.items())
#                    # Saving a NEW item
#                    formset = formsetClass(initial=initial, prefix=prefix, form_kwargs=form_kwargs)
#                else:
#                    # Possibly initial (default) values
#                    if 'initial' in formsetObj:
#                        initial = formsetObj['initial']
#                    else:
#                        initial = None
#                    # show the data belonging to the current [obj]
#                    instance = self.get_instance(prefix)
#                    qs = self.get_queryset(prefix)
#                    if qs == None:
#                        formset = formsetClass(prefix=prefix, instance=instance, form_kwargs=form_kwargs)
#                    else:
#                        formset = formsetClass(prefix=prefix, instance=instance, queryset=qs, initial=initial, form_kwargs=form_kwargs)
#                # Get any possible typeahead parameters
#                lst_formset_ta = getattr(formset.form, "typeaheads", None)
#                if lst_formset_ta != None:
#                    for item in lst_formset_ta:
#                        lst_typeahead.append(item)
#                # Process all the forms in the formset
#                ordered_forms = self.process_formset(prefix, request, formset)
#                if ordered_forms:
#                    context[prefix + "_ordered"] = ordered_forms
#                # Store the instance
#                formsetObj['formsetinstance'] = formset
#                # Add the formset to the context
#                context[prefix + "_formset"] = formset
#            # Allow user to add to the context
#            context = self.add_to_context(context)
#            # Make sure we have a list of any errors
#            error_list = [str(item) for item in self.arErr]
#            context['error_list'] = error_list
#            context['errors'] = self.arErr
#            # Standard: add request user to context
#            context['requestuser'] = request.user

#            # Set any possible typeaheads
#            self.data['typeaheads'] = json.dumps(lst_typeahead)
            
#            # Get the HTML response
#            sHtml = render_to_string(self.template_name, context, request)
#            sHtml = treat_bom(sHtml)
#            self.data['html'] = sHtml
#        else:
#            self.data['html'] = "Please log in before continuing"

#        # Return the information
#        return JsonResponse(self.data)
      
#    def checkAuthentication(self,request):
#        # first check for authentication
#        if not request.user.is_authenticated:
#            # Simply redirect to the home page
#            self.data['html'] = "Please log in to work on this project"
#            return False
#        else:
#            return True

#    def rebuild_formset(self, prefix, formset):
#        return formset

#    def initializations(self, request, object_id):
#        # Store the previous page
#        #self.previous = get_previous_page(request)
#        # Clear errors
#        self.arErr = []
#        # COpy the request
#        self.request = request
#        # Copy any object id
#        self.object_id = object_id
#        self.add = object_id is None
#        # Get the parameters
#        if request.POST:
#            self.qd = request.POST.copy()
#        else:
#            self.qd = request.GET.copy()

#        # Immediately take care of the rangeslider stuff
#        lst_remove = []
#        for k,v in self.qd.items():
#            if "-rangeslider" in k: lst_remove.append(k)
#        for item in lst_remove: self.qd.pop(item)
#        #lst_remove = []
#        #dictionary = {}
#        #for k,v in self.qd.items():
#        #    if "-rangeslider" not in k: 
#        #        dictionary[k] = v
#        #self.qd = dictionary

#        # Check for action
#        if 'action' in self.qd:
#            self.action = self.qd['action']

#        # Find out what the Main Model instance is, if any
#        if self.add:
#            self.obj = None
#        elif self.MainModel != None:
#            # Get the instance of the Main Model object
#            self.obj =  self.MainModel.objects.filter(pk=object_id).first()
#            # NOTE: if the object doesn't exist, we will NOT get an error here
#        # ALWAYS: perform some custom initialisations
#        self.custom_init()

#    def get_instance(self, prefix):
#        return self.obj

#    def is_custom_valid(self, prefix, form):
#        return True

#    def get_queryset(self, prefix):
#        return None

#    def get_form_kwargs(self, prefix):
#        return None

#    def get_data(self, prefix, dtype, response=None):
#        return ""

#    def before_save(self, prefix, request, instance=None, form=None):
#        return False

#    def before_delete(self, prefix=None, instance=None):
#        return True

#    def after_save(self, prefix, instance=None, form=None):
#        return True

#    def add_to_context(self, context):
#        return context

#    def process_formset(self, prefix, request, formset):
#        return None

#    def can_process_formset(self, prefix):
#        return True

#    def custom_init(self):
#        pass    
           



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


