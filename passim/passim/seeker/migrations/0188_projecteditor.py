# Generated by Django 2.2 on 2023-03-02 07:58

from django.db import migrations, models
import django.db.models.deletion
import passim.seeker.models


class Migration(migrations.Migration):

    dependencies = [
        ('seeker', '0187_auto_20230302_0846'),
    ]

    operations = [
        migrations.CreateModel(
            name='ProjectEditor',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created', models.DateTimeField(default=passim.seeker.models.get_current_datetime)),
                ('saved', models.DateTimeField(blank=True, null=True)),
                ('profile', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='project_editor', to='seeker.Profile')),
                ('project', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='project_editor', to='seeker.Project2')),
            ],
        ),
    ]