"""A loopback-only Python form server for verifying Selenium + SQLite insertion."""
import html
import sqlite3
from contextlib import closing
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit
from .documents import STYLE

FORM = '''<p class="tag">TOOL 2 · LOCAL DEMO</p><h1>이력서 자동 입력 시연</h1>
<p>샘플 입력을 저장하면 로컬 SQLite 데이터베이스에 등록됩니다.</p>
<form method="post" action="/save">
<label for="title">이력서 제목</label><input required id="title" name="resume_title">
<label for="intro_title">자기소개서 제목</label><input required id="intro_title" name="intro_title">
<label for="intro_contents">자기소개서 내용</label><textarea required id="intro_contents" name="intro_contents" rows="15"></textarea>
<button id="save" type="submit">로컬 저장</button></form>'''


def create_server(output, port=0):
    root = Path(output).resolve()
    root.mkdir(parents=True, exist_ok=True)
    database = root / 'submissions.sqlite3'
    with closing(sqlite3.connect(database)) as conn, conn:
        conn.execute('CREATE TABLE IF NOT EXISTS submissions (id INTEGER PRIMARY KEY, resume_title TEXT NOT NULL, '
                     'intro_title TEXT NOT NULL, intro_contents TEXT NOT NULL, created_at TEXT DEFAULT CURRENT_TIMESTAMP)')

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def page(self, body, status=200):
            body = (f'<!doctype html><html lang="ko"><meta charset="utf-8"><title>채용 POC</title><style>{STYLE}'
                    'label{display:block;margin-top:20px}input,textarea{box-sizing:border-box;width:100%;padding:12px;'
                    'border:1px solid #bcc9de;border-radius:8px;font:inherit}button{margin-top:22px;padding:12px 24px;'
                    'background:#225ad6;color:white;border:0;border-radius:8px;font:inherit}'
                    f'</style><main>{body}</main></html>').encode('utf-8')
            self.send_response(status)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            parsed = urlsplit(self.path)
            if parsed.path == '/':
                self.page(FORM)
            elif parsed.path == '/success':
                record_id = parse_qs(parsed.query).get('id', [''])[0]
                with closing(sqlite3.connect(database)) as conn, conn:
                    row = conn.execute('SELECT id, resume_title, intro_title, intro_contents FROM submissions WHERE id=?',
                                       (record_id,)).fetchone()
                if not row:
                    return self.page('저장 내역을 찾을 수 없습니다.', 404)
                self.page(f'<h1 id="success" data-id="{row[0]}">저장 완료</h1><p>등록 번호: {row[0]}</p>'
                          + ''.join(f'<pre>{html.escape(v)}</pre>' for v in row[1:]))
            else:
                self.page('페이지를 찾을 수 없습니다.', 404)

        def do_POST(self):
            if self.path != '/save':
                return self.page('지원하지 않는 경로입니다.', 404)
            try:
                size = int(self.headers.get('Content-Length', '0'))
                if size <= 0 or size > 100000:
                    raise ValueError()
                form = parse_qs(self.rfile.read(size).decode('utf-8'))
                values = [form.get(k, [''])[0].replace('\r\n', '\n') for k in ('resume_title', 'intro_title', 'intro_contents')]
                if not all(v.strip() for v in values):
                    raise ValueError()
            except (ValueError, UnicodeError):
                return self.page('입력값을 확인하세요.', 400)
            with closing(sqlite3.connect(database)) as conn, conn:
                cursor = conn.execute('INSERT INTO submissions (resume_title, intro_title, intro_contents) VALUES (?,?,?)', values)
                record_id = cursor.lastrowid
            self.send_response(303)
            self.send_header('Location', f'/success?id={record_id}')
            self.send_header('Content-Length', '0')
            self.end_headers()

    return ThreadingHTTPServer(('127.0.0.1', port), Handler)
