"""Streamlit-independent helpers for local runs and interactive browser steps."""
from contextlib import closing
import json
from pathlib import Path
import sqlite3
import threading
from urllib.parse import urlsplit

from .automation import automate_local, fill_fields, SARAMIN_URL
from .demo_site import create_server


def save_json(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')


def run_local_demo(payload, output):
    output = Path(output)
    server = create_server(output)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        result = automate_local(f'http://127.0.0.1:{server.server_port}', payload, output)
        with closing(sqlite3.connect(output / 'submissions.sqlite3')) as conn:
            row = conn.execute('SELECT resume_title, intro_title, intro_contents FROM submissions WHERE id=?',
                               (result['record_id'],)).fetchone()
        if row != tuple(payload[k].replace('\r\n', '\n') for k in ('resume_title', 'intro_title', 'intro_contents')):
            raise RuntimeError('저장된 데이터가 입력 문서와 다릅니다.')
        result['database_verified'] = True
        save_json(output / 'automation_result.json', result)
        return result
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def fill_saramin(driver, payload, output, overwrite=False):
    current = urlsplit(driver.current_url)
    if (current.scheme, current.hostname, current.path) != ('https', 'www.saramin.co.kr', urlsplit(SARAMIN_URL).path):
        raise ValueError('로그인 후 사람인 이력서 작성 페이지에서 자기소개서 직접 입력 폼을 열어주세요.')
    fields = fill_fields(driver, payload, {
        'resume_title': 'input#title',
        'intro_title': '#introduce input[name="intro_title[]"]',
        'intro_contents': '#introduce textarea[name="intro_contents[]"]',
    }, overwrite=overwrite)
    result = {'status': 'filled_not_submitted', 'target': 'saramin', 'fields_verified': fields}
    save_json(Path(output) / 'saramin_result.json', result)
    return result
