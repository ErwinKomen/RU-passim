# Generated by Django 2.2 on 2022-07-14 10:55

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('seeker', '0171_equalgoldexternal'),
    ]

    operations = [
        migrations.AddField(
            model_name='collection',
            name='comments',
            field=models.ManyToManyField(related_name='comments_collection', to='seeker.Comment'),
        ),
    ]
