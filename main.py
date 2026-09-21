import streamlit as st
import pandas as pd
import requests
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo


# ---------------------------------------------------------
# 1. 기본 페이지 설정
# ---------------------------------------------------------
st.set_page_config(
    page_title="어제의 박스오피스",
    page_icon="🎬",
    layout="wide",
)


# ---------------------------------------------------------
# 2. KOBIS API 설정
# ---------------------------------------------------------
API_URL = (
    "https://www.kobis.or.kr/"
    "kobisopenapi/webservice/rest/boxoffice/"
    "searchDailyBoxOfficeList.json"
)


# ---------------------------------------------------------
# 3. 한국 시간 기준으로 '어제' 날짜 계산
# ---------------------------------------------------------
# Streamlit Cloud 서버가 어느 나라 시간대를 사용하더라도
# 한국 시간(Asia/Seoul)을 기준으로 날짜를 계산합니다.
def get_yesterday_kst():
    korea_now = datetime.now(ZoneInfo("Asia/Seoul"))
    yesterday = korea_now - timedelta(days=1)

    # KOBIS가 요구하는 YYYYMMDD 형식으로 변환합니다.
    return yesterday.strftime("%Y%m%d"), yesterday.strftime("%Y년 %m월 %d일")


# ---------------------------------------------------------
# 4. API에서 어제의 박스오피스 가져오기
# ---------------------------------------------------------
def get_boxoffice(target_date):
    # 인증키는 코드에 직접 넣지 않고 Streamlit Secrets에서 가져옵니다.
    # Streamlit Cloud에서는 앱의 Settings > Secrets에
    # KOBIS_KEY = "발급받은_키" 형태로 등록하면 됩니다.
    try:
        api_key = st.secrets["KOBIS_KEY"]
    except Exception:
        raise RuntimeError(
            "KOBIS_KEY를 찾을 수 없습니다. "
            "Streamlit Cloud의 앱 설정 > Secrets에 "
            "KOBIS_KEY가 등록되어 있는지 확인하세요."
        )

    # KOBIS API에 보낼 요청값입니다.
    params = {
        "key": api_key,
        "targetDt": target_date,
    }

    try:
        response = requests.get(
            API_URL,
            params=params,
            timeout=15,
        )
    except requests.RequestException as error:
        raise RuntimeError(
            "KOBIS API에 연결하지 못했습니다. "
            "인터넷 연결이나 KOBIS API 상태를 확인하세요."
        ) from error

    # HTTP 오류가 발생했는지 먼저 확인합니다.
    try:
        response.raise_for_status()
    except requests.HTTPError as error:
        raise RuntimeError(
            f"KOBIS API 요청에 실패했습니다. "
            f"(HTTP 상태 코드: {response.status_code})"
        ) from error

    # 응답이 JSON인지 확인합니다.
    try:
        data = response.json()
    except ValueError as error:
        raise RuntimeError(
            "KOBIS API가 올바른 JSON 응답을 보내지 않았습니다."
        ) from error

    # 중요:
    # KOBIS는 인증키가 잘못되어도 HTTP 200을 반환할 수 있습니다.
    # 따라서 faultInfo가 있는지도 반드시 확인합니다.
    if "faultInfo" in data:
        fault_info = data["faultInfo"]

        fault_message = (
            fault_info.get("message")
            or fault_info.get("messageId")
            or "KOBIS API에서 오류 정보를 반환했습니다."
        )

        raise RuntimeError(
            f"KOBIS API 오류: {fault_message}"
        )

    # 정상적인 응답 구조가 맞는지 확인합니다.
    boxoffice_result = data.get("boxOfficeResult")

    if not boxoffice_result:
        raise RuntimeError(
            "KOBIS 응답에 boxOfficeResult가 없습니다. "
            "API 응답 형식이나 조회 날짜를 확인하세요."
        )

    movie_list = boxoffice_result.get("dailyBoxOfficeList", [])

    # 영화 목록이 비어 있는 경우도 사용자에게 안내합니다.
    if not movie_list:
        raise RuntimeError(
            "조회된 영화 목록이 없습니다. "
            "어제 날짜의 박스오피스 집계가 완료되었는지, "
            "KOBIS API 상태와 조회 날짜를 확인하세요."
        )

    return movie_list


