# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
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
                ('name', models.CharField(max_length=100, null=True, blank=True)),
                ('description', models.TextField(max_length=200, null=True, blank=True)),
                ('created_on', models.DateField(auto_now_add=True)),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='Domain',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('domain', models.CharField(unique=True, max_length=253, db_index=True)),
                ('is_primary', models.BooleanField(default=True)),
                ('tenant', models.ForeignKey(related_name='domains', to='customers.Client')),
            ],
            options={
                'abstract': False,
            },
        ),
    ]
