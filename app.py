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

# --- CALCULATION + MAP ---
if place1 and place2 and place1 != place2:
    result = get_distance(place1, place2)

    if result is not None:
        st.success(f"{place1} → {place2}: {result:,.1f} km")

    coords = get_coordinates(place1, place2)

    if coords:
        df = pd.DataFrame(coords, columns=["name", "lat", "lon"])

        lat1, lon1 = df.iloc[0]["lat"], df.iloc[0]["lon"]
        lat2, lon2 = df.iloc[1]["lat"], df.iloc[1]["lon"]

        html = """
        <html>
        <head>
            <script src="https://cesium.com/downloads/cesiumjs/releases/1.111/Build/Cesium/Cesium.js"></script>
            <link href="https://cesium.com/downloads/cesiumjs/releases/1.111/Build/Cesium/Widgets/widgets.css" rel="stylesheet">
            <style>
                html, body, #cesiumContainer {{
                    width: 100%; height: 500px; margin: 0; padding: 0;
                }}
            </style>
        </head>
        <body>
        <div id="cesiumContainer"></div>
        <script>
            Cesium.Ion.defaultAccessToken = '{token}';

            const viewer = new Cesium.Viewer('cesiumContainer', {{
                terrainProvider: Cesium.createWorldTerrain()
            }});

            viewer.imageryLayers.addImageryProvider(
                new Cesium.IonImageryProvider({{ assetId: 2 }})
            );

            const p1 = Cesium.Cartesian3.fromDegrees({lon1}, {lat1});
            const p2 = Cesium.Cartesian3.fromDegrees({lon2}, {lat2});

            viewer.entities.add({{
                position: p1,
                point: {{ pixelSize: 10, color: Cesium.Color.RED }}
            }});

            viewer.entities.add({{
                position: p2,
                point: {{ pixelSize: 10, color: Cesium.Color.BLUE }}
            }});

            viewer.entities.add({{
                polyline: {{
                    positions: [p1, p2],
                    width: 4,
                    material: new Cesium.PolylineGlowMaterialProperty({{
                        glowPower: 0.2,
                        color: Cesium.Color.YELLOW
                    }}),
                    arcType: Cesium.ArcType.GEODESIC
                }}
            }});

            viewer.zoomTo(viewer.entities);
        </script>
        </body>
        </html>
        """.format(
            lat1=lat1,
            lon1=lon1,
            lat2=lat2,
            lon2=lon2,
            token=st.secrets["eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJqdGkiOiI3ZjdmNDlhZC1jMjQxLTRiNmMtOTRjMy1iOGU2MmE3NDhjY2UiLCJpZCI6NDI1NjAwLCJpYXQiOjE3Nzc1MjI1MTh9.zRNbOUNTDY5cAl2308K0d1CWyagQ-va8ZUcFY2DYkss"]
        )

        components.html(html, height=500)