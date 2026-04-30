import streamlit as st
import psycopg2

# --- DB CONNECTION (cached so it isn't recreated every run)
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

# --- LOAD PLACE LIST (cached = faster UI)
@st.cache_data
def get_places():
    with conn.cursor() as cur:
        cur.execute("SELECT name FROM places ORDER BY name;")
        return [row[0] for row in cur.fetchall()]

places = get_places()

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

            result = cur.fetchone()[0]

    # --- SAFE OUTPUT ---
    if result is not None:
        st.success(f"{place1} → {place2}: {result:,.1f} km")
    else:
        st.error("Could not calculate distance")