# -*- coding: utf-8 -*-
# Generated by Django 1.11.17 on 2021-03-03 14:47
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('seeker', '0138_auto_20210224_1853'),
    ]

    operations = [
        migrations.AddField(
            model_name='library',
            name='mcount',
            field=models.IntegerField(default=0, verbose_name='Manuscripts for this library'),
        ),
    ]
