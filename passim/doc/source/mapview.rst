.. _mapviewapp:

The 'mapview' app
=================

The ``mapview`` app can right now be downloaded from the GitHub 
`Stalla mapview <https://github.com/ErwinKomen/RU-stalla/tree/master/stalla/stalla/mapview>`_ page.

What it does
------------
The ``mapview`` app facilitates showing a map that is based on the results of a filtered listview.

Usage example
-------------
A practical use-case for the ``mapview`` app is a language mapview. 

A Django web application has a model ``Language`` with field: ``name``,
and it also has a model ``Location`` with fields: ``locname``, ``language``, ``x_coordinate``, ``y_coordinate``.
The field ``language`` is an FK to the model ``Language``.

The application has a listview ``LanguageList()``, where the user can filter the languages he would like to see.

The task is: build a map representation of the locations belonging to the user-selected languages.

Resolving this task with the help of the ``mapview`` app, these are the steps to be taken:

#. View

   a. Add a view ``LanguageMapView`` based on ``MapView``: 
   
      * define the ``LanguageMapView``
         .. code-block:: python
            :linenos:

            class LanguageMapView(MapView):
                """Mapview that goes together with the Language listview"""

                model = Language
                modEntry = Location         # Each point on the map is a Location
                frmSearch = LanguageForm    # Form used by listview ``LanguageList``
                use_object = False          # We are **not** grouping around one language
                param_list = ""             
                prefix = "wer"              # Differs from the ``LanguageList`` prefix
   
      * use ``initialize`` to prepare a queryset with locations of these languages
         .. code-block:: python
            :linenos:

            def initialize(self):
                super(LanguageMapView, self).initialize()

                oErr = ErrHandle()
                try:
                    # Entries with a 'form' value
                    self.entry_list = []
                    # The location: name, id, x-coordinate, y-coordinate
                    self.add_entry('locname',       'str',  'name',     'locname')
                    self.add_entry('location_id',   'str', 'id')
                    # labels 'point_x' and 'point_y' must be used for the coordinates
                    self.add_entry('point_x',       'str', 'x_coordinate')
                    self.add_entry('point_y',       'str', 'y_coordinate')
                    # The name of the language for this location
                    self.add_entry('language',      'str', "language__name")
                    self.add_entry('dialect',       'str', "dialect__name")

                    # Get a version of the current listview
                    lv = LanguageList()
                    lv.initializations()
                    # Get the list of [Language] elements
                    qs_lang = lv.get_queryset(self.request)

                    # Get a full queryset of the locations for these languages
                    qs_loc = Location.objects.filter(Q(language__in=lst_lang) 

      * group the location entries per language
         .. code-block:: python
            :linenos:

            def group_entries(self, lst_this):
                """Allow changing the list of entries"""

                oErr = ErrHandle()
                lst_back = []
                exclude_fields = ['point', 'point_x', 'point_y', 'pop_up', 'locatie', 'country', 'city']
                try:

                    # We need to create a new list, based on the 'point' parameter
                    #   A point is, for example: [42.641667, 45.945556]
                    #   (if not specified, [point] values are calculated inside ``MapView``)
                    set_point = {}
                    for oEntry in lst_this:
                        # Regular stuff
                        point = oEntry['point']
                        if not point in set_point:
                            # Create a new entry - Only the language of the first entry for the point are taken
                            sLanguage = oEntry['language']

                            set_point[point] = dict(count=0, items=[], point=point, 
                                                    trefwoord=sLanguage,
                                                    locatie=oEntry['locname'],
                                                    locid=oEntry['location_id'],
                                                    language=sLanguage)
                        # Retrieve the item from the set
                        oPoint = set_point[point]
                        # Add this entry
                        oPoint['count'] += 1
                        oPoint['items'].append( { k:v for k,v in oEntry.items() if not k in exclude_fields } )

                    # Review them again
                    for point, oEntry in set_point.items():
                        # Create the popup
                        oEntry['pop_up'] = self.get_group_popup(oEntry)
                        # Add it to the list we return
                        lst_back.append(oEntry)
                except:
                    msg = oErr.get_error_message()
                    oErr.DoError("group_entries")

                return lst_back

      * provide a meaningful popup per location point
         .. code-block:: python
            :linenos:

            def get_group_popup(self, oEntry):
                """Create a popup from the 'key' values defined in [initialize()]"""

                oErr = ErrHandle()
                pop_up = ""
                try:
                    pop_up = '<p class="h6">{}</p>'.format(oEntry['locname'])
                    pop_up += '<hr style="border: 1px solid green" />'
                    pop_up += '<p style="font-size: medium;"><span style="color: purple;">{}</span> {}</p>'.format(
                        oEntry['language'], oEntry['locname'])
                except:
                    msg = oErr.get_error_message()
                    oErr.DoError("LanguageMapView/get_group_popup")
                return pop_up


   #. Adapt the ``LanguageList`` view to allow switching between mapview and listview

      * set the context values for ``basicmap`` and ``mapviewurl``
      * calculate the context value for ``mapcount``
         .. code-block:: python
            :linenos:

            def add_to_context(self, context, initial):

                oErr = ErrHandle()
                try:
                    # Fill in necessary details
                    context['mapviewurl'] = reverse('language_map')

                    # Signal that 'basicmap' should be used (used in `basic_list.html`)
                    context['basicmap'] = True

                    # Figure out how many locations there are
                    sLocationCount = Location.objects.filter(self.qs).order_by('id').distinct().count()
                    context['mapcount'] = sLocationCount

      * double check the ``basic_list.html``
         See the use of ``basicmap`` in the ``basic_list.html`` variant of 
         `Passim <https://github.com/ErwinKomen/RU-passim/tree/master/passim/passim/basic/templates/basic/basic_list.html>`_ page.
         That example also illustrates how the context variables ``mapviewurl`` and ``mapcount`` can be used.
         See the basic app's template ``map_list_switch.html`` in the Passim application.

#. Javascript: 

   a. Make a javascript function that calls mapiew's built-in function to draw the map:

      * when the user clicks a button provided by the ``LanguageList`` view, call the ``ru.mapview.list_to_map()``
         Please see the use of ``basicmap`` and ``basiclist_top`` as well as ``.werkstuk-map`` on the 
         `Passim <https://github.com/ErwinKomen/RU-passim/tree/master/passim/passim/basic/templates/basic/basic_list.html>`_ page

         .. code-block:: javascript
            :linenos:

              /**
               * goto_view
               *   Open the indicated view
               *
               */
              goto_view: function (elStart, sView) {
                var height = 0,
                  width = 0,
                  id_mapview = "#basicmap",
                  id_listview = "#basiclist_top";
                try {
                  switch (sView) {
                    case "map":   // Open the map-view
                      $(id_listview).addClass("hidden");
                      $(id_mapview).removeClass("hidden");
                      $(".map-list-switch").addClass("map-active");

                      // Calculate and set the height
                      height = $("footer").position().top - $(".werkstuk-map").position().top - 10;
                      width = $(id_mapview).width();
                      $(".werkstuk-map").css("height", height + "px");
                      $(".werkstuk-map").css("width", width + "px");

                      // Initiate showing a map
                      ru.mapview.list_to_map(elStart);
                      break;
                    case "list":  // Open the listview
                      $(id_mapview).addClass("hidden");
                      $(id_listview).removeClass("hidden");
                      $(".map-list-switch").removeClass("map-active");
                      break;
                  }

                } catch (ex) {
                  private_methods.errMsg("goto_view", ex);
                }
              },


Files and folders
-----------------
the ``mapview`` utility is available as a django 'app'.
The sources consist of the following folders and files::

  mapview
    migrations
    static
      mapview
        css
          fontawesome-5-all.css
          leaflet.css
          ru.mapview.css
        scripts
          leaflest-src.js
          oms.min.js
          ru.mapview.js
        webfonts
    templates
      mapview
        map_view.html               # Modal form size map (as in eWGD, eWLD etc)
        map_view_full.html          # Full page size map
    __init__.py
    admin.py                        # Not used
    apps.py
    models.py                       # Not used
    tests.py                        # Not used
    views.py
    
Settings
--------
Like any other django app, the ``mapview`` app too needs to be added to the installed apps in ``settings.py``.
The ``INSTALLED_APPS`` variable in settings might come to look like this, 
if you have an application called ``yourapplication``, and one Django app in it called ``main``:

.. code-block:: python

    INSTALLED_APPS = [
        'django.contrib.admin',
        'django.contrib.auth',
        'django.contrib.contenttypes',
        'django.contrib.sessions',
        'django.contrib.messages',
        'django.contrib.staticfiles',

        # Needed for mapview
        'django_select2',
        'yourapplication.mapview',

        # Add your apps here to enable them
        'yourapplication.main',   
    ]

views.py            
--------
The main feature of the ``mapview`` app is that it provides the ``MapView`` (in views.py).
That view is based on Django's ``DetailView``. 
Django's ``DetailView`` normally expects to be centered around one object of a model, which is why it has the possibility to
define the ``model`` inside the view. Maps can be based on a listview resulting from one particular object (e.g. all languages from one particular family),
but they do not necessarily have to be. 
The aim of the ``MapView`` view, then, is to show the result of a filtered **listview**.

The ``MapView`` has a couple of class variables, some of which need to be set obligatorily (*), most of which are optional ( [] ).

.. table::
    :widths: auto
    :align: left
    
    ===================== ========================================================================
    Variable              Usage
    ===================== ========================================================================
    ``[entry_list]``      internal use: list of items to show on the map
    ``[filterQ]``         ``Q`` filter expression to be combined with the other criteria
    ``*frmSearch``        search form used in the listview
    ``[instance]``        internal use
    ``[label]``           used by ``JS`` ``lemma_map()`` and ``dialect_map()`` for the map title
    ``[labelfield]``      model's field to get the label from
    ``[model]``           the model-class to which the view is connected 
    ``[modEntry]``        the model class used for the entries shown on the map
    ``[order_by]``        sort order of the list query
    ``[prefix]``          specify a prefix that differs from the one in the (filtered) listview
    ``[qs]``              user-specified queryset, if the listview's search form is not sufficient
    ``[use_object]``      ``True`` if the map takes one object as a starting point
    ===================== ========================================================================


The ``MapView`` class uses the following methods:

    ``add_entry()``  - add one entry into the internal ``self.entry_list``

    ``get()``  - handle a GET request: MapView only redirects to view ``home`` (which should be defined)

    ``get_object()`` - if ``use_object`` is True, then return the object via ``DetailView``'s standard ``get_object()``

    ``get_popup()`` - allows caller to specify a popup

    ``group_entries()`` - allows caller to change the list of entries

    ``initialize()`` - initialize ``entry_list`` and allow user to fill it via calls to ``add_entry()``

    ``post()`` - main entry when called from JS: handles a POST request, returning a JSON response







