# Generated by Django 2.2 on 2023-05-24 12:56

from django.db import migrations, models
import django.db.models.deletion
import passim.seeker.models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('seeker', '0195_equalgold_fullinfo'),
    ]

    operations = [
        migrations.CreateModel(
            name='StemmaSet',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=255, verbose_name='Name')),
                ('notes', models.TextField(blank=True, null=True, verbose_name='Notes')),
                ('contents', models.TextField(default='[]', verbose_name='Contents')),
                ('scope', models.CharField(choices=[('priv', 'Private'), ('publ', 'Public'), ('team', 'Team')], default='priv', max_length=5, verbose_name='Scope')),
                ('created', models.DateTimeField(default=passim.seeker.models.get_current_datetime)),
                ('saved', models.DateTimeField(blank=True, null=True)),
                ('profile', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='profile_stemmasets', to='seeker.Profile')),
            ],
        ),
        migrations.CreateModel(
            name='StemmaItem',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('order', models.IntegerField(default=0, verbose_name='Order')),
                ('equal', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='equal_stemmaitems', to='seeker.EqualGold')),
                ('stemmaset', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='stemmaset_stemmaitems', to='stemma.StemmaSet')),
            ],
        ),
    ]