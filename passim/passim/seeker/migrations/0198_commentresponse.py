# Generated by Django 2.2 on 2023-07-17 07:46

from django.db import migrations, models
import django.db.models.deletion
import passim.seeker.models


class Migration(migrations.Migration):

    dependencies = [
        ('seeker', '0197_commentread'),
    ]

    operations = [
        migrations.CreateModel(
            name='CommentResponse',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created', models.DateTimeField(default=passim.seeker.models.get_current_datetime)),
                ('content', models.TextField(blank=True, null=True, verbose_name='Response')),
                ('comment', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='comment_cresponses', to='seeker.Comment')),
                ('profile', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='profile_cresponses', to='seeker.Profile')),
            ],
        ),
    ]