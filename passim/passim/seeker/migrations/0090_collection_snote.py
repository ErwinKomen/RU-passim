# -*- coding: utf-8 -*-
# Generated by Django 1.11.17 on 2020-08-04 14:32
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('seeker', '0089_auto_20200804_1545'),
    ]

    operations = [
        migrations.AddField(
            model_name='collection',
            name='snote',
            field=models.TextField(default='[]', verbose_name='Status note(s)'),
        ),
    ]
