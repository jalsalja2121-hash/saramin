"""Independent CLI commands plus a full local proof-of-concept run."""
import argparse
import json
import sqlite3
import sys
import threading
from contextlib import closing
from pathlib import Path
from poc.analysis import analyze, validate_analysis
from poc.documents import write_documents
from poc.demo_site import create_server

ROOT = Path(__file__).resolve().parent


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def save_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')


def run_pipeline(args):
    text = Path(args.job).read_text(encoding='utf-8-sig')
    result = analyze(text, args.mode)
    save_json(Path(args.output) / 'analysis.json', result)
    payload = write_documents(result, read_json(args.profile), args.output)
    print(f'분석 및 문서 생성 완료: {Path(args.output).resolve()} (분석 모드: {args.mode})')
    return payload


def main(argv=None):
    parser = argparse.ArgumentParser(description='Python 채용 분석 · 문서 작성 · Selenium 자동 입력 POC')
    sub = parser.add_subparsers(dest='command', required=True)
    for command in ('analyze', 'pipeline', 'demo'):
        p = sub.add_parser(command)
        p.add_argument('--job', default=str(ROOT / 'samples/job.txt'))
        p.add_argument('--mode', choices=['offline', 'llm'], default='offline')
        p.add_argument('--output', default=str(ROOT / 'outputs'))
        if command != 'analyze':
            p.add_argument('--profile', default=str(ROOT / 'samples/profile.json'))
        if command == 'demo':
            p.add_argument('--driver-path', help='수동 설치한 chromedriver 경로 (선택)')
    p = sub.add_parser('document')
    p.add_argument('--analysis', default=str(ROOT / 'outputs/analysis.json'))
    p.add_argument('--profile', default=str(ROOT / 'samples/profile.json'))
    p.add_argument('--output', default=str(ROOT / 'outputs'))
    p = sub.add_parser('serve')
    p.add_argument('--port', type=int, default=8765)
    p.add_argument('--output', default=str(ROOT / 'outputs'))
    p = sub.add_parser('saramin')
    p.add_argument('--payload', default=str(ROOT / 'outputs/resume_payload.json'))
    p.add_argument('--output', default=str(ROOT / 'outputs'))
    p.add_argument('--overwrite', action='store_true')
    p.add_argument('--driver-path')
    args = parser.parse_args(argv)
    try:
        if args.command == 'analyze':
            result = analyze(Path(args.job).read_text(encoding='utf-8-sig'), args.mode)
            save_json(Path(args.output) / 'analysis.json', result)
            print(f'공고 분석 완료: {args.output}/analysis.json')
        elif args.command == 'document':
            job = validate_analysis(read_json(args.analysis))
            if job.get('mode') not in ('offline', 'llm'):
                raise ValueError('분석 JSON에 올바른 mode가 필요합니다.')
            write_documents(job, read_json(args.profile), args.output)
            print(f'문서 생성 완료: {args.output}')
        elif args.command in ('pipeline', 'demo'):
            payload = run_pipeline(args)
            if args.command == 'demo':
                from poc.automation import automate_local
                server = create_server(args.output)
                thread = threading.Thread(target=server.serve_forever, daemon=True)
                thread.start()
                try:
                    result = automate_local(f'http://127.0.0.1:{server.server_port}', payload, args.output, args.driver_path)
                    with closing(sqlite3.connect(Path(args.output) / 'submissions.sqlite3')) as conn, conn:
                        row = conn.execute('SELECT resume_title, intro_title, intro_contents FROM submissions WHERE id=?',
                                           (result['record_id'],)).fetchone()
                    if tuple(payload[k] for k in ('resume_title', 'intro_title', 'intro_contents')) != row:
                        raise RuntimeError('브라우저 저장값과 데이터베이스 내용이 다릅니다.')
                    result['database_verified'] = True
                    save_json(Path(args.output) / 'automation_result.json', result)
                    print(f"Selenium 입력 → 저장 → DB 내용 일치 확인 완료. 등록 번호: {result['record_id']}")
                finally:
                    server.shutdown()
                    server.server_close()
                    thread.join(timeout=5)
        elif args.command == 'serve':
            server = create_server(args.output, args.port)
            print(f'로컬 시연 사이트: http://127.0.0.1:{server.server_port} (종료: Ctrl+C)', flush=True)
            try:
                server.serve_forever()
            finally:
                server.server_close()
        elif args.command == 'saramin':
            from poc.automation import automate_saramin
            result = automate_saramin(read_json(args.payload), args.output, args.overwrite, args.driver_path)
            print(json.dumps(result, ensure_ascii=False))
    except KeyboardInterrupt:
        print('\n실행을 중단했습니다.')
        return 130
    except Exception as exc:
        print(f'실행 실패: {exc}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
