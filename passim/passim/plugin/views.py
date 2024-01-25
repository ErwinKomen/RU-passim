""" Passim-tailored version of dashboard
"""
from django.shortcuts import render
import re

from passim.plugin.forms import BoardForm


def sermonboard(request):
    """Renders the Sermon Board templat."""

    # Specify the template
    template_name = 'plugin/sermonboard.html'
    boardForm = BoardForm()
    context = dict(title="SermonBoard", boardForm=boardForm)
    # context = get_application_context(request, context)

    return render(request,template_name, context)

