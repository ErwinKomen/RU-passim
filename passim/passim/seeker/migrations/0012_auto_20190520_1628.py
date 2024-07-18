# -*- coding: utf-8 -*-
# Generated by Django 1.11.17 on 2019-05-20 14:28
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('seeker', '0011_auto_20190520_0854'),
    ]

    operations = [
        migrations.AddField(
            model_name='sermongold',
            name='srchexplicit',
            field=models.TextField(blank=True, null=True, verbose_name='Explicit (searchable)'),
        ),
        migrations.AddField(
            model_name='sermongold',
            name='srchincipit',
            field=models.TextField(blank=True, null=True, verbose_name='Incipit (searchable)'),
        ),
        migrations.AlterField(
            model_name='report',
            name='reptype',
            field=models.CharField(choices=[('ig', 'Import gold sermon')], max_length=5, verbose_name='Report type'),
        ),
    ]
