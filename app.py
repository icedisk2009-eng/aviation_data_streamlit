import streamlit as st
import requests
import pandas as pd
import numpy as np

st.set_page_config(page_title="AI 스마트 항공 관제탑", layout="wide")

@st.cache_data(ttl=30)
def fetch_flight_data():
    url = "https://opensky-network.org/api/states/all"
    params = {"lamin": 33.0, "lamax": 39.0, "lomin": 124.0, "lomax": 132.0}
    try:
        response = requests.get(url, params=params, timeout=30)
        response.raise_for_status()
        data = response.json()
        if data['states'] is not None:
            columns = ['icao24', 'callsign', 'origin_country', 'time_position',
                       'last_contact', 'longitude', 'latitude', 'baro_altitude',
                       'on_ground', 'velocity', 'true_track', 'vertical_rate',
                       'sensors', 'geo_altitude', 'squawk', 'spi', 'position_source']
            df = pd.DataFrame(data['states'], columns=columns)
            df['callsign'] = df['callsign'].str.strip()
            return df
        return pd.DataFrame()
    except Exception as e:
        st.error(f"API 요청 중 에러: {e}")
        return None

st.title("🚨 AI 스마트 항공 관제탑 (한반도 상공)")

if st.button("🔄 수동 새로고침"):
    st.cache_data.clear()
    st.rerun()

with st.spinner("실시간 데이터를 불러오는 중..."):
    df = fetch_flight_data()

if df is not None and not df.empty:
    analysis_df = df.dropna(subset=['latitude', 'longitude', 'vertical_rate']).copy()
    vr_mean = analysis_df['vertical_rate'].mean()
    vr_std = analysis_df['vertical_rate'].std()
    analysis_df['z_score'] = 0.0 if pd.isna(vr_std) or vr_std == 0 else (analysis_df['vertical_rate'] - vr_mean) / vr_std

    threshold = st.slider("위험 경보 Z-score 기준값", min_value=-5.0, max_value=5.0, value=-3.0, step=0.1)
    analysis_df['status'] = np.where(analysis_df['z_score'] <= threshold, '위험(급강하)', '정상')
    danger_count = (analysis_df['status'] == '위험(급강하)').sum()

    m1, m2, m3 = st.columns(3)
    m1.metric("총 탐지된 비행기", f"{len(analysis_df)} 대")
    m2.metric("위험(급강하) 비행기", f"{danger_count} 대")
    m3.metric("평균 수직 승강률", f"{vr_mean:.2f} m/s")

    st.map(analysis_df[['latitude', 'longitude']], zoom=5)
    st.dataframe(analysis_df[['callsign', 'status', 'z_score', 'vertical_rate']].sort_values(by='z_score'))
else:
    st.warning("현재 감지된 비행기가 없거나 API 호출 대기 중입니다.")
