from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from streamlit.testing.v1 import AppTest


ROOT = Path(__file__).resolve().parents[1]


class StreamlitTests(unittest.TestCase):
    def test_analysis_document_and_payload_edit(self):
        app = AppTest.from_file(str(ROOT / 'streamlit_app.py'), default_timeout=15).run()
        self.assertFalse(app.exception)
        with patch('poc.analysis.llm_analysis') as api:
            next(b for b in app.button if b.label == '공고 분석하기').click().run()
            self.assertFalse(app.exception)
            api.assert_not_called()
        self.assertEqual(app.session_state['job']['mode'], 'offline')
        # Keep generated test documents in a temporary directory.
        with tempfile.TemporaryDirectory() as tmp:
            app.session_state['output'] = Path(tmp)
            next(b for b in app.button if b.label == '문서 생성·로컬 저장').click().run()
            self.assertFalse(app.exception)
            self.assertTrue((Path(tmp) / 'report.html').is_file())
            app.text_input(key='edit_resume_title').set_value('검토 완료 제목')
            next(b for b in app.button if b.label == '입력 문구 확정·저장').click().run()
            self.assertFalse(app.exception)
            self.assertEqual(app.session_state['payload']['resume_title'], '검토 완료 제목')
            self.assertIn('검토 완료 제목', (Path(tmp) / 'resume_payload.json').read_text(encoding='utf-8'))
            self.assertTrue(next(b for b in app.button if b.label == '준비된 사람인 폼에 입력').disabled)
            app.text_area(key='job_text').set_value('회사: 새기업\n직무: 새직무')
            next(b for b in app.button if b.label == '공고 분석하기').click().run()
            self.assertFalse(app.exception)
            self.assertIsNone(app.session_state['payload'])

    def test_empty_analysis_shows_error_without_crash(self):
        app = AppTest.from_file(str(ROOT / 'streamlit_app.py'), default_timeout=15).run()
        app.text_area(key='job_text').set_value(' ')
        next(b for b in app.button if b.label == '공고 분석하기').click().run()
        self.assertFalse(app.exception)
        self.assertTrue(app.error)
        self.assertIsNone(app.session_state['job'])


if __name__ == '__main__':
    unittest.main()
