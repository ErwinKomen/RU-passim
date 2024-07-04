Basic Details View
==================

The Passim Utilities allow defining a generic details view with the following characteristics:

1. Separate 'xxxDetailsView' and 'xxxEditView' classes need to be defined in ``views.py``
2. The 'xxxDetailsView' class must derive from the 'xxxEditView' one (see below)
3. No template needs to be specified neither for the Details nor for the Edit view: two generic templates are used (``basic_details.html``, ``basic_edit.html``) internally

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
``[link]``        the URL that the user can link to from this value (provided type=``bold``)
``[title]``       the popup text displayed when hovering over
``[multiple]``    boolean that indicates whether this field may contain multiple values
``[align]``       the alignment of the ``<td>``
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

*Sections*

As for the ``sections``: TODO explain

*Related Objects*

The ``related_objects`` is a list of objects. Each related object boils down to a **table** that is shown with a list of objects.
A related object can have the following fields:

================= ============================================================================
key               meaning
================= ============================================================================
``*title``        a title of this table shown to the user
``*columns``      a list of names (strings) for each of the columns to be shown
``*rel_list``     a list of related item objects (the rows in the table to be shown)
``*prefix``       short prefix that uniquely identifies this related object
``[use_counter]`` boolean: True means that each line in the table must have a number
``[editable]``    boolean: True means that add/edit/delete options are added
================= ============================================================================

Note that when ``editable`` is set to True, and the user has editing rights, several items are added.
Each row gets an 'edit' button and a 'delete' button. The table as a whole gets an additional row that forms the 'add' button.
The add facility makes use of a hidden empty row that is added.

Each item in the ``rel_list`` is an object that can have the following fields:

================= ============================================================================
key               meaning
================= ============================================================================
``*value``        the HTML of what is shown in this row
``[title]``       a popup title shown when a user hovers over this row
``[link]``        a link (URL) to which the user is directed when pressing this row
================= ============================================================================


Having a many-to-one element
----------------------------

Suppose there is a details view and an edit view for an item of type ``Library``.
Suppose, then, that there is an item ``Book`` that links with a foreign key to Library.
(It will have a field ``name`` for the name of the book and ``library`` linking to the ``Library``.)
There is a many-to-one relation between Book and Library.
How can the 'books' be added to the details view of ``Library``?
Here are the steps:

#. Forms

   (#) Adapt the ``LibraryForm``: 
   
       * Add an element ``booklist`` to the form
       * Initialize the `queryset` and `initial` values of ``booklist`` in method ``__init__()``

   (#) Make sure to have a form ``LibraryBookForm``:
       
       * Make it have a field like ``newname`` where the user can add a new name
       * Have the property `required` set to `False`

#. Model: process ``Library``

   (#) Add a method like ``get__book__markdown()`` that creates a HTML string to show the contents of a book.

#. Views

   (#) There needs to be a formset that provides a set of forms linking ``Library`` with ``Book``
   (#) Method ``add_to_context()``: Make sure the Books are mentioned in ``context['mainitems']``
   (#) Method ``process_formset()``: make sure the form's ``newname`` is handled properly
   (#) Method ``after_save()``:  make sure the procedure ``adapt_m2o()`` is called correctly

Having a many-to-many element
-----------------------------

Continuing the example of a ``Library`` with ``Book`` items connected to it, suppose this library contains
books from two or three (or more) different projects. There's a model ``Project``.
Each book may be part of one or more projects. This means that here should be a many-to-many relation
between ``Book`` and ``Project``. To provide that link, we have a table ``BookProject`` that has a foreign key to a ``Book`` and one to a ``Project``.
To complicate it a bit more, suppose we want to be able to define the 'history' of a particular book in a particular project.
This history field could contain notes as to when the book became part of the project and things like that.
This means we now have a field ``status`` added to the ``BookProject`` model:

.. code-block:: python
   :linenos:

   class BookProject(models.Model):
      """Relation between a Book and a Project"""

      # [1] The link is between a Book instance ...
      book = models.ForeignKey(Book, related_name="book_proj", on_delete=models.CASCADE)
      # [1] ...and a project instance
      project = models.ForeignKey(Project, related_name="book_proj", on_delete=models.CASCADE)
      # [0-1] And a status: any text describing the status
      status = models.TextField(null=True, empty=True)

The question now is: how can we facilitate a (select2-based) interface in the details view to add a book to a particular project or to delete that relation?
Here are the steps:

#. Forms

   (#) Adapt the ``BookForm``, so that it shows _existing_ book-project combinations and allows deleting these: 
   
       * Add an element ``booklist`` to the form. This booklist should make use of a Select2 widget of class ``ModelSelect2MultipleWidget``
       * Initialize the `queryset` and `initial` values of ``booklist`` in method ``__init__()``

   (#) Make sure to have a form ``BookProjectForm``:
       
       * Its Meta-defined required fields are: ``fields = ['book', 'project']``
       * Add a 'free' ``ModelChoiceField`` field ``project__new`` to it. The ``project_new`` field should make use of a Select2 widget of class ``ModelSelect2Widget`` (i.e. **not** ``Multiple``). This form field is used to select one single project in a select2 dropdown list.
       * Make it have a field like ``newstatus`` where the user can add text for the status field
       * Have the property `required` set to `False`

#. Model: process ``BookProject``

   (#) Add a method like ``get__bookproject__markdown()`` that creates a HTML string to show the details of a book-project combination (including possibly status).

#. Views

   (#) There needs to be a formset that provides a set of forms linking ``Project`` with ``Book``
   (#) Method ``add_to_context()``: Make sure the Books are mentioned in ``context['mainitems']``
   (#) Method ``process_formset()``: make sure the form's ``newstatus`` and ``project__new`` are handled properly. The ``newstatus`` information should be put into the field ``status``, while the ``project__new`` information should be used to select the correct Project.
   (#) Method ``after_save()``:  make sure the procedure ``adapt_m2m()`` is called correctly


History button
--------------

The ``basic`` details view provides a method to show the edit history in a standardized way. 
If activated, the method adds a 'History' button to the details view.

#. Activation

#. Notes



