import streamlit as st
import psycopg2
import pandas as pd
import pydeck as pdk

# --- DB CONNECTION ---
@st.cache_resource
def get_conn():
    return psycopg2.connect(
        dbname=st.secrets["DB_NAME"],
        user=st.secrets["DB_USER"],
        password=st.secrets["DB_PASSWORD"],
        host=st.secrets["DB_HOST"],
        port=st.secrets["DB_PORT"],
        sslmode="require"
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
        cur.execute("""<PASTE closest_opt SQL HERE>""")
        return cur.fetchall()

@st.cache_data(ttl=3600)
def get_furthest():
    with conn.cursor() as cur:
        cur.execute("""<PASTE furthest_opt SQL HERE>""")
        return cur.fetchall()

# --- UI ---
st.title("Parkrun Distance Calculator")

place1 = st.selectbox("From", places)
place2 = st.selectbox("To", places)

if place1 == place2:
    st.warning("Please select two different places")
    st.stop()

# --- CALCULATION ---
if place1 and place2:
    with st.spinner("Calculating..."):
        result = get_distance(place1, place2)

    if result is not None:
        st.success(f"{place1} → {place2}: {result:,.1f} km")

    # --- MAP ---
    coords = get_coordinates(place1, place2)
    if coords:
        df = pd.DataFrame(coords, columns=["name", "lat", "lon"])
        df["color"] = [[255,0,0],[0,128,255]]

        scatter = pdk.Layer(
            "ScatterplotLayer",
            data=df,
            get_position="[lon, lat]",
            get_fill_color="color",
            get_radius=20000
        )

        line = pdk.Layer(
            "LineLayer",
            data=[{
                "from_lon": df.iloc[0]["lon"],
                "from_lat": df.iloc[0]["lat"],
                "to_lon": df.iloc[1]["lon"],
                "to_lat": df.iloc[1]["lat"]
            }],
            get_source_position="[from_lon, from_lat]",
            get_target_position="[to_lon, to_lat]",
            get_color=[0,0,255],
            get_width=3
        )

        mid_lat = df["lat"].mean()
        mid_lon = df["lon"].mean()

        view = pdk.ViewState(latitude=mid_lat, longitude=mid_lon, zoom=3)

        st.pydeck_chart(pdk.Deck(
            map_style="https://basemaps.cartocdn.com/gl/positron-gl-style/style.json",
            initial_view_state=view,
            layers=[scatter, line],
            tooltip={"html": "<b>{name}</b>"}
        ))

# --- TOP LISTS ---
st.markdown("---")
st.header("Distance Rankings")

tab1, tab2 = st.tabs(["Closest 100", "Furthest 100"])

with tab1:
    df = pd.DataFrame(get_closest(), columns=["From","To","Distance"])
    df["Distance"] = df["Distance"].map(lambda x: f"{x:,.1f}")
    st.dataframe(df, use_container_width=True)

with tab2:
    df = pd.DataFrame(get_furthest(), columns=["From","To","Distance"])
    df["Distance"] = df["Distance"].map(lambda x: f"{x:,.1f}")
    st.dataframe(df, use_container_width=True)