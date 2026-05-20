import streamlit as st
import feedparser
import pandas as pd
from datetime import datetime
import urllib.parse
import requests
import plotly.express as px
import io

st.set_page_config(page_title="KIST Europe News Monitor", layout="wide")

st.sidebar.title("Monitoring Settings")

# 네이버 사용 여부 선택
st.sidebar.subheader("Data Source")
use_naver = st.sidebar.toggle("Use Naver API", value=True)

# 네이버 사용시, API 입력 란 생성
if use_naver:
    st.sidebar.subheader("Naver API Credentials")
    naver_id = st.sidebar.text_input("Naver Client ID", type="password")
    naver_secret = st.sidebar.text_input("Naver Client Secret", type="password")
else:
    naver_id, naver_secret = None, None

# 키워드 설정
st.sidebar.subheader("1. Search Keywords")
default_keywords = 'KIST Europe, KIST 유럽, KIST 유럽연구소, 한국과학기술연구원 유럽'
user_input_keywords = st.sidebar.text_area("Keywords (comma separated)", default_keywords)
keyword_list = [k.strip() for k in user_input_keywords.split(",")]

# 국가 설정
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

# 연도 설정 
selected_year = st.sidebar.selectbox("Select Year", range(datetime.now().year, 2014, -1))

# KIST 컬러 팔레트
KIST_RED    = "#E44126"
KIST_DGRAY  = "#6D6E67"
KIST_GRAY   = "#ADADB0"
KIST_SILVER = "#B0B9BF"
KIST_GOLD   = "#BC9D54"
KIST_COLORS = [KIST_RED, KIST_GOLD, KIST_DGRAY, KIST_GRAY, KIST_SILVER]

def parse_date(date_str):
    try:
        dt = pd.to_datetime(date_str, errors='coerce') 
        if dt is pd.NaT:
            return datetime(1900, 1, 1)
        if dt.tzinfo is not None:
            dt = dt.tz_localize(None)
        return dt
    except:
        return datetime(1900, 1, 1)

