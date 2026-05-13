import streamlit as st
import firebase_admin
from firebase_admin import credentials, db
import folium
from streamlit_folium import st_folium
from geopy.geocoders import Nominatim
import random
from datetime import datetime, timedelta

# 1. PAGE CONFIGURATION
st.set_page_config(page_title="Community Safety AI", layout="wide")

# 2. FIREBASE INITIALIZATION
if not firebase_admin._apps:
    try:
        fb_creds = dict(st.secrets["firebase"])
        cred = credentials.Certificate(fb_creds)
        firebase_admin.initialize_app(cred, {
            'databaseURL': 'https://chat-app-e4994-default-rtdb.firebaseio.com'
        })
    except Exception as e:
        st.error("Firebase Configuration Missing! Check Streamlit Secrets.")
        st.stop()

ref = db.reference('/markers')
geolocator = Nominatim(user_agent="safety_app_v2")

# --- AI CATEGORIZATION LOGIC ---
def get_safety_details(text):
    text = text.lower()
    if any(word in text for word in ["steal", "rob", "theft", "snatch", "pickpocket"]): 
        return "Theft/Robbery", "red", 25
    if any(word in text for word in ["fight", "hit", "assault", "harass"]): 
        return "Assault/Violence", "darkred", 45
    if any(word in text for word in ["accident", "crash", "road"]): 
        return "Road Safety", "orange", 15
    return "General Alert", "blue", 5

# --- LOGIN & SESSION MANAGEMENT ---
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False

def login_screen():
    st.markdown("<h1 style='text-align: center;'>🛡️ Secure Access Control</h1>", unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        with st.container(border=True):
            mobile = st.text_input("Enter Mobile Number", max_chars=10)
            if 'captcha_val' not in st.session_state:
                st.session_state.num1 = random.randint(1, 10)
                st.session_state.num2 = random.randint(1, 10)
                st.session_state.captcha_val = st.session_state.num1 + st.session_state.num2
            
            captcha_input = st.number_input(f"Verify: What is {st.session_state.num1} + {st.session_state.num2}?", step=1)
            
            if st.button("Access Application", use_container_width=True):
                if len(mobile) == 10 and mobile.isdigit() and captcha_input == st.session_state.captcha_val:
                    st.session_state.logged_in = True
                    st.session_state.user_mobile = mobile
                    st.rerun()
                else:
                    st.error("Invalid credentials or Captcha.")

# --- MAIN APPLICATION ---
if not st.session_state.logged_in:
    login_screen()
else:
    st.sidebar.title("👤 User Profile")
    st.sidebar.write(f"**Verified ID:** {st.session_state.user_mobile}")
    if st.sidebar.button("Logout"):
        st.session_state.logged_in = False
        st.rerun()

    st.title("🛡️ Live Neighborhood Safety AI")

    # --- 1. INCIDENT REPORTING ---
    with st.expander("📝 Report a New Incident"):
        addr_col, desc_col = st.columns([1, 1])
        with addr_col:
            address_input = st.text_input("Location Name", placeholder="e.g. Noida Sector 18")
        with desc_col:
            desc = st.text_area("What happened?", placeholder="Describe the incident...")

        if st.button("Verify and Submit Report", use_container_width=True):
            if address_input and desc:
                location = geolocator.geocode(address_input)
                if location:
                    cat, col, penalty = get_safety_details(desc)
                    report_data = {
                        "address": location.address,
                        "lat": location.latitude,
                        "lon": location.longitude,
                        "desc": desc,
                        "category": cat,
                        "marker_color": col,
                        "penalty": penalty,
                        "user_id": st.session_state.user_mobile,
                        "is_verified": True,
                        "timestamp": datetime.now().isoformat() # <--- 24HR LOGIC START
                    }
                    ref.push(report_data)
                    st.success("Report Submitted!")
                    st.rerun()
                else:
                    st.error("Address not found.")

    # --- 2. DATA FETCH & 24-HOUR FILTER ---
    db_data = ref.get()
    all_reports = []
    
    if db_data:
        current_time = datetime.now()
        for r in db_data.values():
            ts = r.get('timestamp')
            if ts:
                # Only keep if less than 24 hours old
                if current_time - datetime.fromisoformat(ts) < timedelta(hours=24):
                    all_reports.append(r)
            else:
                # Keep old reports that don't have timestamps yet (optional)
                all_reports.append(r)

    # --- 3. DASHBOARD ---
    # Score calculation (based only on last 24 hours)
    safety_metric = max(0, 100 - sum(r.get('penalty', 0) for r in all_reports[-10:]))

    col_map, col_stats = st.columns([3, 1])
    with col_map:
        m = folium.Map(location=[28.61, 77.20], zoom_start=12)
        for r in all_reports:
            folium.Marker(
                location=[r['lat'], r['lon']],
                popup=f"{r.get('category')}: {r.get('desc')}",
                icon=folium.Icon(color=r.get('marker_color', 'blue'))
            ).add_to(m)
        st_folium(m, width=900, height=500)

    with col_stats:
        st.subheader("Safety Analytics")
        st.metric("Area Safety Index", f"{safety_metric}/100")
        st.write(f"**Verified Reports (24h):** {len(all_reports)}")
        if safety_metric < 50: st.error("⚠️ High Risk")
        else: st.success("✅ Secure")
