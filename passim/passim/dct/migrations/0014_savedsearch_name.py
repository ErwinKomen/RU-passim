# Generated by Django 2.2 on 2023-04-05 11:00

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('dct', '0013_selectitem'),
    ]

    operations = [
        migrations.AddField(
            model_name='savedsearch',
            name='name',
            field=models.CharField(default='aap', max_length=255, verbose_name='Name'),
            preserve_default=False,
        ),
    ]