def fetch_naver_api(keyword_list, client_id, client_secret, year):
    all_data = []
    headers = {"X-Naver-Client-Id": client_id, "X-Naver-Client-Secret": client_secret}
    black_list = ["부고", "부음", "별세", "부친상", "모친상", "본인상", "인사"]
    
    press_map = {
        "ajunews.com": "아주경제", "amenews.kr": "신소재경제신문", "apnews.kr": "중앙뉴스",
        "asiatime.co.kr": "아시아타임즈", "asiatoday.co.kr": "아시아투데이", "biz.chosun.com": "조선비즈",
        "biz.heraldcorp.com": "헤럴드경제", "breaknews.com": "브레이크뉴스", "businessplus.kr": "비즈니스플러스",
        "catchnews.co.kr": "캐치뉴스", "cctoday.co.kr": "충청투데이", "chosun.com": "조선일보",
        "chungnamilbo.com": "충남일보", "cnbnews.com": "CNB뉴스", "daejonilbo.com": "대전일보",
        "daily.hankooki.com": "데일리한국", "dailysportshankook.co.kr": "데일리한국", "delighti.co.kr": "딜라이트닷넷",
        "dhnews.co.kr": "대학저널", "domin.co.kr": "전북도민일보", "donga.com": "동아일보",
        "dongascience.com": "동아사이언스", "dt.co.kr": "디지털타임스", "ebn.co.kr": "EBN",
        "economist.co.kr": "이코노미스트", "econovill.com": "이코노믹리뷰", "edaily.co.kr": "이데일리",
        "edu.donga.com": "에듀동아", "ekn.kr": "에너지경제신문", "enewstoday.co.kr": "이뉴스투데이",
        "engjournal.co.kr": "공학저널", "etnews.com": "전자신문", "etoday.co.kr": "이투데이",
        "ezyeconomy.com": "이지경제", "fnnews.com": "파이낸셜뉴스", "hankyung.com": "한국경제",
        "hani.co.kr": "한겨레", "hellodd.com": "헬로디디", "heraldcorp.com": "헤럴드경제",
        "hidomin.com": "경북도민일보", "jjn.co.kr": "전북중앙신문", "joongdo.co.kr": "중도일보",
        "kbmaeil.com": "경북매일", "khan.co.kr": "경향신문", "kpenews.com": "한국정치경제뉴스",
        "kpinews.kr": "KPI뉴스", "kukinews.com": "쿠키뉴스", "kyosu.net": "교수신문",
        "lecturernews.com": "한국강사신문", "metroseoul.co.kr": "메트로신문", "mk.co.kr": "매일경제",
        "mt.co.kr": "머니투데이", "mtn.co.kr": "MTN 머니투데이방송", "nbntv.co.kr": "내외경제TV",
        "news.kbs.co.kr": "KBS", "news.naver.com": "네이버뉴스", "news1.kr": "뉴스1",
        "newsfreezone.co.kr": "뉴스프리존", "newsmaker.or.kr": "뉴스메이커", "newsis.com": "뉴시스",
        "sedaily.com": "서울경제", "tjb.co.kr": "TJB대전방송", "veritas-a.com": "베리타스알파",
        "view.co.kr": "뷰어스", "viva100.com": "브릿지경제", "yna.co.kr": "연합뉴스",
        "zdnet.co.kr": "지디넷코리아", "news.sbs.co.kr": "SBS", "g1tv.co.kr": "G1방송",
        "greened.kr": "녹색경제신문", "gukjenews.com": "국제뉴스", "gw.newdaily.co.kr": "뉴데일리(강원)",
        "handmk.com": "핸드메이커", "hankookilbo.com": "한국일보", "hg-times.com": "한강타임즈",
        "hinews.co.kr": "하이뉴스", "inews24.com": "아이뉴스24", "inews365.com": "충북인뉴스",
        "irobotnews.com": "로봇신문", "issuenbiz.com": "이슈앤비즈", "jeollailbo.com": "전라일보",
        "jeonmin.co.kr": "전민일보", "job-post.co.kr": "잡포스트", "kado.net": "강원도민일보",
        "kbsm.net": "경북신문", "kmib.co.kr": "국민일보", "ksilbo.co.kr": "경상일보",
        "kwnews.co.kr": "강원일보", "kyongbuk.co.kr": "경북일보", "lawissue.co.kr": "로이슈",
        "livesnews.com": "라이브뉴스", "marketnews.co.kr": "마켓뉴스", "mbceg.co.kr": "MBC강원영동",
        "munhwa.com": "문화일보", "naeil.com": "내일신문", "namdonews.com": "남도일보",
        "financialreview.co.kr": "파이낸셜리뷰", "news2day.co.kr": "뉴스투데이", "newscj.com": "천지일보",
        "newstnt.com": "뉴스티앤티", "newswatch.kr": "뉴스워치", "newswell.co.kr": "뉴스웰",
        "newswhoplus.com": "뉴스후플러스", "nongmin.com": "농민신문", "pennmike.com": "펜앤드마이크",
        "pinpointnews.co.kr": "핀포인트뉴스", "pointdaily.co.kr": "포인트데일리", "popcornnews.net": "팝콘뉴스",
        "press9.kr": "프레스나인", "pressian.com": "프레시안", "rightknow.co.kr": "바른댓글실천연대",
        "segye.com": "세계일보", "sentv.co.kr": "SEN서울경제TV", "seouleconews.com": "서울이코노미뉴스",
        "shinailbo.co.kr": "신아일보", "sisacast.kr": "시사캐스트", "sisajournal-e.com": "시사저널e",
        "sisaon.co.kr": "시사오늘", "sjbnews.com": "새전북신문", "sportsseoul.com": "스포츠서울",
        "srtimes.kr": "SR타임스", "techholic.co.kr": "테크홀릭", "tfmedia.co.kr": "조세금융신문",
        "thepowernews.co.kr": "더파워뉴스", "thepublic.kr": "더퍼블릭", "thetracker.co.kr": "더트래커",
        "tournews21.com": "투어타임즈", "ttlnews.com": "TTL뉴스", "webeconomy.co.kr": "웹이코노미",
        "weeklytoday.com": "위클리오늘", "whitepaper.co.kr": "화이트페이퍼", "yeongnam.com": "영남일보",
        "youthdaily.co.kr": "청년일보", "view.asiae.co.kr": "아시아경제", "mtnews.net":"기계신문"
    }
    
    for kw in keyword_list: 
        encoded_query = urllib.parse.quote(f'"{kw}"')
        
        for start in range(1, 1001, 100):
            url = f"https://openapi.naver.com/v1/search/news.json?query={encoded_query}&display=100&start={start}&sort=date"
            try:
                response = requests.get(url, headers=headers)
                if response.status_code != 200: break
                items = response.json().get('items', [])
                if not items: break
                    
                for item in items:
                    pub_date = parse_date(item['pubDate'])
                    if pub_date.year != year:
                        if pub_date.year < year: break
                        continue

                    title = item['title'].replace("<b>", "").replace("</b>", "")
                    title = title.replace("&lt;", "<").replace("&gt;", ">").replace("&quot;", '"').replace("&amp;", "&")
                    
                    description = item['description'].replace("<b>", "").replace("</b>", "")
                    description = description.replace("&lt;", "<").replace("&gt;", ">").replace("&quot;", '"').replace("&amp;", "&")
                    
                    full_text_for_filter = (title + description).replace(" ", "")
                    if any(word in full_text_for_filter for word in black_list):
                        continue 

                    full_text_lower = (title + description).lower()
                    if any(k.lower() in full_text_lower for k in keyword_list):
                        link_to_check = item['originallink'] if item['originallink'] else item['link']
                        
                        try:
                            domain = link_to_check.split('//')[1].split('/')[0].replace('www.', '')
                            source_name = press_map.get(domain, domain.split('.')[0].upper())
                        except:
                            source_name = "Naver News"

                        all_data.append({
                            "Channel": "NAVER (API)",
                            "Source": source_name,
                            "Title": title,
                            "Published": pub_date,
                            "Link": link_to_check,
                            "Region": "South Korea (KO)"
                        })
            except: break
    return all_data

