# -*- coding: utf-8 -*-
# Generated by Django 1.11.17 on 2021-02-03 14:43
from __future__ import unicode_literals

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('seeker', '0132_auto_20210203_1349'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='manuscriptcorpusmanu',
            name='corpus',
        ),
        migrations.RemoveField(
            model_name='manuscriptcorpusmanu',
            name='manu',
        ),
        migrations.RemoveField(
            model_name='manuscriptcorpus',
            name='count',
        ),
        migrations.AddField(
            model_name='manuscriptcorpus',
            name='manu',
            field=models.ForeignKey(default=1, on_delete=django.db.models.deletion.CASCADE, related_name='manucorpora', to='seeker.Manuscript'),
            preserve_default=False,
        ),
        migrations.DeleteModel(
            name='ManuscriptCorpusManu',
        ),
    ]
