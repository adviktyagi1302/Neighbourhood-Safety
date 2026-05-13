import streamlit as st
import firebase_admin
from firebase_admin import credentials, db
import folium
from streamlit_folium import st_folium
from geopy.geocoders import Nominatim
import random
from datetime import datetime, timedelta
import plotly.graph_objects as go

# 1. PAGE CONFIG (MUST BE FIRST)
st.set_page_config(page_title="Community Safety AI", layout="wide")

# 2. INITIALIZE SESSION STATE (Fixes your AttributeError)
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
if 'user_mobile' not in st.session_state:
    st.session_state.user_mobile = None

# 3. FIREBASE INITIALIZATION
if not firebase_admin._apps:
    try:
        fb_creds = dict(st.secrets["firebase"])
        cred = credentials.Certificate(fb_creds)
        firebase_admin.initialize_app(cred, {
            'databaseURL': 'https://chat-app-e4994-default-rtdb.firebaseio.com'
        })
    except Exception as e:
        st.error("Firebase Secrets not found!")
        st.stop()

ref = db.reference('/markers')
geolocator = Nominatim(user_agent="safety_app_v2")

# --- FUNCTIONS ---
def get_safety_details(text):
    text = text.lower()
    if any(word in text for word in ["steal", "rob", "theft", "snatch"]): return "Theft", "red", 25
    if any(word in text for word in ["fight", "hit", "assault"]): return "Assault", "darkred", 45
    return "General Alert", "blue", 5

def draw_danger_meter(score):
    danger_val = 100 - score
    fig = go.Figure(go.Indicator(
        mode = "gauge+number",
        value = danger_val,
        title = {'text': "Danger Level"},
        gauge = {
            'axis': {'range': [0, 100]},
            'bar': {'color': "black"},
            'steps': [
                {'range': [0, 30], 'color': "green"},
                {'range': [30, 70], 'color': "orange"},
                {'range': [70, 100], 'color': "red"}]}))
    fig.update_layout(height=250, margin=dict(l=20, r=20, t=50, b=20))
    return fig

# --- LOGIN LOGIC ---
if not st.session_state.logged_in:
    st.markdown("<h1 style='text-align: center;'>🛡️ Secure Login</h1>", unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        with st.container(border=True):
            mobile = st.text_input("Mobile Number", max_chars=10)
            if 'captcha_val' not in st.session_state:
                st.session_state.n1, st.session_state.n2 = random.randint(1,10), random.randint(1,10)
                st.session_state.captcha_val = st.session_state.n1 + st.session_state.n2
            
            captcha_ans = st.number_input(f"Captcha: {st.session_state.n1} + {st.session_state.n2}?", step=1)
            
            if st.button("Login", use_container_width=True):
                if len(mobile) == 10 and mobile.isdigit() and captcha_ans == st.session_state.captcha_val:
                    st.session_state.logged_in = True
                    st.session_state.user_mobile = mobile
                    st.rerun()
                else:
                    st.error("Invalid Input!")
else:
    # --- MAIN APP UI ---
    st.sidebar.title("👤 Profile")
    st.sidebar.write(f"ID: {st.session_state.user_mobile}")
    if st.sidebar.button("Logout"):
        st.session_state.logged_in = False
        st.rerun()

    st.title("🛡️ Neighborhood Safety AI")

    # 1. REPORTING
    with st.expander("📝 Report Incident"):
        addr = st.text_input("Location")
        desc = st.text_area("Description")
        if st.button("Submit"):
            loc = geolocator.geocode(addr)
            if loc:
                cat, col, penalty = get_safety_details(desc)
                ref.push({
                    "lat": loc.latitude, "lon": loc.longitude, "address": loc.address,
                    "desc": desc, "category": cat, "marker_color": col, 
                    "penalty": penalty, "timestamp": datetime.now().isoformat(),
                    "is_verified": True
                })
                st.success("Reported!")
                st.rerun()

    # 2. DATA & FILTER
    data = ref.get()
    all_reports = []
    if data:
        now = datetime.now()
        for r in data.values():
            ts = r.get('timestamp')
            if ts and (now - datetime.fromisoformat(ts) < timedelta(hours=24)):
                all_reports.append(r)

    # 3. DASHBOARD
    safety_metric = max(0, 100 - sum(r.get('penalty', 0) for r in all_reports[-10:]))
    c1, c2 = st.columns([3, 1])
    
    with c1:
        m = folium.Map(location=[28.61, 77.20], zoom_start=12)
        for r in all_reports:
            folium.Marker([r['lat'], r['lon']], popup=r['desc'], 
                          icon=folium.Icon(color=r.get('marker_color', 'blue'))).add_to(m)
        st_folium(m, width=900, height=500)

    with c2:
        st.plotly_chart(draw_danger_meter(safety_metric), use_container_width=True)
        st.metric("Safety Score", f"{safety_metric}/100")
