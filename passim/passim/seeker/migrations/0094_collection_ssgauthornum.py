# -*- coding: utf-8 -*-
# Generated by Django 1.11.17 on 2020-08-10 13:25
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('seeker', '0093_auto_20200810_1321'),
    ]

    operations = [
        migrations.AddField(
            model_name='collection',
            name='ssgauthornum',
            field=models.IntegerField(blank=True, default=0, null=True, verbose_name='Number of SSG authors'),
        ),
    ]
