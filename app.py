import streamlit as st
import psycopg2
import pandas as pd
import streamlit.components.v1 as components

# --- DB CONNECTION ---
@st.cache_resource
def get_conn():
    return psycopg2.connect(
        dbname=st.secrets["DB_NAME"],
        user=st.secrets["DB_USER"],
        password=st.secrets["DB_PASSWORD"],
        host=st.secrets["DB_HOST"],
        port=st.secrets["DB_PORT"],
        sslmode="require",
    )

conn = get_conn()

# --- LOAD PLACES ---
@st.cache_data(ttl=3600)
def get_places():
    with conn.cursor() as cur:
        cur.execute("SELECT name FROM places ORDER BY name;")
        return [r[0] for r in cur.fetchall()]

places = get_places()

# --- COORDINATES ---
@st.cache_data(ttl=3600)
def get_coordinates(p1, p2):
    with conn.cursor() as cur:
        cur.execute("""
            SELECT name, lat, lon
            FROM places
            WHERE name IN (%s, %s)
        """, (p1, p2))
        return cur.fetchall()

# --- DISTANCE ---
@st.cache_data(ttl=3600)
def get_distance(p1, p2):
    with conn.cursor() as cur:
        cur.execute("""
            SELECT 6371 * acos(
                sin(a.lat_rad) * sin(b.lat_rad) +
                cos(a.lat_rad) * cos(b.lat_rad) *
                cos(b.lon_rad - a.lon_rad)
            )
            FROM places a
            JOIN places b
              ON a.name = %s AND b.name = %s;
        """, (p1, p2))
        row = cur.fetchone()
        return row[0] if row else None

# --- OPTIMISED LISTS ---
@st.cache_data(ttl=3600)
def get_closest():
    with conn.cursor() as cur:
        cur.execute("""
            WITH approx AS (
                SELECT a.name AS from_name, b.name AS to_name,
                       (a.lat - b.lat)^2 + (a.lon - b.lon)^2 AS approx_dist
                FROM places a
                JOIN places b ON a.id < b.id
                ORDER BY approx_dist ASC
                LIMIT 1000
            )
            SELECT from_name, to_name,
                   6371 * acos(
                       sin(radians(a.lat)) * sin(radians(b.lat)) +
                       cos(radians(a.lat)) * cos(radians(b.lat)) *
                       cos(radians(b.lon - a.lon))
                   ) AS distance
            FROM approx
            JOIN places a ON a.name = approx.from_name
            JOIN places b ON b.name = approx.to_name
            ORDER BY distance ASC
            LIMIT 100;
        """)
        return cur.fetchall()

@st.cache_data(ttl=3600)
def get_furthest():
    with conn.cursor() as cur:
        cur.execute("""
            SELECT a.name, b.name,
                   6371 * acos(
                       sin(a.lat_rad) * sin(b.lat_rad) +
                       cos(a.lat_rad) * cos(b.lat_rad) *
                       cos(b.lon_rad - a.lon_rad)
                   ) AS distance
            FROM places a
            JOIN places b ON a.id < b.id
            ORDER BY distance DESC
            LIMIT 100;
        """)
        return cur.fetchall()

# --- UI ---
st.title("Parkrun Distance Calculator")

place1 = st.selectbox("From", [""] + places, index=0, placeholder="Start typing...")
place2 = st.selectbox("To", [""] + places, index=0, placeholder="Start typing...")

# --- CALCULATION + MAP ---
import plotly.graph_objects as go
import numpy as np

coords = get_coordinates(place1, place2)

if coords:
    df = pd.DataFrame(coords, columns=["name", "lat", "lon"])

    lat1, lon1 = df.iloc[0]["lat"], df.iloc[0]["lon"]
    lat2, lon2 = df.iloc[1]["lat"], df.iloc[1]["lon"]

    # --- create great circle curve ---
    lats = np.linspace(lat1, lat2, 100)
    lons = np.linspace(lon1, lon2, 100)

    fig = go.Figure()

    # Points
    fig.add_trace(go.Scattergeo(
        lat=[lat1, lat2],
        lon=[lon1, lon2],
        mode='markers',
        marker=dict(size=8, color=['red', 'blue']),
        text=df["name"],
    ))

    # Curved path
    fig.add_trace(go.Scattergeo(
        lat=lats,
        lon=lons,
        mode='lines',
        line=dict(width=2, color='yellow'),
    ))

    fig.update_layout(
        geo=dict(
            projection_type="orthographic",  # 🌍 globe
            showland=True,
            landcolor="lightgray",
            showocean=True,
            oceancolor="lightblue",
        ),
        margin=dict(l=0, r=0, t=0, b=0)
    )

    st.plotly_chart(fig, use_container_width=True)

# --- TOP LISTS (always visible) ---
st.markdown("---")
st.header("Distance Rankings")

tab1, tab2 = st.tabs(["Closest 100", "Furthest 100"])

with tab1:
    df = pd.DataFrame(get_closest(), columns=["From", "To", "Distance"])
    df["Distance"] = df["Distance"].map(lambda x: f"{x:,.1f}")
    df.insert(0, "Rank", range(1, len(df) + 1))
    st.dataframe(df, use_container_width=True, hide_index=True)

with tab2:
    df = pd.DataFrame(get_furthest(), columns=["From", "To", "Distance"])
    df["Distance"] = df["Distance"].map(lambda x: f"{x:,.1f}")
    df.insert(0, "Rank", range(1, len(df) + 1))
    st.dataframe(df, use_container_width=True, hide_index=True)

