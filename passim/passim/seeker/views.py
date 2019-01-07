"""
Definition of views for the SEEKER app.
"""

from django.contrib import admin
from django.contrib.auth import login, authenticate
from django.contrib.auth.models import Group
from django.core.urlresolvers import reverse
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.db.models import Q
from django.db.models.functions import Lower
from django.http import HttpRequest, HttpResponse, HttpResponseRedirect
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render, redirect
from django.template.loader import render_to_string
from django.views.generic.detail import DetailView
from django.views.generic.base import RedirectView
from django.views.generic import ListView, View
from datetime import datetime
from time import sleep

from passim.settings import APP_PREFIX
from passim.seeker.forms import SearchCollectionForm, SearchManuscriptForm, SearchSermonForm

import fnmatch
import sys
import base64

def home(request):
    """Renders the home page."""

    assert isinstance(request, HttpRequest)
    # Specify the template
    template_name = 'index.html'
    # Define the initial context
    context =  {'title':'RU-passim','year':datetime.now().year,
            'pfx': APP_PREFIX,'site_url': admin.site.site_url}

    ## Create the list of news-items
    #lstQ = []
    #lstQ.append(Q(status='val'))
    #newsitem_list = NewsItem.objects.filter(*lstQ).order_by('-saved', '-created')
    #context['newsitem_list'] = newsitem_list

    # Render and return the page
    return render(request, template_name, context)

def contact(request):
    """Renders the contact page."""
    assert isinstance(request, HttpRequest)
    return render(
        request,
        'contact.html',
        {
            'title':'Contact',
            'message':'Henk van den Heuvel',
            'year':datetime.now().year,
        }
    )

def more(request):
    """Renders the more page."""
    assert isinstance(request, HttpRequest)
    return render(
        request,
        'more.html',
        {
            'title':'More',
            'year':datetime.now().year,
        }
    )

def about(request):
    """Renders the about page."""
    assert isinstance(request, HttpRequest)
    return render(
        request,
        'about.html',
        {
            'title':'About',
            'message':'Radboud University passim utility.',
            'year':datetime.now().year,
        }
    )

def short(request):
    """Renders the page with the short instructions."""

    assert isinstance(request, HttpRequest)
    template = 'short.html'
    context = {'title': 'Short overview',
               'message': 'Radboud University passim short intro',
               'year': datetime.now().year}
    return render(request, template, context)

def nlogin(request):
    """Renders the not-logged-in page."""
    assert isinstance(request, HttpRequest)
    context =  {    'title':'Not logged in', 
                    'message':'Radboud University passim utility.',
                    'year':datetime.now().year,}
    return render(request,'nlogin.html', context)

def search_sermon(request):
    """Search for a sermon"""

    # Set defaults
    template_name = "seeker/sermon.html"

    # Get a link to a form
    searchForm = SearchSermonForm()

    # Other initialisations
    currentuser = request.user
    authenticated = currentuser.is_authenticated()

    # Create context and add to it
    context = dict(title="Search sermon",
                   authenticated=authenticated,
                   searchForm=searchForm)


    # Create and show the result
    return render(request, template_name, context)


def search_manuscript(request):
    """Search for a manuscript"""

    # Set defaults
    template_name = "seeker/manuscript.html"

    # Get a link to a form
    searchForm = SearchManuscriptForm()

    # Other initialisations
    currentuser = request.user
    authenticated = currentuser.is_authenticated()

    # Create context and add to it
    context = dict(title="Search manuscript",
                   authenticated=authenticated,
                   searchForm=searchForm)


    # Create and show the result
    return render(request, template_name, context)


def search_collection(request):
    """Search for a collection"""

    # Set defaults
    template_name = "seeker/collection.html"

    # Get a link to a form
    searchForm = SearchCollectionForm()

    # Other initialisations
    currentuser = request.user
    authenticated = currentuser.is_authenticated()

    # Create context and add to it
    context = dict(title="Search collection",
                   authenticated=authenticated,
                   searchForm=searchForm)


    # Create and show the result
    return render(request, template_name, context)


def signup(request):
    """Provide basic sign up and validation of it """

    if request.method == 'POST':
        form = SignUpForm(request.POST)
        if form.is_valid():
            # Save the form
            form.save()
            # Create the user
            username = form.cleaned_data.get('username')
            raw_password = form.cleaned_data.get('password1')
            # also make sure that the user gets into the STAFF,
            #      otherwise he/she may not see the admin pages
            user = authenticate(username=username, 
                                password=raw_password,
                                is_staff=True)
            user.is_staff = True
            user.save()
            # Add user to the "RegistryUser" group
            gQs = Group.objects.filter(name="seeker_user")
            if gQs.count() > 0:
                g = gQs[0]
                g.user_set.add(user)
            # Log in as the user
            login(request, user)
            return redirect('home')
    else:
        form = SignUpForm()
    return render(request, 'signup.html', {'form': form})
