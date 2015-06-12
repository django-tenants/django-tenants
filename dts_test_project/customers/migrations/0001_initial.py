# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import django.contrib.postgres.fields
import django_tenants.postgresql_backend.base


class Migration(migrations.Migration):

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='Client',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('schema_name', models.CharField(unique=True, max_length=63, validators=[django_tenants.postgresql_backend.base._check_schema_name])),
                ('domain_urls', django.contrib.postgres.fields.ArrayField(base_field=models.CharField(unique=True, max_length=200), size=None)),
                ('name', models.CharField(max_length=100)),
                ('description', models.TextField(max_length=200)),
                ('created_on', models.DateField(auto_now_add=True)),
            ],
            options={
                'abstract': False,
            },
        ),
    ]
