# Generated by Django 2.2 on 2022-01-10 13:59

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('seeker', '0164_equalgold_atype'),
    ]

    operations = [
        migrations.AlterField(
            model_name='equalgold',
            name='atype',
            field=models.CharField(choices=[('acc', 'Accepted'), ('mod', 'Modification needed'), ('def', 'Pending'), ('rej', 'Rejected')], default='def', max_length=5, verbose_name='Approval'),
        ),
    ]
