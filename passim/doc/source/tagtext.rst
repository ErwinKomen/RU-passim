.. _tagtextapp:

The 'tagtext' app
=================

The 'tagtext' app can be downloaded from the GitHub 
`LentenSermons tagtext <https://github.com/ErwinKomen/RU-lenten/tree/master/lenten/lentensermons/tagtext>`_ page.

Basic work
----------
The 'tagtext' app allows transforming standard ``TextField`` fields of models into fields that contain a mixture of text and tags.
The user can add text intermingled with tags in this way::

  This line consists of @a new tag@ that will become available in the future
  
New tags are inserted by starting and finishing text with an ampersand.
Existing tags can be chosen from a list of available tags after the user enters the ampersand @ and at least one other letter.
Tags that have been inserted will in the future appear as a gray-backgrounded piece of text (which I cannot show here).

Files and folders
-----------------
At the moment 'tagtext' is available as a django 'app'.
The sources consist of the following folders and files::

  tagtext
    migrations
    static
      tagtext
        css
          tagtextarea.css
          tribute.css
        js
          tagtextarea.js
          tribute.js
    templates
      tagtext
        tagtextarea.html
    __init__.py
    admin.py
    apps.py
    forms.py
    models.py
    tests.py
    views.py
    
Settings
--------
Like any other django app, the ``tagtext`` app too needs to be added to the installed apps in ``settings.py``.
The ``INSTALLED_APPS`` variable in settings might come to look like this:

.. code-block:: python

    INSTALLED_APPS = [
        'django.contrib.admin',
        'django.contrib.auth',
        'django.contrib.contenttypes',
        'django.contrib.sessions',
        'django.contrib.messages',
        'django.contrib.staticfiles',
        # Add your apps here to enable them
        'django_select2',
        'lentensermons.basic',
        'lentensermons.tagtext',    # Note: prepend the main application name before 'tagtext' 
        'lentensermons.seeker',
    ]

Models.py
---------
The next changes occur in ``models.py``. 
Changes are needed for any *class* that has field in which textfields need to receive the tagtext abilities.
Such class should not build on ``models.Model``, but on ``tagtext.models.TagtextModel`` instead:

.. code-block:: python

   ...
   from lentensermons import tagtext        # make sure the tagtext app is imported in models.py
   ...

   class SermonCollection(tagtext.models.TagtextModel):

      # [0-1] Identification number assigned by the researcher
      idno = models.CharField("Identification", max_length=MEDIUM_LENGTH, blank=True, null=True)
      # [0-1] Relationship with liturgical texts - use markdown '_' to identify repetative elements
      liturgical = models.TextField("Relationship with liturgical texts", blank=True, null=True)
      
      # --------- MANY-TO-MANY connections ------------------
      # [n-n] Liturgical tags
      liturtags = models.ManyToManyField(TagLiturgical, blank=True, related_name="collection_liturtags")


      mixed_tag_fields = [
            {"textfield": "liturgical",     "m2mfield": "liturtags",    "class": TagLiturgical,   "url": "taglitu_details"}
        ]

The class ``SermonCollection`` builds on ``TagtextModel`` (which in turn is built on ``models.Model``, so it has the standard behaviour).
This example class has one text field where tags may be intermingled with tags: ``liturgical``.
The tagging/text abilities of this otherwise normal textfield are derived this way:

1. Add a ``TagLiturgical`` model (see below) that holds tags
2. Connect this model with ``SermonCollection`` through the definition of a ManyToManyField ``liturtags``
3. Fill in a row in the ``mixed_tag_fields`` list that specifies
   - the textfield ``liturgical``
   - its associated many-to-many-field ``liturtags``
   - the class of the latter ``TagLiturgical``
   - the url-name (from ``urls.py``) to the details view ot that tag

The basics of ``TagLiturgical`` that has been mentioned above are defined this way:

.. code-block:: python

    class TagLiturgical(models.Model):
        """The field 'liturgical' can have [0-n] tag words associated with it"""

        # [1]
        name = models.CharField("Name", max_length=LONG_STRING)

        class Meta:
            verbose_name_plural = "Liturgical Tags"

        def __str__(self):
            return "-" if self == None else  self.name

        def get_url_edit(self):
            url = reverse('admin:seeker_tagliturgical_change', args=[self.id])
            return url

        def get_url_view(self):
            url = reverse('taglitu_details', kwargs={'pk': self.id})
            return url

views.py            
--------
The views.py contains definitions to show the ``TagLiturgical``, but that view does not have anything special having to do with *tagtext*.
What does have some specifics for *tagtext* is the ``CollectionDetailsView``. That view builds on ``PassimDetails`` (a predecessor of ``BasicDetails``).
Here is part of its definition (see the Github repository for more):

.. code-block:: python

    class CollectionDetailsView(PassimDetails):
        model = SermonCollection
        mForm = None
        template_name = 'generic_details.html' 
        prefix = ""
        title = "CollectionDetails"
        rtype = "html"
        mainitems = []
        sections = []

        def add_to_context(self, context, instance):
            # Show the main items of this sermon collection
            context['mainitems'] = [
                {'type': 'plain', 'label': "Identifier (Code):", 'value': instance.idno},
                {'type': 'bold',  'label': "Title:", 'value': instance.title},
                {'type': 'plain', 'label': "Authors:", 'value': instance.get_authors()},
                {'type': 'plain', 'label': "Date of composition:", 'value': "{} ({})".format(instance.datecomp, instance.get_datetype_display()) },
                {'type': 'plain', 'label': "Place of composition:", 'value': instance.place.name },
                {'type': 'plain', 'label': "First edition:", 'value': instance.firstedition },
                {'type': 'plain', 'label': "Number of editions:", 'value': instance.numeditions }

                ]

            context['sections'] = [
                {'name': 'Typology / structure', 'id': 'coll_typology', 'fields': [
                    {'type': 'plain', 'label': "Structure:", 'value': instance.structure },
                    {'type': 'safeline',    'label': "Liturgical relation:", 'value': instance.get_liturgical_display.strip(), 'title': "Relationship with liturgical texts"},
                    {'type': 'safeline',    'label': "Communicative strategy:", 'value': instance.get_communicative_display.strip()},
                    ]},
                {'name': 'General notes', 'id': 'coll_general', 'fields': [
                    {'type': 'safeline',    'label': "Quoted sources:", 'value': instance.get_sources_display.strip()},
                    {'type': 'safeline',    'label': "Exempla:", 'value': instance.get_exempla_display.strip()},
                    {'type': 'safeline',    'label': "Notes:", 'value': instance.get_notes_display.strip()}                ]}
                ]

The details view of the collection has a 'Main' section (defined in ``mainitems``). 
It also has two sections that become available when the user presses a button, e.g. ``Typology / structure``.
That section contains a reference to the ``liturgical`` textfield:

1. It stipulates that this textfield is of type ``safeline``
2. It also says how the value should be shown: by taking the field ``get_liturgical_display`` from the instance, and stripping it

This field ``get_liturgical_display`` is one that the 'tagtext' app adds dynamically to the instance.
It is this value in combination with ``safeline`` that facilitates showing the ``liturgical`` textfield as a combination of text and tags.

Internal
--------
The tagtext TextField fields consist of a stringified json list of objects internally.