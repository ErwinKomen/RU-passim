from django.contrib import admin
from passim.enrich.models import *

# Main program models
admin.site.register(Speaker)
admin.site.register(Sentence)
admin.site.register(Testunit)
admin.site.register(Testset)
admin.site.register(TestsetUnit)
