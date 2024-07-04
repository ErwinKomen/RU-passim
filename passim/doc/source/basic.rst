The 'basic' app
===============

The ``basic`` app makes three basic views available:

  ``BasicList`` view - built on Django's ``ListView``, comes with its own default template

  ``BasicDetails`` view - built on Django's ``DetailView``, comes with its own default templates (one for the edit part and one for the overal details)

  ``BasicPart`` view - extends Django's ``View``, without any default template (this is mainly used for Ajax POST communication)

The ``basic`` app provides a few more things that might come in handy:

  ``Custom`` model - an add-in, part of a system to facilitate easy automatic listview Excel downloads

*To be continued*
