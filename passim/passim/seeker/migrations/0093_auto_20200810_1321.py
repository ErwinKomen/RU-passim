# -*- coding: utf-8 -*-
# Generated by Django 1.11.17 on 2020-08-10 11:21
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('seeker', '0092_auto_20200810_1049'),
    ]

    operations = [
        migrations.AlterField(
            model_name='sermondescr',
            name='equalgolds',
            field=models.ManyToManyField(related_name='equalgold_sermons', through='seeker.SermonDescrEqual', to='seeker.EqualGold'),
        ),
    ]
