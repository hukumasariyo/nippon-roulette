import streamlit as st
import geopandas as gpd
import folium
from streamlit_folium import st_folium
import random
import os

st.set_page_config(page_title="全国 市町村ルーレット", layout="centered")

st.title("🎲 全国 市町村ルーレット")
st.write("ボタンを押してランダムに選ばれた全国の市区町村を当てよう！")

# 24MBに軽量化したTopoJSONファイル名
JSON_PATH = "np.json"

@st.cache_resource
def load_data():
    if not os.path.exists(JSON_PATH):
        files = [f for f in os.listdir('.') if f.endswith('.json') or f.endswith('.topojson')]
        if files:
            file_to_read = files[0]
        else:
            raise FileNotFoundError("np.json が見つかりません。")
    else:
        file_to_read = JSON_PATH
        
    try:
        gdf = gpd.read_file(file_to_read)
    except Exception:
        gdf = gpd.read_file(file_to_read, layer=0)
        
    return gdf

try:
    gdf = load_data()
    
    # 都道府県名と市区町村名のカラムを自動検出
    pref_col = next((col for col in ["N03_001", "pref", "PREF"] if col in gdf.columns), gdf.columns[0])
    city_col = next((col for col in ["N03_004", "city", "CITY", "N03_003"] if col in gdf.columns), gdf.columns[1])
    
    # 欠損値を除外
    gdf = gdf[gdf[city_col].notnull() & (gdf[city_col] != "")]
    # 容量制限内でサクサク動くように形を適度にシンプル化
    gdf["geometry"] = gdf["geometry"].simplify(tolerance=0.003, preserve_topology=True)
except Exception as e:
    st.error(f"データの読み込みに失敗しました。エラー: {e}")
    st.stop()

# セッション状態の初期化（重複なしの全域ループ）
if "remaining_indices" not in st.session_state:
    st.session_state.remaining_indices = list(gdf.index)
    random.shuffle(st.session_state.remaining_indices)
    st.session_state.current_idx = None
    st.session_state.revealed = False

def spin():
    if not st.session_state.remaining_indices:
        st.session_state.remaining_indices = list(gdf.index)
        random.shuffle(st.session_state.remaining_indices)
    st.session_state.current_idx = st.session_state.remaining_indices.pop()
    st.session_state.revealed = False

if st.session_state.current_idx is None:
    spin()

current_row = gdf.loc[st.session_state.current_idx]
target_pref = str(current_row.get(pref_col, ""))
target_city = str(current_row.get(city_col, ""))

# 操作ボタン（スマホでも押しやすい横並び）
col1, col2 = st.columns(2)
with col1:
    if st.button("🎲 ルーレットを回す！", use_container_width=True, type="primary"):
        spin()
        st.rerun()

with col2:
    if st.button("👀 答えを見る", use_container_width=True):
        st.session_state.revealed = True

st.caption(f"残り自治体数: {len(st.session_state.remaining_indices)} / {len(gdf)}")

if st.session_state.revealed:
    st.success(f"✨ 正解: 【 {target_pref} {target_city} 】")
else:
    st.info("🔍 どこの市区町村でしょう？ 地図をヒントに考えてみてください！")

# 地図の描画（中心点を自動計算してズーム）
centroid = current_row["geometry"].centroid
m = folium.Map(location=[centroid.y, centroid.x], zoom_start=10, tiles="CartoDB positron")

def get_style(feature):
    c_name = feature.get("properties", {}).get(city_col)
    if c_name == target_city:
        color = "#e74c3c" if st.session_state.revealed else "#3498db"
        return {"fillColor": color, "color": "#2980b9", "weight": 2, "fillOpacity": 0.8}
    else:
        return {"fillColor": "#bdc3c7", "color": "#95a5a6", "weight": 0.5, "fillOpacity": 0.2}

folium.GeoJson(gdf, style_function=get_style).add_to(m)

st_folium(m, width=700, height=450, key="map")