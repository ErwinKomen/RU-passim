# -*- coding: utf-8 -*-
# Generated by Django 1.11.17 on 2020-06-25 12:24
from __future__ import unicode_literals

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('seeker', '0077_userkeyword'),
    ]

    operations = [
        migrations.AlterField(
            model_name='userkeyword',
            name='gold',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='gold_userkeywords', to='seeker.SermonGold'),
        ),
        migrations.AlterField(
            model_name='userkeyword',
            name='manu',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='manu_userkeywords', to='seeker.Manuscript'),
        ),
        migrations.AlterField(
            model_name='userkeyword',
            name='sermo',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='sermo_userkeywords', to='seeker.SermonDescr'),
        ),
        migrations.AlterField(
            model_name='userkeyword',
            name='super',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='super_userkeywords', to='seeker.EqualGold'),
        ),
    ]