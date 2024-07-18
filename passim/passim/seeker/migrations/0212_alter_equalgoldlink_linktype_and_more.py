# Generated by Django 4.1 on 2024-05-13 10:34

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('seeker', '0211_manuscriptexternal_externaltextid'),
    ]

    operations = [
        migrations.AlterField(
            model_name='equalgoldlink',
            name='linktype',
            field=models.CharField(choices=[('ech', 'echoes'), ('eqs', 'equals'), ('neq', 'nearly equals'), ('prt', 'partially equals'), ('rel', 'related to')], default='eqs', max_length=5, verbose_name='Link type'),
        ),
        migrations.AlterField(
            model_name='manuscriptlink',
            name='linktype',
            field=models.CharField(choices=[('ech', 'echoes'), ('eqs', 'equals'), ('neq', 'nearly equals'), ('prt', 'partially equals'), ('rel', 'related to')], default='rel', max_length=5, verbose_name='Link type'),
        ),
        migrations.AlterField(
            model_name='sermondescrequal',
            name='linktype',
            field=models.CharField(choices=[('ech', 'echoes'), ('eqs', 'equals'), ('neq', 'nearly equals'), ('prt', 'partially equals'), ('rel', 'related to')], default='uns', max_length=5, verbose_name='Link type'),
        ),
        migrations.AlterField(
            model_name='sermondescrgold',
            name='linktype',
            field=models.CharField(choices=[('ech', 'echoes'), ('eqs', 'equals'), ('neq', 'nearly equals'), ('prt', 'partially equals'), ('rel', 'related to')], default='eq', max_length=5, verbose_name='Link type'),
        ),
        migrations.AlterField(
            model_name='sermondescrlink',
            name='linktype',
            field=models.CharField(choices=[('ech', 'echoes'), ('eqs', 'equals'), ('neq', 'nearly equals'), ('prt', 'partially equals'), ('rel', 'related to')], default='rel', max_length=5, verbose_name='Link type'),
        ),
        migrations.AlterField(
            model_name='sermongoldsame',
            name='linktype',
            field=models.CharField(choices=[('ech', 'echoes'), ('eqs', 'equals'), ('neq', 'nearly equals'), ('prt', 'partially equals'), ('rel', 'related to')], default='eqs', max_length=5, verbose_name='Link type'),
        ),
    ]
