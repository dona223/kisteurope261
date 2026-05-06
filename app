import streamlit as st
import feedparser
import pandas as pd
from datetime import datetime
import urllib.parse
import requests
import plotly.express as px

st.set_page_config(page_title="KIST Europe Global Monitor v6.0", layout="wide")

st.sidebar.title("🛠️ Monitoring Settings")

st.sidebar.subheader("🔑 Naver API Credentials")
naver_id = st.sidebar.text_input("Naver Client ID", type="password")
naver_secret = st.sidebar.text_input("Naver Client Secret", type="password")

st.sidebar.subheader("1. Search Keywords")
default_keywords = 'KIST Europe, KIST 유럽, KIST 유럽연구소, 한국과학기술연구원 유럽, 한국과학기술연구원(KIST)'
user_input_keywords = st.sidebar.text_area("Keywords (comma separated)", default_keywords)
keyword_list = [k.strip() for k in user_input_keywords.split(",")]
search_query_base = " OR ".join([f'"{kw}"' for kw in keyword_list])

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


def parse_date(date_str):
    try:
        dt = pd.to_datetime(date_str)
        if dt.tzinfo is not None:
            dt = dt.tz_localize(None)
        return dt
    except:
        return datetime(2000, 1, 1)


def fetch_naver_api(keyword_list, client_id, client_secret, year):
    """
    🔧 수정사항:
    1. start 파라미터로 페이지네이션 구현 (최대 1000개)
    2. 연도 필터를 pubDate 문자열 포함 여부로 유지
    """
    search_query = " OR ".join([f'"{kw.strip()}"' for kw in keyword_list])
    encoded_query = urllib.parse.quote(search_query)

    headers = {
        "X-Naver-Client-Id": client_id,
        "X-Naver-Client-Secret": client_secret
    }

    data = []
    # 🔧 핵심 수정: start=1부터 1000까지 100개씩 페이지네이션
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
            break  # 더 이상 결과 없음

        for item in items:
            title = (item['title']
                     .replace("<b>", "").replace("</b>", "")
                     .replace("&quot;", '"').replace("&amp;", "&"))
            description = (item['description']
                           .replace("<b>", "").replace("</b>", ""))

            full_content_clean = (title + description).replace(" ", "").lower()

            is_match = any(
                kw.replace(" ", "").lower() in full_content_clean
                for kw in keyword_list
            )

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


# --- Main UI ---
st.title("📡 KIST Europe Global News Center")

if st.sidebar.button("Start Combined Collection"):
    if not naver_id or not naver_secret:
        st.error("Please enter Naver API credentials in the sidebar.")
    else:
        all_results = []
        with st.spinner('Collecting and sorting news from multiple channels...'):

            for lang_name in selected_langs:
                params = lang_options[lang_name]

                # 🔧 핵심 수정: keyword_list 전체를 한 번만 넘김 (루프 X)
                if lang_name == "South Korea (KO)":
                    all_results.extend(
                        fetch_naver_api(keyword_list, naver_id, naver_secret, selected_year)
                    )

                # Google은 키워드별로 개별 검색 (각 키워드로 더 넓게 수집)
                for kw in keyword_list:
                    all_results.extend(
                        fetch_google_news(kw, params['hl'], params['gl'], lang_name, selected_year)
                    )

        if all_results:
            df = pd.DataFrame(all_results).drop_duplicates(subset=['Link'])
            df = df.sort_values(by="Published", ascending=False)
            df.index = range(1, len(df) + 1)

            st.success(f"Search Complete! Total {len(df)} unique articles found.")

            col1, col2 = st.columns([1, 1])
            with col1:
                st.metric("Total Articles", f"{len(df)} pcs")
                region_counts = df['Region'].value_counts().reset_index()
                region_counts.columns = ['Region', 'Count']
                fig = px.pie(region_counts, values='Count', names='Region', title="Articles by Region")
                st.plotly_chart(fig, use_container_width=True)

            with col2:
                channel_counts = df['Channel'].value_counts().reset_index()
                channel_counts.columns = ['Channel', 'Count']
                fig2 = px.bar(channel_counts, x='Channel', y='Count',
                              title="Articles by Channel", color='Channel')
                st.plotly_chart(fig2, use_container_width=True)

            st.subheader(f"📋 Integrated News List ({selected_year})")
            display_df = df.copy()
            display_df['Published'] = display_df['Published'].dt.strftime('%Y-%m-%d')
            st.dataframe(
                display_df[["Channel", "Region", "Source", "Title", "Published"]],
                use_container_width=True
            )

            st.divider()
            st.subheader("📰 Detailed Preview (Descending Order)")
            for idx, row in df.iterrows():
                with st.expander(
                    f"No.{idx} | {row['Published'].strftime('%Y-%m-%d')} | [{row['Source']}] {row['Title']}"
                ):
                    st.write(f"**Region:** {row['Region']} | **Channel:** {row['Channel']}")
                    st.write(f"[Read Full Article]({row['Link']})")
        else:
            st.warning("No articles found for the selected criteria.")
