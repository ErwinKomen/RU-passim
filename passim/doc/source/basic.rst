The 'basic' app
===============

The ``basic`` app makes three basic views available:

  :ref:`BasicList <basiclist>` view - built on Django's ``ListView``, comes with its own default template

  :ref:`BasicDetails <basicdetails>` view - built on Django's ``DetailView``, comes with its own default templates (one for the edit part and one for the overal details)

  :ref:`BasicPart <basicpart>` view - extends Django's ``View``, without any default template (this is mainly used for Ajax POST communication)

The ``basic`` app provides a few more things that might come in handy:

  :ref:`Custom <basiccustom>` model - an add-in, part of a system to facilitate easy automatic listview Excel downloads

  ``ErrHandle`` model - provides a standard way to deal with errors and provide log information (server level)
    This is meant to be used in Python's ``try: except:`` blocks

*To be continued*
