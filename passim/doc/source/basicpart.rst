.. _basicpart:

The ``BasicPart`` class
=======================

The ``basic`` app provides the view ``BasicPart``, which is based on Django's ``View`` class.
This offers very basic ``POST`` and ``GET`` handling. 
The ``POST`` normally returns a ``JSON`` object with a built-in status and error handling system.

BasicPart methods
-----------------

The ``Basicpart`` class has a couple of class variables, some of which need to be set obligatorily.

.. table::
    :widths: auto
    :align: left
    
    ===================== =======================================================================
    Variable              Usage
    ===================== =======================================================================
    ``*MainModel``        the model-class to which the view is connected
    ``[form_objects]``    List of forms used in this view
    ``[formset_objects]`` List of formsets used in this view
    ``[action]``          can be "", "delete" or "download"
    ===================== =======================================================================


The ``BasicPart`` class makes available the following methods:

    ``post()`` - handle a POST request

    ``get()``  - handle a GET request

    ``action_add()`` - allow custom logging of creation, change or deletion

    ``add_to_context()`` - allow custom logging of creation, change or deletion

    ``after_save()`` - 

    ``before_delete()`` -

    ``before_save()`` -

    ``can_process_formset()`` -

    ``custom_init()`` -

    ``checkAuthentication()`` -

    ``download_excel()`` -

    ``get_form_kwargs()`` -

    ``get_instance()`` -

    ``get_queryset()`` -

    ``initializations()`` -

    ``is_custom_valid()`` -

    ``process_formset()`` -

    ``rebuild_formset()`` -

    ``userpermissions()`` -


Example: save a visualization
-----------------------------

One example of using ``BasicPart`` is the following. 
Suppose we have a visualization made by the user, and the user wants to 'save' this.
That is to say, the particular visualization gets linked to the user saving it.
The JavaScript code handling the 'save' button will make a ``POST`` request to the view called ``SavedVisualizationApply``.

.. code-block:: python
   :linenos:

    class SavedVisualizationApply(BasicPart):
        """Add a named saved visualization item"""

        MainModel = User

        def add_to_context(self, context):

            oErr = ErrHandle()
            data = dict(status="ok")
       
            try:

                # We already know who we are
                profile = self.obj.user_profiles.first()
                # Retrieve necessary parameters
                options = self.qd.get("options")
                # Unwrap the options
                if not options is None:
                    oOptions = json.loads(options)
                    # URL to be called to get the visualization
                    visurl = oOptions.get("visurl")

                    # Figure out what the name of the visualization is
                    searchname = ""
                    for k,v in self.qd.items():
                        if "-visname" in k:
                            searchname = v
                            break
                    if searchname == "":
                        # User did not supply a name
                        data['action'] = "empty"
                    else:
                        # Create a saved search
                        obj = SavedVis.objects.filter(name=searchname, profile=profile).first()
                        if obj is None:
                            obj = SavedVis.objects.create(name=searchname, profile=profile, visurl=visurl, options=options)
                        else:
                            bNeedSaving = False
                            # Check and set the visurl + options
                            if obj.visurl != visurl: 
                                obj.visurl = visurl 
                                bNeedSaving = True
                            if obj.options != options:
                                obj.options = options
                                bNeedSaving = True

                            if bNeedSaving:
                                obj.save()
                        # Indicate what happened: adding
                        data['action'] = "added"

            except:
                msg = oErr.get_error_message()
                oErr.DoError("SavedVisualizationApply")
                data['status'] = "error"

            context['data'] = data
            return context

The code above shows a couple of features of the ``BasicPart`` class.
One is that it aims to make the object from a the desired model class available.
It does so, first of all, by allowing the ``MainModel`` to specify the desired model.
And secondly, it makes the object available as ``self.obj`` (see line 14).
Any parameters passed on in the ``POST`` are made available via the ``self.qd`` dictionary.
The visualization itself gets 'saved' by specifying the URL to that visualization as well as the parameters used by the user in the ``options`` field.
The ``data`` object that is returned by the ``add_to_context()`` method above is also the object that is returned to the Javascript
handler of the "save" button click.

Example: download
-----------------

Suppose one wants to offer the user the possibility to download data from the web application to his/her computer.
The code below illustrates how a simple list of authors could be made available as ``JSON`` for the user's download.

.. code-block:: python
   :linenos:

    class AuthorListDownload(BasicPart):
        MainModel = Author
        template_name = "seeker/download_status.html"
        action = "download"
        dtype = "json"       # downloadtype

        def custom_init(self):
            """Calculate the [dtype]"""
        
            dt = self.qd.get('downloadtype', "")
            if dt != None and dt != '':
                self.dtype = dt

        def get_data(self, prefix, dtype, response=None):
            """Gather the data as CSV, including a header line and comma-separated"""

            # Initialize
            lData = []
            sData = ""

            if dtype == "json":
                # Loop
                for author in Author.objects.all().order_by('name'):
                    row = {"id": author.id, "name": author.name}
                    lData.append(row)
                # convert to string
                sData = json.dumps(lData)

            # Return the data as string
            return sData

The specification of the ``action`` as ``download`` makes sure that this ``BasicPart`` view is used solely for downloading.
Note that the built-in method ``custom_init()`` adds code to make sure the parameter ``self.dtype`` is set correctly early on.
That is one of the parameters that get passed on to the built-in method ``get_data()``, which collects the data for a particular download type.
