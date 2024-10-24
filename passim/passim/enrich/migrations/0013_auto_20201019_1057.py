# -*- coding: utf-8 -*-
# Generated by Django 1.11.17 on 2020-10-19 08:57
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('enrich', '0012_testunit_fname'),
    ]

    operations = [
        migrations.CreateModel(
            name='Information',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=255, verbose_name='Key name')),
                ('kvalue', models.TextField(blank=True, default='', null=True, verbose_name='Key value')),
            ],
            options={
                'verbose_name_plural': 'Information Items',
            },
        ),
        migrations.AlterField(
            model_name='speaker',
            name='gender',
            field=models.CharField(choices=[('m', 'Male'), ('f', 'Female')], default='f', max_length=5, verbose_name='Gender'),
        ),
    ]