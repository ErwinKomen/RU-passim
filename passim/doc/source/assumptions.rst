Assumptions
===========

The 'tagtext' app
-----------------
The use of the ``tagtext`` app makes some assumptions.
It is best to check the ``tagtext`` documentation further down.

The 'basic' app
---------------
The ``basic`` app can best be included by source. This facilitates easier debugging. It also provides an opportunity to extend it application-wide.

The BasicListView
--------------------
This listview is part of the ``basic`` app (see above).
There are a few assumptions for using the ``BasicListView``:

1. The class using it must be inside ``views.py``
2. The class must define a few obligatory attributes
3. The template's default location is ``seeker/basic_list.html``
4. There must be a **DetailsView** using the same ``basic_name`` as the listview

