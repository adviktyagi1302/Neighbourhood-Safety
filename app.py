import streamlit as st
import firebase_admin
from firebase_admin import credentials, db
import folium
from streamlit_folium import st_folium
from geopy.geocoders import Nominatim
import random
from datetime import datetime, timedelta
import plotly.graph_objects as go  # <--- New Import

# ... (Keep your existing Page Config and Firebase Init) ...

# --- NEW FUNCTION: DANGER METER ---
def draw_danger_meter(score):
    # We invert the score because 100 Safety = 0 Danger
    danger_val = 100 - score
    
    fig = go.Figure(go.Indicator(
        mode = "gauge+number",
        value = danger_val,
        domain = {'x': [0, 1], 'y': [0, 1]},
        title = {'text': "Danger Level", 'font': {'size': 24}},
        gauge = {
            'axis': {'range': [0, 100], 'tickwidth': 1},
            'bar': {'color': "black"},
            'bgcolor': "white",
            'borderwidth': 2,
            'bordercolor': "gray",
            'steps': [
                {'range': [0, 30], 'color': 'green'},
                {'range': [30, 70], 'color': 'orange'},
                {'range': [70, 100], 'color': 'red'}
            ],
        }
    ))
    fig.update_layout(height=250, margin=dict(l=20, r=20, t=50, b=20))
    return fig

# ... (Keep Login and Reporting Logic the same) ...

# --- UPDATED DASHBOARD SECTION ---
if st.session_state.logged_in:
    # ... (Keep Data Fetching & Filter Logic) ...

    col_map, col_stats = st.columns([2, 1]) # Adjusted ratio for the meter
    
    with col_map:
        m = folium.Map(location=[28.61, 77.20], zoom_start=12)
        for r in all_reports:
            folium.Marker(
                location=[r['lat'], r['lon']],
                popup=f"{r.get('category')}: {r.get('desc')}",
                icon=folium.Icon(color=r.get('marker_color', 'blue'))
            ).add_to(m)
        st_folium(m, width=800, height=500)

    with col_stats:
        st.subheader("Safety Analytics")
        
        # Display the Gauge Meter
        st.plotly_chart(draw_danger_meter(safety_metric), use_container_width=True)
        
        st.metric("Safety Index", f"{safety_metric}/100")
        st.write(f"**Verified Reports (24h):** {len(all_reports)}")
        
        if safety_metric < 50:
            st.error("🛑 HIGH RISK AREA")
        elif safety_metric < 80:
            st.warning("⚠️ CAUTION")
        else:
            st.success("✅ SECURE")
