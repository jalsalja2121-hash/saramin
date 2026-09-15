"""Local Streamlit interface: python -m streamlit run streamlit_app.py."""
import json
import os
from pathlib import Path
from uuid import uuid4

import streamlit as st

from poc.analysis import analyze
from poc.automation import create_driver, SARAMIN_URL, validate_payload
from poc.documents import write_documents, compose
from poc.ui_workflow import run_local_demo, fill_saramin, save_json

ROOT = Path(__file__).resolve().parent
st.set_page_config(page_title='채용 업무 POC', page_icon=':material/work:', layout='wide')

# Per-session results are kept out of a shared cache. API calls run only on submit.
for key, value in {'job': None, 'payload': None, 'parts': None, 'output': None,
                   'driver': None, 'local_result': None, 'saramin_result': None}.items():
    st.session_state.setdefault(key, value)

with st.sidebar:
    st.title('채용 업무 POC')
    st.caption('Python · Streamlit · Selenium')
    st.divider()
    st.markdown('**진행 순서**\n\n1. 공고 분석\n2. 문서 작성·다운로드\n3. 사이트 자동 입력')
    st.info('샘플은 가상 기업과 가상 지원자입니다. 실제 사이트에 입력하기 전 본인의 정보로 바꿔주세요.')
    st.caption('프로젝트 저장 위치')
    st.code(str(ROOT), language=None)
    if st.session_state.output:
        st.caption('현재 결과 저장 위치')
        st.code(str(st.session_state.output), language=None)

st.title('공고에서 지원 문서까지')
st.write('공고를 분석하고 지원 문서를 만든 뒤, 검토한 내용을 사이트에 입력하세요.')
analysis_tab, document_tab, automation_tab = st.tabs(['1 · 공고 분석', '2 · 문서 작성', '3 · 자동 입력'])

with analysis_tab:
    st.subheader('채용 공고 분석')
    st.caption('공고 본문을 붙여넣으세요. 오프라인 시연은 회사: / 직무: / 자격요건: 같은 항목명을 인식합니다.')
    with st.form('analysis_form'):
        mode = st.selectbox('분석 방식', ['오프라인 시연 (LLM 미사용)', 'LLM API'], key='analysis_mode')
        job_text = st.text_area('채용 공고 본문', value=(ROOT / 'samples/job.txt').read_text(encoding='utf-8'),
                                height=330, key='job_text')
        st.caption('LLM API 선택 시 공고 본문이 OpenAI로 전송됩니다. OPENAI_API_KEY와 OPENAI_MODEL 환경변수를 설정하세요.')
        submitted = st.form_submit_button('공고 분석하기', type='primary', icon=':material/search:')
    if submitted:
        try:
            with st.spinner('공고를 분석하고 있습니다…'):
                job = analyze(job_text, 'llm' if mode == 'LLM API' else 'offline')
                output = ROOT / 'outputs' / 'streamlit' / uuid4().hex
                output.mkdir(parents=True, exist_ok=True)
                save_json(output / 'analysis.json', job)
                st.session_state.update(job=job, output=output, payload=None, parts=None,
                                        local_result=None, saramin_result=None)
            st.success('공고 분석을 저장했습니다. 2 · 문서 작성에서 초안을 만드세요.')
        except Exception as exc:
            st.error(str(exc))
    if st.session_state.job:
        job = st.session_state.job
        st.caption('마지막으로 성공한 분석 · ' + ('LLM API' if job['mode'] == 'llm' else '오프라인 규칙 기반 시연'))
        st.text(job['summary'])
        with st.container(border=True):
            for key, label in [('company', '기업'), ('title', '직무'), ('location', '근무지'),
                               ('employment_type', '고용형태'), ('experience', '경력'), ('deadline', '마감일')]:
                st.text(f'{label}: {job[key]}')
        for key, label in [('responsibilities', '담당 업무'), ('requirements', '필수 요건'),
                           ('preferred', '우대 사항'), ('skills', '기술'), ('questions', '확인할 질문')]:
            with st.expander(label, expanded=key in ('requirements', 'preferred')):
                st.text('\n'.join('• ' + x for x in job[key]) or '공고에 명시되지 않음')

with document_tab:
    st.subheader('지원자 정보로 문서 만들기')
    sample = json.loads((ROOT / 'samples/profile.json').read_text(encoding='utf-8'))
    if not st.session_state.job:
        st.info('먼저 1 · 공고 분석을 실행하세요.')
    with st.form('document_form'):
        name = st.text_input('이름', value=sample['name'], key='profile_name')
        summary = st.text_area('지원자 소개', value=sample['summary'], key='profile_summary')
        skills = st.text_input('보유 기술 (쉼표로 구분)', value=', '.join(sample['skills']), key='profile_skills')
        experiences = st.text_area('실제 프로젝트·업무 경험 (한 줄에 하나씩)',
                                   value='\n'.join(sample['experiences']), height=170, key='profile_experiences')
        generated = st.form_submit_button('문서 생성·로컬 저장', type='primary',
                                          disabled=st.session_state.job is None)
    if generated:
        try:
            profile = {'name': name, 'summary': summary,
                       'skills': [x.strip() for x in skills.split(',') if x.strip()],
                       'experiences': [x.strip() for x in experiences.splitlines() if x.strip()]}
            payload = write_documents(st.session_state.job, profile, st.session_state.output)
            _, parts = compose(st.session_state.job, profile)
            st.session_state.update(payload=payload, parts=parts, local_result=None, saramin_result=None)
            for key, value in payload.items():
                st.session_state['edit_' + key] = value
            st.success('지원 문서를 로컬 폴더에 저장했습니다.')
        except Exception as exc:
            st.error(str(exc))
    if st.session_state.parts:
        st.caption('입력 사실을 조합한 템플릿 초안입니다. 대괄호 부분을 보완하세요.')
        with st.expander('보고서 미리보기', expanded=True):
            for title, text in st.session_state.parts:
                st.markdown('**' + title + '**')
                st.text(text)
        with st.container(horizontal=True):
            for filename, label, mime in [('report.html', 'HTML 보고서', 'text/html'),
                                           ('report.md', 'Markdown 문서', 'text/markdown'),
                                           ('cover_letter.txt', '자기소개서 TXT', 'text/plain')]:
                path = st.session_state.output / filename
                st.download_button(label, path.read_bytes(), file_name=filename, mime=mime)

