# Generated by Django 2.2 on 2022-02-28 15:59

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('seeker', '0166_manuscript_editornotes'),
    ]

    operations = [
        migrations.AlterField(
            model_name='equalgold',
            name='atype',
            field=models.CharField(choices=[('acc', 'Accepted'), ('aut', 'Automatically accepted'), ('mod', 'Modification needed'), ('def', 'Pending'), ('rej', 'Rejected')], default='def', max_length=5, verbose_name='Approval'),
        ),
    ]
