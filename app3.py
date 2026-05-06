import streamlit as st
import feedparser
import pandas as pd
from datetime import datetime
import urllib.parse
import requests
import plotly.express as px

st.set_page_config(page_title="KIST Europe News Monitor", layout="wide")

st.sidebar.title("Monitoring Settings")

# --- Naver 사용 여부 선택 ---
st.sidebar.subheader("Data Source")
use_naver = st.sidebar.toggle("Use Naver API", value=True)

if use_naver:
    st.sidebar.subheader("Naver API Credentials")
    naver_id = st.sidebar.text_input("Naver Client ID", type="password")
    naver_secret = st.sidebar.text_input("Naver Client Secret", type="password")
else:
    naver_id, naver_secret = None, None

st.sidebar.subheader("1. Search Keywords")
default_keywords = 'KIST Europe, KIST 유럽, KIST 유럽연구소, 한국과학기술연구원 유럽'
user_input_keywords = st.sidebar.text_area("Keywords (comma separated)", default_keywords)
keyword_list = [k.strip() for k in user_input_keywords.split(",")]

st.sidebar.subheader("2. Target Countries")
lang_options = {
    "South Korea (KO)": {"hl": "ko", "gl": "KR"},
    "Germany (DE)": {"hl": "de", "gl": "DE"},
    "USA (EN)": {"hl": "en", "gl": "US"},
    "UK (EN)": {"hl": "en", "gl": "GB"},
    "France (FR)": {"hl": "fr", "gl": "FR"},
    "Belgium (NL/FR)": {"hl": "nl", "gl": "BE"},
    "Europe (Global EN)": {"hl": "en", "gl": "IE"}
}
selected_langs = st.sidebar.multiselect(
    "Select regions", list(lang_options.keys()),
    default=["South Korea (KO)", "Germany (DE)", "USA (EN)"]
)

selected_year = st.sidebar.selectbox("Select Year", range(datetime.now().year, 2014, -1))
# KIST 공식 컬러 팔레트
KIST_RED    = "#E44126"
KIST_DGRAY  = "#6D6E67"
KIST_GRAY   = "#ADADB0"
KIST_SILVER = "#B0B9BF"
KIST_GOLD   = "#BC9D54"

KIST_COLORS = [KIST_RED, KIST_GOLD, KIST_DGRAY, KIST_GRAY, KIST_SILVER]


def parse_date(date_str):
    try:
        dt = pd.to_datetime(date_str)
        if dt.tzinfo is not None:
            dt = dt.tz_localize(None)
        return dt
    except:
        return datetime(2000, 1, 1)


def fetch_naver_api(keyword_list, client_id, client_secret, year):
    search_query = " OR ".join([f'"{kw.strip()}"' for kw in keyword_list])
    encoded_query = urllib.parse.quote(search_query)
    headers = {
        "X-Naver-Client-Id": client_id,
        "X-Naver-Client-Secret": client_secret
    }
    data = []
    for start in range(1, 1001, 100):
        url = (
            f"https://openapi.naver.com/v1/search/news.json"
            f"?query={encoded_query}&display=100&start={start}&sort=date"
        )
        response = requests.get(url, headers=headers)
        if response.status_code != 200:
            break
        items = response.json().get('items', [])
        if not items:
            break
        for item in items:
            title = (item['title']
                     .replace("<b>", "").replace("</b>", "")
                     .replace("&quot;", '"').replace("&amp;", "&"))
            description = item['description'].replace("<b>", "").replace("</b>", "")
            full_content_clean = (title + description).replace(" ", "").lower()
            is_match = any(kw.replace(" ", "").lower() in full_content_clean for kw in keyword_list)
            if is_match and str(year) in item['pubDate']:
                link_to_check = item['originallink'] if item['originallink'] else item['link']
                try:
                    domain = link_to_check.split('//')[1].split('/')[0].replace('www.', '')
                    press_map = {
                        "yna.co.kr": "연합뉴스", "news.naver.com": "네이버뉴스",
                        "khan.co.kr": "경향신문", "hani.co.kr": "한겨레",
                        "donga.com": "동아일보", "chosun.com": "조선일보",
                        "joongang.co.kr": "중앙일보", "sedaily.com": "서울경제",
                        "hankyung.com": "한국경제", "etnews.com": "전자신문",
                        "mk.co.kr": "매일경제", "newsis.com": "뉴시스", "news1.kr": "뉴스1"
                    }
                    source_name = press_map.get(domain, domain.split('.')[0].upper())
                except:
                    source_name = "Naver News"
                data.append({
                    "Channel": "NAVER (API)",
                    "Source": source_name,
                    "Title": title,
                    "Published": parse_date(item['pubDate']),
                    "Link": link_to_check,
                    "Region": "South Korea (KO)"
                })
    return data


