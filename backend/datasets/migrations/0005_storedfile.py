from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("datasets", "0004_transformrun_result_preview")]

    operations = [
        migrations.CreateModel(
            name="StoredFile",
            fields=[
                ("name", models.CharField(max_length=500, primary_key=True, serialize=False)),
                ("content", models.BinaryField()),
                ("size_bytes", models.PositiveBigIntegerField()),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
        ),
    ]
