# Generated by Django 4.1 on 2024-06-05 13:15

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('dct', '0022_remove_importset_selitemtype_importset_importtype'),
    ]

    operations = [
        migrations.AddField(
            model_name='importreview',
            name='order',
            field=models.IntegerField(default=0, verbose_name='Order'),
        ),
        migrations.AlterField(
            model_name='importreview',
            name='status',
            field=models.CharField(choices=[('acc', 'Accepted'), ('chg', 'Changed'), ('cre', 'Created'), ('rej', 'Rejected'), ('sub', 'Submitted'), ('ver', 'Verified')], default='cre', max_length=5, verbose_name='Review status'),
        ),
        migrations.AlterField(
            model_name='importset',
            name='status',
            field=models.CharField(choices=[('acc', 'Accepted'), ('chg', 'Changed'), ('cre', 'Created'), ('rej', 'Rejected'), ('sub', 'Submitted'), ('ver', 'Verified')], default='cre', max_length=5, verbose_name='Import status'),
        ),
    ]
