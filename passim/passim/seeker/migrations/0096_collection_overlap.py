# -*- coding: utf-8 -*-
# Generated by Django 1.11.17 on 2020-08-12 12:03
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('seeker', '0095_equalgold_hccount'),
    ]

    operations = [
        migrations.AddField(
            model_name='collection',
            name='overlap',
            field=models.IntegerField(default=0, verbose_name='Overlap with manuscript'),
        ),
    ]