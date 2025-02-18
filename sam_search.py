import requests
from bs4 import BeautifulSoup
import json
import re
# from calendar import mdays, calendar
import calendar
from datetime import datetime, timedelta
from room import *

# 현재 연도와 월을 구하기
today = datetime.today()
current_date = today + timedelta(days=1)
current_year = current_date.year
current_month = current_date.month
current_day = current_date.day

def sam_search_keyword(keyword:str, property_type:str = "오피스텔", max_iter = 50):
    ids = list()

    session = requests.Session()

    headers = {
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        "Accept": "*/*",
        "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Mobile/15E148 Safari/604.1",
        "Referer": "https://33m2.co.kr/webmobile/search?keyword={requests.utils.quote(keyword)}",
    }

    print("33m2에서 {}(으)로 검색중 (최대 {}건)".format(keyword, max_iter*15),end="", flush=True)
    for request_num in range(max_iter):
        # print(request_num, "번째 reqeust 시도...", 15*request_num, "개의 방을 찾고 있습니다")
        print(".",end="", flush=True)
        # 요청 데이터 설정
        data = {
            "theme_type": "",
            "keyword": keyword,  # 사용자가 입력한 키워드
            "start_num": (request_num * 15),
            "room_cnt": "",
            "property_type": property_type,
            "animal": "false",
            "subway": "false",
            "parking_place": "false",
            "longterm_discount": "false",
            "early_discount": "false",
            "min_using_fee": "0",
            "max_using_fee": "0",
        }

        try:
            # POST 요청
            response = session.post(
                "https://33m2.co.kr/webmobile/search/list/more",
                headers=headers,
                data=data
            )

            if len(response.text.strip()) == 0:
                break

            # 응답 확인
            if response.status_code == 200:

                # 응답에서 각각의 link 파싱            
                soup = BeautifulSoup(response.text, "html.parser")

                # 매물 별 링크 찾기
                a_tags = soup.find_all("a")
                href_list = [a["href"] for a in a_tags if "href" in a.attrs]

                # id 저장
                for href in href_list:
                    match = re.search(r'(\d+)$', href)

                    if match:
                        id = match.group(1)  # 숫자 부분
                        ids.append(id)

            # http 오류발생
            else:
                break
        
        # request 오류발생
        except requests.RequestException as e:
            print("❌ 요청 중 오류 발생:", e)
            break

    print("\n{}개의 방을 찾았습니다!".format(len(ids)))
    return ids

def sam_search_map(north_east_lng:float, north_east_lat:float, 
                          south_west_lng:float, south_west_lat:float, 
                          map_level:int, property_type:str = "오피스텔"):
    ids = list() # rid
    lats = list() # latitude
    lngs = list() # longitude

    url = "https://33m2.co.kr/app/room/search"

    headers = {
        "Accept": "*/*",
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.2 Safari/605.1.15",
        "X-Requested-With": "XMLHttpRequest",
    }

    data = {
        "sort": "popular",
        "property_type" : property_type,
        "now_page": 1,
        "map_level": map_level,
        "by_location": "true",
        "north_east_lng": north_east_lng,
        "north_east_lat": north_east_lat,
        "south_west_lng": south_west_lng,
        "south_west_lat": south_west_lat,
        "itemcount": 1000
    }

    # data = {
    #     "theme_type": None,
    #     "keyword": None,
    #     "room_cnt": None,
    #     "property_type": property_type,
    #     "animal": False,
    #     "subway": False,
    #     "longterm_discount": False,
    #     "early_discount": False,
    #     "parking_place": False,
    #     "start_date": None,
    #     "end_date": None,
    #     "week": None,
    #     "min_using_fee": 0,
    #     "max_using_fee": 1000000,
    #     "sort": "popular",
    #     "now_page": 1,
    #     "map_level": map_level,
    #     "by_location": True,
    #     "north_east_lng": north_east_lng,
    #     "north_east_lat": north_east_lat,
    #     "south_west_lng": south_west_lng,
    #     "south_west_lat": south_west_lat,
    #     "itemcount": 1000
    # }


    response = requests.post(url, headers=headers, data=data)

    if response.status_code == 200:
        json_data = response.json()
        room_list = json_data.get("list", [])
        # room_list = json_data["list"][0]
        print("{}개의 방을 찾았습니다!".format(len(room_list)))

        ids = [room["rid"] for room in room_list]
        # lats = [room["lat"] for room in room_list]
        # lngs = [room["lng"] for room in room_list]

        # return ids, lats, lngs
        return ids
    else:
        print(f"지도에서 매물을 가져오는데 실패했습니다. : {response.status_code}")
        # return None, None, None
        return None


import concurrent.futures

r = list()
# for id in sam_search_map(126.94017765746437,37.56115947769192,126.93403835197509,37.55381308037769,3):
#     r.append(Room(id))


def process_entry(id):
    Room(id)

# ThreadPoolExecutor를 사용하여 쓰레드 풀 관리
def process_in_thread_pool(ids):
    with concurrent.futures.ThreadPoolExecutor() as executor:
        # 각 id에 대해 process_entry 함수를 실행
        futures = [executor.submit(process_entry, id) for id in ids]
        
        # 모든 작업이 완료될 때까지 기다리기
        for future in concurrent.futures.as_completed(futures):
            future.result()

process_in_thread_pool(sam_search_map(126.94017765746437,37.56115947769192,126.93403835197509,37.55381308037769,3))