# --- [구글 뉴스 수집 기능 강화] ---
def fetch_google_news(query, hl, gl, region_name, year):
    # 구글 검색 시 공백이 있는 키워드는 큰따옴표로 묶어 정확도를 높이고, 해당 연도의 시작과 끝 날짜를 쿼리에 주입합니다.
    # 예시: "KIST Europe" after:2025-01-01 before:2025-12-31
    start_date = f"{year}-01-01"
    end_date = f"{year}-12-31"
    
    safe_query = f'"{query}"' if ' ' in query else query
    full_query = f"{safe_query} after:{start_date} before:{end_date}"
    encoded_query = urllib.parse.quote(full_query) 
    
    url = f"https://news.google.com/rss/search?q={encoded_query}&hl={hl}&gl={gl}&ceid={gl}:{hl}"
    feed = feedparser.parse(url)
    data = []
    
    blacklist = ["ttc", "부고", "ping pong", "탁구", "bundesliga", "회고", "역사전", "사진전", "역사관", "준공식", "40주년"]

    for entry in feed.entries:
        title = entry.title
        
        # [검증 1] 블랙리스트 필터링
        if any(bad in title.lower() for bad in blacklist): 
            continue

        # [검증 2] 날짜 필터링
        if not hasattr(entry, 'published'):
            continue
        pub_date = parse_date(entry.published)
        if pub_date.year != year:
            continue

        # RSS 제목에 키워드가 완벽히 매칭되지 않더라도, 구글이 본문(Body)을 분석해 
        # 찾아온 유효 기사이므로 local 필터링 단계를 제거하여 수집량을 보존합니다.
        data.append({
            "Channel": "Google (RSS)",
            "Source": entry.source.title if hasattr(entry, 'source') else "Google",
            "Title": title,
            "Published": pub_date,
            "Link": entry.link,
            "Region": region_name
        })
    return data

