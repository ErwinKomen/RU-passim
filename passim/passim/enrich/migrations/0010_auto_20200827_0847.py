# -*- coding: utf-8 -*-
# Generated by Django 1.11.17 on 2020-08-27 06:47
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('enrich', '0009_auto_20200827_0831'),
    ]

    operations = [
        migrations.AlterField(
            model_name='testunit',
            name='ntype',
            field=models.CharField(choices=[('p', 'Natural'), ('n', 'Lombard noise')], max_length=5, verbose_name='Noise type type'),
        ),
    ]
