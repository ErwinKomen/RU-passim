# Generated by Django 2.2 on 2021-12-22 14:51

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('seeker', '0162_projecteditor_status'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='manuscript',
            name='project',
        ),
        migrations.DeleteModel(
            name='Project',
        ),
    ]
