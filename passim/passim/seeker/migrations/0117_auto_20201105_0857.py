# -*- coding: utf-8 -*-
# Generated by Django 1.11.17 on 2020-11-05 07:57
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('seeker', '0116_sermonequaldist'),
    ]

    operations = [
        migrations.AddField(
            model_name='equalgold',
            name='scount',
            field=models.IntegerField(default=0, verbose_name='Sermon set size'),
        ),
        migrations.AddField(
            model_name='sermondescr',
            name='distances',
            field=models.ManyToManyField(related_name='distances_sermons', through='seeker.SermonEqualDist', to='seeker.EqualGold'),
        ),
    ]
