# -*- coding: utf-8 -*-
# Generated by Django 1.9.5 on 2016-06-11 04:12
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('shop', '0012_auto_20160610_1808'),
    ]

    operations = [
        migrations.AlterField(
            model_name='carousel',
            name='image',
            field=models.ImageField(blank=True, null=True, upload_to=b'carousel/images'),
        ),
    ]
