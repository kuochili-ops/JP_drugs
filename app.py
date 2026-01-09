import streamlit as st
import pandas as pd
import requests
import re
import uuid

# --- 1. 初始化與 Azure 設定 ---
st.set_page_config(page_title="藥品清單全效處理器", layout="wide")

# 【重要】請務必填寫正確的 Azure 資訊
AZURE_KEY = "您的_AZURE_SUBSCRIPTION_KEY"
AZURE_LOCATION = "您的_區域" # 例如: eastasia
AZURE_ENDPOINT = "https://api.cognitive.microsofttranslator.com"

# --- 2. 強化版 KEGG 字典模組 ---
@st.cache_data(ttl=3600)
def get_kegg_dict():
    url = "https://rest.kegg.jp/list/drug_ja/"
    kegg_map = {}
    try:
        res = requests.get(url, timeout=20)
        if res.status_code == 200:
            for line in res.text.strip().split('\n'):
                parts = line.split('\t')
                if len(parts) >= 2:
                    k_id = parts[0].replace('dr:', '').strip()
                    full_txt = parts[1]
                    if ';' in full_txt:
                        en_raw = full_txt.split(';')[1].strip()
                        en_name = re.sub(r'[\(\（].*?[\)\）]', '', en_raw).strip()
                        jp_raw = full_text = full_txt.split(';')[0].strip()
                        jp_name = re.sub(r'[\(\（].*?[\)\）]', '', jp_raw).strip()
                        kegg_map[jp_name] = {"id": k_id, "en": en_name}
        return kegg_map
    except:
        return {}

# --- 3. 專為「選定理由」設計的翻譯函數 ---
def translate_reason_azure(text):
    if not text or pd.isna(text) or str(text).strip() == "":
        return ""

    # A. 文本清洗：移除所有換行符，這是翻譯成功的關鍵
    clean_text = str(text).replace('\n', ' ').replace('\r', ' ').strip()
    clean_text = re.sub(r'\s+', ' ', clean_text) # 壓縮空格

    # B. Azure API 請求
    headers = {
        'Ocp-Apim-Subscription-Key': AZURE_KEY,
        'Ocp-Apim-Subscription-Region': AZURE_LOCATION,
        'Content-type': 'application/json',
        'X-ClientTraceId': str(uuid.uuid4())
    }
    params = {'api-version': '3.0', 'from': 'ja', 'to': 'zh-Hant'}
    body = [{'text': clean_text}]

    try:
        r = requests.post(f"{AZURE_ENDPOINT}/translate", params=params, headers=headers, json=body, timeout=15)
        if r.status_code == 200:
            return r.json()[0]['translations'][0]['text']
        else:
            return f"[API錯誤 {r.status_code}] {clean_text[:50]}..."
    except Exception as e:
        return f"[連線失敗] {clean_text[:50]}..."

# --- 4. UI 介面 ---
st.title("💊 藥品清單從頭處理 (KEGG ID + 長文本翻譯)")

k_dict = get_kegg_dict()

uploaded_file = st.file_uploader("上傳您導出的 CSV", type="csv")

if uploaded_file:
    df = pd.read_csv(uploaded_file)
    
    # 預設欄位初始化
    if 'KEGG_ID' not in df.columns: df['KEGG_ID'] = "N/A"
    if '成分名 (英)' not in df.columns: df['成分名 (英)'] = "N/A"
    if '翻譯理由' not in df.columns: df['翻譯理由'] = ""

    if st.button("🚀 開始執行全自動處理"):
        progress_bar = st.progress(0)
        status = st.empty()
        
        for i, row in df.iterrows():
            # 1. KEGG 比對
            jp_name_raw = str(row['成分名 (日)']).strip()
            clean_jp = re.sub(r'[（\(].*?[）\)]', '', jp_name_raw).strip()
            
            if clean_jp in k_dict:
                df.at[i, 'KEGG_ID'] = k_dict[clean_jp]['id']
                df.at[i, '成分名 (英)'] = k_dict[clean_jp]['en']
            
            # 2. 翻譯「選定理由摘要」
            reason_jp = row.get('選定理由摘要', '')
            df.at[i, '翻譯理由'] = translate_reason_azure(reason_jp)
            
            # 3. 處理其他固定欄位 (藥效分類)
            if '藥效分類' in df.columns:
                df.at[i, '藥效分類'] = str(df.at[i, '藥效分類']).replace('血液凝固阻止剤', '抗凝血劑').replace('全身麻酔剤', '全身麻醉劑')

            # 更新進度
            progress_bar.progress((i + 1) / len(df))
            status.text(f"正在處理第 {i+1} 筆: {clean_jp}")

        status.success("✅ 處理完成！")
        
        # 顯示關鍵結果
        st.dataframe(df[['區分', '成分名 (日)', '成分名 (英)', 'KEGG_ID', '翻譯理由']], use_container_width=True)

        # 下載按鈕
        csv_final = df.to_csv(index=False, encoding="utf-8-sig")
        st.download_button("📥 下載最終處理 CSV", csv_final, "final_med_report.csv", "text/csv")
