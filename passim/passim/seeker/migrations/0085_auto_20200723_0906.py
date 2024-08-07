# -*- coding: utf-8 -*-
# Generated by Django 1.11.17 on 2020-07-23 07:06
from __future__ import unicode_literals

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('seeker', '0084_auto_20200722_1517'),
    ]

    operations = [
        migrations.AddField(
            model_name='template',
            name='description',
            field=models.TextField(blank=True, null=True, verbose_name='Description'),
        ),
        migrations.AlterField(
            model_name='template',
            name='manu',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, related_name='manutemplates', to='seeker.Manuscript'),
        ),
    ]