def fetch_google_news(query, hl, gl, region_name, year):
    encoded_query = urllib.parse.quote(f'"{query}" after:{year}-01-01 before:{year}-12-31')
    url = f"https://news.google.com/rss/search?q={encoded_query}&hl={hl}&gl={gl}&ceid={gl}:{hl}"
    feed = feedparser.parse(url)
    data = []
    blacklist = ["ttc", "ping pong", "탁구", "bundesliga"]
    for entry in feed.entries:
        title = entry.title
        if not any(bad in title.lower() for bad in blacklist):
            data.append({
                "Channel": "Google (RSS)",
                "Source": entry.source.title if hasattr(entry, 'source') else "Google",
                "Title": title,
                "Published": parse_date(entry.published),
                "Link": entry.link,
                "Region": region_name
            })
    return data


def render_charts(df):
    col1, col2 = st.columns(2)
    with col1:
        region_counts = df['Region'].value_counts().reset_index()
        region_counts.columns = ['Region', 'Count']
        fig = px.pie(
                region_counts, values='Count', names='Region',
                title="📌 Articles by Region",
                color_discrete_sequence=KIST_COLORS
            )
        st.plotly_chart(fig, use_container_width=True)
    with col2:
        source_counts = df['Source'].value_counts().head(10).reset_index()
        source_counts.columns = ['Source', 'Count']
        fig2 = px.bar(
            source_counts, x='Source', y='Count',
            title="📌 Top 10 Sources",
            color='Count',
            color_continuous_scale=[KIST_DGRAY, KIST_RED]
        )

        fig2.update_layout(xaxis_tickangle=-30)
        st.plotly_chart(fig2, use_container_width=True)

    # 월별 기사 수 트렌드
    df_copy = df.copy()
    df_copy['Month'] = df_copy['Published'].dt.to_period('M').astype(str)
    monthly = df_copy.groupby('Month').size().reset_index(name='Count')
    fig3 = px.line(monthly, x='Month', y='Count',
                   title="📌 Monthly Article Trend", markers=True)
    fig3.update_traces(
        line=dict(color=KIST_RED, width=3),
        marker=dict(size=8, color=KIST_GOLD)  # 마커는 골드
    )
    fig3.update_layout(xaxis_tickangle=-30)
    st.plotly_chart(fig3, use_container_width=True)



# --- Main UI ---
st.title("KIST Europe Global News")

# 현재 모드 표시
if use_naver:
    st.info("Mode: Naver API + Google RSS")
else:
    st.info("Mode: Google RSS")

if st.sidebar.button("▶ Start Collection"):
    if use_naver and (not naver_id or not naver_secret):
        st.error("Please enter your Naver API credentials.")
    else:
        all_results = []
        with st.spinner('Collecting news...'):
            for lang_name in selected_langs:
                params = lang_options[lang_name]

                # Naver: Korea 선택 + Naver 토글 ON일 때만
                if use_naver and lang_name == "South Korea (KO)":
                    all_results.extend(
                        fetch_naver_api(keyword_list, naver_id, naver_secret, selected_year)
                    )

                # Google: 항상 수집
                for kw in keyword_list:
                    all_results.extend(
                        fetch_google_news(kw, params['hl'], params['gl'], lang_name, selected_year)
                    )

        if all_results:
            df = pd.DataFrame(all_results).drop_duplicates(subset=['Link'])
            df = df.sort_values(by="Published", ascending=False)
            df.index = range(1, len(df) + 1)

            st.success(f"✅ Collection Complete! **{len(df)}** articles found.")
            st.metric("Total Articles", f"{len(df)} pcs")
            st.divider()

            render_charts(df)

            st.divider()
            st.subheader(f"Integrated News List ({selected_year})")
            display_df = df.copy()
            display_df['Published'] = display_df['Published'].dt.strftime('%Y-%m-%d')
            st.dataframe(
                display_df[["Channel", "Region", "Source", "Title", "Published"]],
                use_container_width=True
            )
            # --- CSV 다운로드 ---
            csv_df = df.copy()
            csv_df['Published'] = csv_df['Published'].dt.strftime('%Y-%m-%d')
            csv_data = csv_df[["Channel", "Region", "Source", "Title", "Published", "Link"]].to_csv(index=False, encoding='utf-8-sig')

            st.download_button(
                label="📥 Download CSV",
                data=csv_data,
                file_name=f"KIST_Europe_News_{selected_year}.csv",
                mime="text/csv"
            )


            st.divider()
            st.subheader("Detailed Preview (Descending Order)")
            for idx, row in df.iterrows():
                with st.expander(
                    f"No.{idx} | {row['Published'].strftime('%Y-%m-%d')} | [{row['Source']}] {row['Title']}"
                ):
                    st.write(f"**Region:** {row['Region']} | **Channel:** {row['Channel']}")
                    st.write(f"[Read Full Article]({row['Link']})")
        else:
            st.warning("No matching articles found.")
