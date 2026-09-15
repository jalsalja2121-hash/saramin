"""POC 2: factual, editable application drafts and review reports."""
import html
import json
from pathlib import Path

STYLE = '''body{margin:0;background:#f4f6fb;color:#17233a;font:16px/1.8 "Malgun Gothic",sans-serif}
main{max-width:880px;margin:40px auto;padding:42px;background:white;border-radius:18px}
h1{font-size:30px;line-height:1.4}h2{margin-top:32px;font-size:21px;color:#225ad6}
.tag{color:#64748b;font-size:13px}pre{white-space:pre-wrap;overflow-wrap:anywhere;font:inherit}
@media print{body{background:white}main{margin:0;padding:15px}}'''


def validate_profile(profile):
    for key in ('name', 'summary'):
        if not isinstance(profile.get(key), str) or not profile[key].strip():
            raise ValueError(f'지원자 정보에 {key} 문자열이 필요합니다.')
    for key in ('skills', 'experiences'):
        if not isinstance(profile.get(key), list) or any(not isinstance(x, str) for x in profile[key]):
            raise ValueError(f'지원자 정보의 {key}는 문자열 목록이어야 합니다.')
    return profile


def compose(job, profile):
    validate_profile(profile)
    experience = '\n'.join(f'- {x}' for x in profile['experiences']) or '- [본인의 실제 프로젝트 경험을 작성하세요.]'
    introduction = (f"{job['company']}의 {job['title']} 직무에 지원하는 {profile['name']}입니다.\n\n"
                    f"{profile['summary']}\n\n제가 수행한 경험은 다음과 같습니다.\n{experience}\n\n"
                    f"보유 기술은 {', '.join(profile['skills']) or '[보유 기술 작성]'}입니다.\n\n"
                    '[지원 동기와 위 경험이 해당 업무에 기여하는 방법을 본인의 말로 보완하세요.]')
    fields = {'resume_title': f"{job['title']} 지원 | {profile['name']}",
              'intro_title': '지원 동기 및 직무 경험', 'intro_contents': introduction}
    parts = [('공고 요약', job['summary']), ('지원자 소개', profile['summary'])]
    labels = {'company': '기업명', 'title': '직무', 'location': '근무지',
              'employment_type': '고용형태', 'experience': '경력', 'deadline': '마감일'}
    parts.append(('채용 조건', '\n'.join(f'{v}: {job[k]}' for k, v in labels.items())))
    for key, label in [('responsibilities', '주요 업무'), ('requirements', '필수 요건'),
                       ('preferred', '우대 사항'), ('skills', '공고 기술'), ('questions', '확인할 질문')]:
        parts.append((label, '\n'.join(f'- {x}' for x in job[key]) or '공고에 명시되지 않음'))
    parts += [('지원자 경험 (입력 원문)', experience), ('자기소개서 초안', introduction),
              ('검토 메모', '대괄호 부분을 보완하고 회사명·직무·경험의 사실 여부를 확인하세요. '
                         '이 문서는 입력 사실을 조합한 템플릿 초안이며 합격 가능성을 평가하지 않습니다.')]
    return fields, parts


def write_documents(job, profile, output):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    fields, parts = compose(job, profile)
    mode = '오프라인 규칙 기반 시연 (LLM 미사용)' if job['mode'] == 'offline' else 'LLM 분석'
    md = '# 채용 공고 검토 및 지원 문서\n\n' + mode + '\n\n'
    md += '\n\n'.join(f'## {title}\n\n{text}' for title, text in parts) + '\n'
    html_body = ''.join(f'<section><h2>{html.escape(title)}</h2><pre>{html.escape(text)}</pre></section>'
                        for title, text in parts)
    page = (f'<!doctype html><html lang="ko"><meta charset="utf-8"><title>지원 검토 보고서</title>'
            f'<style>{STYLE}</style><main><p class="tag">RECRUITMENT POC · {mode}</p>'
            f'<h1>채용 공고 검토 및 지원 문서</h1>{html_body}</main></html>')
    (output / 'report.md').write_text(md, encoding='utf-8')
    (output / 'report.html').write_text(page, encoding='utf-8')
    (output / 'cover_letter.txt').write_text(fields['intro_contents'], encoding='utf-8')
    (output / 'resume_payload.json').write_text(json.dumps(fields, ensure_ascii=False, indent=2), encoding='utf-8')
    return fields
