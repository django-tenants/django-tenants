# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('customers', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='Domain',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('domain', models.CharField(unique=True, max_length=253, db_index=True)),
                ('is_primary', models.BooleanField(default=True)),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.RemoveField(
            model_name='client',
            name='domain_urls',
        ),
        migrations.AddField(
            model_name='domain',
            name='tenant',
            field=models.ForeignKey(related_name='domains', to='customers.Client'),
        ),
    ]
