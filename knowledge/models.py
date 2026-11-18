from django.db import models


class KnowledgeItem(models.Model):
    SOURCE_NOTE = 'note'
    SOURCE_URL = 'url'
    SOURCE_CHOICES = [
        (SOURCE_NOTE, 'Note'),
        (SOURCE_URL, 'URL'),
    ]

    source_type = models.CharField(max_length=10, choices=SOURCE_CHOICES, default=SOURCE_NOTE)
    title = models.CharField(max_length=200, blank=True, default='')
    content = models.TextField()
    source_url = models.URLField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.title or self.source_url or 'Knowledge item'


class KnowledgeChunk(models.Model):
    item = models.ForeignKey(KnowledgeItem, related_name='chunks', on_delete=models.CASCADE)
    chunk_index = models.IntegerField(default=0)
    content = models.TextField()
    embedding = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['item_id', 'chunk_index']

    def __str__(self):
        return f'{self.item_id}:{self.chunk_index}'
