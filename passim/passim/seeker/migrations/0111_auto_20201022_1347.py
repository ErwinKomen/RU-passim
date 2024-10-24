# -*- coding: utf-8 -*-
# Generated by Django 1.11.17 on 2020-10-22 11:47
from __future__ import unicode_literals

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('seeker', '0110_auto_20201021_1427'),
    ]

    operations = [
        migrations.CreateModel(
            name='Feast',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=255, verbose_name='Name (English)')),
                ('latname', models.CharField(blank=True, max_length=255, null=True, verbose_name='Name (Latin)')),
                ('feastdate', models.TextField(blank=True, null=True, verbose_name='Feast date')),
            ],
        ),
        migrations.AddField(
            model_name='sermondescr',
            name='feastnew',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='feastsermons', to='seeker.Feast'),
        ),
    ]