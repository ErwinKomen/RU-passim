# -*- coding: utf-8 -*-
# Generated by Django 1.11.4 on 2019-05-22 13:38
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('seeker', '0012_auto_20190520_1628'),
    ]

    operations = [
        migrations.AddField(
            model_name='sermongold',
            name='siglist',
            field=models.TextField(default='[]', verbose_name='List of signatures'),
        ),
    ]