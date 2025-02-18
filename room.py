import requests
from bs4 import BeautifulSoup
import re
import json
import calendar
from datetime import datetime, timedelta
from dataclasses import dataclass

from string_utilities import *

f = open(".kakaokey", 'r')
KAKAO_REST_API_KEY = f.read()

SAM_URL_PREFIX = "https://33m2.co.kr/room/detail/"
ROOM_CONTRACT_DATA_LIST = ['임대료', '장기계약 할인', '관리비용', '청소비용', '계약 수수료']

# 현재 연도와 월을 구하기
today = datetime.today()
current_date = today + timedelta(days=1)
current_year = current_date.year
current_month = current_date.month
current_day = current_date.day

class Jibun:
    def __init__(self, region_1depth_name: str, 
                 region_2depth_name: str, region_3depth_name: str, 
                 main_address_no: str, sub_address_no: str):
        self.region_1depth_name = region_1depth_name
        self.region_2depth_name = region_2depth_name
        self.region_3depth_name = region_3depth_name
        self.main_address_no = main_address_no
        self.sub_address_no = sub_address_no

    def __str__(self):
        return self.region_1depth_name + " " + \
            self.region_2depth_name + " " + \
            self.region_3depth_name + " " + \
            self.main_address_no + "-" + \
            self.sub_address_no
    
    def __iter__(self):
        return iter([
            self.region_1depth_name,
            self.region_2depth_name,
            self.region_3depth_name,
            self.main_address_no,
            self.sub_address_no
        ])
    
class Road:
    def __init__(self, region_1depth_name: str, 
                 region_2depth_name: str, road_name: str, 
                 main_building_no: str, sub_building_no: str):
        self.region_1depth_name = region_1depth_name
        self.region_2depth_name = region_2depth_name
        self.road_name = road_name
        self.main_building_no = main_building_no
        self.sub_building_no = sub_building_no

    def __str__(self):
        return (self.region_1depth_name + " " + \
            self.region_2depth_name + " " + \
            self.road_name + " " + \
            self.main_building_no + " " + \
            self.sub_building_no).strip()

    def __iter__(self):
        return iter([
            self.region_1depth_name,
            self.region_2depth_name,
            self.road_name,
            self.main_building_no,
            self.sub_building_no
        ])
        
class Address:
    # 33m2 기준(지번주소)으로 저장
    # 예) 서울특별시 강남구 대치동 943-24 신안메트로칸 7층
    # region1 : 서울시
    # region2 : 강남구
    # region3 : 대치동
    # 
    def __init__(self, query: str):
        if query is None:
            return
        
        url = "https://dapi.kakao.com/v2/local/search/address.json"
        headers = {
            "Authorization": f"KakaoAK {KAKAO_REST_API_KEY}"
        }
        params = {
            "query": query,
            "analyze_type": "similar" # 특수기호 붙으면 exact는 제대로 못찾음
        }
        response = requests.get(url, headers=headers, params=params)

        if not response.status_code == 200:
            print("카카오맵 API 요청 실패. 검색어 :", query)
            return

        data = response.json()

        if data["meta"]["total_count"] == 0:
            print("카카오맵 API에서 검색할 수 없습니다. 검색어 :", query)
            return
        
        # 서울 강남구 삼성동 114-1
        # 서울, 강남구, 삼성동, 114, 1
        self.jibun = Jibun(
            data["documents"][0]["address"]["region_1depth_name"],
            data["documents"][0]["address"]["region_2depth_name"],
            data["documents"][0]["address"]["region_3depth_name"],
            data["documents"][0]["address"]["main_address_no"],
            data["documents"][0]["address"]["sub_address_no"],
        )

        # 서울 강남구 삼성로95길 9
        # 서울, 강남구, 삼성로95길, 9, (emptystring)
        self.doro = Road(
            data["documents"][0]["road_address"]["region_1depth_name"],
            data["documents"][0]["road_address"]["region_2depth_name"],
            data["documents"][0]["road_address"]["road_name"],
            data["documents"][0]["road_address"]["main_building_no"],
            data["documents"][0]["road_address"]["sub_building_no"],
        )

        self.floor = query.split()[-1][:-1] if '층' in query.split()[-1] else '0'
        self.postcode = data["documents"][0]["road_address"]["zone_no"]
        self.building_name = data["documents"][0]["road_address"]["building_name"]
        self.building_name_preprocessed = re.sub(r"[^가-힣a-zA-Z0-9\s]", "", self.building_name)
        self.building_name_preprocessed = replace_roman_numerals(self.building_name_preprocessed)
        self.longitude = data["documents"][0]["x"]
        self.latitude = data["documents"][0]["y"]
        
    def __str__(self):
        return self.jibun.__str__()

