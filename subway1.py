import csv
import re
import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service as CS
from webdriver_manager.chrome import ChromeDriverManager as CDM
from bs4 import BeautifulSoup as BS

# 지하철 매장 정보를 검색할 URL
URL = "https://www.subway.co.kr/storeSearch"

# 검색할 지역 리스트
LOC = ['서울', '부산', '대구', '인천', '광주', '대전', '울산', '세종',
       '경기', ['충북', '충청북도'], ['충남', '충청남도'], ['전남', '전라남도'],
       ['경북', '경상북도'], ['경남', '경상남도'], '강원', '전북', '제주']

# CSS 선택자 (검색창과 검색 버튼)
INPUT_CSS = "#keyword"
SEARCH_BTN = "#mapFrm a.btn_search"

# 데이터를 CSV 파일로 저장하는 함수
def save_csv(csv_list, filename, encoding="cp949", csv_header=None):
    # 파일을 열고 데이터 저장
    with open(filename, "w", encoding=encoding, newline='') as file:
        writer = csv.writer(file)
        # 헤더가 있으면 추가
        if csv_header:
            writer.writerow(csv_header)
        # 리스트의 각 줄을 파일에 저장
        writer.writerows(csv_list)

# 문자열의 공백 문자 처리 함수 (특정 비표준 공백 제거)
def clear(text):
    return re.sub(u"\xa0", u" ", text)

# 페이지의 HTML 소스를 분석하여 매장 정보를 추출하는 함수
def get_page_content(html_src, loc_name, s_loc=None):
    # BeautifulSoup으로 HTML 파싱
    bs = BS(html_src, "html.parser")
    res = bs.select("ul#uiResultList li")  # 매장 리스트 요소 선택

    lines = []  # 결과 데이터를 저장할 리스트
    for r in res:
        line = [loc_name]  # 지역명을 첫 번째 열에 추가

        # 매장명 추출
        stnm = r.select("strong")[0].get_text(strip=True)
        line.append(stnm)

        # 매장 주소 추출
        info = r.select("div.info")[0].select("span")
        addr = info[0].get_text(strip=True)
        line.append(clear(addr))

        # 지역명이 주소에 없으면 무시
        if s_loc not in addr:
            continue

        # 전화번호와 영업시간 초기화
        phon = "-"
        a_tm = "-"
        for inf in info[1:]:
            ss = inf.get_text(strip=True)
            if "연락처" in ss:
                phon = ss.replace("연락처 :", "").strip()  # 연락처 추출
            elif "영업시간" in ss:
                a_tm = ss.replace("영업시간 :", "").strip()  # 영업시간 추출
        line.append(phon)
        line.append(a_tm)

        # 서비스 정보 추출
        serv = ""
        srv = r.select("div.service")[0].select("span")
        for s in srv[:-1]:
            serv += f'{s.get_text(strip=True)}, '
        serv += f'{srv[-1].get_text(strip=True)}'
        line.append(serv)

        # 좌표(위도, 경도) 추출
        lr_txt = r["onclick"]
        lr_lst = lr_txt.split(",")
        lat = lr_lst[7].strip()  # 위도
        line.append(re.sub("'", "", lat))
        lon = lr_lst[8].strip()  # 경도
        line.append(re.sub("'", "", lon))

        # 추출한 데이터를 리스트에 추가
        lines.append(line)

    return lines

# 특정 지역에 대해 데이터를 수집하는 함수
def get_contents(driver, location, s_loc=None):
    driver.get(URL)  # 브라우저에서 URL 열기
    time.sleep(1)  # 페이지 로드 대기

    s_loc = s_loc if s_loc else location  # 하위 지역명 지정
    driver.find_element(By.CSS_SELECTOR, INPUT_CSS).send_keys(s_loc)  # 검색어 입력
    driver.find_element(By.CSS_SELECTOR, SEARCH_BTN).click()  # 검색 버튼 클릭
    time.sleep(2)  # 검색 결과 로드 대기

    res_lines = []
    while True:
        html = driver.page_source  # 현재 페이지 HTML 가져오기
        r_lines = get_page_content(html, location, s_loc)  # 매장 정보 추출
        res_lines.extend(r_lines)

        # 다음 페이지 버튼 확인
        cp = driver.find_element(By.CSS_SELECTOR, "#ui_pager a.active").text.strip()
        next_btn = driver.find_element(By.CSS_SELECTOR, "#ui_pager a.next")
        stc = next_btn.get_attribute("onclick")
        np = stc.split(",")[1].replace(")", "").strip()

        # 현재 페이지가 마지막 페이지면 종료
        if cp == np:
            break

        # 다음 페이지로 이동
        next_btn.click()
        time.sleep(1)

    return res_lines

# 리스트 형식의 지역에 대해 데이터를 수집하는 함수
def get_location_contents(driver, location):
    if isinstance(location, str):  # 문자열(단일 지역명)이면 바로 수집
        return get_contents(driver, location)
    else:  # 리스트(하위 지역 포함)이면 각 하위 지역에 대해 반복
        ret = []
        for lo in location:
            r = get_contents(driver, location[0], lo)
            ret.extend(r)
        return ret

if __name__ == '__main__':
    # 크롬 드라이버 옵션 설정
    opt = webdriver.ChromeOptions()
    opt.add_argument("--headless=old")  # 브라우저를 띄우지 않고 실행
    opt.add_argument("--window-size=1920x1080")  # 창 크기 설정
    opt.add_argument("--disable-gpu")  # GPU 비활성화
    opt.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/94.0.4606.61 Safari/537.36")

    # 크롬 드라이버 실행
    drv = webdriver.Chrome(options=opt, service=CS(CDM().install()))

    res_csv = []  # 결과 데이터를 저장할 리스트
    for loc in LOC:  # 지역 리스트 반복
        print(f"{loc} 지역을 검색중입니다.")
        r_csv = get_location_contents(drv, loc)  # 지역에 대한 데이터 수집
        res_csv.extend(r_csv)  # 결과 누적

    # CSV 파일로 저장
    hd = ['지역명', '매장명', '주소', '전화번호', '영업시간', '서비스', '위도', '경도']
    save_csv(res_csv, "subway.csv", csv_header=hd)
    print("종료되었습니다.")

    drv.close()  # 드라이버 종료
