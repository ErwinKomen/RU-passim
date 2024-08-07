# -*- coding: utf-8 -*-
# Generated by Django 1.11.17 on 2021-03-17 13:29
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('seeker', '0139_library_mcount'),
    ]

    operations = [
        migrations.AddField(
            model_name='equalgoldlink',
            name='alternativs',
            field=models.CharField(blank=True, choices=[('no', 'No'), ('und', 'Undecided'), ('yes', 'Yes')], max_length=5, null=True, verbose_name='Alternatives'),
        ),
        migrations.AddField(
            model_name='equalgoldlink',
            name='note',
            field=models.TextField(blank=True, null=True, verbose_name='Notes on this link'),
        ),
        migrations.AddField(
            model_name='equalgoldlink',
            name='spectype',
            field=models.CharField(blank=True, choices=[('com', 'Common source'), ('uns', 'Unspecified'), ('usd', 'Uses (direct)'), ('usi', 'Uses (indirect)')], max_length=5, null=True, verbose_name='Specification'),
        ),
    ]
