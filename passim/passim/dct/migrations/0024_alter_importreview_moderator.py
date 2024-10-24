# Generated by Django 4.1 on 2024-06-05 14:09

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('seeker', '0216_equalgold_raw_alter_keyword_category'),
        ('dct', '0023_importreview_order_alter_importreview_status_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='importreview',
            name='moderator',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='moderator_reviews', to='seeker.profile'),
        ),
    ]