# -*- coding: utf-8 -*-
# Generated by Django 1.11.17 on 2020-06-22 08:47
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('seeker', '0074_litref_year'),
    ]

    operations = [
        migrations.AddField(
            model_name='profile',
            name='affiliation',
            field=models.TextField(blank=True, null=True, verbose_name='Affiliation'),
        ),
        migrations.AddField(
            model_name='profile',
            name='ptype',
            field=models.CharField(default='unk', max_length=5, verbose_name='Profile status'),
        ),
    ]
