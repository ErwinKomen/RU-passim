# Generated by Django 4.1 on 2024-05-30 07:20

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('dct', '0021_importset_name_alter_importset_excel'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='importset',
            name='selitemtype',
        ),
        migrations.AddField(
            model_name='importset',
            name='importtype',
            field=models.CharField(choices=[('ssg', 'Authority File'), ('manu', 'Manuscript')], default=1, max_length=5, verbose_name='Import type'),
            preserve_default=False,
        ),
    ]
