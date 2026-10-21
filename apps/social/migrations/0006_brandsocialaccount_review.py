from django.db import migrations, models


def queue_typed_links_for_review(apps, schema_editor):
    """Typed Instagram, TikTok and Facebook links were never checked: they now wait for an admin."""
    BrandSocialAccount = apps.get_model("social", "BrandSocialAccount")
    BrandSocialAccount.objects.exclude(platform="youtube").filter(is_verified=False).update(review_status="pending")


class Migration(migrations.Migration):
    dependencies = [("social", "0005_platformstats_review")]

    operations = [
        migrations.AddField(
            model_name="brandsocialaccount",
            name="review_status",
            field=models.CharField(
                choices=[("pending", "Waiting for an admin"), ("approved", "Approved"), ("rejected", "Rejected")],
                default="approved",
                max_length=10,
            ),
        ),
        migrations.AddField(
            model_name="brandsocialaccount",
            name="review_note",
            field=models.CharField(blank=True, default="", max_length=500),
        ),
        migrations.RunPython(queue_typed_links_for_review, migrations.RunPython.noop),
    ]
