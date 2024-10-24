# -*- coding: utf-8 -*-
# Generated by Django 1.11.17 on 2021-03-18 08:28
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('seeker', '0140_auto_20210317_1429'),
    ]

    operations = [
        migrations.RenameField(
            model_name='equalgoldlink',
            old_name='alternativs',
            new_name='alternatives',
        ),
        migrations.AlterField(
            model_name='equalgoldlink',
            name='linktype',
            field=models.CharField(choices=[('ech', 'echoes'), ('eqs', 'equals'), ('neq', 'nearly equals'), ('prt', 'partially equals'), ('sim', 'similar_to'), ('uns', 'unspecified'), ('use', 'uses')], default='eqs', max_length=5, verbose_name='Link type'),
        ),
        migrations.AlterField(
            model_name='equalgoldlink',
            name='spectype',
            field=models.CharField(blank=True, choices=[('com', 'Common source'), ('uns', 'Unspecified'), ('udd', 'Used by (direct)'), ('udi', 'Used by (indirect)'), ('usd', 'Uses (direct)'), ('usi', 'Uses (indirect)')], max_length=5, null=True, verbose_name='Specification'),
        ),
        migrations.AlterField(
            model_name='sermondescrequal',
            name='linktype',
            field=models.CharField(choices=[('ech', 'echoes'), ('eqs', 'equals'), ('neq', 'nearly equals'), ('prt', 'partially equals'), ('sim', 'similar_to'), ('uns', 'unspecified'), ('use', 'uses')], default='uns', max_length=5, verbose_name='Link type'),
        ),
        migrations.AlterField(
            model_name='sermondescrgold',
            name='linktype',
            field=models.CharField(choices=[('ech', 'echoes'), ('eqs', 'equals'), ('neq', 'nearly equals'), ('prt', 'partially equals'), ('sim', 'similar_to'), ('uns', 'unspecified'), ('use', 'uses')], default='eq', max_length=5, verbose_name='Link type'),
        ),
        migrations.AlterField(
            model_name='sermongoldsame',
            name='linktype',
            field=models.CharField(choices=[('ech', 'echoes'), ('eqs', 'equals'), ('neq', 'nearly equals'), ('prt', 'partially equals'), ('sim', 'similar_to'), ('uns', 'unspecified'), ('use', 'uses')], default='eqs', max_length=5, verbose_name='Link type'),
        ),
    ]