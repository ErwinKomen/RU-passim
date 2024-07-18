# -*- coding: utf-8 -*-
# Generated by Django 1.11.17 on 2019-11-27 08:56
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('seeker', '0049_edition_update'),
    ]

    operations = [
        migrations.AlterField(
            model_name='manuscript',
            name='name',
            field=models.CharField(default='SUPPLY A NAME', max_length=255, verbose_name='Name'),
        ),
        migrations.AlterField(
            model_name='manuscript',
            name='yearfinish',
            field=models.IntegerField(default=100, verbose_name='Year until'),
        ),
        migrations.AlterField(
            model_name='manuscript',
            name='yearstart',
            field=models.IntegerField(default=100, verbose_name='Year from'),
        ),
    ]
