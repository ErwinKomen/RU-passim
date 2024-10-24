# Generated by Django 4.1 on 2024-03-21 10:46

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('seeker', '0208_projecteditor_status'),
    ]

    operations = [
        migrations.AddField(
            model_name='equalgoldexternal',
            name='externaltextid',
            field=models.CharField(blank=True, max_length=255, null=True, verbose_name='External identifier (text)'),
        ),
        migrations.AddField(
            model_name='sermongoldexternal',
            name='externaltextid',
            field=models.CharField(blank=True, max_length=255, null=True, verbose_name='External identifier (text)'),
        ),
    ]