Basic Reader
============

.. _basicreader:

Creating and using the ``BasicReader`` class is illustrated by the ``PersonImport`` example, as used in the Solemne project.

.. image:: images/PersonImport.png

.. code-block:: python
   :linenos:
   
    class PersonImport(BasicReader):
        """Import an Excel file with Person information"""

        model = Person
        import_type = "person_excel"    # This must be the same as specified in 'uploads'

        def add_row(self, oRowData, **kwargs):
            """Process the rowdata and return True if added into the DB"""
            bResult = False
            return bResult

        def add_rows(self, lst_row, **kwargs):
            """Process the list of rows and return the number of items added into the DB"""
            added = 0
            return added

        def after_new(self, instance, oRow):
            return instance

        def after_upload(self):
            """Executed after process_files()"""
            pass

        def before_upload(self):
            """Executed just before process_files()"""
            pass


The ``PersonImport`` is based on the view ``BasicReader``, which is provided by the basic app.
The ``BasicReader`` class extends the Django-provided generic ``View`` class.
This  means that it comes with all the standard view methods and attributes.
Here is a discussion of the attributes and methods that are more specific to ``BasicReader``.

Specification
-------------

Most of the handling is actually done by using the ``specification`` attribute defined with the main ``model`` to which 
instances are uploaded. The ``Basic listview downloads`` section contains full details.
Here is an example of the ``specification`` with the model ``Person``:

  .. code-block:: python
     :linenos:

      # Scheme for downloading and uploading
      specification = [
          {'name': 'Name',            'type': 'field', 'path': 'name'         },
          {'name': 'Description',     'type': 'field', 'path': 'description'  },
          {'name': 'Role',            'type': 'fk',    'path': 'role', 
           'fkfield': "name", 'model': Role},
          {'name': 'Label',           'type': 'field', 'path': 'label'        },
          {'name': 'Xml ID',          'type': 'field', 'path': 'xmlid',       'readonly': True},
          {'name': 'Scope',           'type': 'func',  'path': 'scope',       'readonly': True},
          {'name': 'Collections',     'type': 'func',  'path': 'corecols',    'readonly': True },
          {'name': 'Created',         'type': 'field', 'path': 'created',     'readonly': True},
          {'name': 'Saved',           'type': 'field', 'path': 'saved',       'readonly': True},
          ]

It is only the elements that have no ``readonly`` specified that can actually be used in uploading definitions with Excel.
Note that type ``fk`` can be used to upload fields specified in a table linked to ``Person`` with a foreign key.
So the ``Person`` model has a foreign key to the model ``Role``, 
and the value provided in the Excel sheet is the ``name`` field in that model ``Role``.


Attributes
----------

``model``
   The name of the model that is the basis for the import. The model should have been imported (e.g. from ``app``/models).
   
``import_type``
   This should be exactly the same as the ``label`` that has been specified in the ``uploads`` list
   given with the corresponding listview. In this case that would be the ``PersonListView``.
   That listview provides the specification of ``uploads`` as shown below.


   .. code-block:: python
      :linenos:
   
      class PersonListView(BasicList):
          """Search and list instances of Person"""

          model = Person
          uploads = [dict(title="person_excel", label="Person (Excel)",
                          url="person_import", type="multiple", 
                          msg="Select one or more Excels with Person definitions")
              ]

   Note that both the ``import_type`` in the ``PersonImport`` and the ``title`` in the ``uploads`` list of ``PersonListview`` 
   both have the value ``person_excel``. That is the name by which the basic app is able to connect the two.

   Note too that the message ``msg`` within the ``uploads`` definition is automatically extended with the 
   list of **Fields** that are available for import. This uses the ``specification`` file (of model ``Person`` in this case)
   to show the names for the fields that do not have ``readonly`` specified.
   

Methods
-------

All the methods available with Django's regular ``View`` can be used. The class ``BasicList`` adds a few methods itself.
Please note that methods from the list below only need to be used, when a customized handling of uploading is required.
That is to say, when the ``specification`` as provided with the model is not sufficient to handle the uploading.

``add_row()``
   Handle non-automatic addition of one row

``add_rows()``
   Handle non-automatic addition of all the rows

``after_new()``
   This method allows one to take action just after a new instance has been created.
   When a ``Person`` is created from an import action, for instance, its scope must be set to ``all`` 
   (as opposed to the default ``internal``).

   .. code-block:: python
      :linenos:
   
      def after_new(self, instance, oRow):
          """Add to an instance after its creation"""

          oErr = ErrHandle()
          try:
              # This has been added by importing, so its ItemScope must be 'all'
              itemscope = ItemScope.get_scope("all")
              instance.scope = itemscope
              instance.save()
          except:
              msg = oErr.get_error_message()
              oErr.DoError("after_new")
          return instance

``after_upload()``
   Anything that should be done after the uploading has finished

``before__upload()``
   Anything that should be done before the uploading begins


