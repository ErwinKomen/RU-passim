# Generated by Django 2.2 on 2022-08-15 08:04

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('seeker', '0172_collection_comments'),
        ('basic', '0003_usersearch_count'),
        ('dct', '0010_setlist_name'),
    ]

    operations = [
        migrations.CreateModel(
            name='SavedSearch',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('order', models.IntegerField(default=0, verbose_name='Order')),
                ('profile', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='profile_savedsearches', to='seeker.Profile')),
                ('usersearch', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='usersearch_savedsearches', to='basic.UserSearch')),
            ],
        ),
        migrations.CreateModel(
            name='SavedItem',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('order', models.IntegerField(default=0, verbose_name='Order')),
                ('setlisttype', models.CharField(choices=[('ssg', 'Authority File'), ('hist', 'Historical Collection'), ('manu', 'Manuscript'), ('pd', 'Personal Dataset'), ('serm', 'Sermon')], max_length=5, verbose_name='Saved item type')),
                ('collection', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='collection_saveditems', to='seeker.Collection')),
                ('equal', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='equal_saveditems', to='seeker.EqualGold')),
                ('manuscript', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='manuscript_saveditems', to='seeker.Manuscript')),
                ('profile', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='profile_saveditems', to='seeker.Profile')),
                ('sermon', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='sermon_saveditems', to='seeker.SermonDescr')),
            ],
        ),
    ]