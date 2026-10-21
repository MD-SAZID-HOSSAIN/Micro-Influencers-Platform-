from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("campaigns", "0003_campaignmedia")]

    operations = [
        migrations.AddField(
            model_name="campaign",
            name="allow_withdrawal",
            field=models.BooleanField(default=True),
        ),
    ]
