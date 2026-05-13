import streamlit as st
import firebase_admin
from firebase_admin import credentials, db
import folium
from streamlit_folium import st_folium
from geopy.geocoders import Nominatim
import random
from datetime import datetime, timedelta
import plotly.graph_objects as go

# 1. PAGE CONFIG
st.set_page_config(page_title="Community Safety AI", layout="wide")

# 2. INITIALIZE SESSION STATE
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
        st.error("Firebase Secrets missing!")
        st.stop()

ref = db.reference('/markers')
geolocator = Nominatim(user_agent="safety_app_v2")

# --- THREAT LEVEL CHECKPOINTS ---
THREAT_MAP = {
    1: {"color": "blue", "penalty": 5, "cat": "Level 1: General", "desc": "General observation (e.g., suspicious activity, street lights out)"},
    2: {"color": "green", "penalty": 10, "cat": "Level 2: Minor", "desc": "Minor concern (e.g., verbal dispute, public nuisance)"},
    3: {"color": "orange", "penalty": 25, "cat": "Level 3: Moderate", "desc": "Moderate risk (e.g., theft, snatching, reckless driving)"},
    4: {"color": "red", "penalty": 45, "cat": "Level 4: High", "desc": "High threat (e.g., physical assault, robbery)"},
    5: {"color": "darkred", "penalty": 65, "cat": "Level 5: Critical", "desc": "Critical emergency (e.g., armed threat, severe violence)"}
}

def draw_danger_meter(score):
    danger_val = 100 - score
    fig = go.Figure(go.Indicator(
        mode = "gauge+number",
        value = danger_val,
        title = {'text': "Current Danger Level", 'font': {'size': 20}},
        gauge = {
            'axis': {'range': [0, 100]},
            'bar': {'color': "black"},
            'steps': [
                {'range': [0, 30], 'color': "#2ecc71"}, # Green
                {'range': [30, 70], 'color': "#f39c12"}, # Orange
                {'range': [70, 100], 'color': "#e74c3c"}]})) # Red
    fig.update_layout(height=250, margin=dict(l=30, r=30, t=50, b=20))
    return fig

# --- LOGIN SCREEN ---
if not st.session_state.logged_in:
    st.markdown("<h1 style='text-align: center;'>🛡️ Neighborhood Safety Access</h1>", unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        with st.container(border=True):
            mobile = st.text_input("Mobile Number", max_chars=10)
            if 'captcha_val' not in st.session_state:
                st.session_state.n1, st.session_state.n2 = random.randint(1,10), random.randint(1,10)
                st.session_state.captcha_val = st.session_state.n1 + st.session_state.n2
            
            captcha_ans = st.number_input(f"Verify: {st.session_state.n1} + {st.session_state.n2}?", step=1)
            
            if st.button("Enter App", use_container_width=True):
                if len(mobile) == 10 and mobile.isdigit() and captcha_ans == st.session_state.captcha_val:
                    st.session_state.logged_in = True
                    st.session_state.user_mobile = mobile
                    st.rerun()
                else:
                    st.error("Invalid credentials.")
else:
    # --- MAIN DASHBOARD ---
    st.sidebar.title("👤 Account")
    st.sidebar.write(f"ID: {st.session_state.user_mobile}")
    if st.sidebar.button("Logout"):
        st.session_state.logged_in = False
        st.rerun()

    st.title("🛡️ Live Neighborhood Safety AI")

    # 1. REPORTING (Slider Checkpoints + Description)
    with st.expander("🚨 Report Incident"):
        addr = st.text_input("Incident Location", placeholder="e.g. Noida Sector 18")
        
        # Drag Line / Slider with 1-5 Checkpoints
        level = st.select_slider(
            "Drag to Select Threat Level",
            options=[1, 2, 3, 4, 5],
            value=1,
            help="1 is General, 5 is Life-Threatening"
        )
        
        # Display the auto-generated description for that level
        st.warning(f"**{THREAT_MAP[level]['cat']}**: {THREAT_MAP[level]['desc']}")
        
        # Additional custom details
        custom_desc = st.text_area("Detailed Description", placeholder="Add specific details about the event...")

        if st.button("Post Verified Report", use_container_width=True):
            if addr and custom_desc:
                loc = geolocator.geocode(addr)
                if loc:
                    threat = THREAT_MAP[level]
                    ref.push({
                        "lat": loc.latitude, 
                        "lon": loc.longitude, 
                        "address": loc.address,
                        "desc": custom_desc,
                        "category": threat["cat"], 
                        "marker_color": threat["color"], 
                        "penalty": threat["penalty"], 
                        "timestamp": datetime.now().isoformat(),
                        "is_verified": True,
                        "threat_level": level
                    })
                    st.success("Pinned to Map!")
                    st.rerun()
                else:
                    st.error("Location not found.")
            else:
                st.warning("Please provide a location and details.")

    # 2. DATA PROCESSING (24hr Filter)
    data = ref.get()
    active_reports = []
    if data:
        now = datetime.now()
        for r in data.values():
            ts = r.get('timestamp')
            if ts and (now - datetime.fromisoformat(ts) < timedelta(hours=24)):
                active_reports.append(r)

    # 3. VISUALIZATION
    safety_metric = max(0, 100 - sum(r.get('penalty', 0) for r in active_reports[-10:]))
    c1, c2 = st.columns([2.5, 1])
    
    with c1:
        m = folium.Map(location=[28.61, 77.20], zoom_start=12)
        for r in active_reports:
            folium.Marker(
                [r['lat'], r['lon']], 
                popup=f"<b>{r.get('category')}</b><br>{r.get('desc')}", 
                icon=folium.Icon(color=r.get('marker_color', 'blue'))
            ).add_to(m)
        st_folium(m, width=850, height=500)

    with c2:
        st.plotly_chart(draw_danger_meter(safety_metric), use_container_width=True)
        st.metric("Safety Score", f"{safety_metric}/100")
        st.write(f"Recent Alerts (24h): {len(active_reports)}")
