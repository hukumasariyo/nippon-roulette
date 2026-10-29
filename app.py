import streamlit as st
import geopandas as gpd
import folium
from streamlit_folium import st_folium
import random
import os

st.set_page_config(page_title="全国 市町村ルーレット", layout="centered")

st.title("🎲 全国 市町村ルーレット")
st.write("ランダムに選ばれた全国の市区町村を当てよう！")

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
    raw_gdf = load_data()
    
    if raw_gdf.crs is None:
        raw_gdf = raw_gdf.set_crs("EPSG:4326")
    else:
        raw_gdf = raw_gdf.to_crs("EPSG:4326")

    # 都道府県名と市区町村名のカラムを自動検出
    pref_col = next((col for col in ["N03_001", "pref", "PREF"] if col in raw_gdf.columns), raw_gdf.columns[0])
    city_col = next((col for col in ["N03_004", "city", "CITY", "N03_003"] if col in raw_gdf.columns), raw_gdf.columns[1])
    
    # 欠損値を除外
    raw_gdf = raw_gdf[raw_gdf[city_col].notnull() & (raw_gdf[city_col] != "")]
    
    # 🌟 同じ市区町村のポリゴンを一つにまとめて約1700自治体に正確化 ＆ 軽量化
    gdf = raw_gdf.dissolve(by=[pref_col, city_col], as_index=False)
    gdf["geometry"] = gdf["geometry"].simplify(tolerance=0.003, preserve_topology=True)

except Exception as e:
    st.error(f"データの読み込みに失敗しました。エラー: {e}")
    st.stop()

# セッション状態の初期化
if "remaining_indices" not in st.session_state:
    st.session_state.remaining_indices = list(gdf.index)
    random.shuffle(st.session_state.remaining_indices)
    st.session_state.current_idx = None
    st.session_state.answered_history = {} # 答えた履歴 {city_name: "correct" or "revealed"}

def spin():
    if not st.session_state.remaining_indices:
        st.session_state.remaining_indices = list(gdf.index)
        random.shuffle(st.session_state.remaining_indices)
    st.session_state.current_idx = st.session_state.remaining_indices.pop()

if st.session_state.current_idx is None:
    spin()

current_row = gdf.loc[st.session_state.current_idx]
target_pref = str(current_row.get(pref_col, ""))
target_city = str(current_row.get(city_col, ""))

# ─── 回答・操作セクション ───
st.caption(f"残り自治体数: {len(st.session_state.remaining_indices)} / {len(gdf)}")

# ユーザーの文字入力欄
with st.form(key="guess_form", clear_on_submit=True):
    user_input = st.text_input("自治体名を入力（例: 〇〇市 / 〇〇町 / 〇〇村）", placeholder="市区町村名を入力してEnter")
    col_sub1, col_sub2 = st.columns(2)
    with col_sub1:
        submit_guess = st.form_submit_button("🎯 回答する", use_container_width=True)
    with col_sub2:
        give_up = st.form_submit_button("👀 答えを見る", use_container_width=True)

# 判定処理
if submit_guess and user_input:
    # 入力された文字にターゲット名が含まれているか判定
    if target_city in user_input or user_input in target_city:
        st.success(f"🎉 正解！ 【 {target_pref} {target_city} 】")
        st.session_state.answered_history[target_city] = "correct"
        spin()
        st.rerun()
    else:
        st.error(f"❌ 惜しい！ 「{user_input}」ではありません。もう一度トライ！")

if give_up:
    st.warning(f"💡 正解は 【 {target_pref} {target_city} 】 でした。")
    st.session_state.answered_history[target_city] = "revealed"
    spin()
    st.rerun()

# ─── 地図の描画（回答済み区域に色を保持） ───
centroid = current_row["geometry"].centroid
m = folium.Map(location=[centroid.y, centroid.x], zoom_start=10, tiles="CartoDB positron")

def get_style(feature):
    props = feature.get("properties", {})
    c_name = props.get(city_col)
    
    if c_name == target_city:
        # 現在のターゲット
        return {"fillColor": "#3498db", "color": "#2980b9", "weight": 2, "fillOpacity": 0.8}
    elif c_name in st.session_state.answered_history:
        # 過去に答えた区域（正解は緑、ギブアップはオレンジ）
        status = st.session_state.answered_history[c_name]
        color = "#2ecc71" if status == "correct" else "#e67e22"
        return {"fillColor": color, "color": "#d35400", "weight": 1, "fillOpacity": 0.7}
    else:
        # 未訪問
        return {"fillColor": "#ecf0f1", "color": "#bdc3c7", "weight": 0.5, "fillOpacity": 0.3}

folium.GeoJson(gdf, style_function=get_style).add_to(m)

st_folium(m, width=700, height=450, key="map")