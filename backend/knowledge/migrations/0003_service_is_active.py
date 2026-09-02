from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("knowledge", "0002_procedure_versions")]

    operations = [
        migrations.AddField(
            model_name="service",
            name="is_active",
            field=models.BooleanField(default=False),
        ),
    ]
