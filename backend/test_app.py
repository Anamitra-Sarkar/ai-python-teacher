"""
Unit tests for the AI Python Teacher backend.
"""
import json
import unittest
from unittest.mock import patch, MagicMock

# Import the Flask app
from app import app
from gemini_ai import (
    build_tutor_prompt,
    sanitize_tutor_output,
    MAX_CODE_BLOCK_LINES,
    SUSPICIOUS_LINE_THRESHOLD,
    MAX_OUTPUT_LINES,
)


class TestHealthEndpoint(unittest.TestCase):
    """Tests for the /health endpoint."""

    def setUp(self):
        """Set up test client."""
        app.testing = True
        self.client = app.test_client()

    def test_health_returns_ok(self):
        """Health endpoint should return status ok."""
        response = self.client.get('/health')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertEqual(data['status'], 'ok')


class TestAskAiEndpoint(unittest.TestCase):
    """Tests for the /ask-ai endpoint."""

    def setUp(self):
        """Set up test client."""
        app.testing = True
        self.client = app.test_client()

    def test_ask_ai_requires_json(self):
        """Should return 400 when Content-Type is not JSON."""
        response = self.client.post('/ask-ai', data='not json')
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.data)
        self.assertIn('error', data)
        self.assertIn('Content-Type', data['error'])

    def test_ask_ai_requires_question(self):
        """Should return 400 when question field is missing."""
        response = self.client.post(
            '/ask-ai',
            data=json.dumps({'topic': 'test'}),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.data)
        self.assertIn('question', data['error'])

    def test_ask_ai_rejects_large_code(self):
        """Should return 413 when code is too large."""
        large_code = 'x' * 100000
        response = self.client.post(
            '/ask-ai',
            data=json.dumps({'question': 'test', 'code': large_code}),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 413)
        data = json.loads(response.data)
        self.assertIn('too large', data['error'])

    @patch('app.generate_response')
    def test_ask_ai_returns_answer(self, mock_generate):
        """Should return answer when API call succeeds."""
        mock_generate.return_value = ('This is the tutor response', None)
        
        response = self.client.post(
            '/ask-ai',
            data=json.dumps({'question': 'How do I use loops?', 'level': 'beginner'}),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertIn('answer', data)
        self.assertIn('request_id', data)
        self.assertEqual(data['answer'], 'This is the tutor response')

    @patch('app.generate_response')
    def test_ask_ai_handles_api_error(self, mock_generate):
        """Should return 502 when AI API fails."""
        mock_generate.return_value = (None, {'message': 'API key invalid'})
        
        response = self.client.post(
            '/ask-ai',
            data=json.dumps({'question': 'test question'}),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 502)
        data = json.loads(response.data)
        self.assertIn('AI provider error', data['error'])


class TestBuildTutorPrompt(unittest.TestCase):
    """Tests for the build_tutor_prompt function."""

    def test_prompt_contains_question(self):
        """Prompt should contain the student's question."""
        prompt = build_tutor_prompt(
            topic='loops',
            code='for i in range(10): print(i)',
            question='Why does this print 0-9?',
            level='beginner'
        )
        self.assertIn('Why does this print 0-9?', prompt)

    def test_prompt_contains_code(self):
        """Prompt should contain the student's code."""
        code = 'def hello(): print("hello")'
        prompt = build_tutor_prompt(
            topic='functions',
            code=code,
            question='Is this correct?',
            level='intermediate'
        )
        self.assertIn(code, prompt)

    def test_prompt_normalizes_level(self):
        """Prompt should normalize invalid levels to beginner."""
        prompt = build_tutor_prompt(
            topic='test',
            code='',
            question='test',
            level='INVALID_LEVEL'
        )
        self.assertIn('Level: beginner', prompt)

    def test_prompt_handles_empty_inputs(self):
        """Prompt should handle empty optional inputs."""
        prompt = build_tutor_prompt(
            topic='',
            code='',
            question='What is a variable?',
            level=''
        )
        self.assertIn('(unspecified)', prompt)
        self.assertIn('What is a variable?', prompt)


class TestSanitizeTutorOutput(unittest.TestCase):
    """Tests for the sanitize_tutor_output function."""

    def test_passes_through_short_code(self):
        """Should pass through code blocks with few lines."""
        text = """Here's an example:
```python
x = 1
print(x)
```
That's it!"""
        result = sanitize_tutor_output(text)
        self.assertIn('x = 1', result)
        self.assertIn('print(x)', result)

    def test_omits_long_code_blocks(self):
        """Should omit code blocks with many lines."""
        long_code = '\n'.join([f'line{i} = {i}' for i in range(20)])
        text = f"""Here's the solution:
```python
{long_code}
```
Done!"""
        result = sanitize_tutor_output(text)
        self.assertIn('[Code omitted', result)
        self.assertNotIn('line10', result)

    def test_handles_empty_input(self):
        """Should handle empty input."""
        self.assertEqual(sanitize_tutor_output(''), '')
        self.assertEqual(sanitize_tutor_output(None), None)

    def test_truncates_suspicious_output(self):
        """Should truncate output with many suspicious lines."""
        suspicious_lines = '\n'.join([f'import module{i}' for i in range(20)])
        text = f"Here's some code:\n{suspicious_lines}\nEnd."
        result = sanitize_tutor_output(text)
        self.assertIn('[Output truncated', result)


class TestModuleIntegration(unittest.TestCase):
    """Integration tests for module connectivity."""

    def test_app_imports_from_config(self):
        """App should successfully import from config module."""
        from config import CORS_ORIGINS, logger
        self.assertIsNotNone(CORS_ORIGINS)
        self.assertIsNotNone(logger)

    def test_app_imports_from_gemini_ai(self):
        """App should successfully import from gemini_ai module."""
        from gemini_ai import build_tutor_prompt, generate_response, sanitize_tutor_output
        self.assertTrue(callable(build_tutor_prompt))
        self.assertTrue(callable(generate_response))
        self.assertTrue(callable(sanitize_tutor_output))

    def test_constants_are_defined(self):
        """Constants should be properly defined."""
        self.assertIsInstance(MAX_CODE_BLOCK_LINES, int)
        self.assertIsInstance(SUSPICIOUS_LINE_THRESHOLD, int)
        self.assertIsInstance(MAX_OUTPUT_LINES, int)
        self.assertGreater(MAX_CODE_BLOCK_LINES, 0)
        self.assertGreater(SUSPICIOUS_LINE_THRESHOLD, 0)
        self.assertGreater(MAX_OUTPUT_LINES, 0)


if __name__ == '__main__':
    unittest.main()
