# Generated by Django 2.2 on 2022-10-24 09:44

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('seeker', '0180_sermongoldexternal'),
    ]

    operations = [
        migrations.AddField(
            model_name='sermongold',
            name='edinote',
            field=models.TextField(blank=True, null=True, verbose_name='Edition note'),
        ),
    ]