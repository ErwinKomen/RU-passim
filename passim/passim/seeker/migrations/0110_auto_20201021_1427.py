# -*- coding: utf-8 -*-
# Generated by Django 1.11.17 on 2020-10-21 12:27
from __future__ import unicode_literals

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('seeker', '0109_bibverse'),
    ]

    operations = [
        migrations.AlterField(
            model_name='sermondescr',
            name='manu',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='manusermons', to='seeker.Manuscript'),
        ),
    ]