# ---------------------------------------------------------
# 5. 숫자 데이터를 보기 좋게 변환
# ---------------------------------------------------------
def make_dataframe(movie_list):
    rows = []

    for movie in movie_list:
        # KOBIS API의 숫자값은 문자열로 오므로 int로 변환합니다.
        rows.append(
            {
                "순위": int(movie.get("rank", 0)),
                "영화명": movie.get("movieNm", "-"),
                "개봉일": movie.get("openDt", "-"),
                "관객수": int(movie.get("audiCnt", 0)),
                "누적관객": int(movie.get("audiAcc", 0)),
                "스크린수": int(movie.get("scrnCnt", 0)),
            }
        )

    return pd.DataFrame(rows)


# ---------------------------------------------------------
# 6. 화면 제목
# ---------------------------------------------------------
target_date, display_date = get_yesterday_kst()

st.title("🎬 어제의 박스오피스")
st.caption(f"KOBIS 기준 · {display_date} 집계")


# ---------------------------------------------------------
# 7. API 호출
# ---------------------------------------------------------
try:
    movie_list = get_boxoffice(target_date)
    df = make_dataframe(movie_list)

except Exception as error:
    # API 오류가 발생해도 빈 화면을 보여주지 않고
    # 사용자가 무엇을 확인해야 하는지 안내합니다.
    st.error("박스오피스 정보를 가져오지 못했습니다.")

    st.markdown(
        """
        ### 확인해 주세요

        - Streamlit Cloud의 **Settings → Secrets**에
          `KOBIS_KEY`가 등록되어 있는지 확인하세요.
        - KOBIS 인증키가 정확한지 확인하세요.
        - KOBIS API 서비스가 정상적으로 응답하는지 확인하세요.
        - 조회 날짜가 한국 시간 기준 어제 날짜인지 확인하세요.
        - 어제의 박스오피스 집계가 아직 완료되지 않았을 가능성도 있습니다.
        """
    )

    # 개발자에게 도움이 되도록 실제 오류 내용도 접어서 보여줍니다.
    with st.expander("오류 상세 내용"):
        st.code(str(error))

    st.stop()


# ---------------------------------------------------------
# 8. 데이터가 최종적으로 비어 있는지 한 번 더 확인
# ---------------------------------------------------------
if df.empty:
    st.warning(
        "조회된 영화 목록이 없습니다. "
        "KOBIS의 어제 박스오피스 집계가 완료되었는지 확인해 주세요."
    )
    st.stop()


# ---------------------------------------------------------
# 9. 1위 영화 지표 카드
# ---------------------------------------------------------
first_movie = df.iloc[0]

st.subheader("🏆 1위 영화")

card1, card2, card3 = st.columns(3)

with card1:
    st.metric(
        label="영화",
        value=first_movie["영화명"],
    )

with card2:
    st.metric(
        label="어제 관객수",
        value=f"{first_movie['관객수']:,}명",
    )

with card3:
    st.metric(
        label="누적 관객",
        value=f"{first_movie['누적관객']:,}명",
    )


# ---------------------------------------------------------
# 10. 관객수 상위 5편 막대그래프
# ---------------------------------------------------------
st.subheader("📊 관객수 상위 5편")

top5 = (
    df.sort_values("관객수", ascending=False)
    .head(5)
    .set_index("영화명")
)

st.bar_chart(
    top5["관객수"],
    horizontal=True,
)


# ---------------------------------------------------------
# 11. 전체 박스오피스 표
# ---------------------------------------------------------
st.subheader("🎞️ 전체 박스오피스")

# 화면에서는 숫자에 천 단위 구분기호를 표시합니다.
display_df = df.copy()

for column in ["관객수", "누적관객", "스크린수"]:
    display_df[column] = display_df[column].map(lambda x: f"{x:,}")

st.dataframe(
    display_df,
    use_container_width=True,
    hide_index=True,
)
