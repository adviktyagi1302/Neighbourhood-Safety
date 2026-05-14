import streamlit as st
import firebase_admin
from firebase_admin import credentials, db
import folium
from streamlit_folium import st_folium
from geopy.geocoders import Nominatim
from geopy.distance import geodesic
import random
from datetime import datetime, timedelta
import plotly.graph_objects as go

st.set_page_config(page_title="Community Safety AI", layout="wide")

if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False

if not firebase_admin._apps:
    try:
        fb_creds = dict(st.secrets["firebase"])
        cred = credentials.Certificate(fb_creds)
        firebase_admin.initialize_app(cred, {'databaseURL': 'https://chat-app-e4994-default-rtdb.firebaseio.com'})
    except:
        st.error("Firebase Secrets missing!")
        st.stop()

ref = db.reference('/markers')

geolocator = Nominatim(user_agent="my_unique_safety_project_2026", timeout=10)

def safe_geocode(address):
    try:
        return geolocator.geocode(address)
    except Exception:
        return None

THREAT_MAP = {
    1: {"color": "blue", "penalty": 5, "cat": "Level 1: General", "desc": "General concerns/infrastructure."},
    2: {"color": "green", "penalty": 10, "cat": "Level 2: Minor", "desc": "Minor nuisance/harassment."},
    3: {"color": "orange", "penalty": 25, "cat": "Level 3: Moderate", "desc": "Theft/Snatching/Reckless driving."},
    4: {"color": "red", "penalty": 45, "cat": "Level 4: High", "desc": "Physical assault/Robbery."},
    5: {"color": "darkred", "penalty": 65, "cat": "Level 5: Critical", "desc": "Extreme danger/Life threat."}
}

def draw_danger_meter(score, area):
    fig = go.Figure(go.Indicator(
        mode = "gauge+number",
        value = 100 - score,
        title = {'text': f"Danger: {area}"},
        gauge = {'axis': {'range': [0, 100]}, 'bar': {'color': "black"},
                 'steps': [{'range': [0, 30], 'color': "green"},
                          {'range': [30, 70], 'color': "orange"},
                          {'range': [70, 100], 'color': "red"}]}))
    fig.update_layout(height=250, margin=dict(l=30, r=30, t=50, b=20))
    return fig

if not st.session_state.logged_in:
    st.title("🛡️ Secure Neighborhood Login")
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        with st.container(border=True):
            mobile = st.text_input("Mobile No", max_chars=10)
            if 'captcha_val' not in st.session_state:
                st.session_state.n1, st.session_state.n2 = random.randint(1,10), random.randint(1,10)
                st.session_state.captcha_val = st.session_state.n1 + st.session_state.n2
            ans = st.number_input(f"Captcha: {st.session_state.n1} + {st.session_state.n2}?", step=1)
            if st.button("Login", use_container_width=True):
                if len(mobile) == 10 and mobile.isdigit() and ans == st.session_state.captcha_val:
                    st.session_state.logged_in = True
                    st.session_state.user_mobile = mobile
                    st.rerun()
                else:
                    st.error("Invalid Input!")
else:
    st.sidebar.button("Logout", on_click=lambda: st.session_state.update({"logged_in": False}))
    
    st.title("🛡️ Neighborhood Safety AI")

    view_city = st.text_input("Area to Inspect:", value="Ghaziabad")
    view_loc = safe_geocode(view_city)
    
    v_lat, v_lon = (28.6692, 77.4538) if not view_loc else (view_loc.latitude, view_loc.longitude)

    with st.expander("🚨 Submit Local Report"):
        addr = st.text_input("Incident Location")
        level = st.select_slider("Threat Checkpoint", options=[1, 2, 3, 4, 5])
        st.info(f"**{THREAT_MAP[level]['cat']}**: {THREAT_MAP[level]['desc']}")
        details = st.text_area("Observations")
        if st.button("Post Report"):
            loc = safe_geocode(addr)
            if loc:
                ref.push({
                    "lat": loc.latitude, "lon": loc.longitude, "address": loc.address,
                    "desc": details, "category": THREAT_MAP[level]['cat'], 
                    "marker_color": THREAT_MAP[level]['color'], "penalty": THREAT_MAP[level]['penalty'],
                    "timestamp": datetime.now().isoformat(), "is_verified": True
                })
                st.success("Pinned!")
                st.rerun()
            else:
                st.error("Location service busy. Try a nearby landmark.")

    data = ref.get()
    local_r, global_r = [], []
    if data:
        now = datetime.now()
        for r in data.values():
            ts = r.get('timestamp')
            if ts and (now - datetime.fromisoformat(ts) < timedelta(hours=24)):
                global_r.append(r)
                if geodesic((v_lat, v_lon), (r['lat'], r['lon'])).km <= 10:
                    local_r.append(r)

    score = max(0, 100 - sum(r.get('penalty', 0) for r in local_r))
    c1, c2 = st.columns([2.5, 1])
    with c1:
        m = folium.Map(location=[v_lat, v_lon], zoom_start=13)
        for r in global_r:
            folium.Marker([r['lat'], r['lon']], popup=r['desc'], 
                          icon=folium.Icon(color=r.get('marker_color', 'blue'))).add_to(m)
        st_folium(m, width=850, height=500, key="main_map")
    with c2:
        st.plotly_chart(draw_danger_meter(score, view_city), use_container_width=True)
        st.metric("Local Safety Index", f"{score}/100")
