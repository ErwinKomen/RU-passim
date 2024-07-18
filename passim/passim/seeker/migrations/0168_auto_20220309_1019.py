# Generated by Django 2.2 on 2022-03-09 09:19

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('seeker', '0167_auto_20220228_1659'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='daterange',
            name='manuscript',
        ),
        migrations.AlterField(
            model_name='equalgoldlink',
            name='linktype',
            field=models.CharField(choices=[('pwh', 'Is part of / has as its part'), ('rel', 'Related to'), ('ech', 'echoes'), ('eqs', 'equals'), ('neq', 'nearly equals'), ('prt', 'partially equals'), ('sim', 'similar_to'), ('uns', 'unspecified'), ('use', 'uses')], default='eqs', max_length=5, verbose_name='Link type'),
        ),
        migrations.AlterField(
            model_name='report',
            name='reptype',
            field=models.CharField(choices=[('ixlsx', 'Import Excel'), ('ijson', 'Import JSON'), ('iecod', 'Import e-codices'), ('ig', 'Import gold sermon')], max_length=5, verbose_name='Report type'),
        ),
        migrations.AlterField(
            model_name='sermondescrequal',
            name='linktype',
            field=models.CharField(choices=[('pwh', 'Is part of / has as its part'), ('rel', 'Related to'), ('ech', 'echoes'), ('eqs', 'equals'), ('neq', 'nearly equals'), ('prt', 'partially equals'), ('sim', 'similar_to'), ('uns', 'unspecified'), ('use', 'uses')], default='uns', max_length=5, verbose_name='Link type'),
        ),
        migrations.AlterField(
            model_name='sermondescrgold',
            name='linktype',
            field=models.CharField(choices=[('pwh', 'Is part of / has as its part'), ('rel', 'Related to'), ('ech', 'echoes'), ('eqs', 'equals'), ('neq', 'nearly equals'), ('prt', 'partially equals'), ('sim', 'similar_to'), ('uns', 'unspecified'), ('use', 'uses')], default='eq', max_length=5, verbose_name='Link type'),
        ),
        migrations.AlterField(
            model_name='sermongoldsame',
            name='linktype',
            field=models.CharField(choices=[('pwh', 'Is part of / has as its part'), ('rel', 'Related to'), ('ech', 'echoes'), ('eqs', 'equals'), ('neq', 'nearly equals'), ('prt', 'partially equals'), ('sim', 'similar_to'), ('uns', 'unspecified'), ('use', 'uses')], default='eqs', max_length=5, verbose_name='Link type'),
        ),
    ]
