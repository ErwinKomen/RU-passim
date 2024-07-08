Basic listview downloads
========================

The ``BasicList`` view comes with an automatic button for Excel downloading, provided a few criteria are met.

  ``Custom`` - the listview's model must use ``Custom`` as an add-in

  ``specification`` - listview's model must have a ``specification`` supplied


The 'Custom' add-in
-------------------

The ``Custom`` add-in can be used quite by specifying it next to the ``models.Model`` in the model class code.
The code below shows how to get a model class started with ``Custom``.

.. code-block:: python
    :linenos:

    # ... other imports
    from passim.basic.models import Custom

    # ... other code

    class Author(models.Model, Custom):
        """This illustrates an Author class with help from Custom"""
        pass

The download 'specification'
----------------------------

The model should have an additional model variable ``specification``, which defines a list of objects.
The fields of the objects in the ``specification`` list have the following meaning:

================= ============================================================================
key               meaning
================= ============================================================================
``*name``         the name of the column used in Excel
``*type``         use ``field`` for simple values specified in the model, otherwise ``func``
``*path``         for type ``field`` this is the name of the model's field
                  for type ``func`` this is the ``path`` used in function ``custom_get()``
``[readonly]``    if ``True``, this means that uploading may not take place for this items
================= ============================================================================

A download example
------------------

Here is an example of how downloading for a listview is specified.
Note that the downloading specification is entirely done in the model code.


.. code-block:: python
   :linenos:
   
   class Author(models.Model, Custom):
      """Search and list authors"""
	    
        """We have a set of authors that are the 'golden' standard"""

        # [1] Name of the author
        name = models.CharField("Name", max_length=LONG_STRING)
        # [0-1] Possibly add the Gryson abbreviation for the author
        abbr = models.CharField("Abbreviation", null=True, blank=True, max_length=LONG_STRING)
        # [0-1] Author number: automatically consecutively filled when added to EqualGold
        number = models.IntegerField("Number", null=True, blank=True)

        # Scheme for downloading
        specification = [
            {'name': 'Name',            'type': 'field', 'path': 'name',       'readonly': True},
            {'name': 'Abbreviation',    'type': 'field', 'path': 'abbr'         },
            {'name': 'Number',          'type': 'field', 'path': 'number'       },
            {'name': 'Contributions',   'type': 'func',  'path': 'contributions'},
            ]

        def custom_get(self, path, **kwargs):
            sBack = ""
            oErr = ErrHandle()
            try:
                # Use if - elif - else to check the *path* defined in *specification*
                if path == "contributions":
                    # The contributions are fetched via a model method
                    sBack = self.get_contributions()
            except:
                msg = oErr.get_error_message()
                oErr.DoError("Author/custom_get")
            return sBack


The above specification says that the Excel should contain columns *Name*, *Abbreviation* and *Number*,
and that these columns should contain the values from the fields ``name``, ``abbr`` and ``number``. 
By virtue of the ``func`` type path, there also is a column named *Contributions*, and the values of cells
in that column are calculated via ``custom_get()``, which, in turn, makes a call to the model's function
``get_contributions()``. The code of that function is not shown in the example.

