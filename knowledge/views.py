import json

from django.core.exceptions import ValidationError
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from .models import KnowledgeChunk, KnowledgeItem
from .services import (
    EmbeddingService,
    build_agent_greeting_answer,
    build_note_title,
    build_rag_answer,
    chunk_text,
    cosine_similarity,
    fetch_url_content,
    is_greeting_question,
)


def _serialize_item(item):
    return {
        'id': item.id,
        'source_type': item.source_type,
        'title': item.title,
        'content': item.content,
        'source_url': item.source_url,
        'created_at': item.created_at.isoformat(),
        'chunk_count': item.chunks.count(),
        'metadata': item.metadata,
    }


def _index_item(item, text, source_url=''):
    chunks = chunk_text(text)
    if not chunks:
        return

    service = EmbeddingService()
    for index, chunk in enumerate(chunks):
        embedding = service.embed(chunk)
        KnowledgeChunk.objects.create(
            item=item,
            chunk_index=index,
            content=chunk,
            embedding=embedding,
        )

    item.metadata = {'source_url': source_url or item.source_url, 'chunks': len(chunks)}
    item.save(update_fields=['metadata'])


@api_view(['POST'])
@permission_classes([AllowAny])
def ingest_item(request):
    payload = request.data if hasattr(request, 'data') and isinstance(request.data, dict) else json.loads(request.body or '{}')
    source_type = str(payload.get('source_type', 'note')).lower()
    text = (payload.get('content') or '').strip()
    item_url = (payload.get('url') or '').strip()
    title = (payload.get('title') or '').strip()

    if source_type not in {'note', 'url'}:
        return Response({'error': 'source_type must be "note" or "url".'}, status=status.HTTP_400_BAD_REQUEST)

    if source_type == 'url' and not item_url:
        return Response({'error': 'URL is required when source_type is "url".'}, status=status.HTTP_400_BAD_REQUEST)

    if source_type == 'note' and not text:
        return Response({'error': 'Note content is required.'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        if source_type == 'url':
            fetched = fetch_url_content(item_url)
            text = fetched or text
            if not text:
                return Response({'error': 'The URL did not produce any readable content.'}, status=status.HTTP_400_BAD_REQUEST)
            title = title or item_url.split('//')[-1].split('/')[0]
        else:
            title = title or build_note_title(text)

        item = KnowledgeItem.objects.create(
            source_type=source_type,
            title=title or 'Untitled note',
            content=text,
            source_url=item_url,
            metadata={'source_url': item_url, 'source_type': source_type},
        )
        _index_item(item, text, source_url=item_url)
        return Response(_serialize_item(item), status=status.HTTP_201_CREATED)
    except ValueError as exc:
        return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
    except ValidationError as exc:
        return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
    except Exception as exc:
        return Response({'error': f'Failed to ingest item: {exc}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([AllowAny])
def list_items(request):
    items = KnowledgeItem.objects.all()
    return Response([_serialize_item(item) for item in items])


@api_view(['POST'])
@permission_classes([AllowAny])
def query_items(request):
    payload = request.data if hasattr(request, 'data') and isinstance(request.data, dict) else json.loads(request.body or '{}')
    raw_question = str(payload.get('question', '')).strip()
    messages = payload.get('messages') or []

    if not raw_question and isinstance(messages, list) and messages:
        for message in reversed(messages):
            content = str(message.get('content') or message.get('text') or '').strip()
            if content:
                raw_question = content
                break

    question = raw_question
    if not question:
        return Response({'error': 'A question is required.'}, status=status.HTTP_400_BAD_REQUEST)

    if is_greeting_question(question):
        return Response({
            'answer': build_agent_greeting_answer(question),
            'sources': [],
            'matches': [],
        }, status=status.HTTP_200_OK)

    chunks = list(KnowledgeChunk.objects.select_related('item').all())
    if not chunks:
        return Response({'answer': 'No saved content is available yet.', 'sources': [], 'matches': []}, status=status.HTTP_200_OK)

    service = EmbeddingService()
    query_vector = service.embed(question)
    ranked = []
    for chunk in chunks:
        score = cosine_similarity(query_vector, chunk.embedding)
        if score <= 0:
            continue
        ranked.append({
            'score': score,
            'content': chunk.content,
            'source': {
                'id': chunk.item.id,
                'title': chunk.item.title or build_note_title(chunk.item.content),
                'source_type': chunk.item.source_type,
                'source_url': chunk.item.source_url,
                'snippet': chunk.content,
                'created_at': chunk.item.created_at.isoformat(),
            },
        })

    ranked.sort(key=lambda item: item['score'], reverse=True)
    top_chunks = ranked[:3]
    result = build_rag_answer(question, top_chunks, history=messages, provider=payload.get('provider'))
    return Response({
        'answer': result['answer'],
        'sources': [
            {
                **item,
                'snippet': item.get('snippet') or item.get('content') or '',
                'created_at': item.get('created_at') or item.get('source', {}).get('created_at'),
            }
            for item in result['sources']
        ],
        'matches': [{'score': round(item['score'], 4), 'source': item['source']} for item in top_chunks],
    })
