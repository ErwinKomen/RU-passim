# Generated by Django 2.2 on 2021-07-14 07:52

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('seeker', '0152_auto_20210610_0651'),
    ]

    operations = [
        migrations.AddField(
            model_name='manuscript',
            name='itype',
            field=models.CharField(default='no', max_length=200, verbose_name='Import codico status'),
        ),
    ]
