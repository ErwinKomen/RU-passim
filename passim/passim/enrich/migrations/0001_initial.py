# -*- coding: utf-8 -*-
# Generated by Django 1.11.17 on 2020-08-20 12:40
from __future__ import unicode_literals

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='Sentence',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=255, verbose_name='Name')),
            ],
        ),
        migrations.CreateModel(
            name='Speaker',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=255, verbose_name='Name')),
            ],
        ),
        migrations.CreateModel(
            name='Testunit',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('ntype', models.CharField(choices=[('p', 'Plain'), ('n', 'Lombard noise')], max_length=5, verbose_name='Noise type type')),
                ('sentence', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='enrich.Sentence')),
                ('speaker', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='enrich.Speaker')),
            ],
        ),
    ]
