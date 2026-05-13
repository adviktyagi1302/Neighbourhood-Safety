import streamlit as st
import firebase_admin
from firebase_admin import credentials, db
import folium
from streamlit_folium import st_folium
from geopy.geocoders import Nominatim

# 1. MUST BE FIRST STREAMLIT COMMAND
st.set_page_config(page_title="Community Safety AI", layout="wide")

# 2. INITIALIZE FIREBASE
if not firebase_admin._apps:
    fb_creds = dict(st.secrets["firebase"])
    cred = credentials.Certificate(fb_creds)
    firebase_admin.initialize_app(cred, {
        'databaseURL': 'https://chat-app-e4994-default-rtdb.firebaseio.com'
    })

ref = db.reference('/markers') # Point directly to your markers node
geolocator = Nominatim(user_agent="safety_app_v1")

# --- AI LOGIC ---
def get_safety_details(text):
    text = text.lower()
    if any(word in text for word in ["steal", "rob", "theft", "snatch"]): 
        return "Theft", "red", 20
    if any(word in text for word in ["fight", "hit", "assault"]): 
        return "Assault", "orange", 40
    return "General Alert", "blue", 5

# --- UI LAYOUT ---
st.title("🛡️ Neighborhood Safety AI")

# --- INPUT SECTION ---
with st.expander("📍 Report an Incident (Address Search)"):
    address_input = st.text_input("Where did this happen?", placeholder="e.g. Sector 62, Noida")
    desc = st.text_area("Describe what happened:")
    
    if st.button("Confirm & Post Report"):
        if address_input and desc:
            location = geolocator.geocode(address_input)
            if location:
                cat, col, penalty = get_safety_details(desc)
                new_report = {
                    "address": location.address,
                    "lat": location.latitude,
                    "lon": location.longitude,
                    "desc": desc,
                    "category": cat,
                    "color": col,
                    "penalty": penalty
                }
                ref.push(new_report)
                st.balloons()
                st.success("Reported successfully!")
            else:
                st.error("Address not found.")
        else:
            st.warning("Please fill in both address and description.")

# --- FETCH & DISPLAY ---
data = ref.get()
all_reports = list(data.values()) if data else []

# SAFE CALCULATION (Prevents KeyError)
score = max(0, 100 - sum(r.get('penalty', 0) for r in all_reports[-10:]))

col1, col2 = st.columns([3, 1])

with col1:
    m = folium.Map(location=[28.61, 77.20], zoom_start=12)
    for r in all_reports:
        # Check if lat/lon exist in report before marking
        if 'lat' in r and 'lon' in r:
            folium.Marker(
                [r['lat'], r['lon']], 
                popup=f"{r.get('category', 'Alert')}: {r.get('desc', '')}", 
                icon=folium.Icon(color=r.get('color', 'blue'))
            ).add_to(m)
    st_folium(m, width=700, height=500)

with col2:
    st.metric("Area Safety Score", f"{score}/100")
    if score < 50: 
        st.error("⚠️ High Risk Area")
    elif score < 80:
        st.warning("⚠️ Moderate Risk")
    else:
        st.success("✅ Generally Safe")
