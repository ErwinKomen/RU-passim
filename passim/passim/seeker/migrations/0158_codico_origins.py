# Generated by Django 2.2 on 2021-12-09 09:00

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('seeker', '0157_origincod'),
    ]

    operations = [
        migrations.AddField(
            model_name='codico',
            name='origins',
            field=models.ManyToManyField(through='seeker.OriginCod', to='seeker.Origin'),
        ),
    ]
