# -*- coding: utf-8 -*-
# Generated by Django 1.11.17 on 2020-04-23 11:49
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('seeker', '0060_auto_20200409_0846'),
    ]

    operations = [
        migrations.AddField(
            model_name='sermondescr',
            name='postscriptum',
            field=models.TextField(blank=True, null=True, verbose_name='Postscriptum'),
        ),
        migrations.AddField(
            model_name='sermondescr',
            name='sectiontitle',
            field=models.CharField(blank=True, max_length=255, null=True, verbose_name='Section title'),
        ),
    ]