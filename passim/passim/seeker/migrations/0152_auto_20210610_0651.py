# Generated by Django 2.2 on 2021-06-10 04:51

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('seeker', '0151_auto_20210526_1712'),
    ]

    operations = [
        migrations.AlterField(
            model_name='action',
            name='user',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='user_actions', to=settings.AUTH_USER_MODEL),
        ),
        migrations.AlterField(
            model_name='city',
            name='country',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='country_cities', to='seeker.Country'),
        ),
        migrations.AlterField(
            model_name='collection',
            name='owner',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='owner_collections', to='seeker.Profile'),
        ),
        migrations.AlterField(
            model_name='library',
            name='city',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='city_libraries', to='seeker.City'),
        ),
        migrations.AlterField(
            model_name='library',
            name='country',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='country_libraries', to='seeker.Country'),
        ),
        migrations.AlterField(
            model_name='library',
            name='lcity',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='lcity_libraries', to='seeker.Location'),
        ),
        migrations.AlterField(
            model_name='library',
            name='lcountry',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='lcountry_libraries', to='seeker.Location'),
        ),
        migrations.AlterField(
            model_name='library',
            name='location',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='location_libraries', to='seeker.Location'),
        ),
        migrations.AlterField(
            model_name='location',
            name='lcity',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='lcity_locations', to='seeker.Location'),
        ),
        migrations.AlterField(
            model_name='location',
            name='lcountry',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='lcountry_locations', to='seeker.Location'),
        ),
        migrations.AlterField(
            model_name='manuscript',
            name='lcity',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='lcity_manuscripts', to='seeker.Location'),
        ),
        migrations.AlterField(
            model_name='manuscript',
            name='lcountry',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='lcountry_manuscripts', to='seeker.Location'),
        ),
        migrations.AlterField(
            model_name='origin',
            name='location',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='location_origins', to='seeker.Location'),
        ),
        migrations.AlterField(
            model_name='profile',
            name='user',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='user_profiles', to=settings.AUTH_USER_MODEL),
        ),
        migrations.AlterField(
            model_name='provenance',
            name='location',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='location_provenances', to='seeker.Location'),
        ),
        migrations.AlterField(
            model_name='report',
            name='user',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='user_reports', to=settings.AUTH_USER_MODEL),
        ),
        migrations.AlterField(
            model_name='sermondescrequal',
            name='manu',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='sermondescr_super', to='seeker.Manuscript'),
        ),
        migrations.AlterField(
            model_name='sermonsignature',
            name='gsig',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='sermongoldsignatures', to='seeker.Signature'),
        ),
        migrations.AlterField(
            model_name='sourceinfo',
            name='profile',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='profile_sourceinfos', to='seeker.Profile'),
        ),
        migrations.AlterField(
            model_name='userkeyword',
            name='gold',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='gold_userkeywords', to='seeker.SermonGold'),
        ),
        migrations.AlterField(
            model_name='userkeyword',
            name='manu',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='manu_userkeywords', to='seeker.Manuscript'),
        ),
        migrations.AlterField(
            model_name='userkeyword',
            name='sermo',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='sermo_userkeywords', to='seeker.SermonDescr'),
        ),
        migrations.AlterField(
            model_name='userkeyword',
            name='super',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='super_userkeywords', to='seeker.EqualGold'),
        ),
        migrations.AlterField(
            model_name='visit',
            name='user',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='user_visits', to=settings.AUTH_USER_MODEL),
        ),
    ]