with automation_tab:
    st.subheader('검토한 문서를 자동 입력')
    if not st.session_state.payload:
        st.info('2 · 문서 작성에서 문서를 생성하면 자동 입력을 사용할 수 있습니다.')
    else:
        st.caption('아래 수정은 사이트 입력용 JSON에 반영됩니다. 앞 단계의 보고서·TXT 원본은 유지됩니다.')
        with st.form('payload_form'):
            title = st.text_input('이력서 제목', key='edit_resume_title')
            intro_title = st.text_input('자기소개서 제목', key='edit_intro_title')
            intro = st.text_area('자기소개서 본문', height=280, key='edit_intro_contents')
            updated = st.form_submit_button('입력 문구 확정·저장')
        if updated:
            try:
                payload = validate_payload({'resume_title': title, 'intro_title': intro_title, 'intro_contents': intro})
                save_json(st.session_state.output / 'resume_payload.json', payload)
                st.session_state.update(payload=payload, local_result=None, saramin_result=None)
                st.success('자동 입력에 사용할 문구를 저장했습니다.')
            except Exception as exc:
                st.error(str(exc))
        with st.expander('현재 확정된 입력 문구 확인'):
            st.json(st.session_state.payload)
        st.download_button('확정된 입력 JSON 다운로드', json.dumps(st.session_state.payload, ensure_ascii=False, indent=2),
                           file_name='resume_payload.json', mime='application/json')
        with st.container(border=True):
            st.markdown('### 로컬 사이트 시연')
            st.write('Chrome이 확정된 문구를 입력하고 저장한 뒤, 데이터베이스 내용까지 확인합니다.')
            if st.button('로컬 자동 입력·저장 실행', key='run_local', type='primary'):
                try:
                    with st.spinner('브라우저 입력과 저장을 확인하고 있습니다…'):
                        st.session_state.local_result = run_local_demo(st.session_state.payload, st.session_state.output)
                except Exception as exc:
                    st.error(str(exc))
            if st.session_state.local_result:
                st.success('자동 입력 → 저장 → DB 내용 일치 확인 완료')
                st.json(st.session_state.local_result)
                st.image(str(st.session_state.output / '02_saved.png'), caption='로컬 저장 완료 화면')
        with st.container(border=True):
            st.markdown('### 사람인 이력서 입력')
            st.write('새 Chrome에서 직접 로그인하고 자기소개서 → 추가 → 직접 입력하기를 열어주세요.')
            st.caption('입력 대상: 이력서 제목·자기소개서 제목·본문. 최종 저장은 사람인 화면에서 직접 선택합니다.')
            if st.button('사람인 Chrome 열기', disabled=st.session_state.driver is not None):
                driver = None
                try:
                    with st.spinner('Chrome을 열고 있습니다…'):
                        driver = create_driver(headless=False)
                        driver.get(SARAMIN_URL)
                    st.session_state.driver = driver
                    st.rerun()
                except Exception as exc:
                    if driver:
                        driver.quit()
                    st.error(str(exc))
            approved = st.checkbox('확정된 문구를 확인했으며 내 사람인 계정에 입력합니다.', key='approve_insert')
            overwrite = st.checkbox('기존 입력 내용을 교체합니다.', key='overwrite')
            st.caption('사이트 자체의 임시 저장이 발생할 수 있습니다. 작업 중 이 Streamlit 탭을 새로고침하지 마세요.')
            if st.button('준비된 사람인 폼에 입력', disabled=not approved or st.session_state.driver is None):
                try:
                    with st.spinner('사람인 입력값을 확인하고 있습니다…'):
                        st.session_state.saramin_result = fill_saramin(st.session_state.driver, st.session_state.payload,
                                                                       st.session_state.output, overwrite)
                except Exception as exc:
                    st.error(str(exc))
            if st.session_state.saramin_result:
                st.success('입력 확인 완료. 사람인에서 검토 후 자기소개서 저장 → 작성완료를 선택하세요.')
            if st.button('작업 완료 · Chrome 닫기', disabled=st.session_state.driver is None):
                try:
                    st.session_state.driver.quit()
                except Exception as exc:
                    st.warning(f'브라우저 종료 상태를 확인하세요: {exc}')
                finally:
                    st.session_state.driver = None
                st.rerun()
