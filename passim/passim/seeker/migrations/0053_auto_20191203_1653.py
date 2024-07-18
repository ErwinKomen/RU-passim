# -*- coding: utf-8 -*-
# Generated by Django 1.11.17 on 2019-12-03 15:53
from __future__ import unicode_literals

from django.db import migrations, models
import django.db.models.deletion
import passim.seeker.models


class Migration(migrations.Migration):

    dependencies = [
        ('seeker', '0052_collection'),
    ]

    operations = [
        migrations.CreateModel(
            name='ManuscriptKeyword',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created', models.DateTimeField(default=passim.seeker.models.get_current_datetime)),
                ('keyword', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='manuscript_kw', to='seeker.Keyword')),
                ('manuscript', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='manuscript_kw', to='seeker.Manuscript')),
            ],
        ),
        migrations.AddField(
            model_name='manuscript',
            name='keywords',
            field=models.ManyToManyField(related_name='keywords_manu', through='seeker.ManuscriptKeyword', to='seeker.Keyword'),
        ),
    ]
