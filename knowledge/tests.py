from unittest.mock import MagicMock, patch

from django.test import TestCase
from django.urls import reverse

from .services import build_rag_answer, fetch_url_content


class KnowledgeInboxApiTests(TestCase):
    def test_ingest_note_creates_item(self):
        response = self.client.post(
            reverse('ingest_item'),
            {'source_type': 'note', 'content': 'The product launch is scheduled for January 2027.'},
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()['source_type'], 'note')
        self.assertIn('The product launch is scheduled for January 2027.', response.json()['content'])

    def test_query_returns_answer_with_sources(self):
        self.client.post(
            reverse('ingest_item'),
            {'source_type': 'note', 'content': 'The quarterly planning meeting is on Tuesday at 3pm. Budget approval happens after the demo.'},
            content_type='application/json',
        )

        response = self.client.post(
            reverse('query_items'),
            {'question': 'When is the quarterly planning meeting?'},
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn('Tuesday', response.json()['answer'])
        self.assertTrue(response.json()['sources'])

    def test_note_ingest_auto_titles_from_content(self):
        response = self.client.post(
            reverse('ingest_item'),
            {'source_type': 'note', 'content': 'The launch is scheduled for January 12. We are finalizing the release notes.'},
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()['title'], 'The launch is scheduled for January 12.')

    def test_build_rag_answer_uses_full_context_when_no_openai_key(self):
        chunks = [
            {'content': 'The hardest thing we built was the conversion pipeline for our accessible PDF viewer.', 'source': {'title': 'Note 1'}},
            {'content': 'We used a multi-tier cache and parallel processing so conversions stayed fast and accurate for real users.', 'source': {'title': 'Note 2'}},
        ]

        result = build_rag_answer('What was the hardest thing you built?', chunks)

        self.assertIn('conversion pipeline', result['answer'].lower())
        self.assertIn('multi-tier cache', result['answer'].lower())
        self.assertTrue(len(result['answer']) > 120)

    def test_greeting_question_returns_agentic_response(self):
        response = self.client.post(
            reverse('query_items'),
            {'question': 'hello'},
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn('Hi', response.json()['answer'])
        self.assertIn('saved notes', response.json()['answer'].lower())

    @patch('knowledge.services.requests.post')
    def test_build_rag_answer_uses_gemini_provider_when_requested(self, mock_post):
        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {
            'candidates': [{'content': {'parts': [{'text': 'Gemini-powered answer from the saved context.'}]}}]
        }
        mock_post.return_value = mock_response

        chunks = [
            {'content': 'The team ships on Fridays after testing.', 'source': {'title': 'Delivery note'}},
            {'content': 'We review launch readiness every Wednesday.', 'source': {'title': 'Weekly review'}}
        ]

        with patch.dict('os.environ', {'GEMINI_API_KEY': 'fake-key'}):
            result = build_rag_answer('When do we ship?', chunks, provider='gemini')

        self.assertIn('Gemini-powered answer', result['answer'])
        mock_post.assert_called_once()

    @patch('knowledge.services.requests.get')
    def test_fetch_url_content_falls_back_when_blocked(self, mock_get):
        blocked_response = MagicMock()
        blocked_response.status_code = 403
        blocked_response.raise_for_status.side_effect = Exception('Forbidden')

        fallback_response = MagicMock()
        fallback_response.status_code = 200
        fallback_response.text = '<html><body><p>Medium content after fallback</p></body></html>'

        mock_get.side_effect = [blocked_response, fallback_response]

        result = fetch_url_content('https://medium.com/example')

        self.assertIn('Medium content after fallback', result)
