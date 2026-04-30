import streamlit as st
import psycopg2

conn = psycopg2.connect(
    dbname=st.secrets["DB_NAME"],
    user=st.secrets["DB_USER"],
    password=st.secrets["DB_PASSWORD"],
    host=st.secrets["DB_HOST"],
    port=st.secrets["DB_PORT"],
    sslmode="require"
)

cur = conn.cursor()

@st.cache_data
def get_places():
    cur.execute("SELECT name FROM places ORDER BY name;")
    return [row[0] for row in cur.fetchall()]

places = get_places()

st.title("Parkrun Distance Calculator")

place1 = st.selectbox("From", places)
place2 = st.selectbox("To", places)

if place1 and place2:
    cur.execute("SELECT distance_km(%s, %s);", (place1, place2))
    result = cur.fetchone()[0]

    if result:
        st.success(f"{place1} → {place2}: {result:,.1f} km")