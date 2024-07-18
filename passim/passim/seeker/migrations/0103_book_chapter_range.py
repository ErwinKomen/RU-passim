# -*- coding: utf-8 -*-
# Generated by Django 1.11.17 on 2020-09-28 11:01
from __future__ import unicode_literals

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('seeker', '0102_auto_20200923_1437'),
    ]

    operations = [
        migrations.CreateModel(
            name='Book',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100, verbose_name='Name')),
                ('abbr', models.CharField(max_length=5, verbose_name='Abbreviation')),
                ('idno', models.IntegerField(default=-1, verbose_name='Identifier')),
                ('chnum', models.IntegerField(default=-1, verbose_name='Number of chapters')),
            ],
        ),
        migrations.CreateModel(
            name='Chapter',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('number', models.IntegerField(default=-1, verbose_name='Chapter')),
                ('vsnum', models.IntegerField(default=-1, verbose_name='Number of verses')),
                ('book', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='bookchapters', to='seeker.Book')),
            ],
        ),
        migrations.CreateModel(
            name='Range',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('start', models.CharField(default='', max_length=9, verbose_name='Start')),
                ('einde', models.CharField(default='', max_length=9, verbose_name='Einde')),
                ('sermon', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='sermonranges', to='seeker.SermonDescr')),
            ],
        ),
    ]
