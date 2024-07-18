# -*- coding: utf-8 -*-
# Generated by Django 1.11.17 on 2019-05-07 13:34
from __future__ import unicode_literals

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('seeker', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='Edition',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=255, verbose_name='Name')),
                ('editype', models.CharField(default='gr', max_length=5, verbose_name='Edition type')),
            ],
        ),
        migrations.CreateModel(
            name='Signature',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('code', models.CharField(max_length=255, verbose_name='Code')),
                ('edition', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='edition_signatures', to='seeker.Edition')),
                ('gold', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='goldsermon_signatures', to='seeker.SermonGold')),
            ],
        ),
    ]
