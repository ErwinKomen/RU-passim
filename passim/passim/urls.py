"""
Definition of urls for passim.
"""

from datetime import datetime
from django.contrib.auth.decorators import login_required, permission_required
from django.conf.urls import include, url
from django.contrib import admin
import django.contrib.auth.views

import passim.seeker.forms
import passim.seeker.views
from passim.seeker.views import *

# Import from PASSIM as a whole
from passim.settings import APP_PREFIX

# Other Django stuff
from django.core import urlresolvers
from django.shortcuts import redirect
from django.core.urlresolvers import reverse, reverse_lazy
from django.views.generic.base import RedirectView

admin.autodiscover()


# Set admin stie information
admin.site.site_header = "Patristic Sermons in the Middle Ages"
admin.site.site_title = "passim Admin"

pfx = APP_PREFIX

urlpatterns = [
    # Examples:
    url(r'^$', passim.seeker.views.home, name='home'),
    url(r'^contact$', passim.seeker.views.contact, name='contact'),
    url(r'^about', passim.seeker.views.about, name='about'),
    url(r'^short', passim.seeker.views.about, name='short'),
    url(r'^nlogin', passim.seeker.views.nlogin, name='nlogin'),

    url(r'^sync/entry/$', passim.seeker.views.sync_entry, name='entries_json'),
    url(r'^sync/start/$', passim.seeker.views.sync_start, name='sync_start'),
    url(r'^sync/progress/$', passim.seeker.views.sync_progress, name='sync_progress'),


    url(r'^search/sermon', passim.seeker.views.search_sermon, name='search_sermon'),
    url(r'^search/manuscript', ManuscriptListView.as_view(), name='search_manuscript'),
    url(r'^search/collection', passim.seeker.views.search_collection, name='search_collection'),
    url(r'^search/library', LibraryListView.as_view(), name='library_search'),
    url(r'^search/author', AuthorListView.as_view(), name='author_search'),

    url(r'^libraries/download', LibraryListDownload.as_view(), name='library_results'),
    url(r'^authors/download', AuthorListDownload.as_view(), name='author_results'),

    url(r'^manuscript/view/(?P<pk>\d+)/$', ManuscriptDetailsView.as_view(), name='manuscript_view'),
    url(r'^sermon/view(?:/(?P<pk>\d+))?/$', SermonDetailsView.as_view(), name='sermon_view'),

    url(r'^api/countries/$', passim.seeker.views.get_countries, name='api_countries'),
    url(r'^api/cities/$', passim.seeker.views.get_cities, name='api_cities'),
    url(r'^api/libraries/$', passim.seeker.views.get_libraries, name='api_libraries'),
    url(r'^api/origins/$', passim.seeker.views.get_origins, name='api_origins'),
    url(r'^api/manuscripts/$', passim.seeker.views.get_manuscripts, name='api_manuscripts'),
    url(r'^api/authors/list/$', passim.seeker.views.get_authors, name='api_authors'),
    url(r'^api/nicknames/$', passim.seeker.views.get_nicknames, name='api_nicknames'),

    url(r'^api/import/authors/$', passim.seeker.views.import_authors, name='import_authors'),
    url(r'^api/import/ecodex/$', passim.seeker.views.import_ecodex, name='import_ecodex'),
    url(r'^api/import/ead/$', passim.seeker.views.import_ead, name='import_ead'),

    url(r'^definitions$', RedirectView.as_view(url='/'+pfx+'admin/'), name='definitions'),
    url(r'^signup/$', passim.seeker.views.signup, name='signup'),

    url(r'^login/$',
        django.contrib.auth.views.login,
        {
            'template_name': 'login.html',
            'authentication_form': passim.seeker.forms.BootstrapAuthenticationForm,
            'extra_context':
            {
                'title': 'Log in',
                'year': datetime.now().year,
            }
        },
        name='login'),
    url(r'^logout$',
        django.contrib.auth.views.logout,
        {
            'next_page':  reverse_lazy('home'),
        },
        name='logout'),

    # Uncomment the admin/doc line below to enable admin documentation:
    url(r'^admin/doc/', include('django.contrib.admindocs.urls')),

    # Uncomment the next line to enable the admin:
    url(r'^admin/', include(admin.site.urls), name='admin_base'),
]
