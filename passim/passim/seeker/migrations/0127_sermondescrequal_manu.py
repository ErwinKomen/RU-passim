# -*- coding: utf-8 -*-
# Generated by Django 1.11.17 on 2021-02-03 09:33
from __future__ import unicode_literals

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('seeker', '0126_auto_20210121_1532'),
    ]

    operations = [
        migrations.AddField(
            model_name='sermondescrequal',
            name='manu',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='sermondescr_super', to='seeker.Manuscript'),
        ),
    ]
