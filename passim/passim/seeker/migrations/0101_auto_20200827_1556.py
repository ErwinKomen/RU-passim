# -*- coding: utf-8 -*-
# Generated by Django 1.11.17 on 2020-08-27 13:56
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('seeker', '0100_auto_20200817_1216'),
    ]

    operations = [
        migrations.AddField(
            model_name='collectiongold',
            name='order',
            field=models.IntegerField(default=-1, verbose_name='Order'),
        ),
        migrations.AddField(
            model_name='collectionman',
            name='order',
            field=models.IntegerField(default=-1, verbose_name='Order'),
        ),
        migrations.AddField(
            model_name='collectionserm',
            name='order',
            field=models.IntegerField(default=-1, verbose_name='Order'),
        ),
        migrations.AddField(
            model_name='collectionsuper',
            name='order',
            field=models.IntegerField(default=-1, verbose_name='Order'),
        ),
    ]
