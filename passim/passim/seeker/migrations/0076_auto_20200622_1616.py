# -*- coding: utf-8 -*-
# Generated by Django 1.11.17 on 2020-06-22 14:16
from __future__ import unicode_literals

from django.db import migrations, models
import django.db.models.deletion
import passim.seeker.models


class Migration(migrations.Migration):

    dependencies = [
        ('seeker', '0075_auto_20200622_1047'),
    ]

    operations = [
        migrations.CreateModel(
            name='EqualGoldKeywordUser',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created', models.DateTimeField(default=passim.seeker.models.get_current_datetime)),
                ('equal', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='equal_kwu', to='seeker.EqualGold')),
                ('keyword', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='equal_kwu', to='seeker.Keyword')),
            ],
        ),
        migrations.CreateModel(
            name='ManuscriptKeywordUser',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created', models.DateTimeField(default=passim.seeker.models.get_current_datetime)),
                ('keyword', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='manuscript_kwu', to='seeker.Keyword')),
                ('manuscript', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='manuscript_kwu', to='seeker.Manuscript')),
            ],
        ),
        migrations.CreateModel(
            name='SermonDescrKeywordUser',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created', models.DateTimeField(default=passim.seeker.models.get_current_datetime)),
                ('keyword', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='sermondescr_kwu', to='seeker.Keyword')),
            ],
        ),
        migrations.CreateModel(
            name='SermonGoldKeywordUser',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created', models.DateTimeField(default=passim.seeker.models.get_current_datetime)),
                ('gold', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='sermongold_kwu', to='seeker.SermonGold')),
                ('keyword', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='sermongold_kwu', to='seeker.Keyword')),
            ],
        ),
        migrations.AlterField(
            model_name='profile',
            name='ptype',
            field=models.CharField(choices=[('akw', 'Approved keyword editor'), ('dev', 'Developer of this application'), ('usr', 'Simple user'), ('unk', 'Unknown')], default='unk', max_length=5, verbose_name='Profile status'),
        ),
        migrations.AddField(
            model_name='sermongoldkeyworduser',
            name='profile',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='sermongold_kwu', to='seeker.Profile'),
        ),
        migrations.AddField(
            model_name='sermondescrkeyworduser',
            name='profile',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='sermondescr_kwu', to='seeker.Profile'),
        ),
        migrations.AddField(
            model_name='sermondescrkeyworduser',
            name='sermon',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='sermondescr_kwu', to='seeker.SermonDescr'),
        ),
        migrations.AddField(
            model_name='manuscriptkeyworduser',
            name='profile',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='manuscript_kwu', to='seeker.Profile'),
        ),
        migrations.AddField(
            model_name='equalgoldkeyworduser',
            name='profile',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='equal_kwu', to='seeker.Profile'),
        ),
    ]
