Basic Details View
==================

The Passim Utilities allow defining a generic details view with the following characteristics:

1. Separate 'DetailsView' and 'EditView' classes need to be defined in ``views.py``
2. The 'DetailsView' class must derive from the 'EditView' one (see below)
3. No template needs to be specified neither for the Details nor for the Edit view: two generic templates are used (``generic_details.html``, ``generic_edit.html``)

The following sections describe how to write the EditView and the DetailsView.
Note that the *name* for these views in ``urls.py`` needs to use the same ``basic_name`` as used for the BasicListView.

EditView
--------

The name of the EditView in ``urls.py`` must be like ``author_edit``, if ``author`` is the ``basic_name`` (in BasicListView).
If the ``basic_name`` is not the same as the name of the model, then it needs to be specified.

Here is an example of an EditView:

.. code-block:: python
   :linenos:

   class EqualGoldEdit(BasicDetails):
      model = EqualGold
      mForm = SuperSermonGoldForm
      prefix = 'ssg'
      title = "Super Sermon Gold"
      rtype = "json"   
      mainitems = []
      is_basic = True      

      def add_to_context(self, context, instance):
         """Add to the existing context"""

         # Define the main items to show and edit
         context['mainitems'] = [
            {'type': 'plain', 'label': "Author:",      'value': instance.author, 
             'field_key': 'author', 'field_ta': 'authorname', 'key_ta': 'author-key'},
            {'type': 'plain', 'label': "Number:",      'value': instance.number},
            {'type': 'plain', 'label': "Passim Code:", 'value': instance.code}
            ]
         # Return the context we have made
         return context
      
*Attributes*
      
The EditView derives from the class ``BasicDetails``. A lot is defined generically because of the flag **is_basic** that is set to ``True``.
In fact, there are but a few things that need to be specified for the EditView:

   ``model`` - the name of the model class that this edit view is based on
   
   ``mForm`` - the name of the model form class that this edit view uses (define this in ``forms.py``)
   
   ``prefix`` - the prefix that is used to show and identify elements of the form
   
   ``title`` - the verbose name for this item. This can differ from the model name. The latter here is 'EqualGold', whereas the verbose name is 'Super Sermon Gold'.
   
   ``rtype`` - this needs to be set to **json** for the EditView
   
   ``mainitems`` - an empty array that is specified fully in ``add_to_context()``
   
   ``is_basic`` - obligatory for the EditView and the DetailsView: must be set to ``True``
   
*Methods*

The EditView must have an ``add_to_context()`` method, as shown in the example above.
The ``mainitems`` list in the context contains one object for each field that needs to be displayed.
Each description has at least values for ``type``, ``label`` and ``value``.
The descriptions for the user-editable fields should have values for at least ``field_key``.

Here is a short description of the field-description object:

================= ==========================================================================
key               meaning
================= ==========================================================================
``*type``         normally 'plain'. Alternatives: ``bold``, ``line``, ``safe``, ``safeline``
``*label``        the label shown in the details view for this item
``*value``        the value to be displayed (use ``instance`` to derive it)
``*link``         the URL that the user can link to from this value
``[field_key]``   the name of the form field for this item
``[field_ta]``    the name of the typeahead form field for this item
``[key_ta]``      the 'key' used for typeahead (CSS class name, e.g. "author-key")
``[field_list]``  the name of the select2 form field (multi-valuable)
================= ==========================================================================


Note that the ``add_to_context()`` method may also be used to define deviating values for ``afterdelurl`` and ``afternewurl``.

DetailsView
-----------

The name of the DetailsView in ``urls.py`` must be like ``author_details``, if ``author`` is the ``basic_name`` (in BasicListView).
If the ``basic_name`` is not the same as the name of the model, then it needs to be specified.

Here is an example of a DetailsView:

.. code-block:: python
   :linenos:

   class EqualGoldDetails(EqualGoldEdit):
      rtype = "html"

      def add_to_context(self, context, instance):
         """Add to the existing context"""

         # Start by executing the standard handling
         super(EqualGoldDetails, self).add_to_context(context, instance)

         context['sections'] = []
         
         related_objects = []

         context['related_objects'] = related_objects
         # Return the context we have made
         return context

*Attributes*
         
The details view class is based on the EditView class. It is from that class that it inherits the ``model``, the ``mForm``, the prefix, the title and so forth.
What remains to be specified for the DetailsView is that ``rtype`` parameter: that should be set to *html*.

*Methods*

In terms of *methods*, the DetailsView is not obliged to specify anything.
It already inherits the ``mainitems`` from the EditView.
However, the DetailsView usually contains more information than just the 'basic' fields of a model.
The generic details view allows specifying two additional matters:

1. ``sections``: Sets of object details that are hidden by default, but appear when pressing a button
2. ``related_objects``: listviews of objects that link with it.
