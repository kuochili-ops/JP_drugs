import streamlit as st
import pandas as pd
import requests
import re
import uuid
import time

# --- 1. 配置與診斷 ---
st.set_page_config(page_title="Azure 翻譯連線診斷", layout="wide")

# 【請再次檢查這裡】
AZURE_KEY = "您的_32位元金鑰"
# 注意：Endpoint 通常只需要到 .com，後面的 path 程式會補
AZURE_ENDPOINT = "https://api.cognitive.microsofttranslator.com"
AZURE_LOCATION = "eastasia" 

# --- 2. 診斷型翻譯函數 ---
def translate_diagnostic(text):
    if not text or pd.isna(text): return ""
    
    # 清理舊標籤
    clean_text = str(text).replace('[連線錯誤]', '').replace('[超時]', '').replace('\n', ' ').strip()
    clean_text = re.sub(r'\s+', ' ', clean_text)
    if not clean_text: return ""

    # 更細緻的切割（按句號或括號）
    segments = re.split(r'(?<=。)|(?=（|\()', clean_text)
    segments = [s.strip() for s in segments if s.strip()]

    # 確保 Endpoint 格式正確
    base_url = AZURE_ENDPOINT.strip().rstrip('/')
    target_url = f"{base_url}/translate?api-version=3.0&from=ja&to=zh-Hant"

    headers = {
        'Ocp-Apim-Subscription-Key': str(AZURE_KEY).strip(),
        'Ocp-Apim-Subscription-Region': str(AZURE_LOCATION).strip(),
        'Content-type': 'application/json',
        'X-ClientTraceId': str(uuid.uuid4())
    }
    
    translated_parts = []
    
    for seg in segments:
        body = [{'text': seg}]
        try:
            # 增加 verify=True 確保 SSL 安全連線
            r = requests.post(target_url, headers=headers, json=body, timeout=20)
            
            if r.status_code == 200:
                translated_parts.append(r.json()[0]['translations'][0]['text'])
            else:
                # 這裡會顯示具體的 HTTP 狀態碼 (如 401, 403, 404)
                translated_parts.append(f"[HTTP {r.status_code}]")
        except requests.exceptions.RequestException as e:
            # 這裡會顯示底層連線錯誤的原因
            translated_parts.append(f"[連線異常: {type(e).__name__}]")
        
    return " ".join(translated_parts)

# --- 3. UI 介面 ---
st.title("🛡️ Azure Translator 深度診斷測試")
st.info(f"目前設定區域: **{AZURE_LOCATION}** | 端點: **{AZURE_ENDPOINT}**")

uploaded_file = st.file_uploader("上傳 export.csv", type="csv")

if uploaded_file:
    df_raw = pd.read_csv(uploaded_file).head(5)
    
    if st.button("🔍 開始診斷翻譯"):
        results = []
        for i, row in df_raw.iterrows():
            st.write(f"正在測試: {row['成分名 (日)']}...")
            original_val = row.get('翻譯理由') or row.get('選定理由摘要')
            
            translated_val = translate_diagnostic(original_val)
            results.append({"成分名": row['成分名 (日)'], "翻譯結果": translated_val})
        
        st.divider()
        st.subheader("診斷結果")
        st.table(results)
        
        # 故障排除指引
        for res in results:
            if "[HTTP 401]" in res['翻譯結果']:
                st.error("❌ **錯誤 401**: 金鑰 (Key) 無效，請檢查是否複製完全。")
                break
            if "[HTTP 403]" in res['翻譯結果']:
                st.error("❌ **錯誤 403**: 區域 (Location) 設定錯誤，請在 Azure Portal 確認 Region。")
                break
            if "[連線異常" in res['翻譯結果']:
                st.warning("⚠️ **連線異常**: 可能是防火牆攔截或 Endpoint 網址錯誤。")
                break
