# -*- coding: utf-8 -*-
# Generated by Django 1.11 on 2019-05-13 08:10
from __future__ import unicode_literals

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('seeker', '0008_remove_signature_edition'),
    ]

    operations = [
        migrations.AddField(
            model_name='edition',
            name='gold',
            field=models.ForeignKey(default=1, on_delete=django.db.models.deletion.CASCADE, related_name='goldeditions', to='seeker.SermonGold'),
            preserve_default=False,
        ),
    ]
