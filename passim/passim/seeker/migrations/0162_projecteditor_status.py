# Generated by Django 2.2 on 2021-12-22 08:13

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('seeker', '0161_auto_20211215_1446'),
    ]

    operations = [
        migrations.AddField(
            model_name='projecteditor',
            name='status',
            field=models.CharField(choices=[('excl', 'Exclude'), ('incl', 'Include')], default='incl', max_length=5, verbose_name='Default assignment'),
        ),
    ]
