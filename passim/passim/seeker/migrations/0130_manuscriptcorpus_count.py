# -*- coding: utf-8 -*-
# Generated by Django 1.11.17 on 2021-02-03 12:37
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('seeker', '0129_auto_20210203_1218'),
    ]

    operations = [
        migrations.AddField(
            model_name='manuscriptcorpus',
            name='count',
            field=models.IntegerField(default=0, verbose_name='Manuscript links'),
        ),
    ]