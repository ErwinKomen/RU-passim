# -*- coding: utf-8 -*-
# Generated by Django 1.11.17 on 2020-07-23 08:42
from __future__ import unicode_literals

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('seeker', '0085_auto_20200723_0906'),
    ]

    operations = [
        migrations.AlterField(
            model_name='template',
            name='profile',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, related_name='profiletemplates', to='seeker.Profile'),
        ),
    ]