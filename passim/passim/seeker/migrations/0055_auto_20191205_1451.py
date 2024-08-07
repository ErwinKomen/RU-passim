# -*- coding: utf-8 -*-
# Generated by Django 1.11.17 on 2019-12-05 13:51
from __future__ import unicode_literals

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('seeker', '0054_auto_20191205_0950'),
    ]

    operations = [
        migrations.AddField(
            model_name='collection',
            name='descrip',
            field=models.CharField(blank=True, max_length=255, null=True, verbose_name='Description'),
        ),
        migrations.AddField(
            model_name='collection',
            name='name',
            field=models.CharField(blank=True, max_length=255, null=True, verbose_name='Name'),
        ),
        migrations.AddField(
            model_name='collection',
            name='owner',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, to='seeker.Profile'),
        ),
        migrations.AddField(
            model_name='collection',
            name='readonly',
            field=models.TextField(blank=True, null=True, verbose_name='ReadOnly'),
        ),
        migrations.AddField(
            model_name='collection',
            name='url',
            field=models.URLField(blank=True, null=True, verbose_name='Web info'),
        ),
    ]
