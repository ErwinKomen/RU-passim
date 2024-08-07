# Generated by Django 2.2 on 2021-08-12 12:13

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('seeker', '0153_manuscript_itype'),
    ]

    operations = [
        migrations.AddField(
            model_name='manuscript',
            name='external',
            field=models.IntegerField(null=True, verbose_name='ID in external DB'),
        ),
        migrations.AlterField(
            model_name='equalgoldlink',
            name='spectype',
            field=models.CharField(blank=True, choices=[('com', 'Common source'), ('uns', 'Unspecified'), ('udd', 'Used by'), ('udi', 'Used by (indirect)'), ('usd', 'Uses'), ('usi', 'Uses (indirect)')], max_length=5, null=True, verbose_name='Specification'),
        ),
    ]
