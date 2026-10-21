from django.db import migrations, models


def queue_typed_stats_for_review(apps, schema_editor):
    """Instagram, TikTok and Facebook numbers that already exist were never checked: they wait for an admin."""
    PlatformStats = apps.get_model("social", "PlatformStats")
    PlatformStats.objects.exclude(platform="youtube").filter(is_verified=False).update(review_status="pending")


class Migration(migrations.Migration):
    dependencies = [("social", "0004_unverify_unproven_stats")]

    operations = [
        migrations.AddField(
            model_name="platformstats",
            name="review_status",
            field=models.CharField(
                choices=[("pending", "Waiting for an admin"), ("approved", "Approved"), ("rejected", "Rejected")],
                default="approved",
                max_length=10,
            ),
        ),
        migrations.AddField(
            model_name="platformstats",
            name="review_note",
            field=models.CharField(blank=True, default="", max_length=500),
        ),
        migrations.RunPython(queue_typed_stats_for_review, migrations.RunPython.noop),
    ]
