# Generated by Django 4.1 on 2024-06-17 06:27

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('seeker', '0216_equalgold_raw_alter_keyword_category'),
    ]

    operations = [
        migrations.AddField(
            model_name='sermonsignature',
            name='codesort',
            field=models.CharField(blank=True, max_length=255, null=True, verbose_name='Code (sortable)'),
        ),
        migrations.AddField(
            model_name='signature',
            name='codesort',
            field=models.CharField(blank=True, max_length=255, null=True, verbose_name='Code (sortable)'),
        ),
    ]