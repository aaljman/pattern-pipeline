from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("datasets", "0003_transformrun_optional_transform_fields")]

    operations = [
        migrations.AddField(
            model_name="transformrun",
            name="result_columns",
            field=models.JSONField(default=list),
        ),
        migrations.AddField(
            model_name="transformrun",
            name="result_preview",
            field=models.JSONField(default=list),
        ),
    ]
