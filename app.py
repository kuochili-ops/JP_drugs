import streamlit as st
import pandas as pd
import requests
import re
import uuid
import time

# --- 1. 基本配置 ---
st.set_page_config(page_title="藥品清單翻譯補完系統", layout="wide")

# 【務必檢查】請確保這裡的英文字母完全正確，不要有空格
AZURE_KEY = "您的_32位元金鑰"
AZURE_ENDPOINT = "https://api.cognitive.microsofttranslator.com"
AZURE_LOCATION = "eastasia" # 必須是英文小寫，例如 eastasia, southeastasia 或 global

# --- 2. KEGG 字典模組 (確保 ID 與 英文名正確) ---
@st.cache_data(ttl=3600)
def get_kegg_master_dict():
    url = "https://rest.kegg.jp/list/drug_ja/"
    kegg_map = {}
    try:
        response = requests.get(url, timeout=30)
        if response.status_code == 200:
            for line in response.text.strip().split('\n'):
                parts = line.split('\t')
                if len(parts) >= 2:
                    k_id = parts[0].replace('dr:', 'dr_ja:').strip()
                    full_text = parts[1]
                    if ';' in full_text:
                        en_part = full_text.split(';')[1].strip()
                        en_name = re.sub(r'[\(\（].*?[\)\）]', '', en_part).strip()
                        jp_part = full_text.split(';')[0].strip()
                        jp_name = re.sub(r'[\(\（].*?[\)\）]', '', jp_part).strip()
                        kegg_map[jp_name] = {"id": k_id, "en": en_name}
        return kegg_map
    except Exception:
        return {}

# --- 3. 強力分段翻譯函數 (解決超時核心) ---
def translate_via_azure_safe(text):
    if not text or pd.isna(text) or str(text).strip() == "":
        return ""

    # 清洗文本：移除換行並壓縮空格
    clean_text = str(text).replace('\n', ' ').replace('\r', ' ').strip()
    clean_text = re.sub(r'\s+', ' ', clean_text)

    # 【策略】如果長度超過 500 字，進行拆分翻譯以防 API 超時
    chunk_size = 500
    chunks = [clean_text[i:i+chunk_size] for i in range(0, len(clean_text), chunk_size)]
    
    headers = {
        'Ocp-Apim-Subscription-Key': str(AZURE_KEY).strip(),
        'Ocp-Apim-Subscription-Region': str(AZURE_LOCATION).strip(),
        'Content-type': 'application/json',
        'X-ClientTraceId': str(uuid.uuid4())
    }
    params = {'api-version': '3.0', 'from': 'ja', 'to': 'zh-Hant'}
    
    translated_result = []
    
    for chunk in chunks:
        body = [{'text': chunk}]
        try:
            # 將 timeout 增加到 60 秒，確保長文本有足夠時間運算
            r = requests.post(f"{AZURE_ENDPOINT}/translate", params=params, headers=headers, json=body, timeout=60)
            if r.status_code == 200:
                translated_result.append(r.json()[0]['translations'][0]['text'])
            else:
                translated_result.append(f"[API錯誤 {r.status_code}]")
        except Exception:
            translated_result.append("[翻譯超時/連線失敗]")
        
        # 增加短暫延遲，避免請求過快
        time.sleep(0.5)

    return "".join(translated_result)

# --- 4. Streamlit UI 流程 ---
st.title("💊 醫藥資料全自動處理系統 (分段處理版)")

kegg_lookup = get_kegg_master_dict()

uploaded_file = st.file_uploader("1. 上傳 CSV 檔案", type="csv")

if uploaded_file:
    df = pd.read_csv(uploaded_file)
    
    if st.button("2. 開始全自動執行 (ID 比對 + 分段翻譯理由)"):
        # 確保目標欄位初始化
        if 'KEGG_ID' not in df.columns: df['KEGG_ID'] = ""
        if '成分名 (英)' not in df.columns: df['成分名 (英)'] = ""
        if '翻譯理由' not in df.columns: df['翻譯理由'] = ""

        progress_bar = st.progress(0)
        status_text = st.empty()
        total = len(df)

        for i, row in df.iterrows():
            # A. KEGG ID 與 英文名對照
            raw_jp = str(row['成分名 (日)']).strip()
            clean_jp = re.sub(r'[（\(].*?[）\)]', '', raw_jp).strip()
            
            if clean_jp in kegg_lookup:
                df.at[i, 'KEGG_ID'] = kegg_lookup[clean_jp]['id']
                df.at[i, '成分名 (英)'] = kegg_lookup[clean_jp]['en']
            else:
                df.at[i, 'KEGG_ID'] = "Not Found"

            # B. 採用理由翻譯 (分段處理)
            # 自動偵測欄位：若無「選定理由摘要」則抓最後一欄
            reason_col = '選定理由摘要' if '選定理由摘要' in df.columns else df.columns[-1]
            df.at[i, '翻譯理由'] = translate_via_azure_safe(row[reason_col])

            # C. 更新進度
            if i % 5 == 0 or i == total - 1:
                progress_bar.progress((i + 1) / total)
                status_text.text(f"正在處理 ({i+1}/{total}): {clean_jp}")

        status_text.success("✅ 全部處理完成！")
        st.dataframe(df, use_container_width=True)

        # 下載按鈕 (使用 sig 確保 Excel 開啟不亂碼)
        csv_out = df.to_csv(index=False, encoding="utf-8-sig")
        st.download_button("📥 下載最終完成版 CSV", csv_out, "final_data.csv", "text/csv")
