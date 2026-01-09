import streamlit as st
import pandas as pd
import requests
import re
import io

# --- 1. 從 KEGG 官網下載完整的日文對照字典 ---
@st.cache_data
def get_kegg_master_dict():
    url = "https://rest.kegg.jp/list/drug_ja/"
    try:
        response = requests.get(url, timeout=10)
        kegg_map = {}
        if response.status_code == 200:
            for line in response.text.strip().split('\n'):
                parts = line.split('\t')
                if len(parts) >= 2:
                    k_id = parts[0].replace('dr:', '')
                    # 格式通常為: 日文名 (英文名); 其他名
                    full_name = parts[1]
                    # 使用正則提取括號內的英文名
                    match = re.search(r'^(.+?)\s*\((.+?)\)', full_name)
                    if match:
                        jp_name = match.group(1).strip()
                        en_name = match.group(2).strip()
                        kegg_map[jp_name] = {"id": k_id, "en": en_name}
        return kegg_map
    except Exception as e:
        st.error(f"無法讀取 KEGG 字典: {e}")
        return {}

# --- 2. 醫學術語翻譯對照表 (補充 Azure 漏掉的部分) ---
TERM_MAP = {
    "他に分類されない代謝性医薬品": "其他類別代謝藥物",
    "血液凝固阻止剤": "抗凝血劑",
    "薬効分類名": "藥效分類名稱",
    "選定理由概要": "選定理由摘要",
    "継続成分": "持續成分",
    "新規成分": "新成分",
    "内": "內服", "注": "注射", "外": "外用"
}

# --- 3. Streamlit 介面 ---
st.set_page_config(page_title="藥品清單處理器", layout="wide")
st.title("💊 藥品清單自動化處理 (KEGG + 翻譯)")

# 預先載入 KEGG 字典
kegg_dict = get_kegg_master_dict()

uploaded_file = st.file_uploader("上傳您導出的 CSV 檔案", type="csv")

if uploaded_file:
    df = pd.read_csv(uploaded_file)
    
    if st.button("開始逐項比對與翻譯"):
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        # 逐行處理
        for i, row in df.iterrows():
            # A. 處理成分名並比對 KEGG
            raw_jp_name = str(row['成分名 (日)']).replace('\n', '').strip()
            # 移除括號內容進行精準比對 (如: 水和物)
            clean_jp_name = re.sub(r'[（\(].*?[）\)]', '', raw_jp_name)
            
            if clean_jp_name in kegg_dict:
                df.at[i, 'KEGG_ID'] = kegg_dict[clean_jp_name]['id']
                df.at[i, '成分名 (英)'] = kegg_dict[clean_jp_name]['en']
            
            # B. 處理其餘日文翻譯
            for col in df.columns:
                val = str(df.at[i, col])
                for jp, tw in TERM_MAP.items():
                    val = val.replace(jp, tw)
                df.at[i, col] = val
            
            progress_bar.progress((i + 1) / len(df))
            status_text.text(f"正在處理: {raw_jp_name}")

        status_text.success("處理完畢！")
        st.dataframe(df)

        # 下載按鈕
        csv_data = df.to_csv(index=False, encoding="utf-8-sig")
        st.download_button("下載修正後的 CSV", data=csv_data, file_name="fixed_drugs.csv", mime="text/csv")
