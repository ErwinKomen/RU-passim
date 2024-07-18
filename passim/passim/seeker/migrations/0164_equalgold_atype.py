# Generated by Django 2.2 on 2021-12-22 15:48

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('seeker', '0163_auto_20211222_1551'),
    ]

    operations = [
        migrations.AddField(
            model_name='equalgold',
            name='atype',
            field=models.CharField(choices=[('acc', 'Accepted'), ('def', 'Default'), ('mod', 'Modification needed'), ('rej', 'Rejected')], default='def', max_length=5, verbose_name='Approval'),
        ),
    ]
