# -*- coding: utf-8 -*-
# Generated by Django 1.11.17 on 2020-07-22 13:17
from __future__ import unicode_literals

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('seeker', '0083_sermonhead_title'),
    ]

    operations = [
        migrations.CreateModel(
            name='Template',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=255, verbose_name='Name')),
            ],
        ),
        migrations.AddField(
            model_name='manuscript',
            name='mtype',
            field=models.CharField(choices=[('man', 'Manifestation'), ('tem', 'Template')], default='man', max_length=5, verbose_name='Manifestation type'),
        ),
        migrations.AddField(
            model_name='sermondescr',
            name='mtype',
            field=models.CharField(choices=[('man', 'Manifestation'), ('tem', 'Template')], default='man', max_length=5, verbose_name='Manifestation type'),
        ),
        migrations.AddField(
            model_name='template',
            name='manu',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='manutemplates', to='seeker.Manuscript'),
        ),
        migrations.AddField(
            model_name='template',
            name='profile',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='profiletemplates', to='seeker.Profile'),
        ),
    ]
