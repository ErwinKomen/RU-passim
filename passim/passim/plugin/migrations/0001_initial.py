# Generated by Django 4.1 on 2024-01-25 13:28

from django.db import migrations, models
import passim.basic.models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='BoardDataset',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100, verbose_name='Name')),
                ('location', models.CharField(max_length=100, verbose_name='Location')),
                ('notes', models.TextField(blank=True, null=True, verbose_name='Notes')),
                ('created', models.DateTimeField(default=passim.basic.models.get_current_datetime)),
                ('saved', models.DateTimeField(default=passim.basic.models.get_current_datetime)),
            ],
        ),
        migrations.CreateModel(
            name='ClMethod',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100, verbose_name='Name')),
                ('abbr', models.CharField(max_length=100, verbose_name='Abbreviation')),
                ('notes', models.TextField(blank=True, null=True, verbose_name='Notes')),
                ('created', models.DateTimeField(default=passim.basic.models.get_current_datetime)),
                ('saved', models.DateTimeField(default=passim.basic.models.get_current_datetime)),
            ],
        ),
        migrations.CreateModel(
            name='Dimension',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100, verbose_name='Name')),
                ('abbr', models.CharField(max_length=100, verbose_name='Abbreviation')),
                ('notes', models.TextField(blank=True, null=True, verbose_name='Notes')),
                ('created', models.DateTimeField(default=passim.basic.models.get_current_datetime)),
                ('saved', models.DateTimeField(default=passim.basic.models.get_current_datetime)),
            ],
        ),
        migrations.CreateModel(
            name='Highlight',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100, verbose_name='Name')),
                ('info', models.TextField(blank=True, null=True, verbose_name='Information')),
                ('notes', models.TextField(blank=True, null=True, verbose_name='Notes')),
                ('created', models.DateTimeField(default=passim.basic.models.get_current_datetime)),
                ('saved', models.DateTimeField(default=passim.basic.models.get_current_datetime)),
            ],
        ),
        migrations.CreateModel(
            name='SeriesDistance',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100, verbose_name='Name')),
                ('codepath', models.CharField(max_length=100, verbose_name='Code path')),
                ('notes', models.TextField(blank=True, null=True, verbose_name='Notes')),
                ('created', models.DateTimeField(default=passim.basic.models.get_current_datetime)),
                ('saved', models.DateTimeField(default=passim.basic.models.get_current_datetime)),
            ],
        ),
        migrations.CreateModel(
            name='SermonsDistance',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100, verbose_name='Name')),
                ('codepath', models.CharField(max_length=100, verbose_name='Code path')),
                ('notes', models.TextField(blank=True, null=True, verbose_name='Notes')),
                ('created', models.DateTimeField(default=passim.basic.models.get_current_datetime)),
                ('saved', models.DateTimeField(default=passim.basic.models.get_current_datetime)),
            ],
        ),
    ]