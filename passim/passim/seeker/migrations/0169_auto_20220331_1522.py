# Generated by Django 2.2 on 2022-03-31 13:22

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('seeker', '0168_auto_20220309_1019'),
    ]

    operations = [
        migrations.CreateModel(
            name='OnlineSources',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=255, verbose_name='Name')),
                ('url', models.URLField(max_length=255, verbose_name='External URL')),
                ('sortname', models.TextField(blank=True, default='', verbose_name='Unicode version of the name of the online source')),
            ],
        ),
        migrations.AddField(
            model_name='litref',
            name='sortref',
            field=models.TextField(blank=True, default='', verbose_name='Unicode version of short reference'),
        ),
    ]
