# Generated by Django 2.2 on 2021-12-13 15:25

from django.db import migrations, models
import django.db.models.deletion
import passim.seeker.models


class Migration(migrations.Migration):

    dependencies = [
        ('seeker', '0158_codico_origins'),
    ]

    operations = [
        migrations.CreateModel(
            name='ProjectEditor',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('rights', models.CharField(default='edi', max_length=5, verbose_name='Rights')),
                ('created', models.DateTimeField(default=passim.seeker.models.get_current_datetime)),
                ('saved', models.DateTimeField(blank=True, null=True)),
                ('profile', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='project_editor', to='seeker.Profile')),
                ('project', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='project_editor', to='seeker.Project2')),
            ],
        ),
        migrations.AddField(
            model_name='profile',
            name='projects',
            field=models.ManyToManyField(related_name='projects_profile', through='seeker.ProjectEditor', to='seeker.Project2'),
        ),
    ]
