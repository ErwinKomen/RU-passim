# -*- coding: utf-8 -*-
# Generated by Django 1.11.17 on 2021-02-03 12:49
from __future__ import unicode_literals

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('seeker', '0131_auto_20210203_1344'),
    ]

    operations = [
        migrations.RenameModel(
            old_name='CorpusManu',
            new_name='ManuscriptCorpusManu',
        ),
    ]