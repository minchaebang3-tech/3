import streamlit as st
import pandas as pd
import requests

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo


# ============================================================
# 1. Streamlit 기본 설정
# ============================================================

st.set_page_config(
    page_title="KOBIS 박스오피스",
    page_icon="🎬",
    layout="wide",
)


# ============================================================
# 2. KOBIS API 주소
# ============================================================

# 일일 박스오피스 API
BOXOFFICE_API_URL = (
    "https://www.kobis.or.kr/"
    "kobisopenapi/webservice/rest/boxoffice/"
    "searchDailyBoxOfficeList.json"
)

# 영화 목록 검색 API
MOVIE_SEARCH_API_URL = (
    "https://www.kobis.or.kr/"
    "kobisopenapi/webservice/rest/movie/"
    "searchMovieList.json"
)


# ============================================================
# 3. 관심 영화 목록 초기화
# ============================================================

# 관심 영화는 별도의 DB 대신 Streamlit Session State에 저장합니다.
#
# 예:
# {
#     "12345678": {
#         "movieCd": "12345678",
#         "movieNm": "영화 제목",
#         "openDt": "2026-01-01"
#     }
# }
#
# Session State는 현재 사용자의 앱 세션에서 유지됩니다.
if "favorite_movies" not in st.session_state:
    st.session_state["favorite_movies"] = {}


# ============================================================
# 4. 한국 시간 기준 날짜 계산
# ============================================================

def get_korea_dates():
    """
    배포 서버의 시간대가 한국 시간이 아니더라도
    Asia/Seoul 기준으로 오늘과 어제 날짜를 계산합니다.
    """

    korea_now = datetime.now(ZoneInfo("Asia/Seoul"))

    yesterday = korea_now - timedelta(days=1)

    yesterday_api = yesterday.strftime("%Y%m%d")
    yesterday_display = yesterday.strftime("%Y년 %m월 %d일")

    return yesterday_api, yesterday_display


# ============================================================
# 5. KOBIS 인증키 가져오기
# ============================================================

def get_kobis_key():
    """
    인증키를 코드에 직접 작성하지 않습니다.

    Streamlit Cloud의 Secrets에 다음처럼 등록하세요.

    KOBIS_KEY = "실제_인증키"
    """

    try:
        key = st.secrets["KOBIS_KEY"]
    except KeyError as error:
        raise RuntimeError(
            "KOBIS_KEY를 찾을 수 없습니다.\n\n"
            "Streamlit Cloud의 앱 설정 → Secrets에서 "
            "KOBIS_KEY가 등록되어 있는지 확인하세요."
        ) from error

    except Exception as error:
        raise RuntimeError(
            "Streamlit Secrets를 읽는 중 문제가 발생했습니다."
        ) from error

    if not str(key).strip():
        raise RuntimeError(
            "KOBIS_KEY가 비어 있습니다. "
            "Streamlit Cloud의 Secrets에 올바른 인증키를 입력하세요."
        )

    return str(key).strip()


# ============================================================
# 6. KOBIS API 공통 요청 함수
# ============================================================

def request_kobis_api(url, params):
    """
    KOBIS API를 호출하고 기본적인 오류를 검사합니다.

    중요한 점:
    KOBIS는 인증키가 틀려도 HTTP 200을 반환할 수 있으므로
    HTTP 상태 코드만 확인하지 않고 faultInfo도 확인합니다.
    """

    try:
        response = requests.get(
            url,
            params=params,
            timeout=15,
        )

    except requests.exceptions.Timeout as error:
        raise RuntimeError(
            "KOBIS API 요청 시간이 초과되었습니다. "
            "잠시 후 다시 시도해 주세요."
        ) from error

    except requests.exceptions.RequestException as error:
        raise RuntimeError(
            "KOBIS API에 연결하지 못했습니다. "
            "네트워크 연결 또는 KOBIS API 상태를 확인해 주세요."
        ) from error

    if response.status_code != 200:
        raise RuntimeError(
            f"KOBIS API 요청에 실패했습니다. "
            f"(HTTP 상태 코드: {response.status_code})"
        )

    try:
        data = response.json()

    except ValueError as error:
        raise RuntimeError(
            "KOBIS API가 올바른 JSON 응답을 반환하지 않았습니다."
        ) from error

    # 인증키 오류 등은 HTTP 200이어도 faultInfo로 전달될 수 있습니다.
    fault_info = data.get("faultInfo")

    if fault_info:
        message = (
            fault_info.get("message")
            or fault_info.get("messageId")
            or "KOBIS API에서 오류가 반환되었습니다."
        )

        raise RuntimeError(
            f"KOBIS API 오류: {message}"
        )

    return data


