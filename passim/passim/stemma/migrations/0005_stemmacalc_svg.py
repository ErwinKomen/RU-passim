# Generated by Django 2.2 on 2023-07-20 10:30

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('stemma', '0004_stemmacalc_signal'),
    ]

    operations = [
        migrations.AddField(
            model_name='stemmacalc',
            name='svg',
            field=models.TextField(blank=True, null=True, verbose_name='SVG'),
        ),
    ]