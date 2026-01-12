import streamlit as st
import pandas as pd
import requests
import re
import uuid
import time

# --- 1. 配置區 ---
st.set_page_config(page_title="藥品清單翻譯系統 - 穩定版", layout="wide")

# 已更新為您提供的新 Key
AZURE_KEY = "9JDF24qrsW8rXiYmChS17yEPyNRI96nNXXqEKn5CyI6ql6iYcTOFJQQJ99BLAC3pKaRXJ3w3AAAbACOGVYVU"
AZURE_LOCATION = "eastasia"  # 請根據您的 Azure 面板確認此區域 (例如 eastasia 或 global)
AZURE_ENDPOINT = "https://api.cognitive.microsofttranslator.com"

# --- 2. 翻譯核心邏輯 (具備自動清理與分段功能) ---
def translate_robust(text):
    if not text or pd.isna(text): return ""
    
    # 【關鍵清理】移除上週產生的所有錯誤標籤，找回原始日文
    clean_text = str(text)
    error_patterns = [
        r'\[連線失敗\]', r'\[超時\]', r'\[HTTP \d+\]', 
        r'\[連線異常.*?\]', r'\[401.*?\]', r'\[錯誤.*?\]'
    ]
    for pattern in error_patterns:
        clean_text = re.sub(pattern, '', clean_text)
    
    clean_text = clean_text.replace('\n', ' ').strip()
    clean_text = re.sub(r'\s+', ' ', clean_text)
    
    if not clean_text or len(clean_text) < 2: return clean_text

    # 準備 Headers
    headers = {
        'Ocp-Apim-Subscription-Key': AZURE_KEY.strip(),
        'Ocp-Apim-Subscription-Region': AZURE_LOCATION.strip(),
        'Content-type': 'application/json',
        'X-ClientTraceId': str(uuid.uuid4())
    }
    target_url = f"{AZURE_ENDPOINT.strip().rstrip('/')}/translate?api-version=3.0&from=ja&to=zh-Hant"

    # 長文分段處理 (按句號或學會括號切分)
    segments = re.split(r'(?<=。)|(?=（|\()', clean_text)
    segments = [s.strip() for s in segments if s.strip()]

    translated_parts = []
    for seg in segments:
        try:
            r = requests.post(target_url, headers=headers, json=[{'text': seg}], timeout=30)
            if r.status_code == 200:
                translated_parts.append(r.json()[0]['translations'][0]['text'])
            else:
                translated_parts.append(f"[API錯誤: {r.status_code}]")
        except:
            translated_parts.append("[傳輸超時]")
        time.sleep(0.1) # 保護頻率限制
        
    return " ".join(translated_parts)

# --- 3. UI 介面 ---
st.title("💊 藥品資料翻譯補完工具")
st.info("💡 系統會自動移除舊檔案中的錯誤標記，重新翻譯日文內容。")

uploaded_file = st.file_uploader("上傳檔案 (例如 2026-01-09T07-14_export.csv)", type="csv")

if uploaded_file:
    df = pd.read_csv(uploaded_file)
    st.write(f"✅ 成功讀取 {len(df)} 筆藥品資料。")

    if st.button("🚀 開始執行全檔案翻譯"):
        # 初始化或覆蓋翻譯欄位
        if '翻譯理由' not in df.columns:
            df['翻譯理由'] = ""
        
        progress_bar = st.progress(0)
        status_msg = st.empty()
        
        for i, row in df.iterrows():
            # 優先從「翻譯理由」或「選定理由摘要」抓取原始文字
            input_text = row.get('翻譯理由') or row.get('選定理由摘要') or ""
            df.at[i, '翻譯理由'] = translate_robust(input_text)
            
            # 每處理 5 筆更新一次進度條
            if i % 5 == 0 or i == len(df) - 1:
                progress_bar.progress((i + 1) / len(df))
                status_msg.text(f"正在處理 ({i+1}/{len(df)}): {row.get('成分名 (日)', '處理中')}")

        st.success("🎉 全部翻譯任務完成！")
        st.dataframe(df[['成分名 (日)', '翻譯理由']], use_container_width=True)
        
        # 下載按鈕
        csv_out = df.to_csv(index=False, encoding="utf-8-sig")
        st.download_button("📥 下載最終處理 CSV", csv_out, "translated_med_list.csv", "text/csv")
