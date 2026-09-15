"""POC 3: Selenium local insertion and an observed Saramin form adapter."""
import json
from pathlib import Path
from urllib.parse import urlsplit

SARAMIN_URL = 'https://www.saramin.co.kr/zf_user/member/resume-manage/write?template_cd=1'


def validate_payload(payload):
    for key in ('resume_title', 'intro_title', 'intro_contents'):
        if not isinstance(payload.get(key), str) or not payload[key].strip():
            raise ValueError(f'자동 입력 데이터가 비어 있습니다: {key}')
    return payload


def create_driver(headless=True, driver_path=None):
    try:
        from selenium import webdriver
        from selenium.webdriver.chrome.service import Service
    except ImportError:
        raise RuntimeError('Selenium 설치가 필요합니다: python -m pip install -r requirements.txt') from None
    options = webdriver.ChromeOptions()
    if headless:
        options.add_argument('--headless=new')
    options.add_argument('--window-size=1280,1000')
    options.add_argument('--disable-notifications')
    options.add_experimental_option('prefs', {'credentials_enable_service': False,
                                              'profile.password_manager_enabled': False})
    driver = webdriver.Chrome(service=Service(executable_path=driver_path) if driver_path else Service(), options=options)
    driver.set_page_load_timeout(45)
    return driver


def visible_element(driver, selector, timeout=15):
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait

    def find_one(d):
        matches = [e for e in d.find_elements(By.CSS_SELECTOR, selector) if e.is_displayed() and e.is_enabled()]
        if len(matches) > 1:
            raise ValueError(f'여러 입력칸이 발견되었습니다. 편집할 문항 하나만 열어주세요: {selector}')
        return matches[0] if matches else False

    return WebDriverWait(driver, timeout).until(find_one)


def fill_fields(driver, payload, selectors, overwrite=False):
    """Validate all fields before changing any field, then verify every typed value."""
    validate_payload(payload)
    elements = {}
    for key, selector in selectors.items():
        element = visible_element(driver, selector)
        previous = element.get_attribute('value') or ''
        if previous.strip() and previous != payload[key] and not overwrite:
            raise ValueError(f'기존 내용이 있는 {key} 항목입니다. 교체하려면 --overwrite를 사용하세요.')
        limit = element.get_attribute('maxlength')
        if limit and int(limit) >= 0 and len(payload[key].encode('utf-16-le')) // 2 > int(limit):
            raise ValueError(f'{key}가 사이트의 최대 글자 수 {limit}를 초과합니다.')
        elements[key] = element
    for key, element in elements.items():
        element.clear()
        element.send_keys(payload[key])
        actual = (element.get_attribute('value') or '').replace('\r\n', '\n')
        if actual != payload[key].replace('\r\n', '\n'):
            raise RuntimeError(f'{key} 입력값 검증에 실패했습니다. 저장하지 않았습니다.')
    return list(elements)


def automate_local(url, payload, output, driver_path=None):
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    if urlsplit(url).hostname != '127.0.0.1':
        raise ValueError('로컬 자동 저장은 127.0.0.1에서만 지원합니다.')
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    driver = create_driver(driver_path=driver_path)
    try:
        driver.get(url)
        filled = fill_fields(driver, payload, {'resume_title': '#title', 'intro_title': '#intro_title',
                                               'intro_contents': '#intro_contents'})
        driver.save_screenshot(str(output / '01_filled.png'))
        driver.find_element(By.ID, 'save').click()
        success = WebDriverWait(driver, 15).until(lambda d: d.find_element(By.ID, 'success'))
        record_id = int(success.get_attribute('data-id'))
        driver.save_screenshot(str(output / '02_saved.png'))
        result = {'status': 'saved', 'record_id': record_id, 'fields_verified': filled, 'target': 'local'}
        (output / 'automation_result.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
        return result
    except Exception:
        driver.save_screenshot(str(output / 'error.png'))
        raise
    finally:
        driver.quit()


def automate_saramin(payload, output, overwrite=False, driver_path=None):
    """User signs in to a fresh browser; code inserts three observed text fields."""
    validate_payload(payload)
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    print('사람인에 입력할 문서:')
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    print('실제 계정에 위 초안이 입력됩니다. 사이트가 입력 중 임시 저장할 수 있습니다.')
    if input('내용을 검토한 뒤 입력하려면 INSERT를 입력하세요: ').strip() != 'INSERT':
        return {'status': 'cancelled', 'target': 'saramin'}
    driver = create_driver(headless=False, driver_path=driver_path)
    try:
        driver.get(SARAMIN_URL)
        print('열린 Chrome에서 직접 로그인하세요. 기존 Chrome의 로그인은 공유되지 않습니다.')
        print('이력서 작성 화면에서 자기소개서 → 추가 → 직접 입력하기를 열어주세요.')
        input('입력칸이 준비되면 이 터미널에서 Enter: ')
        current = urlsplit(driver.current_url)
        if current.scheme != 'https' or current.hostname != 'www.saramin.co.kr' or current.path != urlsplit(SARAMIN_URL).path:
            raise ValueError('사람인 이력서 작성 페이지가 아닙니다. 로그인 후 지정 URL로 이동하세요.')
        filled = fill_fields(driver, payload, {
            'resume_title': 'input#title',
            'intro_title': '#introduce input[name="intro_title[]"]',
            'intro_contents': '#introduce textarea[name="intro_contents[]"]',
        }, overwrite=overwrite)
        result = {'status': 'filled_not_submitted', 'target': 'saramin', 'fields_verified': filled}
        (output / 'saramin_result.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
        print('입력값 검증 완료. 브라우저에서 내용을 확인하고 자기소개서 저장 → 작성완료를 직접 선택하세요.')
        input('브라우저 작업을 마쳤으면 Enter (브라우저가 닫힙니다): ')
        return result
    finally:
        driver.quit()
