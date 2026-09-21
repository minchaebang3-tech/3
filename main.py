import streamlit as st
import pandas as pd

from utils import (
    get_yesterday_dates,
    get_daily_boxoffice,
    make_boxoffice_dataframe,
    get_favorite_movies,
    add_favorite_movie,
    remove_favorite_movie,
)


# ---------------------------------------------------------
# 페이지 기본 설정
# ---------------------------------------------------------
st.set_page_config(
    page_title="KOBIS 박스오피스",
    page_icon="🎬",
    layout="wide",
)


# ---------------------------------------------------------
# 세션 상태 초기화
# ---------------------------------------------------------
# 관심 영화 목록을 현재 브라우저 세션에 저장합니다.
if "favorite_movies" not in st.session_state:
    st.session_state["favorite_movies"] = {}


# ---------------------------------------------------------
# 제목
# ---------------------------------------------------------
st.title("🎬 KOBIS 박스오피스")

target_date, display_date = get_yesterday_dates()

st.caption(
    f"{display_date} · 한국 시간(Asia/Seoul) 기준 어제"
)


# ---------------------------------------------------------
# 어제 박스오피스 가져오기
# ---------------------------------------------------------
try:
    movie_list = get_daily_boxoffice(target_date)

except Exception as error:
    st.error("박스오피스 정보를 가져오지 못했습니다.")

    st.markdown(
        """
        ### 확인해 주세요

        - Streamlit Cloud의 **Settings → Secrets**에
          `KOBIS_KEY`가 등록되어 있는지 확인하세요.
        - KOBIS 인증키가 정확한지 확인하세요.
        - KOBIS API가 정상적으로 응답하는지 확인하세요.
        - 한국 시간 기준 어제의 박스오피스 집계가 완료되었는지 확인하세요.
        """
    )

    with st.expander("오류 상세 내용"):
        st.code(str(error))

    st.stop()


# ---------------------------------------------------------
# DataFrame으로 변환
# ---------------------------------------------------------
try:
    df = make_boxoffice_dataframe(movie_list)

except Exception as error:
    st.error("박스오피스 데이터를 화면에 표시하지 못했습니다.")

    with st.expander("오류 상세 내용"):
        st.code(str(error))

    st.stop()


if df.empty:
    st.warning(
        "조회된 영화 목록이 없습니다. "
        "KOBIS의 어제 박스오피스 집계가 완료되었는지 확인해 주세요."
    )
    st.stop()


# ---------------------------------------------------------
# 관심 영화 목록
# ---------------------------------------------------------
favorites = get_favorite_movies()


# ---------------------------------------------------------
# 1위 영화
# ---------------------------------------------------------
first_movie = df.iloc[0]

st.subheader("🏆 1위 영화")

card1, card2, card3 = st.columns(3)

with card1:
    st.metric(
        "영화",
        first_movie["영화명"],
    )

with card2:
    st.metric(
        "어제 관객수",
        f"{first_movie['관객수']:,}명",
    )

with card3:
    st.metric(
        "누적 관객",
        f"{first_movie['누적관객']:,}명",
    )


# ---------------------------------------------------------
# 1위 영화 관심 영화 버튼
# ---------------------------------------------------------
first_movie_code = str(first_movie["영화코드"])

if first_movie_code:
    if first_movie_code in favorites:
        if st.button(
            "⭐ 관심 영화 해제",
            key=f"main_remove_{first_movie_code}",
        ):
            remove_favorite_movie(first_movie_code)
            st.rerun()
    else:
        if st.button(
            "☆ 관심 영화 등록",
            key=f"main_add_{first_movie_code}",
        ):
            add_favorite_movie(
                movie_code=first_movie_code,
                movie_name=first_movie["영화명"],
                open_date=first_movie["개봉일"],
            )
            st.rerun()


# ---------------------------------------------------------
# 관객수 TOP 5
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
# 전체 박스오피스
# ---------------------------------------------------------
st.subheader("🎞️ 전체 박스오피스")

# 관심 영화 여부를 표시하기 위한 컬럼입니다.
display_df = df.copy()

display_df.insert(
    0,
    "관심",
    display_df["영화코드"].apply(
        lambda code: "⭐" if str(code) in favorites else ""
    ),
)

# 화면에 보여줄 컬럼만 선택합니다.
display_df = display_df[
    [
        "관심",
        "순위",
        "영화명",
        "개봉일",
        "관객수",
        "누적관객",
        "스크린수",
    ]
].copy()


# 숫자를 읽기 쉽게 천 단위 쉼표로 표시합니다.
for column in ["관객수", "누적관객", "스크린수"]:
    display_df[column] = display_df[column].map(
        lambda value: f"{value:,}"
    )


st.dataframe(
    display_df,
    use_container_width=True,
    hide_index=True,
)


# ---------------------------------------------------------
# 관심 영화 관리
# ---------------------------------------------------------
st.subheader("⭐ 관심 영화")

if not favorites:
    st.info(
        "관심 영화가 없습니다. "
        "영화 옆의 ☆ 버튼을 눌러 관심 영화로 등록해 보세요."
    )
else:
    for movie_code, movie_info in favorites.items():
        col1, col2 = st.columns([5, 1])

        with col1:
            st.write(
                f"⭐ **{movie_info.get('movie_name', '알 수 없는 영화')}**"
            )

        with col2:
            if st.button(
                "삭제",
                key=f"main_favorite_delete_{movie_code}",
            ):
                remove_favorite_movie(movie_code)
                st.rerun()

st.divider()

st.info(
    "📌 더 자세한 기능은 왼쪽 메뉴의 "
    "**어제 vs 그제 / 영화 검색 / 관심 영화** 페이지에서 이용할 수 있습니다."
)

