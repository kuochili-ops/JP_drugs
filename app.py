import streamlit as st
import pandas as pd
import requests
import io
import re

# 1. 基礎工具函數：僅用於「比對時」的清洗，不影響原始顯示
def clean_for_match(text):
    if not isinstance(text, str): return ""
    # 轉半形
    text = text.translate(str.maketrans(
        '０１２３４５６７８９ＡＢＣＤＥＦＧＨＩＪＫＬＭＮＯＰＱＲＳＴＵＶＷＸＹＺ（）',
        '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ()'
    ))
    # 移除藥典標註 (比對用)
    text = re.sub(r'\(JP\d+.*?\)', '', text)
    text = re.sub(r'\(USP.*?\)', '', text)
    text = re.sub(r'\(NF.*?\)', '', text)
    # 移除 ※ 和 * 號註記
    text = re.sub(r'[※\*]\d+', '', text)
    # 處理 L/D 前綴符號與空白
    text = text.replace('－', '-').replace(' ', '').replace('　', '')
    return text.strip()

# 2. 核心智慧比對邏輯
def smart_match(search_name, kegg_ref):
    cleaned_input = clean_for_match(search_name)
    if not cleaned_input: return None, None
    
    # 優先級 1: 清洗後完全一致
    for ref in kegg_ref:
        if cleaned_input == ref['cleaned_name']:
            return ref['id'], ref['eng']

    # 優先級 2: 包含比對
    for ref in kegg_ref:
        if cleaned_input in ref['cleaned_name']:
            return ref['id'], ref['eng']

    # 優先級 3: 複方拆解 (・)
    if '・' in cleaned_input:
        parts = [p for p in cleaned_input.split('・') if p]
        for ref in kegg_ref:
            if all(part in ref['cleaned_name'] for part in parts):
                return ref['id'], ref['eng']
    
    return None, None

def fetch_and_fill_kegg_data_final(input_df):
    target_col = '成分名 (日)'
    eng_col = '成分名 (英)'
    id_col = 'KEGG_ID'

    # 下載 KEGG 對照表
    url = "https://rest.kegg.jp/list/dr_ja"
    try:
        response = requests.get(url, timeout=20)
        response.raise_for_status()
    except:
        st.error("無法連線至 KEGG 資料庫。")
        return None

    # 預處理 KEGG 資料
    kegg_ref = []
    for line in response.text.strip().split('\n'):
        parts = line.split('\t')
        if len(parts) < 2: continue
        d_id = "dr_ja:" + parts[0].replace("dr:", "")
        full_info = parts[1]
        
        # 提取括號內的英文名 (通常是最後一個括號)
        eng_match = re.search(r'\(([^)]+)\)$', full_info)
        eng_name = eng_match.group(1) if eng_match else ""
        
        kegg_ref.append({
            'id': d_id,
            'cleaned_name': clean_for_match(full_info),
            'eng': eng_name
        })

    # 執行補齊
    progress_bar = st.progress(0)
    total_rows = len(input_df)
    
    for i, row in input_df.iterrows():
        # 若 ID 為空才補
        if pd.isna(row.get(id_col)) or str(row.get(id_col)).strip() in ["", "nan"]:
            found_id, found_eng = smart_match(row[target_col], kegg_ref)
            if found_id:
                input_df.at[i, id_col] = found_id
                # 若英文名為空才補
                if pd.isna(row.get(eng_col)) or str(row.get(eng_col)).strip() == "":
                    input_df.at[i, eng_col] = found_eng
        
        progress_bar.progress((i + 1) / total_rows)
    
    return input_df

# --- 3. Streamlit UI ---
st.set_page_config(page_title="藥品清單自動補齊", layout="wide")
st.title("💊 藥品清單自動補齊 (高相容性版)")
st.markdown("""
### 匹配規則說明：
1. **保留藥典標註**：程式會識別但「不會刪除」您原始資料中的 `(JP18)` 等內容。
2. **自動過濾註記**：比對時自動忽略 `※1`, `※2` 等符號。
3. **複方與異構體支援**：精確處理 `・` 分隔的成分及 `L-`, `D-` 前綴。
""")

uploaded_file = st.file_uploader("上傳 CSV 檔案 (欄位需包含 '成分名 (日)')", type=['csv'])

if uploaded_file:
    df = pd.read_csv(uploaded_file)
    st.write("### 原始資料預覽")
    st.dataframe(df.head(5))

    if st.button("開始智慧補齊"):
        initial_missing = df['KEGG_ID'].isna().sum()
        with st.spinner("正在檢索並比對資料..."):
            result_df = fetch_and_fill_kegg_data_final(df.copy())
            
            if result_df is not None:
                final_missing = result_df['KEGG_ID'].isna().sum()
                filled_count = initial_missing - final_missing
                
                st.success("處理完畢！")
                
                # 數據面板
                c1, c2, c3 = st.columns(3)
                c1.metric("成功補齊", f"{filled_count} 項")
                c2.metric("尚未配對", f"{final_missing} 項")
                c3.metric("總筆數", f"{len(result_df)} 筆")
                
                if final_missing > 0:
                    with st.expander("🔍 檢視未配對項目"):
                        st.table(result_df[result_df['KEGG_ID'].isna()][['成分名 (日)', '成分名 (英)']])
                
                st.subheader("完整結果")
                st.dataframe(result_df)
                
                # 下載
                csv_buffer = io.BytesIO()
                result_df.to_csv(csv_buffer, index=False, encoding='utf-8-sig')
                st.download_button("📥 下載更新後的 CSV", data=csv_buffer.getvalue(), file_name="KEGG_Updated_List.csv")
