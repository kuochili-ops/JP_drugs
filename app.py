import streamlit as st
import pandas as pd
import requests
import re
import uuid
import time

# --- 1. 配置 ---
st.set_page_config(page_title="Azure 翻譯診斷版", layout="wide")

# 【請在此處填寫】務必確保這裡只有半形英數字
AZURE_KEY = "您的_32位元金鑰" 
AZURE_ENDPOINT = "https://api.cognitive.microsofttranslator.com"
AZURE_LOCATION = "eastasia" # 必須是英文小寫，例如 global, eastasia, southeastasia

# --- 2. 翻譯函數 ---
def translate_diagnostic(text):
    if not text or pd.isna(text): return ""
    
    # 1. 清理 Body 內容
    clean_text = str(text).replace('[連線錯誤]', '').replace('[超時]', '').replace('\n', ' ').strip()
    clean_text = re.sub(r'\s+', ' ', clean_text)
    if not clean_text: return ""

    # 2. 準備 Headers (關鍵修正點：使用 .encode('ascii', 'ignore') 確保無非法字元)
    try:
        # 強制移除 Key 和 Location 中任何可能導致 latin-1 錯誤的非 ASCII 字元
        safe_key = str(AZURE_KEY).encode('ascii', 'ignore').decode('ascii').strip()
        safe_location = str(AZURE_LOCATION).encode('ascii', 'ignore').decode('ascii').strip()
        
        headers = {
            'Ocp-Apim-Subscription-Key': safe_key,
            'Ocp-Apim-Subscription-Region': safe_location,
            'Content-type': 'application/json',
            'X-ClientTraceId': str(uuid.uuid4())
        }
    except Exception as e:
        return f"[Header 設定錯誤: {str(e)}]"

    # 3. 準備 URL 與分段
    base_url = AZURE_ENDPOINT.strip().rstrip('/')
    target_url = f"{base_url}/translate?api-version=3.0&from=ja&to=zh-Hant"
    segments = re.split(r'(?<=。)|(?=（|\()', clean_text)
    segments = [s.strip() for s in segments if s.strip()]

    translated_parts = []
    for seg in segments:
        try:
            r = requests.post(target_url, headers=headers, json=[{'text': seg}], timeout=25)
            if r.status_code == 200:
                translated_parts.append(r.json()[0]['translations'][0]['text'])
            else:
                translated_parts.append(f"[HTTP {r.status_code}]")
        except Exception as e:
            translated_parts.append(f"[連線異常: {type(e).__name__}]")
        time.sleep(0.2)
        
    return " ".join(translated_parts)

# --- 3. UI 介面 ---
st.title("🛡️ Azure 翻譯最終修復測試")

uploaded_file = st.file_uploader("上傳您原本的 CSV", type="csv")

if uploaded_file:
    # 讀取並只取前五筆
    df_raw = pd.read_csv(uploaded_file).head(5)
    
    if st.button("🚀 執行前五項翻譯測試"):
        results = []
        for i, row in df_raw.iterrows():
            st.write(f"正在處理: {row['成分名 (日)']}...")
            
            # 抓取理由欄位 (檢查多個可能的名稱)
            original_val = row.get('選定理由摘要') or row.get('翻譯理由') or ""
            
            translated_val = translate_diagnostic(original_val)
            results.append({
                "成分名": row['成分名 (日)'], 
                "處理結果": translated_val
            })
        
        st.divider()
        st.subheader("測試結果回報")
        st.table(results)
        
        # 下載測試後的 CSV
        test_out = pd.DataFrame(results)
        csv = test_out.to_csv(index=False, encoding="utf-8-sig")
        st.download_button("📥 下載此五項測試結果", csv, "debug_test.csv")
