import streamlit as st
import pandas as pd
import requests
import io
import re

# 定義全形轉半形的簡單函數，解決「４」與「4」的問題
def zen_to_han(text):
    if not isinstance(text, str): return text
    # 建立全形數字/字母轉半形的對照
    return text.translate(str.maketrans(
        '０１２３４５６７８９ＡＢＣＤＥＦＧＨＩＪＫＬＭＮＯＰＱＲＳＴＵＶＷＸＹＺ',
        '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ'
    ))

def fetch_and_fill_kegg_data_smart(input_df):
    target_col = '成分名 (日)'
    eng_col = '成分名 (英)'
    id_col = 'KEGG_ID'

    if target_col not in input_df.columns:
        st.error(f"找不到欄位 '{target_col}'。請檢查檔案。")
        return None

    # 1. 抓取 KEGG 清單
    st.info("正在連線至 KEGG 資料庫 (dr_ja)...")
    url = "https://rest.kegg.jp/list/dr_ja"
    try:
        response = requests.get(url, timeout=15)
        response.raise_for_status()
    except:
        st.error("連線 KEGG 失敗")
        return None

    # 建立參考清單，並預先將 KEGG 名稱轉為半形以利比對
    kegg_ref = []
    for line in response.text.strip().split('\n'):
        parts = line.split('\t')
        if len(parts) < 2: continue
        d_id = parts[0].replace("dr:", "")
        full_info = parts[1]
        
        # 提取英文名 (通常在最後一個括號)
        eng_match = re.search(r'\(([^)]+)\)$', full_info)
        eng_name = eng_match.group(1) if eng_match else ""
        
        kegg_ref.append({
            'id': d_id,
            'original_full': full_info,
            'clean_full': zen_to_han(full_info), # 轉半形方便比對
            'eng': eng_name
        })

    # 2. 開始逐行比對
    st.write("正在進行智慧搜尋與自動填補...")
    progress_bar = st.progress(0)
    total_rows = len(input_df)

    for i, row in input_df.iterrows():
        # 如果 ID 已經有值，就不重複填寫
        if pd.notna(row.get(id_col)) and str(row.get(id_col)).strip() != "":
            progress_bar.progress((i + 1) / total_rows)
            continue
            
        search_name = zen_to_han(str(row[target_col])) # 將輸入也轉半形
        
        # 邏輯：搜尋 KEGG 的名稱中是否包含使用者的藥名
        match_id = None
        match_eng = None
        
        for ref in kegg_ref:
            # 只要 KEGG 包含你的藥名，例如 "４価髄膜炎菌ワクチン" 包含在 "４価髄膜炎菌ワクチン (結合型)"
            if search_name in ref['clean_full']:
                match_id = "dr_ja:" + ref['id']
                match_eng = ref['eng']
                break # 找到第一個就跳出
        
        if match_id:
            input_df.at[i, id_col] = match_id
            # 如果英文名是空的才補
            if pd.isna(row.get(eng_col)) or str(row.get(eng_col)).strip() == "":
                input_df.at[i, eng_col] = match_eng
        
        progress_bar.progress((i + 1) / total_rows)

    return input_df

# --- Streamlit UI ---
st.title("💊 智慧型藥品資料補齊工具")
st.markdown("針對 `成分名 (日)` 進行模糊比對，填補 `KEGG_ID` 與 `成分名 (英)`")

uploaded_file = st.file_uploader("上傳 CSV 檔案", type=['csv'])

if uploaded_file:
    df = pd.read_csv(uploaded_file)
    st.write("### 原始資料預覽")
    st.dataframe(df.head(10))

    if st.button("啟動智慧補齊"):
        with st.spinner("智慧搜尋中..."):
            result_df = fetch_and_fill_kegg_data_smart(df)
            
            if result_df is not None:
                st.success("處理完成！")
                st.dataframe(result_df)
                
                # 輸出下載
                output = io.BytesIO()
                result_df.to_csv(output, index=False, encoding='utf-8-sig')
                st.download_button("📥 下載修正後的 CSV", data=output.getvalue(), file_name="KEGG_Fixed_List.csv")
