# -*- coding: utf-8 -*-
# Generated by Django 1.11.17 on 2021-05-12 09:01
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('seeker', '0145_auto_20210510_1635'),
    ]

    operations = [
        migrations.AddField(
            model_name='codico',
            name='keywords',
            field=models.ManyToManyField(related_name='keywords_codi', through='seeker.CodicoKeyword', to='seeker.Keyword'),
        ),
        migrations.AddField(
            model_name='codico',
            name='provenances',
            field=models.ManyToManyField(through='seeker.ProvenanceCod', to='seeker.Provenance'),
        ),
    ]
