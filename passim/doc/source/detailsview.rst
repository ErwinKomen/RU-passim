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

   class EqualGoldEdit(PassimDetails):
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
            {'type': 'plain', 'label': "Author:",      'value': instance.author, 'field_key': 'author', 'field_ta': 'authorname', 'key_ta': 'author-key'},
            {'type': 'plain', 'label': "Number:",      'value': instance.number},
            {'type': 'plain', 'label': "Passim Code:", 'value': instance.code}
            ]
         # Return the context we have made
         return context
      
*Attributes*
      
The EditView derives from the class ``PassimDetails``. A lot is defined generically because of the flag **is_basic** that is set to ``True``.
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

Note that the ``add_to_context()`` method may also be used to define deviating values for ``afterdelurl`` and ``afternewurl``.

DetailsView
-----------   