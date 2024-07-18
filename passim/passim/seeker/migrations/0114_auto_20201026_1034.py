# -*- coding: utf-8 -*-
# Generated by Django 1.11.17 on 2020-10-26 09:34
from __future__ import unicode_literals

from django.db import migrations, models
import django.db.models.deletion
import passim.seeker.models


class Migration(migrations.Migration):

    dependencies = [
        ('seeker', '0113_auto_20201022_1549'),
    ]

    operations = [
        migrations.CreateModel(
            name='Comment',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('content', models.TextField(blank=True, null=True, verbose_name='Comment')),
                ('created', models.DateTimeField(default=passim.seeker.models.get_current_datetime)),
                ('profile', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='profilecomments', to='seeker.Profile')),
            ],
        ),
        migrations.AddField(
            model_name='equalgold',
            name='comments',
            field=models.ManyToManyField(related_name='comments_super', to='seeker.Comment'),
        ),
        migrations.AddField(
            model_name='manuscript',
            name='comments',
            field=models.ManyToManyField(related_name='comments_manuscript', to='seeker.Comment'),
        ),
        migrations.AddField(
            model_name='sermondescr',
            name='comments',
            field=models.ManyToManyField(related_name='comments_sermon', to='seeker.Comment'),
        ),
        migrations.AddField(
            model_name='sermongold',
            name='comments',
            field=models.ManyToManyField(related_name='comments_gold', to='seeker.Comment'),
        ),
    ]
