from selenium import webdriver
from selenium.webdriver.chrome.service import Service as CS
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager as CDM
from bs4 import BeautifulSoup as BS
import time
import csv
import re


# 맥도날드 매장 검색 페이지의 URL
URL = "https://www.mcdonalds.co.kr/kor/store/list.do"

# 검색할 지역 리스트 (일부 지역은 다른 이름도 포함)
LOC = ['서울', '부산', '대구', '인천', '광주', '대전', '울산', '세종',
       '경기', ['충북', '충청북도'], ['충남', '충청남도'], ['전남', '전라남도'],
       ['경북', '경상북도'], ['경남', '경상남도'], '강원', '전북', '제주']

# 검색 창과 버튼을 찾기 위한 CSS 선택자
INPUT_CSS = ".srchBox #searchWord"  # 검색어 입력 필드
SEARCH_BTN = ".srchBox button.btnMC.btnM"  # 검색 버튼


# CSV 파일에 데이터를 저장하는 함수
def save_csv(csv_list, filename, encoding="cp949", csv_header=None):
    """
    주어진 데이터를 CSV 파일로 저장합니다.
    :param csv_list: 저장할 데이터 리스트
    :param filename: 저장할 파일 이름
    :param encoding: 파일의 문자 인코딩 (기본값: "cp949")
    :param csv_header: CSV 파일의 헤더 (첫 번째 행)
    """
    with open(filename, "w", encoding=encoding, newline='') as file:
        writer = csv.writer(file)  # CSV 작성 도구 생성
        if csv_header:  # 헤더가 있으면 첫 줄에 작성
            writer.writerow(csv_header)
        writer.writerows(csv_list)  # 데이터 리스트를 파일에 작성


# 특정 텍스트에서 비표준 공백 문자 제거
def clear(text):
    """
    비표준 공백 문자인 \xa0를 일반 공백으로 변환합니다.
    :param text: 변환할 문자열
    :return: 공백이 수정된 문자열
    """
    return re.sub(u"\xa0", u" ", text)  # \xa0를 공백으로 대체


# HTML 소스를 분석하여 매장 정보를 가져오는 함수
def get_page_content(html_src, loc_name, s_loc=None):
    """
    HTML 소스를 분석하여 매장 정보를 리스트로 반환합니다.
    :param html_src: HTML 소스 코드
    :param loc_name: 지역 이름 (예: "서울")
    :param s_loc: 세부 지역 이름 (예: "강남구")
    :return: 매장 정보 리스트
    """
    bs = BS(html_src, "html.parser")  # BeautifulSoup으로 HTML 파싱
    res = bs.select(".mcStore table.tableType01 tbody tr")  # 매장 정보가 담긴 테이블 행 선택

    lines = []  # 결과 데이터를 저장할 리스트
    for r in res:
        line = [loc_name]  # 첫 번째 열에 지역 이름 추가
        info = r.select("td.tdName .name")[0]  # 매장 정보를 담고 있는 부분 선택
        stnm = info.select("dt")[0].select("a")[0].get_text(strip=True)  # 매장명 가져오기
        line.append(stnm)
        addr = info.select("dd")[0].get_text(strip=True)  # 주소 가져오기
        if s_loc not in addr:  # 세부 지역이 주소에 포함되지 않으면 무시
            continue
        line.append(clear(addr))  # 주소를 정리하여 추가
        doro = info.select("dd")[1].get_text(strip=True)  # 도로명 주소 가져오기
        line.append(clear(doro))
        td = r.select("td")
        phon = td[1].get_text(strip=True)  # 전화번호 가져오기
        phones = re.findall(r'\d{2,3}-\d{3,4}-\d{4}', phon)  # 정규식으로 전화번호 찾기
        formatted_phone = ", ".join(phones)  # 여러 전화번호를 쉼표로 구분
        line.append(formatted_phone)
        a_tm = td[2].get_text(strip=True)  # 영업시간 가져오기
        line.append(a_tm)
        serv = ""  # 제공 서비스 초기화
        srv = r.select("td.tdService")[0].select("span.srvc")
        for s in srv[:-1]:  # 마지막 항목 제외하고 반복
            serv += f'{s.get_text(strip=True)}, '
        serv += f'{srv[-1].get_text(strip=True)}'  # 마지막 항목 추가
        line.append(serv)
        # 좌표 정보 (위도, 경도)
        lr_txt = info.select("dt")[0].select("a")[0]["href"].strip()  # JavaScript에서 좌표 추출
        lr_txt = lr_txt.replace("javascript:moveMap(", "").replace(");", "")  # 필요 없는 부분 제거
        lr_lst = lr_txt.split(",")  # 쉼표로 나눔
        lat = lr_lst[0].strip()  # 위도
        line.append(re.sub("'", "", lat))
        lon = lr_lst[1].strip()  # 경도
        line.append(re.sub("'", "", lon))
        lines.append(line)  # 한 매장의 정보를 리스트에 추가
    return lines


