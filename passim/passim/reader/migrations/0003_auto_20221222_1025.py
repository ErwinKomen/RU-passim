# Generated by Django 2.2 on 2022-12-22 09:25

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('reader', '0002_auto_20221222_0924'),
    ]

    operations = [
        migrations.RenameField(
            model_name='edition',
            old_name='opera',
            new_name='operaid',
        ),
        migrations.CreateModel(
            name='OperaLit',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('operaid', models.IntegerField(verbose_name='Opera ID')),
                ('literatur', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='literatur_operalits', to='reader.Literatur')),
            ],
        ),
    ]