# ============================================================
# 7. 일일 박스오피스 조회
# ============================================================

@st.cache_data(ttl=600)
def get_daily_boxoffice(target_date):
    """
    지정한 날짜의 박스오피스를 가져옵니다.

    10분 동안 같은 날짜의 API 결과를 캐시해서
    불필요하게 API를 반복 호출하지 않도록 합니다.
    """

    api_key = get_kobis_key()

    params = {
        "key": api_key,
        "targetDt": target_date,
    }

    data = request_kobis_api(
        BOXOFFICE_API_URL,
        params,
    )

    boxoffice_result = data.get("boxOfficeResult")

    if not isinstance(boxoffice_result, dict):
        raise RuntimeError(
            "KOBIS 응답에 boxOfficeResult가 없습니다. "
            "KOBIS API 응답 형식을 확인해 주세요."
        )

    movie_list = boxoffice_result.get(
        "dailyBoxOfficeList"
    )

    if not isinstance(movie_list, list):
        raise RuntimeError(
            "KOBIS 응답에 영화 목록이 없습니다. "
            "조회 날짜와 API 상태를 확인해 주세요."
        )

    if len(movie_list) == 0:
        raise RuntimeError(
            "조회된 영화 목록이 없습니다.\n\n"
            "한국 시간 기준 어제의 박스오피스 집계가 "
            "아직 완료되지 않았을 수 있습니다."
        )

    return movie_list


# ============================================================
# 8. 영화 검색
# ============================================================

@st.cache_data(ttl=600)
def search_movies(movie_name):
    """
    영화 제목으로 KOBIS 영화 목록을 검색합니다.
    """

    api_key = get_kobis_key()

    params = {
        "key": api_key,
        "movieNm": movie_name,
        "itemPerPage": "20",
    }

    data = request_kobis_api(
        MOVIE_SEARCH_API_URL,
        params,
    )

    movie_list_result = data.get("movieListResult")

    if not isinstance(movie_list_result, dict):
        raise RuntimeError(
            "KOBIS 영화 검색 결과 형식이 올바르지 않습니다."
        )

    movie_list = movie_list_result.get("movieList", [])

    if not isinstance(movie_list, list):
        return []

    return movie_list


# ============================================================
# 9. 숫자 안전하게 변환
# ============================================================

def safe_int(value, default=0):
    """
    KOBIS API의 숫자는 문자열로 오므로 안전하게 정수로 변환합니다.
    """

    try:
        return int(value)
    except (TypeError, ValueError):
        return default


# ============================================================
# 10. 박스오피스 DataFrame 만들기
# ============================================================

def make_boxoffice_dataframe(movie_list):
    """
    KOBIS 박스오피스 응답을 화면에 표시하기 좋은
    DataFrame으로 변환합니다.
    """

    rows = []

    for movie in movie_list:

        rows.append(
            {
                "순위": safe_int(movie.get("rank")),
                "영화명": movie.get("movieNm", "-"),
                "개봉일": movie.get("openDt", "-"),
                "관객수": safe_int(movie.get("audiCnt")),
                "누적관객": safe_int(movie.get("audiAcc")),
                "스크린수": safe_int(movie.get("scrnCnt")),
                "영화코드": movie.get("movieCd", ""),
            }
        )

    return pd.DataFrame(rows)


# ============================================================
# 11. 관심 영화 추가
# ============================================================

