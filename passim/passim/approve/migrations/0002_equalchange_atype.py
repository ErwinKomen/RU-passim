# Generated by Django 2.2 on 2021-12-23 12:42

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('approve', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='equalchange',
            name='atype',
            field=models.CharField(choices=[('acc', 'Accepted'), ('def', 'Default'), ('mod', 'Modification needed'), ('rej', 'Rejected')], default='def', max_length=5, verbose_name='Approval'),
        ),
    ]
