import streamlit as st
import pandas as pd
import requests
import re
import uuid
import time

# --- 1. 設定區 ---
st.set_page_config(page_title="Azure 翻譯 - 401 故障排除版", layout="wide")

# 【請從 Azure 控制台重新複製】
AZURE_KEY = "您的_32位元金鑰" 
AZURE_LOCATION = "eastasia" # 必須是小寫英文，例如 global, eastasia, westus
AZURE_ENDPOINT = "https://api.cognitive.microsofttranslator.com"

# --- 2. 翻譯邏輯 (加入 401 錯誤診斷) ---
def translate_final_check(text):
    if not text or pd.isna(text): return ""
    
    # 清理舊標籤並清洗文本
    clean_text = str(text).replace('[HTTP 401]', '').replace('[連線失敗]', '').replace('\n', ' ').strip()
    clean_text = re.sub(r'\s+', ' ', clean_text)
    if not clean_text or len(clean_text) < 2: return clean_text

    # 強制清洗 Headers 確保無非 ASCII 字元
    try:
        safe_key = "".join(c for c in str(AZURE_KEY) if c.isalnum()).strip()
        safe_location = "".join(c for c in str(AZURE_LOCATION) if c.islower() or c.isalpha()).strip()
        
        headers = {
            'Ocp-Apim-Subscription-Key': safe_key,
            'Ocp-Apim-Subscription-Region': safe_location,
            'Content-type': 'application/json',
            'X-ClientTraceId': str(uuid.uuid4())
        }
    except Exception as e:
        return f"[Header格式錯誤]"

    # 準備請求網址
    target_url = f"{AZURE_ENDPOINT.strip().rstrip('/')}/translate?api-version=3.0&from=ja&to=zh-Hant"
    
    # 針對長文進行分段
    segments = re.split(r'(?<=。)|(?=（|\()', clean_text)
    segments = [s.strip() for s in segments if s.strip()]

    translated_parts = []
    for seg in segments:
        try:
            r = requests.post(target_url, headers=headers, json=[{'text': seg}], timeout=25)
            if r.status_code == 200:
                translated_parts.append(r.json()[0]['translations'][0]['text'])
            elif r.status_code == 401:
                return "[401 授權失敗: 請檢查金鑰是否正確]"
            elif r.status_code == 403:
                return f"[403 區域不符: 目前設定 {safe_location}，請檢查 Azure Portal]"
            else:
                translated_parts.append(f"[HTTP {r.status_code}]")
        except Exception:
            translated_parts.append("[連線超時]")
        time.sleep(0.1)
        
    return " ".join(translated_parts)

# --- 3. UI 介面 ---
st.title("🛡️ Azure 翻譯最終修復測試 (前五項)")

# 快速診斷
if len(AZURE_KEY.strip()) != 32:
    st.warning(f"⚠️ 警告：您的金鑰長度為 {len(AZURE_KEY.strip())} 位，標準金鑰應為 32 位英數字。請重新檢查。")

uploaded_file = st.file_uploader("上傳您最新的 CSV", type="csv")

if uploaded_file:
    df_raw = pd.read_csv(uploaded_file).head(5)
    
    if st.button("🚀 開始測試前五項"):
        results = []
        status = st.empty()
        
        for i, row in df_raw.iterrows():
            status.write(f"正在處理 ({i+1}/5): {row['成分名 (日)']}...")
            
            # 優先抓取日文原文
            # 如果「翻譯理由」裡面已經滿是 [HTTP 401]，我們需要抓原始的理由欄位
            # 假設原始日文欄位可能在「選定理由摘要」
            original_val = row.get('選定理由摘要') or row.get('翻譯理由')
            
            translated_val = translate_final_check(original_val)
            results.append({
                "成分名": row['成分名 (日)'], 
                "翻譯結果": translated_val
            })
        
        st.divider()
        st.subheader("處理結果")
        res_df = pd.DataFrame(results)
        st.table(res_df)
        
        csv = res_df.to_csv(index=False, encoding="utf-8-sig")
        st.download_button("📥 下載測試結果", csv, "final_test_result.csv")