def add_favorite(movie):
    """
    관심 영화 목록에 영화를 추가합니다.
    """

    movie_cd = str(movie.get("movieCd", "")).strip()

    if not movie_cd:
        st.warning(
            "이 영화에는 영화 코드가 없어 "
            "관심 영화로 저장할 수 없습니다."
        )
        return

    st.session_state["favorite_movies"][movie_cd] = {
        "movieCd": movie_cd,
        "movieNm": movie.get("movieNm", "이름 없음"),
        "openDt": movie.get("openDt", ""),
    }


# ============================================================
# 12. 관심 영화 삭제
# ============================================================

def remove_favorite(movie_cd):
    """
    관심 영화 목록에서 영화를 삭제합니다.
    """

    if movie_cd in st.session_state["favorite_movies"]:
        del st.session_state["favorite_movies"][movie_cd]


# ============================================================
# 13. 관심 영화 여부 확인
# ============================================================

def is_favorite(movie_cd):
    """
    해당 영화가 관심 영화로 등록되어 있는지 확인합니다.
    """

    return movie_cd in st.session_state["favorite_movies"]


# ============================================================
# 14. 날짜 준비
# ============================================================

target_date, display_date = get_korea_dates()


# ============================================================
# 15. 화면 제목
# ============================================================

st.title("🎬 KOBIS 박스오피스")

st.caption(
    f"한국 시간 기준 · {display_date} 박스오피스"
)


# ============================================================
# 16. 탭 구성
# ============================================================

tab_boxoffice, tab_search, tab_favorite = st.tabs(
    [
        "🏠 어제의 박스오피스",
        "🔎 영화 검색",
        "⭐ 관심 영화",
    ]
)


# ============================================================
# 17. 어제의 박스오피스 탭
# ============================================================