class Room:
    def __init__(self, samsam_id: str, duration = 28):
        self.sam_id = samsam_id
        self.naver_id = None
        self.address = None
        self.prices = None
        self.room_name = None
        self.room_size_pyeong_sam = None
        self.room_size_pyeong_naver = None
        self.room_type = None
        self.vacancy_rate = None
        self.deposit = None
        self.monthly_rent = None

        # self.valid = False
        self.updateLand()
        self.updateRentFee()
        self.updateVacancyRate()
        self.updateLandPrice(exact=False)

    def updateLand(self):
        room_url = SAM_URL_PREFIX + str(self.sam_id)

        # 1. 이름과 주소 찾기
        headers = {
            'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 13_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/13.0 Mobile/15E148 Safari/604.1'
        }
        response = requests.get(room_url, headers=headers)

        if response.status_code != 200:
            print('33m2에서 응답을 받지 못했습니다. id :', self.sam_id)
            return
        
        soup = BeautifulSoup(response.text, 'html.parser')

        # 이름과 주소
        room_intro = soup.find('div', id='room_intro')

        self.room_name = room_intro.find('strong').text.strip() if room_intro.find('strong') else None
        self.address = Address(room_intro.find('p', class_='address').text.strip() if room_intro.find('p', class_='address') else None)

        # 전용면적과 건물 유형 찾기
        self.room_size_pyeong_sam = 0
        self.room_type = ""
        # 'place_detail' 클래스를 가진 ul 요소 찾기
        place_detail_ul = soup.find('ul', class_='place_detail')

        # place_detail_ul이 None이 아닌지 확인
        if place_detail_ul:
            # 모든 li 요소를 찾기
            li_elements = place_detail_ul.find_all('li')
            
            # '전용 면적' 텍스트를 포함한 li를 찾고, 그 다음 p 태그의 값 추출
            for li in li_elements:
                span_tag = li.find('span')
                if span_tag and '전용 면적' in span_tag.text:
                    p_tag = li.find('p')
                    if p_tag:
                        self.room_size_pyeong_sam = int(p_tag.text.strip()[:-1])
                        break  # 첫 번째 항목만 찾고 종료
            else:
                print("33m2에서", self.sam_id, "의 전용 면적을 찾을 수 없습니다.")
            
            # '건물 유형' 텍스트를 포함한 li를 찾고, 그 다음 p 태그의 값 추출
            for li in li_elements:
                span_tag = li.find('span')
                if span_tag and '건물 유형' in span_tag.text:
                    p_tag = li.find('p')
                    if p_tag:
                        self.room_type = p_tag.text.strip()
                        break  # 첫 번째 항목만 찾고 종료
            else:
                print("33m2에서", self.sam_id, "의 건물 유형을 찾을 수 없습니다.")
                
        else:
            print("(전용면적) place_detail 클래스를 가진 ul을 찾을 수 없습니다.")

        # self.valid = True

    def updateRentFee(self):

        # 2. 가격 정보 가져오기
        session = requests.Session()
        
        # 요청 URL
        url = 'https://33m2.co.kr/webpc/booking/start'
        room_url = SAM_URL_PREFIX + str(self.sam_id)

        # 요청 헤더
        headers = {
            'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
            'Accept': '*/*',
            'Sec-Fetch-Site': 'same-origin',
            'Accept-Language': 'ko-KR,ko;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Sec-Fetch-Mode': 'cors',
            'Origin': "https://33m2.co.kr/",
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.2 Safari/605.1.15',
            'Referer': room_url,
            'Sec-Fetch-Dest': 'empty',
            'X-Requested-With': 'XMLHttpRequest',
            'Priority': 'u=3, i'
        }

        # 요청 데이터
        data = {
            'rid': int(self.sam_id),  # 방 ID
            'start_date': '2026-09-01', # 유효한 날을 선택해야하기 때문에 예약이 없을거같은 임의 날짜 설정
            'end_date': '2026-09-28',
            'week': '4',
            'is_extend': 'false',
            'popup': 'true'
        }

        # POST 요청 보내기
        response = session.post(url, headers=headers, data=data)

        # BeautifulSoup 객체 생성
        soup = BeautifulSoup(response.text, 'html.parser')

        # contract_list 내의 모든 li 요소 찾기
        contract_items = soup.select('.contract_list li')

        # 가격 추출 (장기계약 할인이 없으면 0원 추가)
        prices_dict = {}

        for item in contract_items:
            key = item.select_one('span').text.strip()
            value = item.select_one('p').text.strip()[:-1]
            value = int(value.replace(",", ""))
            prices_dict[key] = value

        # 장기계약 할인이 없으면 0원 추가
        if "장기계약 할인" not in prices_dict:
            prices_dict["장기계약 할인"] = "0"

        # list로 변경
        self.prices = {}
        for l in ROOM_CONTRACT_DATA_LIST:
            self.prices[l] = prices_dict[l]

    def updateVacancyRate(self, duration = 28):
        self.vacancy_rate = -1 # 오류시
        # 세션 생성
        session = requests.Session()

        # 요청 URL
        url = "https://33m2.co.kr/app/room/schedule"
        room_url = SAM_URL_PREFIX + str(self.sam_id)

        # 헤더 정보
        headers = {
            "Accept": "*/*",
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            "Origin": "https://33m2.co.kr",
            "Referer": room_url,
            "Accept-Language": "ko-KR,ko;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.2 Safari/605.1.15",
            "X-Requested-With": "XMLHttpRequest",
            "Priority": "u=5, i"
        }

        num_day = 0
        num_vacant = 0
        
        # 이번달과 다음달의 공실 여부를 load
        year = current_year
        month = current_month
        start_day = current_day # 이번달은 내일부터, 다음달은 1일부터
        # 여러달 request할 수 있음
        while num_day < duration:
            # 요청 데이터
            data = {
                "rid": int(self.sam_id),  # room ID
                "year": str(year),  # year
                "month": str(month)    # month
            }

            # POST 요청 보내기
            response = session.post(url, headers=headers, data=data)

            # print(response.text)

            # 응답 내용 확인
            if response.status_code == 200:
                # print(response.json())  # JSON 응답으로 데이터를 확인

                # response는 불가능한 날만 status = booking 이나 disable로 반환. 가능한날은 따로 반환안함
                days_booking = [int(item["date"].split("-")[2]) for item in response.json()["schedule_list"] if item["status"] == "booking"]
                days_disable = [int(item["date"].split("-")[2]) for item in response.json()["schedule_list"] if item["status"] == "disable"]

                _, last_day = calendar.monthrange(year, month)

                for day in range(start_day, last_day+1):
                    if num_day < duration:
                        # disable되지 않은 날만 셈
                        if day not in days_disable:
                            num_day = num_day + 1
                            if day not in days_booking:
                                num_vacant = num_vacant + 1
                    else:
                        break
            
            # 응답 오류
            else:
                print("Error:", response.status_code)
                break

            # 이후 다른 요청도 session을 통해 쿠키가 자동으로 포함됩니다.

            # 다음 달로
            if num_day < duration:
                year = year + int(month/12)
                month = (month-1+1) % 12 + 1
                start_day = 1

        # 날짜 수 추출
        self.vacancy_rate = num_vacant / num_day

    def updateLandPrice(self, exact: bool = True):
        page_url_prefix = "https://fin.land.naver.com/complexes/"
        page_url_suffix = "?tradeTypes=B2&spaceType=평&tab=article"
        self.naver_id = None
        if self.address is None:
            print("room id", self.sam_id, "의 주소가 없습니다.")
            return
        
        # naver id 검색하기
        # search/result/에서 
        building_name_url = remove_trailing_numerals(self.address.building_name_preprocessed)

        search_url = 'https://m.land.naver.com/search/result/' + building_name_url

        headers = {
            'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 13_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/13.0 Mobile/15E148 Safari/604.1'
        }
        response = requests.get(search_url, headers=headers)

        if response.status_code != 200:
            print("네이버 부동산에서 응답을 받지 못했습니다. 검색어 :", building_name_url)
            return None
        
        soup = BeautifulSoup(response.text, 'html.parser')
        # case 1. 검색 매물 없음
        if soup.find(class_="p_noresult"):
            print("네이버 부동산에서 해당 매물을 찾을 수 없습니다. 검색어 :", building_name_url)
            return None
        
        # 검색 페이지에 들어옴(https://m.land.naver.com/search/result/신안메트로칸)
        # case 2. 만약 이름이 중복된 건물이 있을 경우 주소를 통해서 하나 선택
        elif soup.find(class_='layer_result'):
            is_found = False
            for item in soup.find_all("li", class_="result_item"):
                address_tag = item.find("span", class_="address")
                link_tag = item.find("a", class_="inner")
                
                # 33m2는 지번주소 제공 / 네이버는 도로명주소 제공 -> 주소 중 앞에서 두번째 행정구역을 비교
                # 서울시 강남구 테헤란로 -> 강남구 만 이용
                if address_tag and link_tag:
                    address = address_tag.text.strip() # list
                    href = link_tag["href"]
                    if self.address.doro.road_name in address:
                        self.naver_id = href.split("/")[-1]
                        is_found = True
                        break

            if not is_found:
                print("네이버 부동산에서", self.address, "를 찾지 못했습니다.")
                return None
        
        # case 3. 바로 매물 페이지에 리디레팅됨
        elif response.url.startswith(page_url_prefix):
            _url = response.url.split('?')[0]
            self.naver_id = _url[len(page_url_prefix):]

        # 매물 페이지로 들어옴(https://fin.land.naver.com/complexes/18350?tradeTypes=B2&spaceType=평&tab=article)
        response = requests.get(page_url_prefix + self.naver_id + page_url_suffix, headers=headers)

        if response.status_code != 200:
            print(search_url, "에서 응답을 받지 못했습니다.")
            return None
        
        soup = BeautifulSoup(response.text, 'html.parser')

        # 결과 저장할 변수
        target_price = None

        # 모든 항목을 순회
        for item in soup.find_all("li", class_="ComplexArticleItem_item__L5o7k"):
            summary_list = item.find_all("li", class_="ComplexArticleItem_item-summary__oHSwl")

            # "평수 (전용면적)"이 있는 요소 찾기
            for summary in summary_list:
                if "(" in summary.text and ")" in summary.text:
                    _, _area = summary.text.split("(")
                    _area = _area.strip(") ")
                    # 숫자만 추출
                    _area = re.sub(r'[^0-9]', '', _area)

                    # 전용면적이 같을 경우 해당 항목의 월세 찾기
                    if _area == str(self.room_size_pyeong_sam):
                        self.room_size_pyeong_naver = self.room_size_pyeong_sam
                        price = item.find("span", class_="ComplexArticleItem_price__DFeIb")
                        target_price = price.text.strip() if price else None
                        target_price = target_price.split(" ~ ")[0]
                        # print(target_price)
                        break

            if target_price:  # 찾으면 루프 종료
                break

        if not target_price:
            print("네이버 부동산에서", self.naver_id, "의 전용면적", self.room_size_pyeong_sam, "평 의 매물을 찾지 못하였습니다.")
            if exact:
                return
            else:
                print("대신하여 전용면적", self.room_size_pyeong_sam - 1, "~", self.room_size_pyeong_sam + 1, "평의 매물을 찾습니다.")
                # 결과 저장할 변수
                target_price = None

                # 모든 항목을 순회
                for item in soup.find_all("li", class_="ComplexArticleItem_item__L5o7k"):
                    summary_list = item.find_all("li", class_="ComplexArticleItem_item-summary__oHSwl")

                    # "평수 (전용면적)"이 있는 요소 찾기
                    for summary in summary_list:
                        if "(" in summary.text and ")" in summary.text:
                            _, _area = summary.text.split("(")
                            _area = _area.strip(") ")
                            # 숫자만 추출
                            _area = re.sub(r'[^0-9]', '', _area)

                            # 전용면적이 +-1 차이날 경우 해당 항목의 월세 찾기
                            if _area == str(self.room_size_pyeong_sam-1):
                                self.room_size_pyeong_naver = self.room_size_pyeong_sam-1
                                price = item.find("span", class_="ComplexArticleItem_price__DFeIb")
                                target_price = price.text.strip() if price else None
                                target_price = target_price.split(" ~ ")[0]
                                # print(target_price)
                                break

                            if _area == str(self.room_size_pyeong_sam+1):
                                self.room_size_pyeong_naver = self.room_size_pyeong_sam+1
                                price = item.find("span", class_="ComplexArticleItem_price__DFeIb")
                                target_price = price.text.strip() if price else None
                                target_price = target_price.split(" ~ ")[0]
                                # print(target_price)
                                break

                    if target_price:  # 찾으면 루프 종료
                        break

                if not target_price:
                    print("네이버 부동산에서", self.naver_id, "의 전용면적", self.room_size_pyeong_sam-1, "~", self.room_size_pyeong_sam+1, "평 의 매물을 찾지 못하였습니다.")
                    return
                print("대신하여", self.room_size_pyeong_naver,"평의 매물을 찾았습니다.")

        else:
            print("네이버 부동산에서", self.naver_id, "의 전용면적", self.room_size_pyeong_sam, "평 의 매물을 찾았습니다.")

        # if not target_price and not exact:
        #     print("대신하여 전용면적", self.room_size_pyeong_sam - 1, "~", self.room_size_pyeong_sam + 1, "평의 매물을 찾습니다.")
        #     # 결과 저장할 변수
        #     target_price = None

        #     # 모든 항목을 순회
        #     for item in soup.find_all("li", class_="ComplexArticleItem_item__L5o7k"):
        #         summary_list = item.find_all("li", class_="ComplexArticleItem_item-summary__oHSwl")

        #         # "평수 (전용면적)"이 있는 요소 찾기
        #         for summary in summary_list:
        #             if "(" in summary.text and ")" in summary.text:
        #                 _, _area = summary.text.split("(")
        #                 _area = _area.strip(") ")
        #                 # 숫자만 추출
        #                 _area = re.sub(r'[^0-9]', '', _area)

        #                 # 전용면적이 +-1 차이날 경우 해당 항목의 월세 찾기
        #                 if _area == str(self.room_size_pyeong_sam-1):
        #                     self.room_size_pyeong_naver = self.room_size_pyeong_sam-1
        #                     price = item.find("span", class_="ComplexArticleItem_price__DFeIb")
        #                     target_price = price.text.strip() if price else None
        #                     target_price = target_price.split(" ~ ")[0]
        #                     # print(target_price)
        #                     break

        #                 if _area == str(self.room_size_pyeong_sam+1):
        #                     self.room_size_pyeong_naver = self.room_size_pyeong_sam+1
        #                     price = item.find("span", class_="ComplexArticleItem_price__DFeIb")
        #                     target_price = price.text.strip() if price else None
        #                     target_price = target_price.split(" ~ ")[0]
        #                     # print(target_price)
        #                     break

        #         if target_price:  # 찾으면 루프 종료
        #             break
            
        #     if not target_price:
        #         print("네이버 부동산에서", self.naver_id, "의 전용면적", self.room_size_pyeong_sam-1, "~", self.room_size_pyeong_sam+1, "평 의 매물을 찾지 못하였습니다.")
        #         return
        
        # target_price는 이제 '월세 1,000/80'의 형태
        target_price = target_price[2:]
        target_prices = target_price.split("/")
        self.deposit = int(target_prices[0].replace(',',''))
        self.monthly_rent = int(target_prices[1].replace(',',''))


r = Room('38048')
print(r.address, r.naver_id, r.sam_id, r.deposit, r.monthly_rent, r.prices)