# -*- coding: utf-8 -*-
# Generated by Django 1.11.17 on 2019-05-07 14:13
from __future__ import unicode_literals

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('seeker', '0004_auto_20190507_1608'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='sermongold',
            name='signature',
        ),
    ]