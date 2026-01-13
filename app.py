import streamlit as st
import pandas as pd
import requests

# 1. 定義處理函式 (與上方修正版相同)
def fetch_and_fill_kegg_data(input_df):
    url = "https://rest.kegg.jp/list/dr_ja"
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
    except:
        st.error("無法連線至 KEGG 資料庫")
        return input_df

    # 解析數據
    kegg_data = []
    for line in response.text.strip().split('\n'):
        parts = line.split('\t')
        if len(parts) < 2: continue
        k_id = parts[0].replace("dr:", "")
        full_info = parts[1]
        jap_name = full_info.split(';')[0].split(' (')[0].strip()
        eng_name = ""
        if "(" in full_info and ")" in full_info:
            eng_name = full_info[full_info.rfind("(")+1 : full_info.rfind(")")]
        kegg_data.append({'品項名稱': jap_name, 'KEGG_ID_REF': k_id, 'ENG_REF': eng_name})

    ref_df = pd.DataFrame(kegg_data).drop_duplicates('品項名稱')
    merged = pd.merge(input_df, ref_df, on='品項名稱', how='left')

    # 補值邏輯
    for col, ref in [('KEGG_ID', 'KEGG_ID_REF'), ('成分名 (英)', 'ENG_REF')]:
        if col not in merged.columns:
            merged[col] = merged[ref]
        else:
            merged[col] = merged[col].fillna(merged[ref])
    
    return merged.drop(columns=['KEGG_ID_REF', 'ENG_REF'])

# 2. Streamlit 介面設計
st.title("💊 KEGG 藥品資料補齊工具")

uploaded_file = st.file_uploader("請上傳 Excel 或 CSV 檔案", type=['xlsx', 'csv'])

if uploaded_file:
    # 讀取檔案
    if uploaded_file.name.endswith('.csv'):
        df = pd.read_csv(uploaded_file)
    else:
        df = pd.read_excel(uploaded_file)

    st.subheader("原始資料預覽")
    st.write(df.head()) # 顯示前幾行

    if st.button("開始自動補齊"):
        with st.spinner('檢索中...'):
            # 執行補齊功能
            final_df = fetch_and_fill_kegg_data(df)
            
            # --- 關鍵：顯示結果 ---
            st.subheader("補齊後的資料")
            st.dataframe(final_df) # 在畫面上印出表格
            
            # 下載按鈕
            csv = final_df.to_csv(index=False).encode('utf-8-sig')
            st.download_button(
                label="下載修正後的 CSV",
                data=csv,
                file_name="filled_drug_data.csv",
                mime="text/csv",
            )
