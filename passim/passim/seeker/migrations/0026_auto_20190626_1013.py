# -*- coding: utf-8 -*-
# Generated by Django 1.11.17 on 2019-06-26 08:13
from __future__ import unicode_literals

from django.db import migrations, models
import passim.seeker.models


class Migration(migrations.Migration):

    dependencies = [
        ('seeker', '0025_information'),
    ]

    operations = [
        migrations.AlterField(
            model_name='newsitem',
            name='created',
            field=models.DateTimeField(default=passim.seeker.models.get_current_datetime),
        ),
        migrations.AlterField(
            model_name='report',
            name='created',
            field=models.DateTimeField(default=passim.seeker.models.get_current_datetime),
        ),
        migrations.AlterField(
            model_name='sermongoldkeyword',
            name='created',
            field=models.DateTimeField(default=passim.seeker.models.get_current_datetime),
        ),
        migrations.AlterField(
            model_name='sourceinfo',
            name='created',
            field=models.DateTimeField(default=passim.seeker.models.get_current_datetime),
        ),
        migrations.AlterField(
            model_name='visit',
            name='when',
            field=models.DateTimeField(default=passim.seeker.models.get_current_datetime),
        ),
    ]