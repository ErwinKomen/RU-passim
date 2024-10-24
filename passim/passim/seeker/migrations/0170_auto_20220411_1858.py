# Generated by Django 2.2 on 2022-04-11 16:58

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('seeker', '0169_auto_20220331_1522'),
    ]

    operations = [
        migrations.AlterField(
            model_name='equalgoldlink',
            name='linktype',
            field=models.CharField(choices=[('ech', 'echoes'), ('eqs', 'equals'), ('neq', 'nearly equals'), ('prt', 'partially equals'), ('rel', 'related to'), ('sim', 'similar_to'), ('uns', 'unspecified'), ('use', 'uses')], default='eqs', max_length=5, verbose_name='Link type'),
        ),
        migrations.AlterField(
            model_name='equalgoldlink',
            name='spectype',
            field=models.CharField(blank=True, choices=[('cap', 'Capitula'), ('cdo', 'Commented on'), ('cso', 'Comments on'), ('com', 'Common source'), ('epi', 'Epilogue'), ('pth', 'Has as its part'), ('pto', 'Is part of'), ('pad', 'Paraphrased'), ('pas', 'Paraphrases'), ('pro', 'Prologue'), ('tki', 'Tabula/key/index'), ('tra', 'Translated as'), ('tro', 'Translation of'), ('uns', 'Unspecified'), ('udd', 'Used by'), ('udi', 'Used by (indirect)'), ('usd', 'Uses'), ('usi', 'Uses (indirect)')], max_length=5, null=True, verbose_name='Specification'),
        ),
        migrations.AlterField(
            model_name='sermondescrequal',
            name='linktype',
            field=models.CharField(choices=[('ech', 'echoes'), ('eqs', 'equals'), ('neq', 'nearly equals'), ('prt', 'partially equals'), ('rel', 'related to'), ('sim', 'similar_to'), ('uns', 'unspecified'), ('use', 'uses')], default='uns', max_length=5, verbose_name='Link type'),
        ),
        migrations.AlterField(
            model_name='sermondescrgold',
            name='linktype',
            field=models.CharField(choices=[('ech', 'echoes'), ('eqs', 'equals'), ('neq', 'nearly equals'), ('prt', 'partially equals'), ('rel', 'related to'), ('sim', 'similar_to'), ('uns', 'unspecified'), ('use', 'uses')], default='eq', max_length=5, verbose_name='Link type'),
        ),
        migrations.AlterField(
            model_name='sermongoldsame',
            name='linktype',
            field=models.CharField(choices=[('ech', 'echoes'), ('eqs', 'equals'), ('neq', 'nearly equals'), ('prt', 'partially equals'), ('rel', 'related to'), ('sim', 'similar_to'), ('uns', 'unspecified'), ('use', 'uses')], default='eqs', max_length=5, verbose_name='Link type'),
        ),
    ]