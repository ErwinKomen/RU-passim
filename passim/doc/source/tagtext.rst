The 'tagtext' app
=================

Folders
-------
At the moment 'tagtext' is available as a django 'app'. It needs to be loaded from the Github pages.
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
        'lentensermons.tagtext',
        'lentensermons.seeker',
    ]

