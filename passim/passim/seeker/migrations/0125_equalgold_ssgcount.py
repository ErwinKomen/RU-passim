# -*- coding: utf-8 -*-
# Generated by Django 1.11.17 on 2021-01-20 15:10
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('seeker', '0124_auto_20210118_1752'),
    ]

    operations = [
        migrations.AddField(
            model_name='equalgold',
            name='ssgcount',
            field=models.IntegerField(default=0, verbose_name='SSG set size'),
        ),
    ]