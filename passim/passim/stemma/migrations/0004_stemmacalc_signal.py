# Generated by Django 2.2 on 2023-06-30 06:38

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('stemma', '0003_auto_20230630_0649'),
    ]

    operations = [
        migrations.AddField(
            model_name='stemmacalc',
            name='signal',
            field=models.CharField(default='none', max_length=20, verbose_name='Signal'),
        ),
    ]