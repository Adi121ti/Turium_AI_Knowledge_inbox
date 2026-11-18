from django.core.management.base import BaseCommand

from knowledge.models import KnowledgeItem
from knowledge.services import build_note_title


class Command(BaseCommand):
    help = 'Backfill note titles from the first sentence of each note.'

    def handle(self, *args, **options):
        updated = 0
        for item in KnowledgeItem.objects.filter(source_type='note'):
            generated = build_note_title(item.content, 'Untitled note')
            if item.title != generated:
                item.title = generated
                item.save(update_fields=['title'])
                updated += 1

        self.stdout.write(self.style.SUCCESS(f'Updated {updated} note titles.'))
