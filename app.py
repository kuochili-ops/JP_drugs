import streamlit as st
import pandas as pd
import requests

def fetch_and_fill_kegg_data_advanced(input_df):
    target_col = '成分名 (日)'
    
    # 1. 抓取 KEGG 清單並建立搜尋字典
    url = "https://rest.kegg.jp/list/dr_ja"
    response = requests.get(url)
    kegg_lines = response.text.strip().split('\n')
    
    kegg_records = []
    for line in kegg_lines:
        parts = line.split('\t')
        if len(parts) < 2: continue
        d_id = parts[0].replace("dr:", "")
        full_text = parts[1]
        kegg_records.append({'id': d_id, 'full_text': full_text})

    # 2. 定義一個智慧比對函數
    def find_best_kegg(name):
        if pd.isna(name) or name == "": return None, None
        
        # 清理輸入名稱（轉半形、去空格）
        clean_name = str(name).replace('　', ' ').strip()
        
        # 第一輪：完全匹配
        for rec in kegg_records:
            if clean_name in rec['full_text']:
                # 提取英文名 (假設在最後一個括號)
                eng = ""
                if "(" in rec['full_text'] and ")" in rec['full_text']:
                    eng = rec['full_text'][rec['full_text'].rfind("(")+1 : rec['full_text'].rfind(")")]
                return rec['id'], eng
        
        # 第二輪：模糊關鍵字匹配（將名稱拆開比對）
        # 這裡可以再加入更複雜的模糊邏輯
        return None, None

    # 3. 執行填補
    st.info("正在進行智慧比對中...")
    
    # 建立進度條
    progress_bar = st.progress(0)
    total = len(input_df)

    for i, row in input_df.iterrows():
        # 只有當 KEGG_ID 為空時才填補
        if pd.isna(row.get('KEGG_ID')) or row.get('KEGG_ID') == "":
            found_id, found_eng = find_best_kegg(row[target_col])
            if found_id:
                input_df.at[i, 'KEGG_ID'] = found_id
                if pd.isna(row.get('成分名 (英)')) or row.get('成分名 (英)') == "":
                    input_df.at[i, '成分名 (英)'] = found_eng
        
        progress_bar.progress((i + 1) / total)
        
    return input_df