with tab_boxoffice:

    try:
        movie_list = get_daily_boxoffice(
            target_date
        )

        df = make_boxoffice_dataframe(
            movie_list
        )

    except Exception as error:

        st.error(
            "박스오피스 정보를 가져오지 못했습니다."
        )

        st.markdown(
            """
            ### 🔎 다음 항목을 확인해 주세요

            1. **KOBIS 인증키**
               - Streamlit Cloud의 앱 설정 → Secrets를 확인하세요.
               - `KOBIS_KEY`가 정확하게 등록되어 있는지 확인하세요.

            2. **KOBIS API 상태**
               - KOBIS API가 일시적으로 응답하지 않을 수 있습니다.
               - 잠시 후 다시 실행해 보세요.

            3. **어제 날짜의 집계 상태**
               - 이 앱은 한국 시간 기준으로 어제 날짜를 조회합니다.
               - 박스오피스 집계가 아직 완료되지 않았을 수 있습니다.

            4. **네트워크 연결**
               - Streamlit Cloud에서 KOBIS API에 연결할 수 있는지 확인하세요.
            """
        )

        with st.expander("오류 상세 내용"):
            st.code(str(error))

        st.stop()

    # 영화 목록이 비어 있는 경우를 한 번 더 확인합니다.
    if df.empty:

        st.warning(
            "조회된 영화 목록이 없습니다. "
            "KOBIS의 어제 박스오피스 집계 상태와 "
            "KOBIS_KEY를 확인해 주세요."
        )

    else:

        # ----------------------------------------------------
        # 1위 영화
        # ----------------------------------------------------

        first_movie = df.iloc[0]

        st.subheader("🏆 박스오피스 1위")

        card1, card2, card3 = st.columns(3)

        with card1:
            st.metric(
                label="영화",
                value=str(first_movie["영화명"]),
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

        # ----------------------------------------------------
        # 관객수 TOP 5
        # ----------------------------------------------------

        st.subheader("📊 관객수 상위 5편")

        top5 = (
            df.sort_values(
                "관객수",
                ascending=False,
            )
            .head(5)
        )

        chart_data = (
            top5.set_index("영화명")[["관객수"]]
        )

        st.bar_chart(
            chart_data,
            horizontal=True,
        )

        # ----------------------------------------------------
        # 전체 박스오피스
        # ----------------------------------------------------

        st.subheader("🎞️ 전체 박스오피스")

        display_df = df.copy()

        # 화면에만 천 단위 구분기호를 적용합니다.
        display_df["관객수"] = display_df[
            "관객수"
        ].map(lambda x: f"{x:,}")

        display_df["누적관객"] = display_df[
            "누적관객"
        ].map(lambda x: f"{x:,}")

        display_df["스크린수"] = display_df[
            "스크린수"
        ].map(lambda x: f"{x:,}")

        # 영화코드는 사용자에게 보여줄 필요가 없으므로 제외합니다.
        display_df = display_df[
            [
                "순위",
                "영화명",
                "개봉일",
                "관객수",
                "누적관객",
                "스크린수",
            ]
        ]

        st.dataframe(
            display_df,
            use_container_width=True,
            hide_index=True,
        )


# ============================================================
# 18. 영화 검색 탭
# ============================================================

with tab_search:

    st.subheader("🔎 영화 검색")

    st.write(
        "KOBIS에 등록된 영화 제목을 검색할 수 있습니다."
    )

    # 검색어 입력창
    search_keyword = st.text_input(
        "영화 제목",
        placeholder="예: 아바타",
        key="movie_search_keyword",
    )

    search_button = st.button(
        "🔍 검색",
        key="movie_search_button",
        use_container_width=False,
    )

    if search_button:

        # 검색어가 비어 있으면 API를 호출하지 않습니다.
        if not search_keyword.strip():

            st.warning(
                "검색할 영화 제목을 입력해 주세요."
            )

        else:

            try:
                search_result = search_movies(
                    search_keyword.strip()
                )

            except Exception as error:

                st.error(
                    "영화 검색에 실패했습니다."
                )

                st.markdown(
                    """
                    ### 🔎 다음 항목을 확인해 주세요

                    - Streamlit Cloud의 `KOBIS_KEY`가 등록되어 있는지 확인하세요.
                    - KOBIS API가 정상적으로 응답하는지 확인하세요.
                    - 잠시 후 다시 검색해 보세요.
                    """
                )

                with st.expander("오류 상세 내용"):
                    st.code(str(error))

            else:

                if not search_result:

                    st.info(
                        "검색 결과가 없습니다. "
                        "영화 제목을 조금 다르게 입력해 보세요."
                    )

                else:

                    st.success(
                        f"총 {len(search_result)}개의 검색 결과를 찾았습니다."
                    )

                    # 검색 결과를 하나씩 보여줍니다.
                    for index, movie in enumerate(
                        search_result
                    ):

                        movie_cd = str(
                            movie.get(
                                "movieCd",
                                ""
                            )
                        ).strip()

                        movie_name = movie.get(
                            "movieNm",
                            "영화명 없음"
                        )

                        open_date = movie.get(
                            "openDt",
                            "-"
                        )

                        directors = movie.get(
                            "directors",
                            []
                        )

                        # 감독 이름을 하나의 문자열로 만듭니다.
                        director_names = ", ".join(
                            director.get(
                                "peopleNm",
                                ""
                            )
                            for director in directors
                            if director.get(
                                "peopleNm"
                            )
                        )

                        genres = movie.get(
                            "genreAlt",
                            "-"
                        )

                        nations = movie.get(
                            "nationAlt",
                            "-"
                        )

                        # 영화마다 구분선을 넣습니다.
                        st.markdown("---")

                        col1, col2 = st.columns(
                            [5, 1]
                        )

                        with col1:

                            st.markdown(
                                f"### 🎬 {movie_name}"
                            )

                            st.write(
                                f"**개봉일:** {open_date}"
                            )

                            st.write(
                                f"**장르:** {genres}"
                            )

                            st.write(
                                f"**제작국가:** {nations}"
                            )

                            if director_names:
                                st.write(
                                    f"**감독:** {director_names}"
                                )

                            if movie_cd:
                                st.caption(
                                    f"영화코드: {movie_cd}"
                                )

                        with col2:

                            if movie_cd:

                                if is_favorite(
                                    movie_cd
                                ):

                                    if st.button(
                                        "⭐ 관심 해제",
                                        key=(
                                            f"search_remove_"
                                            f"{movie_cd}_{index}"
                                        ),
                                    ):
                                        remove_favorite(
                                            movie_cd
                                        )

                                        st.rerun()

                                else:

                                    if st.button(
                                        "☆ 관심 등록",
                                        key=(
                                            f"search_add_"
                                            f"{movie_cd}_{index}"
                                        ),
                                    ):
                                        add_favorite(
                                            movie
                                        )

                                        st.rerun()


# ============================================================
# 19. 관심 영화 탭
# ============================================================

with tab_favorite:

    st.subheader("⭐ 관심 영화")

    favorites = st.session_state[
        "favorite_movies"
    ]

    # 관심 영화가 하나도 없는 경우
    if not favorites:

        st.info(
            "아직 관심 영화가 없습니다.\n\n"
            "「🔎 영화 검색」 탭에서 영화를 검색한 뒤 "
            "☆ 관심 등록 버튼을 눌러 보세요."
        )

    else:

        st.write(
            f"현재 {len(favorites)}개의 영화를 관심 목록에 저장했습니다."
        )

        # 현재 박스오피스 데이터를 가져옵니다.
        # 관심 영화의 현재 순위를 보여주기 위해 사용합니다.
        try:

            current_boxoffice = (
                get_daily_boxoffice(
                    target_date
                )
            )

            current_by_code = {}

            for movie in current_boxoffice:

                movie_cd = str(
                    movie.get(
                        "movieCd",
                        ""
                    )
                ).strip()

                if movie_cd:
                    current_by_code[
                        movie_cd
                    ] = movie

        except Exception:

            # 관심 영화 자체는 볼 수 있어야 하므로
            # 박스오피스 API가 실패해도 페이지 전체를 막지 않습니다.
            current_by_code = {}

            st.warning(
                "현재 박스오피스 정보를 가져오지 못했습니다. "
                "관심 영화 목록은 볼 수 있지만 "
                "현재 순위와 관객수는 표시할 수 없습니다."
            )

        # 관심 영화 하나씩 표시합니다.
        for movie_cd, favorite in list(
            favorites.items()
        ):

            movie_name = favorite.get(
                "movieNm",
                "영화명 없음"
            )

            open_date = favorite.get(
                "openDt",
                "-"
            )

            st.markdown("---")

            col1, col2, col3 = st.columns(
                [4, 3, 1]
            )

            with col1:

                st.markdown(
                    f"### ⭐ {movie_name}"
                )

                st.write(
                    f"개봉일: {open_date}"
                )

            with col2:

                current_movie = (
                    current_by_code.get(
                        movie_cd
                    )
                )

                if current_movie:

                    rank = safe_int(
                        current_movie.get(
                            "rank"
                        )
                    )

                    audience = safe_int(
                        current_movie.get(
                            "audiCnt"
                        )
                    )

                    accumulated = safe_int(
                        current_movie.get(
                            "audiAcc"
                        )
                    )

                    screens = safe_int(
                        current_movie.get(
                            "scrnCnt"
                        )
                    )

                    st.write(
                        f"**현재 순위:** {rank}위"
                    )

                    st.write(
                        f"**어제 관객수:** "
                        f"{audience:,}명"
                    )

                    st.write(
                        f"**누적 관객:** "
                        f"{accumulated:,}명"
                    )

                    st.write(
                        f"**스크린수:** "
                        f"{screens:,}개"
                    )

                else:

                    st.caption(
                        "현재 박스오피스에 없습니다."
                    )

            with col3:

                if st.button(
                    "관심 해제",
                    key=f"favorite_remove_{movie_cd}",
                ):

                    remove_favorite(
                        movie_cd
                    )

                    st.rerun()


# ============================================================
# 20. 하단 안내
# ============================================================

st.divider()

st.caption(
    "데이터 출처: 영화관입장권통합전산망(KOBIS) Open API"
)
