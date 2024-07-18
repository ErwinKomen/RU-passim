.. _basicapp:

The 'basic' app
===============

The ``basic`` app can be downloaded from the GitHub 
`Passim basic <https://github.com/ErwinKomen/RU-passim/tree/master/passim/passim/basic>`_ page.

Contents of the app
-------------------

The ``basic`` app makes three basic views available:

  :ref:`BasicList <basiclist>` view - built on Django's ``ListView``, comes with its own default template

  :ref:`BasicDetails <basicdetails>` view - built on Django's ``DetailView``, comes with its own default templates (one for the edit part and one for the overal details)

  :ref:`BasicPart <basicpart>` view - extends Django's ``View``, without any default template (this is mainly used for Ajax POST communication)

The ``basic`` app provides a few more things that might come in handy:

  :ref:`Custom <basiccustom>` model - an add-in, part of a system to facilitate easy automatic listview Excel downloads

  ``ErrHandle`` model - provides a standard way to deal with errors and provide log information (server level)
    This is meant to be used in Python's ``try: except:`` blocks

Files and folders
-----------------
The top directory of the ``basic`` *app* should be placed next to other apps in your Django application.
The sources consist of the following folders and files::

  basic
    migrations
    static
      basic
        css
          basic.css
          clippy.png            # for 'stable_url'
          font-awesome.min.css  # listview sorting symbols
        fonts
        scripts
          basic.js
          html2canvas.js
          htmlsvg2canvas.js
    templates
      basic
        basic_details.html
        basic_edit.html
        basic_list.html
        basic_row.html
        filter_help.html
        xlsx_symbol.html
    __init__.py
    admin.py
    apps.py
    forms.py
    models.py
    tests.py
    utils.py
    views.py
    widgets.py                  # Rangeslider widget
    
Settings
--------
Like any other django app, the ``basic`` app too needs to be added to the installed apps in ``settings.py``.
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

        # Add these to make use of 'basic'
        'django_select2',
        'yourapplication.basic',

        # Add your apps here to enable them
        'yourapplication.main',
    ]

.. _basicapi:

API
--------

.. automodule:: passim.basic.views
   :members:

.. _basiccustomapi:

.. automodule:: passim.basic.models
   :members:

