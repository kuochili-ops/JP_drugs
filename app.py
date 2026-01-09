import streamlit as st
import pandas as pd
import requests
import re
import uuid
import time

# --- 1. 頁面配置 ---
st.set_page_config(page_title="藥品清單補完與翻譯系統", layout="wide")

# 【設定區】請填入您的正確金鑰
AZURE_KEY = "您的_AZURE_SUBSCRIPTION_KEY"
AZURE_ENDPOINT = "https://api.cognitive.microsofttranslator.com"
AZURE_LOCATION = "您的_區域" # 例如: eastasia

# --- 2. KEGG 字典模組 ---
@st.cache_data(ttl=3600)
def get_kegg_master_dict():
    url = "https://rest.kegg.jp/list/drug_ja/"
    kegg_map = {}
    try:
        response = requests.get(url, timeout=20)
        if response.status_code == 200:
            for line in response.text.strip().split('\n'):
                parts = line.split('\t')
                if len(parts) >= 2:
                    k_id = parts[0].replace('dr:', '').strip()
                    full_text = parts[1]
                    if ';' in full_text:
                        en_part = full_text.split(';')[1].strip()
                        en_name = re.sub(r'[\(\（].*?[\)\）]', '', en_part).strip()
                        jp_part = full_text.split(';')[0].strip()
                        jp_name = re.sub(r'[\(\（].*?[\)\）]', '', jp_part).strip()
                        kegg_map[jp_name] = {"id": k_id, "en": en_name}
        return kegg_map
    except Exception as e:
        st.error(f"KEGG 下載失敗: {e}")
        return {}

# --- 3. 強化版翻譯函數：解決超時問題 ---
def translate_via_azure(text):
    if not text or pd.isna(text) or str(text).strip() == "" or text == "N/A":
        return ""

    # 清洗換行符號，這是防止 API 誤判的關鍵
    clean_text = str(text).replace('\n', ' ').replace('\r', ' ').strip()
    clean_text = re.sub(r'\s+', ' ', clean_text)

    # 如果文本太長（超過 1000 字），截斷或分段處理（此處先採預防性截斷，或直接增加超時）
    if len(clean_text) > 4000:
        clean_text = clean_text[:4000]

    path = '/translate'
    url = AZURE_ENDPOINT + path
    headers = {
        'Ocp-Apim-Subscription-Key': AZURE_KEY,
        'Ocp-Apim-Subscription-Region': AZURE_LOCATION,
        'Content-type': 'application/json',
        'X-ClientTraceId': str(uuid.uuid4())
    }
    params = {'api-version': '3.0', 'from': 'ja', 'to': 'zh-Hant'}
    body = [{'text': clean_text}]

    # 嘗試多次翻譯，防止偶發性連線中斷
    for attempt in range(2): 
        try:
            # 將 timeout 增加到 45 秒，處理超長文本
            r = requests.post(url, params=params, headers=headers, json=body, timeout=45)
            if r.status_code == 200:
                return r.json()[0]['translations'][0]['text']
            elif r.status_code == 429: # Too Many Requests
                time.sleep(1) # 等待一秒重試
                continue
            else:
                return f"[API錯誤 {r.status_code}]"
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError):
            if attempt == 0:
                time.sleep(2)
                continue
            return "[翻譯超時/連線失敗]"
    return "[翻譯失敗]"

# --- 4. Streamlit UI ---
st.title("💊 藥品清單全自動處理 (從頭到尾版)")

kegg_lookup = get_kegg_master_dict()

uploaded_file = st.file_uploader("1. 上傳導出的 CSV 檔案", type="csv")

if uploaded_file:
    df = pd.read_csv(uploaded_file)
    
    # 檢查是否有必要的欄位，若沒有則根據您的導出檔重新定位
    target_col = '選定理由摘要' if '選定理由摘要' in df.columns else None
    
    if st.button("2. 開始執行 (對照 ID + 完整翻譯理由)"):
        # 初始化欄位
        df['KEGG_ID'] = "Searching..."
        df['成分名 (英)'] = "N/A"
        df['翻譯理由'] = ""

        progress_bar = st.progress(0)
        status_text = st.empty()
        
        total_rows = len(df)
        
        for i, row in df.iterrows():
            # A. KEGG 對照
            raw_jp = str(row['成分名 (日)']).strip()
            clean_jp = re.sub(r'[（\(].*?[）\)]', '', raw_jp).strip()
            
            if clean_jp in kegg_lookup:
                df.at[i, 'KEGG_ID'] = kegg_lookup[clean_jp]['id']
                df.at[i, '成分名 (英)'] = kegg_lookup[clean_jp]['en']
            else:
                df.at[i, 'KEGG_ID'] = "Not Found"

            # B. 選定理由翻譯
            if target_col:
                reason_jp = row[target_col]
                df.at[i, '翻譯理由'] = translate_via_azure(reason_jp)
            
            # 每 10 筆更新一次進度，避免畫面閃爍
            if i % 10 == 0 or i == total_rows - 1:
                progress_bar.progress((i + 1) / total_rows)
                status_text.text(f"進度: {i+1}/{total_rows} - 正在處理: {clean_jp}")

        status_text.success("✅ 任務完成！")
        
        # 顯示結果 (顯示主要欄位)
        show_cols = ['區分', '成分名 (日)', '成分名 (英)', 'KEGG_ID', '翻譯理由']
        existing_show = [c for c in show_cols if c in df.columns]
        st.dataframe(df[existing_show], use_container_width=True)

        # 提供下載
        csv_data = df.to_csv(index=False, encoding="utf-8-sig")
        st.download_button("📥 下載最終完成版 CSV", csv_data, "final_data.csv", "text/csv")
