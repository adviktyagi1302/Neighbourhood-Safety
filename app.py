import streamlit as st
import firebase_admin
from firebase_admin import credentials, db
import folium
from streamlit_folium import st_folium
from geopy.geocoders import Nominatim
from geopy.distance import geodesic # <--- NEW: For calculating distance
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
    1: {"color": "blue", "penalty": 5, "cat": "Level 1: General", "desc": "Suspicious activity or infrastructure issues."},
    2: {"color": "green", "penalty": 10, "cat": "Level 2: Minor", "desc": "Minor public nuisance or disputes."},
    3: {"color": "orange", "penalty": 25, "cat": "Level 3: Moderate", "desc": "Theft, snatching, or reckless driving."},
    4: {"color": "red", "penalty": 45, "cat": "Level 4: High", "desc": "Physical assault or robbery."},
    5: {"color": "darkred", "penalty": 65, "cat": "Level 5: Critical", "desc": "Life-threatening emergency."}
}

def draw_danger_meter(score, area_name="Selected Area"):
    danger_val = 100 - score
    fig = go.Figure(go.Indicator(
        mode = "gauge+number",
        value = danger_val,
        title = {'text': f"Danger: {area_name}", 'font': {'size': 18}},
        gauge = {
            'axis': {'range': [0, 100]},
            'bar': {'color': "black"},
            'steps': [
                {'range': [0, 30], 'color': "#2ecc71"},
                {'range': [30, 70], 'color': "#f39c12"},
                {'range': [70, 100], 'color': "#e74c3c"}]}))
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

    st.title("🛡️ Neighborhood Safety AI")

    # 1. SEARCH AREA FOR SCORE (THE NEW FEATURE)
    st.subheader("🔍 Check Local Safety Score")
    view_city = st.text_input("Enter city/area to view safety level:", value="Ghaziabad")
    view_loc = geolocator.geocode(view_city)
    
    view_lat, view_lon = (28.6692, 77.4538) # Default Ghaziabad
    if view_loc:
        view_lat, view_lon = view_loc.latitude, view_loc.longitude

    # 2. REPORTING SECTION
    with st.expander("🚨 Report Incident in this Area"):
        addr = st.text_input("Specific Location", placeholder="e.g. Indirapuram")
        level = st.select_slider("Threat Level", options=[1, 2, 3, 4, 5], value=1)
        st.warning(f"**{THREAT_MAP[level]['cat']}**: {THREAT_MAP[level]['desc']}")
        custom_desc = st.text_area("Details")

        if st.button("Post Verified Report", use_container_width=True):
            if addr and custom_desc:
                loc = geolocator.geocode(addr)
                if loc:
                    threat = THREAT_MAP[level]
                    ref.push({
                        "lat": loc.latitude, "lon": loc.longitude, "address": loc.address,
                        "desc": custom_desc, "category": threat["cat"], "marker_color": threat["color"], 
                        "penalty": threat["penalty"], "timestamp": datetime.now().isoformat(),
                        "is_verified": True
                    })
                    st.success("Pinned to Map!")
                    st.rerun()

    # 3. DATA PROCESSING (24hr + Radius Filter)
    data = ref.get()
    local_reports = []
    global_reports = []
    
    if data:
        now = datetime.now()
        center_coords = (view_lat, view_lon)
        
        for r in data.values():
            ts = r.get('timestamp')
            if ts and (now - datetime.fromisoformat(ts) < timedelta(hours=24)):
                report_coords = (r['lat'], r['lon'])
                dist = geodesic(center_coords, report_coords).km
                
                global_reports.append(r)
                
                # ONLY count reports within 10km for the Safety Score
                if dist <= 10:
                    local_reports.append(r)

    # 4. LOCALIZED DASHBOARD
    # Score is now calculated ONLY using reports within 10km of the searched area
    local_penalty = sum(r.get('penalty', 0) for r in local_reports)
    safety_metric = max(0, 100 - local_penalty)
    
    c1, c2 = st.columns([2.5, 1])
    
    with c1:
        m = folium.Map(location=[view_lat, view_lon], zoom_start=13)
        for r in global_reports:
            folium.Marker(
                [r['lat'], r['lon']], 
                popup=f"<b>{r.get('category')}</b><br>{r.get('desc')}", 
                icon=folium.Icon(color=r.get('marker_color', 'blue'))
            ).add_to(m)
        st_folium(m, width=850, height=500, key="safety_map")

    with c2:
        st.plotly_chart(draw_danger_meter(safety_metric, view_city), use_container_width=True)
        st.metric(f"Safety in {view_city}", f"{safety_metric}/100")
        st.write(f"Incidents within 10km: {len(local_reports)}")
