# Configuration file for the Sphinx documentation builder.
#
# This file only contains a selection of the most common options. For a full
# list see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

# -- Path setup --------------------------------------------------------------

# If extensions (or modules to document with autodoc) are in another directory,
# add these directories to sys.path here. If the directory is relative to the
# documentation root, use os.path.abspath to make it absolute, like shown here.
#
# import os
# import sys
# sys.path.insert(0, os.path.abspath('.'))
import os
import sys
root_path = 'd:/data files/vs2010/projects/ru-passim/passim'
sys.path.insert(0, os.path.abspath(root_path))
# sys.path.insert(0, os.path.abspath('d:/data files/vs2010/projects/ru-passim/passim/passim'))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "passim.settings")
os.chdir(root_path)

# Setup Django
import django
django.setup()


# -- Project information -----------------------------------------------------

project = 'BasicUtils'
copyright = '2020-2024, Erwin R. Komen'
author = 'Erwin R. Komen'

# The full version, including alpha/beta/rc tags
release = '1.0'


# -- General configuration ---------------------------------------------------

# Add any Sphinx extension module names here, as strings. They can be
# extensions coming with Sphinx (named 'sphinx.ext.*') or your custom
# ones.
extensions = [ 'sphinx.ext.todo', 'sphinx.ext.viewcode', 'sphinx.ext.autodoc'
]

# Add any paths that contain templates here, relative to this directory.
templates_path = ['_templates']

# List of patterns, relative to source directory, that match files and
# directories to ignore when looking for source files.
# This pattern also affects html_static_path and html_extra_path.
exclude_patterns = []


# -- Options for HTML output -------------------------------------------------

# The theme to use for HTML and HTML Help pages.  See the documentation for
# a list of builtin themes.
# html_theme = 'alabaster'
# html_theme = 'nature'
html_theme = 'default'
# html_theme = "sphinxdoc"
html_theme_options = {'body_max_width': None}

# Add any paths that contain custom static files (such as style sheets) here,
# relative to this directory. They are copied after the builtin static files,
# so a file named "default.css" will overwrite the builtin "default.css".
html_static_path = ['_static']
