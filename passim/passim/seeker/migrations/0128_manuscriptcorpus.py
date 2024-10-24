# -*- coding: utf-8 -*-
# Generated by Django 1.11.17 on 2021-02-03 11:06
from __future__ import unicode_literals

from django.db import migrations, models
import django.db.models.deletion
import passim.seeker.models


class Migration(migrations.Migration):

    dependencies = [
        ('seeker', '0127_sermondescrequal_manu'),
    ]

    operations = [
        migrations.CreateModel(
            name='ManuscriptCorpus',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created', models.DateTimeField(default=passim.seeker.models.get_current_datetime)),
                ('manu', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='manucorpora', to='seeker.Manuscript')),
                ('profile', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='profilecorpora', to='seeker.Profile')),
                ('source', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='sourcecorpora', to='seeker.SermonDescr')),
                ('target', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='targetcorpora', to='seeker.SermonDescr')),
            ],
        ),
    ]