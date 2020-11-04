from django.contrib import admin
from passim.enrich.models import *

class SpeakerAdmin(admin.ModelAdmin):
    fields = ['name', 'gender']
    list_display = ['name', 'gender']



# Main program models
admin.site.register(Speaker, SpeakerAdmin)
admin.site.register(Sentence)
admin.site.register(Testunit)
admin.site.register(Testset)
admin.site.register(TestsetUnit)
