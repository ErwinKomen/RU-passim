# -*- coding: utf-8 -*-
# Generated by Django 1.11.17 on 2021-05-19 12:36
from __future__ import unicode_literals

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('seeker', '0148_msitem_codico'),
    ]

    operations = [
        migrations.AlterField(
            model_name='daterange',
            name='codico',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='codico_dateranges', to='seeker.Codico'),
        ),
        migrations.AlterField(
            model_name='msitem',
            name='codico',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='codicoitems', to='seeker.Codico'),
        ),
    ]
