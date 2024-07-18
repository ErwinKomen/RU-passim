# -*- coding: utf-8 -*-
# Generated by Django 1.11.17 on 2020-08-26 07:03
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('enrich', '0007_auto_20200826_0902'),
    ]

    operations = [
        migrations.AddField(
            model_name='testunit',
            name='testsets',
            field=models.ManyToManyField(related_name='testset_testunits', through='enrich.TestsetUnit', to='enrich.Testset'),
        ),
    ]
