import streamlit as st
import geopandas as gpd
import folium
from streamlit_folium import st_folium
import random
import os

st.set_page_config(page_title="市区町村ルーレット", layout="centered")

st.set_page_config(page_title="市区町村ルーレット", layout="centered")

# ─── Streamlitのロゴやメニューを非表示にして通常のWebサイト風にするCSS ───
hide_style = """
    <style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    </style>
"""
st.markdown(hide_style, unsafe_allow_html=True)

st.title("市区町村ルーレット")
st.markdown("ランダムに選ばれる全国の市区町村を当てていくゲームです。")

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
    
    # 壊れた形状を修復してから合体処理
    raw_gdf["geometry"] = raw_gdf["geometry"].buffer(0)
    
    gdf = raw_gdf.dissolve(by=[pref_col, city_col], as_index=False)
    gdf["geometry"] = gdf["geometry"].simplify(tolerance=0.003, preserve_topology=True)

except Exception as e:
    st.error(f"データの読み込みに失敗しました。エラー: {e}")
    st.stop()

# ─── 都道府県別の選択フィルター ───
prefectures = ["全国"] + sorted(list(gdf[pref_col].unique()))
selected_pref = st.selectbox("出題範囲の選択", prefectures)

# フィルター適用
if selected_pref == "全国":
    filtered_gdf = gdf
else:
    filtered_gdf = gdf[gdf[pref_col] == selected_pref].reset_index(drop=True)

if len(filtered_gdf) == 0:
    st.warning("選択された条件に該当するデータがありません。")
    st.stop()

# セッション状態の初期化（フィルター変更時もリセット）
if "last_pref" not in st.session_state or st.session_state.last_pref != selected_pref:
    st.session_state.last_pref = selected_pref
    st.session_state.remaining_indices = list(filtered_gdf.index)
    random.shuffle(st.session_state.remaining_indices)
    st.session_state.current_idx = None
    st.session_state.answered_history = {}
    st.session_state.status = "guessing" # "guessing", "correct", "revealed"
    st.session_state.last_target_name = ""

if "remaining_indices" not in st.session_state or not st.session_state.remaining_indices:
    st.session_state.remaining_indices = list(filtered_gdf.index)
    random.shuffle(st.session_state.remaining_indices)

if st.session_state.current_idx is None or st.session_state.current_idx not in filtered_gdf.index:
    st.session_state.current_idx = st.session_state.remaining_indices.pop()
    st.session_state.status = "guessing"

current_row = filtered_gdf.loc[st.session_state.current_idx]
target_pref = str(current_row.get(pref_col, ""))
target_city = str(current_row.get(city_col, ""))

def next_question():
    if st.session_state.remaining_indices:
        st.session_state.current_idx = st.session_state.remaining_indices.pop()
    else:
        st.session_state.remaining_indices = list(filtered_gdf.index)
        random.shuffle(st.session_state.remaining_indices)
        st.session_state.current_idx = st.session_state.remaining_indices.pop()
    st.session_state.status = "guessing"

st.caption(f"残り自治体数: {len(st.session_state.remaining_indices) + 1} / {len(filtered_gdf)}")

# ─── 回答・操作セクション ───
if st.session_state.status == "correct":
    st.success(f"正解: {st.session_state.last_pref_name} {st.session_state.last_target_name}")
    if st.button("次の問題へ進む", use_container_width=True, type="primary"):
        next_question()
        st.rerun()

elif st.session_state.status == "revealed":
    st.info(f"正解: {st.session_state.last_pref_name} {st.session_state.last_target_name}")
    if st.button("次の問題へ進む", use_container_width=True, type="primary"):
        next_question()
        st.rerun()

else:
    with st.form(key="guess_form", clear_on_submit=True):
        user_input = st.text_input("自治体名を入力", placeholder="例: 〇〇市 / 〇〇町 / 〇〇村")
        col_sub1, col_sub2 = st.columns(2)
        with col_sub1:
            submit_guess = st.form_submit_button("回答する", use_container_width=True)
        with col_sub2:
            give_up = st.form_submit_button("答えを見る", use_container_width=True)

    if submit_guess and user_input:
        if target_city in user_input or user_input in target_city:
            st.session_state.status = "correct"
            st.session_state.last_pref_name = target_pref
            st.session_state.last_target_name = target_city
            st.session_state.answered_history[target_city] = "correct"
            st.rerun()
        else:
            st.error(f"間違い: 「{user_input}」ではありません。")

    if give_up:
        st.session_state.status = "revealed"
        st.session_state.last_pref_name = target_pref
        st.session_state.last_target_name = target_city
        st.session_state.answered_history[target_city] = "revealed"
        st.rerun()

# ─── 地図の描画 ───
centroid = current_row["geometry"].centroid
m = folium.Map(location=[centroid.y, centroid.x], zoom_start=10, tiles="CartoDB positron")

def get_style(feature):
    props = feature.get("properties", {})
    c_name = props.get(city_col)
    
    if c_name == target_city and st.session_state.status == "guessing":
        return {"fillColor": "#3498db", "color": "#2980b9", "weight": 2, "fillOpacity": 0.8}
    elif c_name in st.session_state.answered_history:
        status = st.session_state.answered_history[c_name]
        color = "#2ecc71" if status == "correct" else "#e67e22"
        return {"fillColor": color, "color": "#d35400", "weight": 1, "fillOpacity": 0.7}
    else:
        return {"fillColor": "#ecf0f1", "color": "#bdc3c7", "weight": 0.5, "fillOpacity": 0.3}

folium.GeoJson(filtered_gdf, style_function=get_style).add_to(m)

st_folium(m, width=700, height=450, key="map")