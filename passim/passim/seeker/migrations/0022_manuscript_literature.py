# -*- coding: utf-8 -*-
# Generated by Django 1.11.17 on 2019-06-12 14:47
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('seeker', '0021_auto_20190612_0952'),
    ]

    operations = [
        migrations.AddField(
            model_name='manuscript',
            name='literature',
            field=models.TextField(blank=True, null=True, verbose_name='Literature'),
        ),
    ]
