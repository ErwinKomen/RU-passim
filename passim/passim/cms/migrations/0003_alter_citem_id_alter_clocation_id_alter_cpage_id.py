# Generated by Django 4.1 on 2024-01-24 12:03

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('cms', '0002_citem_original'),
    ]

    operations = [
        migrations.AlterField(
            model_name='citem',
            name='id',
            field=models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID'),
        ),
        migrations.AlterField(
            model_name='clocation',
            name='id',
            field=models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID'),
        ),
        migrations.AlterField(
            model_name='cpage',
            name='id',
            field=models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID'),
        ),
    ]
