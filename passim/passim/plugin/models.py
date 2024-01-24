"""Models for the PLUGIN app.

This plugin has originally been created by Gleb Schmidt.
"""
from django.db import models
from django.db.models import Q
from django.urls import reverse
from django.utils import timezone
from django.utils.html import mark_safe
from markdown import markdown

import re, copy
import pytz

# From own stuff
from passim.settings import APP_PREFIX, WRITABLE_DIR, TIME_ZONE
from passim.utils import *

LONG_STRING=255
STANDARD_LENGTH=100

# Create your models here.
