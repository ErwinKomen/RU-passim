# Generated by Django 2.2 on 2023-12-11 11:23

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('seeker', '0204_bibrange_order'),
    ]

    operations = [
        migrations.CreateModel(
            name='AltPages',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('altpage', models.CharField(blank=True, max_length=255, null=True, verbose_name='Locus')),
                ('note', models.TextField(blank=True, null=True, verbose_name='Note on the alternative pages')),
                ('sermon', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='sermonaltpages', to='seeker.SermonDescr')),
            ],
        ),
    ]
