import json
import os
from pathlib import Path
import tempfile
import sqlite3
import threading
from contextlib import closing
import unittest
from urllib.parse import urlencode
from urllib.request import urlopen
from unittest.mock import patch
from poc.analysis import analyze, llm_analysis
from poc.documents import write_documents
from poc.automation import fill_fields
from poc.demo_site import create_server


class WorkflowTests(unittest.TestCase):
    def test_form_roundtrip_normalizes_browser_newlines(self):
        with tempfile.TemporaryDirectory() as tmp:
            server = create_server(tmp)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                data = urlencode({'resume_title': '제목', 'intro_title': '소개',
                                  'intro_contents': '첫 줄\r\n다음 줄'}).encode()
                with urlopen(f'http://127.0.0.1:{server.server_port}/save', data=data, timeout=3) as response:
                    self.assertIn('저장 완료', response.read().decode('utf-8'))
                with closing(sqlite3.connect(Path(tmp) / 'submissions.sqlite3')) as conn, conn:
                    self.assertEqual(conn.execute('SELECT intro_contents FROM submissions').fetchone()[0], '첫 줄\n다음 줄')
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=3)

    def test_offline_extracts_requirements_without_inventing_missing_details(self):
        result = analyze('회사: 예시\n직무: 개발자\n자격요건:\n- Python\n우대사항:\n- SQL')
        self.assertEqual(result['requirements'], ['Python'])
        self.assertEqual(result['preferred'], ['SQL'])
        self.assertEqual(result['location'], '공고에 명시되지 않음')
        self.assertEqual(result['mode'], 'offline')

    def test_empty_job_rejected(self):
        with self.assertRaises(ValueError):
            analyze('  ')

    def test_real_mode_never_silently_falls_back(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(ValueError, 'OPENAI_API_KEY'):
                analyze('회사: 예시', 'llm')

    def test_api_response_parsed_and_schema_requested(self):
        result = analyze('회사: 예시\n직무: 개발자')
        result.pop('mode')
        result.pop('source_text')
        response = unittest.mock.MagicMock()
        response.__enter__.return_value.read.return_value = json.dumps({
            'status': 'completed', 'output': [{'content': [{'type': 'output_text', 'text': json.dumps(result)}]}]
        }).encode()
        with patch.dict(os.environ, {'OPENAI_API_KEY': 'test-key', 'OPENAI_MODEL': 'test-model'}):
            with patch('poc.analysis.urlopen', return_value=response) as api:
                self.assertEqual(llm_analysis('회사: 예시')['company'], '예시')
                payload = json.loads(api.call_args.args[0].data)
                self.assertEqual(payload['text']['format']['type'], 'json_schema')
                self.assertFalse(payload['store'])

    def test_incomplete_llm_response_rejected(self):
        response = unittest.mock.MagicMock()
        response.__enter__.return_value.read.return_value = b'{"status":"incomplete"}'
        with patch.dict(os.environ, {'OPENAI_API_KEY': 'test-key', 'OPENAI_MODEL': 'test-model'}):
            with patch('poc.analysis.urlopen', return_value=response):
                with self.assertRaises(RuntimeError):
                    llm_analysis('test')

    def test_documents_escape_html_and_preserve_experience(self):
        job = analyze('회사: <script>alert(1)</script>\n직무: 개발자')
        profile = {'name': '테스트', 'summary': '직접 작성한 소개', 'skills': ['Python'],
                   'experiences': ['직접 작성한 실제 경험']}
        with tempfile.TemporaryDirectory() as tmp:
            payload = write_documents(job, profile, tmp)
            page = (Path(tmp) / 'report.html').read_text(encoding='utf-8')
            self.assertNotIn('<script>', page)
            self.assertIn('&lt;script&gt;', page)
            self.assertIn('직접 작성한 실제 경험', payload['intro_contents'])
            self.assertEqual(json.loads((Path(tmp) / 'resume_payload.json').read_text(encoding='utf-8')), payload)

    def test_existing_content_blocks_all_changes(self):
        field = unittest.mock.MagicMock()
        field.get_attribute.return_value = '기존 이력서'
        payload = {'resume_title': '새 제목', 'intro_title': '소개', 'intro_contents': '본문'}
        with patch('poc.automation.visible_element', return_value=field):
            with self.assertRaisesRegex(ValueError, '기존 내용'):
                fill_fields(None, payload, {'resume_title': '#title'})
        field.clear.assert_not_called()
        field.send_keys.assert_not_called()


if __name__ == '__main__':
    unittest.main()
