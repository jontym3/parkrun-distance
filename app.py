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

# --- LOAD PLACE LIST ---
@st.cache_data
def get_places():
    with conn.cursor() as cur:
        cur.execute("SELECT name FROM places ORDER BY name;")
        return [row[0] for row in cur.fetchall()]

places = get_places()

# --- GET COORDINATES ---
@st.cache_data
def get_coordinates(place1, place2):
    with conn.cursor() as cur:
        cur.execute("""
            SELECT name, lat, lon
            FROM places
            WHERE name IN (%s, %s);
        """, (place1, place2))
        return cur.fetchall()

# --- UI ---
st.title("Parkrun Distance Calculator")

place1 = st.selectbox("From", places)
place2 = st.selectbox("To", places)

# --- VALIDATION ---
if place1 == place2:
    st.warning("Please select two different places")
    st.stop()

# --- CALCULATION ---
if place1 and place2:
    with st.spinner("Calculating distance..."):
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
            """, (place1, place2))

            row = cur.fetchone()
            result = row[0] if row else None

    # --- OUTPUT ---
    if result is not None:
        st.success(f"{place1} → {place2}: {result:,.1f} km")
    else:
        st.error("Could not calculate distance")

    st.caption(f"From: {place1} | To: {place2}")
    st.markdown("---")

    # --- MAP ---
    coords = get_coordinates(place1, place2)

    if coords:
        df = pd.DataFrame(coords, columns=["name", "lat", "lon"])

        # --- Different colours
        if len(df) == 2:
            df["color"] = [[255, 0, 0], [0, 128, 255]]
        else:
            df["color"] = [[255, 0, 0]] * len(df)

        # --- Scatter points
        scatter_layer = pdk.Layer(
            "ScatterplotLayer",
            data=df,
            get_position="[lon, lat]",
            get_radius=20000,
            get_fill_color="color",
            pickable=True,
        )

        # --- Line
        if len(df) == 2:
            line_data = pd.DataFrame([{
                "from_lon": df.iloc[0]["lon"],
                "from_lat": df.iloc[0]["lat"],
                "to_lon": df.iloc[1]["lon"],
                "to_lat": df.iloc[1]["lat"]
            }])

            line_layer = pdk.Layer(
                "LineLayer",
                data=line_data,
                get_source_position="[from_lon, from_lat]",
                get_target_position="[to_lon, to_lat]",
                get_color=[0, 0, 255],
                get_width=3,
            )
        else:
            line_layer = None

        # --- AUTO-FIT BOUNDS ---
        min_lat = df["lat"].min()
        max_lat = df["lat"].max()
        min_lon = df["lon"].min()
        max_lon = df["lon"].max()

        mid_lat = (min_lat + max_lat) / 2
        mid_lon = (min_lon + max_lon) / 2

        lat_diff = max_lat - min_lat
        lon_diff = max_lon - min_lon

        spread = max(lat_diff, lon_diff)

        # Padding so points aren't on edge
        spread *= 1.2

        if spread > 100:
            zoom = 1
        elif spread > 50:
            zoom = 2
        elif spread > 20:
            zoom = 3
        elif spread > 10:
            zoom = 4
        elif spread > 5:
            zoom = 5
        elif spread > 2:
            zoom = 6
        elif spread > 1:
            zoom = 7
        else:
            zoom = 8

        view_state = pdk.ViewState(
            latitude=mid_lat,
            longitude=mid_lon,
            zoom=zoom,
        )

        # --- Tooltip
        tooltip = {
            "html": "<b>{name}</b>",
            "style": {"backgroundColor": "steelblue", "color": "white"}
        }

        layers = [scatter_layer]
        if line_layer:
            layers.append(line_layer)

        st.pydeck_chart(pdk.Deck(
            map_style="https://basemaps.cartocdn.com/gl/positron-gl-style/style.json",
            initial_view_state=view_state,
            layers=layers,
            tooltip=tooltip,
        ))