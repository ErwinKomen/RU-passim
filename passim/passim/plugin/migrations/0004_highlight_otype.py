# Generated by Django 4.1 on 2024-02-05 15:25

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('plugin', '0003_alter_boarddataset_status'),
    ]

    operations = [
        migrations.AddField(
            model_name='highlight',
            name='otype',
            field=models.IntegerField(default=0, verbose_name='Order type'),
        ),
    ]