# 검색어를 입력하고 결과를 가져오는 함수
def get_contents(driver, location, s_loc=None):
    """
    특정 지역에 대한 매장 정보를 가져옵니다.
    :param driver: Selenium 웹 드라이버
    :param location: 검색할 지역
    :param s_loc: 세부 지역
    :return: 지역의 모든 매장 정보 리스트
    """
    driver.get(URL)  # 맥도날드 검색 페이지 열기
    time.sleep(1)  # 페이지 로딩 대기
    s_loc = s_loc if s_loc else location  # 세부 지역이 없으면 지역명 사용
    driver.find_element(By.CSS_SELECTOR, INPUT_CSS).send_keys(s_loc)  # 검색어 입력
    driver.find_element(By.CSS_SELECTOR, SEARCH_BTN).click()  # 검색 버튼 클릭
    time.sleep(2)  # 검색 결과 대기

    res_lines = []  # 결과 데이터를 저장할 리스트
    cp = 0  # 현재 페이지 번호
    while True:
        html = driver.page_source  # 현재 페이지의 HTML 가져오기
        r_lines = get_page_content(html, location, s_loc)  # HTML에서 매장 정보 추출
        if not r_lines:  # 데이터가 없으면 종료
            break
        res_lines.extend(r_lines)  # 결과 추가

        # 다음 페이지로 이동
        cp += 1
        next_btn = driver.find_element(By.CSS_SELECTOR, ".mcStore .btnPaging a.next")
        stc = next_btn.get_attribute("href")
        np = stc.replace("javascript:page(", "").replace(");", "").strip()
        if str(cp) == np:  # 마지막 페이지인 경우 종료
            break
        if cp % 10 == 0:  # 10 페이지마다 '다음' 버튼 클릭
            next_btn.click()
        else:  # 특정 페이지 번호 클릭
            num_bns = driver.find_elements(By.CSS_SELECTOR, ".mcStore .btnPaging span.num a")
            num_bns[cp % 10].click()
        time.sleep(1)  # 페이지 로딩 대기
    return res_lines


# 리스트 형식으로 지역 처리
def get_location_contents(driver, location):
    """
    지역이 문자열인지 리스트인지 구분하여 매장 정보를 가져옵니다.
    :param driver: Selenium 웹 드라이버
    :param location: 지역 또는 지역 리스트
    :return: 모든 매장 정보 리스트
    """
    if isinstance(location, str):  # 지역이 문자열인 경우
        return get_contents(driver, location)
    else:  # 지역이 리스트인 경우
        ret = []
        for lo in location:  # 각 하위 지역 검색
            r = get_contents(driver, location[0], lo)
            ret.extend(r)
        return ret


# 프로그램 실행 부분
if __name__ == '__main__':
    opt = webdriver.ChromeOptions()
    opt.add_argument("--headless=old")  # 화면 없이 실행
    opt.add_argument("--window-size=1920x1080")  # 브라우저 창 크기 설정
    opt.add_argument("--disable-gpu")  # GPU 비활성화
    opt.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/94.0.4606.61 Safari/537.36")

    drv = webdriver.Chrome(options=opt, service=CS(CDM().install()))  # 웹 드라이버 설정
    res_csv = []
    for loc in LOC:  # 모든 지역에 대해 검색 수행
        print(f"{loc} 지역을 검색중입니다.")
        r_csv = get_location_contents(drv, loc)
        res_csv.extend(r_csv)

    # CSV 파일로 저장
    hd = ['지역명', '매장명', '주소', "도로명", '전화번호', '영업시간', '서비스', '위도', '경도']
    save_csv(res_csv, r"C:\Users\Public\Documents\pythonProject2\static\mcdonalds.csv", csv_header=hd)
    print("종료되었습니다.")

    drv.close()  # 웹 드라이버 종료

