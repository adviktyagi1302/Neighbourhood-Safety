import streamlit as st
import firebase_admin
from firebase_admin import credentials, db
import folium
from streamlit_folium import st_folium
from geopy.geocoders import Nominatim
import random

# 1. PAGE CONFIGURATION (Must be the very first Streamlit command)
st.set_page_config(page_title="Community Safety AI", layout="wide")

# 2. FIREBASE INITIALIZATION
# Uses Streamlit Secrets to bypass Google's public repo security blocks
if not firebase_admin._apps:
    try:
        fb_creds = dict(st.secrets["firebase"])
        cred = credentials.Certificate(fb_creds)
        firebase_admin.initialize_app(cred, {
            'databaseURL': 'https://chat-app-e4994-default-rtdb.firebaseio.com'
        })
    except Exception as e:
        st.error("Firebase Configuration Missing in Streamlit Secrets!")
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
            mobile = st.text_input("Enter Mobile Number", max_chars=10, help="Enter 10-digit mobile number")
            
            # Persistent Captcha values to prevent reset on every typing stroke
            if 'captcha_val' not in st.session_state:
                st.session_state.num1 = random.randint(1, 10)
                st.session_state.num2 = random.randint(1, 10)
                st.session_state.captcha_val = st.session_state.num1 + st.session_state.num2
            
            captcha_input = st.number_input(f"Verify: What is {st.session_state.num1} + {st.session_state.num2}?", step=1)
            
            if st.button("Access Application", use_container_width=True):
                if len(mobile) == 10 and mobile.isdigit() and captcha_input == st.session_state.captcha_val:
                    st.session_state.logged_in = True
                    st.session_state.user_mobile = mobile
                    st.success("Identity Verified!")
                    st.rerun()
                else:
                    st.error("Invalid credentials or incorrect Captcha answer.")

# --- MAIN APPLICATION INTERFACE ---
if not st.session_state.logged_in:
    login_screen()
else:
    # Sidebar for User Info and Logout
    st.sidebar.title("👤 User Profile")
    st.sidebar.write(f"**Verified ID:** {st.session_state.user_mobile}")
    if st.sidebar.button("Logout"):
        st.session_state.logged_in = False
        # Clear captcha for next time
        if 'captcha_val' in st.session_state: del st.session_state.captcha_val 
        st.rerun()

    st.title("🛡️ Live Neighborhood Safety AI")

    # --- 1. INCIDENT REPORTING (Geocoding + AI) ---
    with st.expander("📝 Report a New Incident"):
        st.info("Searching for an address will automatically generate coordinates.")
        addr_col, score_col = st.columns([2, 1])
        
        with addr_col:
            address_input = st.text_input("Incident Location", placeholder="e.g. Indirapuram, Ghaziabad")
            desc = st.text_area("Description of Event", placeholder="Describe what happened clearly...")
        
        with score_col:
            safety_score = st.slider("User Safety Perception", 1, 5, 3)
            st.caption("1: Very Dangerous | 5: Very Safe")

        if st.button("Verify and Submit Report", use_container_width=True):
            if address_input and desc:
                with st.spinner("Geocoding address..."):
                    location = geolocator.geocode(address_input)
                    if location:
                        # Process through AI categorization
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
                            "is_verified": True
                        }
                        ref.push(report_data)
                        st.balloons()
                        st.success(f"Verified report pinned to: {location.address}")
                    else:
                        st.error("Address not found. Please try adding city or area name.")
            else:
                st.warning("Please provide both location and description.")

    # --- 2. DATA PROCESSING ---
    db_data = ref.get()
    all_reports = list(db_data.values()) if db_data else []
    
    # Filter for verified reports only for the safety metric
    verified_reports = [r for r in all_reports if r.get('is_verified') == True]
    # Calculate safety score based on last 10 reports
    safety_metric = max(0, 100 - sum(r.get('penalty', 0) for r in verified_reports[-10:]))

    # --- 3. DASHBOARD DISPLAY ---
    col_map, col_stats = st.columns([3, 1])

    with col_map:
        # Centered near Delhi/NCR by default
        m = folium.Map(location=[28.61, 77.20], zoom_start=12)
        
        for r in all_reports:
            if 'lat' in r and 'lon' in r:
                folium.Marker(
                    location=[r['lat'], r['lon']],
                    popup=f"<b>{r.get('category')}</b><br>{r.get('desc')}<br><small>{r.get('address')}</small>",
                    icon=folium.Icon(color=r.get('marker_color', 'blue'), icon='info-sign')
                ).add_to(m)
        
        st_folium(m, width=900, height=500)

    with col_stats:
        st.subheader("Safety Analytics")
        st.metric("Area Safety Index", f"{safety_metric}/100")
        
        if safety_metric < 40:
            st.error("🛑 HIGH RISK AREA")
        elif safety_metric < 75:
            st.warning("⚠️ CAUTION ADVISED")
        else:
            st.success("✅ GENERALLY SAFE")
        
        st.write("---")
        st.write(f"**Total Reports:** {len(all_reports)}")
        st.write(f"**Verified Records:** {len(verified_reports)}")
        
        if all_reports:
            st.caption("Latest incident:")
            st.write(all_reports[-1].get('category'))
