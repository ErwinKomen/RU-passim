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


# Import from CESAR as a whole
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
