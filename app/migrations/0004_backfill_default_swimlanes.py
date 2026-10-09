from django.db import migrations


def backfill_default_swimlanes(apps, schema_editor):
    """Give every board a swimlane and every card a swimlane on its board.

    Older signups created boards without one; the board page used to create
    it on first view, which it no longer does.
    """
    Board = apps.get_model('app', 'Board')
    Swimlane = apps.get_model('app', 'Swimlane')
    Card = apps.get_model('app', 'Card')

    for board in Board.objects.all():
        first = Swimlane.objects.filter(board=board).order_by('position').first()
        if first is None:
            first = Swimlane.objects.create(board=board, name='Default', position=0, height=300)
        Card.objects.filter(column__board=board, swimlane__isnull=True).update(swimlane=first)


class Migration(migrations.Migration):

    dependencies = [
        ('app', '0003_remove_unused_models_and_fields'),
    ]

    operations = [
        migrations.RunPython(backfill_default_swimlanes, migrations.RunPython.noop),
    ]
