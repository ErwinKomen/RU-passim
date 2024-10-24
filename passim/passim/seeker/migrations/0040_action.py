# -*- coding: utf-8 -*-
# Generated by Django 1.11.17 on 2019-08-29 14:44
from __future__ import unicode_literals

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import passim.seeker.models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('seeker', '0039_litref_data'),
    ]

    operations = [
        migrations.CreateModel(
            name='Action',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('itemtype', models.CharField(max_length=200, verbose_name='Item type')),
                ('actiontype', models.CharField(max_length=200, verbose_name='Action type')),
                ('details', models.TextField(blank=True, null=True, verbose_name='Detail')),
                ('created', models.DateTimeField(default=passim.seeker.models.get_current_datetime)),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
            ],
        ),
    ]