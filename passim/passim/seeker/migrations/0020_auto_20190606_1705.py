# -*- coding: utf-8 -*-
# Generated by Django 1.11.17 on 2019-06-06 15:05
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('seeker', '0019_auto_20190603_1048'),
    ]

    operations = [
        migrations.AlterField(
            model_name='sermondescrgold',
            name='linktype',
            field=models.CharField(choices=[('eqs', 'equals'), ('neq', 'nearly equals'), ('prt', 'partially equals'), ('sim', 'similar_to'), ('use', 'uses')], default='eq', max_length=5, verbose_name='Link type'),
        ),
        migrations.AlterField(
            model_name='sermongoldsame',
            name='linktype',
            field=models.CharField(choices=[('eqs', 'equals'), ('neq', 'nearly equals'), ('prt', 'partially equals'), ('sim', 'similar_to'), ('use', 'uses')], default='eqs', max_length=5, verbose_name='Link type'),
        ),
    ]