from django.db import migrations


def create_roles(apps, schema_editor):
    Role = apps.get_model('api', 'Role')
    for label in ('ADMIN', 'USER'):
        Role.objects.get_or_create(label=label)


def delete_roles(apps, schema_editor):
    apps.get_model('api', 'Role').objects.filter(label__in=('ADMIN', 'USER')).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(create_roles, delete_roles),
    ]
