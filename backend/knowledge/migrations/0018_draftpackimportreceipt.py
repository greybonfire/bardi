import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("knowledge", "0017_procedureversionauditevent_review_mode")]

    operations = [
        migrations.CreateModel(
            name="DraftPackImportReceipt",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
                    ),
                ),
                ("request_digest", models.CharField(max_length=64)),
                ("post_revision", models.CharField(max_length=64)),
                (
                    "version",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="draft_pack_receipt",
                        to="knowledge.procedureversion",
                    ),
                ),
            ],
        ),
    ]
