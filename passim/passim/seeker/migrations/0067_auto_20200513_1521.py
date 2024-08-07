# -*- coding: utf-8 -*-
# Generated by Django 1.11.17 on 2020-05-13 13:21
from __future__ import unicode_literals

from django.db import migrations, models
import json

def edit_actions(apps, schema_editor):
    Action = apps.get_model('seeker', 'Action')
    SermonDescrEqual = apps.get_model('seeker', 'SermonDescrEqual')
    for obj in Action.objects.all():
        details = obj.details
        if details != None and details != "":
            oDetails = json.loads(details)
            if 'id' in oDetails:
                id_value = oDetails['id']
                obj.itemid = id_value
                # Save the result
                obj.save()


class Migration(migrations.Migration):

    dependencies = [
        ('seeker', '0066_auto_20200507_1654'),
    ]

    operations = [
        migrations.AddField(
            model_name='action',
            name='itemid',
            field=models.IntegerField(default=0, verbose_name='Item id'),
        ),
        migrations.AddField(
            model_name='action',
            name='linkid',
            field=models.IntegerField(blank=True, null=True, verbose_name='Link id'),
        ),
        migrations.AddField(
            model_name='action',
            name='linktype',
            field=models.CharField(blank=True, max_length=200, null=True, verbose_name='Link type'),
        ),
        migrations.RunPython(edit_actions)

    ]
