# -*- coding: utf-8 -*-
# Generated by Django 1.11.17 on 2020-01-09 11:38
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('seeker', '0056_auto_20191223_1540'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='edition',
            name='gold',
        ),
        migrations.AddField(
            model_name='sermongold',
            name='litrefs',
            field=models.ManyToManyField(related_name='litrefs_gold', through='seeker.LitrefSG', to='seeker.Litref'),
        ),
        migrations.DeleteModel(
            name='Edition',
        ),
    ]
