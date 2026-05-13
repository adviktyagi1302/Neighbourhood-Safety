import streamlit as st
import firebase_admin
from firebase_admin import credentials, db
import folium
from streamlit_folium import st_folium
from streamlit_folium import st_folium
from geopy.geocoders import Nominatim

# Initialize the geocoder
geolocator = Nominatim(user_agent="my_safety_app")

st.title("Report Neighborhood Safety")

st.subheader("📍 Report an Incident")

# Only one input box for the user
address_input = st.text_input("Where did this happen?", placeholder="e.g. Sector 62, Noida")

if address_input:
    geolocator = Nominatim(user_agent="safety_app_v1")
    location = geolocator.geocode(address_input)
    
    if location:
        # We store the coordinates invisibly in the background
        lat, lon = location.latitude, location.longitude
        
        st.success(f"Selected: {location.address}")
        
        # Now show the safety details
        safety_score = st.slider("Safety Score (1 = Dangerous, 5 = Very Safe)", 1, 5, 3)
        comment = st.text_area("What's the situation there?")
        
        if st.button("Confirm & Post Report"):
            # Save everything to Firebase
            new_report = {
                "address": location.address,
                "lat": lat,
                "lon": lon,
                "score": safety_score,
                "comment": comment
            }
            db.reference('/markers').push(new_report)
            st.balloons()
            st.success("Report submitted successfully!")
    else:
        st.error("Address not found. Please try adding the city name (e.g., 'Indirapuram, Ghaziabad').")
# Initialize Firebase only once
if not firebase_admin._apps:
    # Pulling from the Streamlit Secrets vault
    fb_creds = dict(st.secrets["firebase"])
    cred = credentials.Certificate(fb_creds)
    firebase_admin.initialize_app(cred, {
        'databaseURL': 'https://chat-app-e4994-default-rtdb.firebaseio.com'
    })

# Now try the get request
ref = db.reference('/')
try:
    data = ref.get()
    st.write("Data successfully loaded!")
except Exception as e:
    st.error(f"Failed to fetch data: {e}")
# --- UI CONFIG ---
st.set_page_config(page_title="Community Safety AI", layout="wide")
st.title("🛡️ Live Neighborhood Safety App")

# --- AI CATEGORIZATION ---
def get_safety_details(text):
    text = text.lower()
    if "steal" in text or "rob" in text: return "Theft", "red", 20
    if "fight" in text or "hit" in text: return "Assault", "orange", 40
    return "General Alert", "blue", 5

# --- SIDEBAR: REPORT ---
with st.sidebar.form("report"):
    st.header("Report Incident")
    desc = st.text_area("What happened?")
    lat = st.number_input("Lat", value=28.61)
    lon = st.number_input("Lon", value=77.20)
    if st.form_submit_button("Submit"):
        cat, col, penalty = get_safety_details(desc)
        ref.push({
            "category": cat, "desc": desc, "lat": lat, "lon": lon, "color": col, "penalty": penalty
        })
        st.success("Reported to Cloud!")

# --- FETCH DATA & RENDER ---
data = ref.get()
all_reports = list(data.values()) if data else []

# Calculate Score
score = max(0, 100 - sum(r['penalty'] for r in all_reports[-10:])) # Uses last 10 reports

# Display Map & Score
col1, col2 = st.columns([3, 1])
with col1:
    m = folium.Map(location=[28.61, 77.20], zoom_start=12)
    for r in all_reports:
        folium.Marker([r['lat'], r['lon']], popup=r['desc'], icon=folium.Icon(color=r['color'])).add_to(m)
    st_folium(m, width=700)

with col2:
    st.metric("Area Safety Score", f"{score}/100")
    if score < 50: st.error("⚠️ High Risk Area")
