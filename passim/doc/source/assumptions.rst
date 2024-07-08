Introduction
============

The 'tagtext' app
-----------------
The use of the ``tagtext`` app makes some assumptions.
It is best to check the ``tagtext`` documentation further down.

The 'basic' app
---------------
The ``basic`` app can best be included by source. This facilitates easier debugging. It also provides an opportunity to extend it application-wide.
The app can be copied and pasted from one of the web application that uses it.
It is recommended that one takes the Passim application's variant from the developer's 
`Github page <https://github.com/ErwinKomen/RU-passim/blob/master/passim/passim/basic>`_ as a starting point.

Publically viewable web applications that partly or completely make use of the ``basic`` app are: 

.. table::
	:widths: auto
	:align: left

	================= ==================================================== =================================
	App               Name                                                 Section
	================= ==================================================== =================================
	``RU-cesar``      Corpus editor for syntactically annotated resources  ``Tablet`` (=``Doc``), ``Simple``
	``RU-collbank``   Collection bank                                      ``VloItem``, ``SourceInfo``
	``RU-iberian``    Iberian saints                                       ``Upload``
	``RU-lenten``     Lenten sermons                                       (all)
	``RU-lilac``      Living law web application                           (all)
	``RU-passim``     Patristic sermons                                    (all)
	``RU-stalla``     Medieval choir stalls                                ``Werkstuk``
	================= ==================================================== =================================



The BasicListView
--------------------
This listview is part of the ``basic`` app (see above).
There are a few assumptions for using the ``BasicListView``:

1. The class using it must be inside ``views.py``
2. The class must define a few obligatory attributes
3. The template's default location is ``seeker/basic_list.html``
4. There must be a **DetailsView** using the same ``basic_name`` as the listview

