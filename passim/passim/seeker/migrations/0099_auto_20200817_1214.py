# -*- coding: utf-8 -*-
# Generated by Django 1.11.17 on 2020-08-17 10:14
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('seeker', '0098_auto_20200812_1522'),
    ]

    operations = [
        migrations.AddField(
            model_name='library',
            name='stype',
            field=models.CharField(choices=[('app', 'Approved'), ('edi', 'Edited'), ('imp', 'Imported'), ('man', 'Manually created'), ('-', 'Undefined')], default='man', max_length=5, verbose_name='Status'),
        ),
        migrations.AddField(
            model_name='location',
            name='stype',
            field=models.CharField(choices=[('app', 'Approved'), ('edi', 'Edited'), ('imp', 'Imported'), ('man', 'Manually created'), ('-', 'Undefined')], default='man', max_length=5, verbose_name='Status'),
        ),
    ]
