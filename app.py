import streamlit as st
import requests
import pandas as pd
import numpy as np
import time

st.set_page_config(page_title="AI 스마트 항공 관제탑", layout="wide")

TOKEN_URL = "https://auth.opensky-network.org/auth/realms/opensky-network/protocol/openid-connect/token"
STATES_URL = "https://opensky-network.org/api/states/all"


@st.cache_data(ttl=1500)  # 토큰 유효시간(보통 30분)보다 짧게 캐시
def get_access_token():
    """OpenSky OAuth2 client_credentials 방식으로 access token 발급받기"""
    client_id = st.secrets["client_id"]
    client_secret = st.secrets["client_secret"]

    payload = {
        "grant_type": "client_credentials",
        "client_id": client_id,
        "client_secret": client_secret,
    }
    response = requests.post(TOKEN_URL, data=payload, timeout=30)
    response.raise_for_status()
    return response.json()["access_token"]


@st.cache_data(ttl=15)  # OpenSky 인증 사용자 기준 최소 요청 간격은 5초, 여유있게 15초로 설정
def fetch_flight_data(token):
    params = {"lamin": 33.0, "lamax": 39.0, "lomin": 124.0, "lomax": 132.0}
    headers = {"Authorization": f"Bearer {token}"}

    for attempt in range(3):
        try:
            response = requests.get(STATES_URL, params=params, headers=headers, timeout=30)
            response.raise_for_status()
            data = response.json()
            if data.get("states") is not None:
                columns = [
                    "icao24", "callsign", "origin_country", "time_position",
                    "last_contact", "longitude", "latitude", "baro_altitude",
                    "on_ground", "velocity", "true_track", "vertical_rate",
                    "sensors", "geo_altitude", "squawk", "spi", "position_source",
                ]
                df = pd.DataFrame(data["states"], columns=columns)
                df["callsign"] = df["callsign"].str.strip()
                return df
            return pd.DataFrame()
        except Exception as e:
            if attempt == 2:
                st.error(f"API 요청 중 에러: {e}")
                return None
            time.sleep(3)


st.title("🚨 AI 스마트 항공 관제탑 (한반도 상공)")

if st.button("🔄 수동 새로고침"):
    st.cache_data.clear()
    st.rerun()

try:
    with st.spinner("인증 토큰 발급 중..."):
        token = get_access_token()
except Exception as e:
    st.error(f"OAuth2 인증 실패: {e}")
    st.info("Streamlit Cloud의 App settings → Secrets에 client_id / client_secret이 올바르게 등록되어 있는지 확인해야 함.")
    st.stop()

with st.spinner("실시간 데이터를 불러오는 중..."):
    df = fetch_flight_data(token)

if df is not None and not df.empty:
    analysis_df = df.dropna(subset=["latitude", "longitude", "vertical_rate"]).copy()
    vr_mean = analysis_df["vertical_rate"].mean()
    vr_std = analysis_df["vertical_rate"].std()
    analysis_df["z_score"] = 0.0 if pd.isna(vr_std) or vr_std == 0 else (analysis_df["vertical_rate"] - vr_mean) / vr_std

    threshold = st.slider("위험 경보 Z-score 기준값", min_value=-5.0, max_value=5.0, value=-3.0, step=0.1)
    analysis_df["status"] = np.where(analysis_df["z_score"] <= threshold, "위험(급강하)", "정상")
    danger_count = (analysis_df["status"] == "위험(급강하)").sum()

    m1, m2, m3 = st.columns(3)
    m1.metric("총 탐지된 비행기", f"{len(analysis_df)} 대")
    m2.metric("위험(급강하) 비행기", f"{danger_count} 대")
    m3.metric("평균 수직 승강률", f"{vr_mean:.2f} m/s")

    st.map(analysis_df[["latitude", "longitude"]], zoom=5)
    st.dataframe(analysis_df[["callsign", "status", "z_score", "vertical_rate"]].sort_values(by="z_score"))
else:
    st.warning("현재 감지된 비행기가 없거나 API 호출 대기 중입니다.")
