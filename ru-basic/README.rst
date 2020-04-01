=====
basic
=====

Basic is a Django app that offers fast and flexible development of list views and detail views. 
The app is used in several applications made at the Radboud University (RU) Nijmegen.

Detailed documentation is in the "docs" directory.

Quick start
-----------

1. Add "basic" to your INSTALLED_APPS setting like this::

    INSTALLED_APPS = [
        ...
        'basic',
    ]

   N.B: make sure that the installed apps are in the correct order. Basic comes after the other apps, but before your user apps.
   
2. Make sure to copy the static files from the basic app to your static collect directory.
   Copy this directory::

    basic/static/basic
    
