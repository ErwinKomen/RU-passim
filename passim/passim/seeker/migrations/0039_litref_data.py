# -*- coding: utf-8 -*-
# Generated by Django 1.11.17 on 2019-08-26 09:37
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('seeker', '0038_auto_20190822_1252'),
    ]

    operations = [
        migrations.AddField(
            model_name='litref',
            name='data',
            field=models.TextField(blank=True, default='', verbose_name='JSON data'),
        ),
    ]
