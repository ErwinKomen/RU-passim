# -*- coding: utf-8 -*-
# Generated by Django 1.11.17 on 2021-05-04 11:43
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='UserSearch',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('view', models.CharField(max_length=255, verbose_name='Listview')),
                ('params', models.TextField(default='[]', verbose_name='Parameters')),
                ('history', models.TextField(default='{}', verbose_name='History')),
            ],
        ),
    ]
