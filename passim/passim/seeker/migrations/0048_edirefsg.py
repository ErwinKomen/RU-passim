# -*- coding: utf-8 -*-
# Generated by Django 1.11.17 on 2019-10-21 13:18
from __future__ import unicode_literals

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('seeker', '0047_litrefsg'),
    ]

    operations = [
        migrations.CreateModel(
            name='EdirefSG',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('pages', models.CharField(blank=True, max_length=200, null=True, verbose_name='Pages')),
                ('reference', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='reference_edition', to='seeker.Litref')),
                ('sermon_gold', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='sermon_gold_editions', to='seeker.SermonGold')),
            ],
        ),
    ]
