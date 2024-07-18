# Generated by Django 2.2 on 2023-05-17 07:48

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('seeker', '0193_auto_20230510_0910'),
    ]

    operations = [
        migrations.AddField(
            model_name='manuscript',
            name='manucount',
            field=models.IntegerField(default=0, verbose_name='Number of related manuscripts'),
        ),
        migrations.AlterField(
            model_name='codico',
            name='name',
            field=models.CharField(blank=True, default='', max_length=255, verbose_name='Name'),
        ),
        migrations.AlterField(
            model_name='manuscript',
            name='name',
            field=models.CharField(blank=True, default='', max_length=255, verbose_name='Name'),
        ),
        migrations.CreateModel(
            name='ManuscriptLink',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('linktype', models.CharField(choices=[('ech', 'echoes'), ('eqs', 'equals'), ('neq', 'nearly equals'), ('prt', 'partially equals'), ('rel', 'related to'), ('sim', 'similar_to'), ('uns', 'unspecified'), ('use', 'uses')], default='rel', max_length=5, verbose_name='Link type')),
                ('note', models.TextField(blank=True, null=True, verbose_name='Notes on this link')),
                ('dst', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='manuscript_dst', to='seeker.Manuscript')),
                ('src', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='manuscript_src', to='seeker.Manuscript')),
            ],
        ),
        migrations.AddField(
            model_name='manuscript',
            name='relations',
            field=models.ManyToManyField(related_name='related_to', through='seeker.ManuscriptLink', to='seeker.Manuscript'),
        ),
    ]
