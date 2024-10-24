# -*- coding: utf-8 -*-
# Generated by Django 1.11.17 on 2020-07-02 10:36
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('seeker', '0080_auto_20200702_0924'),
    ]

    operations = [
        migrations.AddField(
            model_name='sermondescr',
            name='equalgolds',
            field=models.ManyToManyField(through='seeker.SermonDescrEqual', to='seeker.EqualGold'),
        ),
        migrations.AlterField(
            model_name='sermondescr',
            name='autype',
            field=models.CharField(choices=[('vun', '1 Very uncertain'), ('unc', '2 Uncertain'), ('ave', '3 Average'), ('rea', '4 Reasonably certain'), ('vce', '5 Very certain')], default='ave', max_length=5, verbose_name='Author certainty'),
        ),
    ]