# -*- coding: utf-8 -*-
# Generated by Django 1.11.17 on 2020-05-06 08:54
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('seeker', '0064_auto_20200506_0951'),
    ]

    operations = [
        migrations.AddField(
            model_name='keyword',
            name='visibility',
            field=models.CharField(default='all', max_length=5, verbose_name='Visibility'),
        ),
    ]