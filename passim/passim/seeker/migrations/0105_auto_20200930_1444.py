# -*- coding: utf-8 -*-
# Generated by Django 1.11.17 on 2020-09-30 12:44
from __future__ import unicode_literals

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('seeker', '0104_auto_20200930_0834'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='chapter',
            name='book',
        ),
        migrations.DeleteModel(
            name='Book',
        ),
        migrations.DeleteModel(
            name='Chapter',
        ),
    ]