def render_charts(df):
    col1, col2 = st.columns(2)
    with col1:
        region_counts = df['Region'].value_counts().reset_index()
        region_counts.columns = ['Region', 'Count']
        fig = px.pie(region_counts, values='Count', names='Region', title="📌 Articles by Region", color_discrete_sequence=KIST_COLORS)
        st.plotly_chart(fig, use_container_width=True)
    with col2:
        source_counts = df['Source'].value_counts().head(10).reset_index()
        source_counts.columns = ['Source', 'Count']
        fig2 = px.bar(source_counts, x='Source', y='Count', title="📌 Top 10 Sources", color='Count', color_continuous_scale=[KIST_DGRAY, KIST_RED])
        st.plotly_chart(fig2, use_container_width=True)

    df_copy = df.copy()
    df_copy['Month'] = df_copy['Published'].dt.to_period('M').astype(str)
    monthly = df_copy.groupby('Month').size().reset_index(name='Count')
    fig3 = px.line(monthly, x='Month', y='Count', title="📌 Monthly Article Trend", markers=True)
    fig3.update_traces(line=dict(color=KIST_RED, width=3), marker=dict(size=8, color=KIST_GOLD))
    st.plotly_chart(fig3, use_container_width=True)

# Main UI
st.title("KIST Europe News Monitor")

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
            # 구글 뉴스 수집 루프
            for lang_name in selected_langs:
                # 네이버 API를 쓰고 있고, 현재 루프 국가가 한국(South Korea)이면 구글 수집을 패스 (네이버가 수집하므로)
                if use_naver and "South Korea" in lang_name:
                    continue
                
                params = lang_options[lang_name]
                for kw in keyword_list:
                    # fetch_google_news 내부에서 기간 필터링이 자동 적용되도록 인자 수정
                    all_results.extend(fetch_google_news(kw, params['hl'], params['gl'], lang_name, selected_year))
            
            # 네이버 뉴스 수집 (네이버 ON + 한국 선택 시에만 실행)
            if use_naver and any("South Korea" in l for l in selected_langs):
                all_results.extend(fetch_naver_api(keyword_list, naver_id, naver_secret, selected_year))

        if all_results:
            df = pd.DataFrame(all_results)
            
            # --- [정교한 중복 제거 로직] ---
            # 1. 텍스트 정규화: 제목에서 공백과 특수문자를 제거하고 앞 20자만 추출
            df['short_key'] = (
                df['Title']
                .str.replace(r'[^a-zA-Z0-9가-힣]', '', regex=True)
                .str.slice(0, 20)
            )

            # 2. 우선순위 설정 (Google RSS를 0순위로 하여 중복 시 구글 데이터 유지)
            df['priority'] = df['Channel'].apply(lambda x: 0 if x == 'Google (RSS)' else 1)
            
            # 3. 정렬: 우선순위 -> 발행일(최신순)
            df = df.sort_values(by=['priority', 'Published'], ascending=[True, False])

            # 4. 링크 중복 제거 (URL 기준)
            df = df.drop_duplicates(subset=['Link'], keep='first')
            
            # 5. 유사 제목 중복 제거 (short_key 기준)
            df = df.drop_duplicates(subset=['short_key'], keep='first')
            
            # 6. 뒷정리: 임시 컬럼 삭제 및 최종 정렬
            df = df.drop(columns=['priority', 'short_key'])
            df = df.sort_values(by="Published", ascending=False)
            df.index = range(1, len(df) + 1)

            # --- 결과 표시 ---
            st.success(f"✅ Collection Complete! **{len(df)}** unique articles found.")
            st.metric("Total Articles", f"{len(df)} pcs")
            st.divider()
            render_charts(df)

            st.divider()
            st.subheader(f"Integrated News List ({selected_year})")
            display_df = df.copy()
            display_df['Published'] = display_df['Published'].dt.strftime('%Y-%m-%d')
            st.dataframe(display_df[["Channel", "Region", "Source", "Title", "Published"]], use_container_width=True)

            # --- 엑셀 파일 생성 ---
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                df[["Channel", "Region", "Source", "Title", "Published", "Link"]].to_excel(writer, index=False, sheet_name='KIST_News')
            processed_data = output.getvalue()

            st.download_button(
                label="📥 Download Excel (.xlsx)",
                data=processed_data,
                file_name=f"KIST_Europe_News_{selected_year}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

            st.divider()
            st.subheader("Detailed Preview")
            for idx, row in df.iterrows():
                with st.expander(f"No.{idx} | {row['Published'].strftime('%Y-%m-%d')} | [{row['Source']}] {row['Title']}"):
                    st.write(f"**Region:** {row['Region']} | **Channel:** {row['Channel']}")
                    st.write(f"[Read Full Article]({row['Link']})")
        else:
            st.warning("No matching articles found.")