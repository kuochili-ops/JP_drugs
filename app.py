import streamlit as st
import pandas as pd
import requests
import re
import uuid
import time

# --- 1. 核心配置 ---
st.set_page_config(page_title="Azure 翻譯除錯工具", layout="wide")

# 【請務必再次確認這三項】
AZURE_KEY = "您的_32位元金鑰"
AZURE_ENDPOINT = "https://api.cognitive.microsofttranslator.com"
AZURE_LOCATION = "eastasia" # 請確認您的 Azure 資源是在哪個區域，例如 global 或 eastasia

# --- 2. 強化翻譯函數 ---
def translate_debug(text):
    if not text or pd.isna(text): return ""
    
    # 清理：移除舊有的錯誤標記 [連線失敗]
    clean_text = str(text).replace('[連線失敗]', '').replace('\n', ' ').strip()
    # 壓縮空白
    clean_text = re.sub(r'\s+', ' ', clean_text)
    
    if not clean_text: return ""

    # 按學會括號分割段落
    segments = re.split(r'(?=（|\()', clean_text)
    segments = [s.strip() for s in segments if s.strip()]

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
            # 測試階段：使用 30 秒超時
            res = requests.post(
                f"{AZURE_ENDPOINT}/translate?api-version=3.0&from=ja&to=zh-Hant",
                headers=headers,
                json=body,
                timeout=30
            )
            if res.status_code == 200:
                translated_parts.append(res.json()[0]['translations'][0]['text'])
            else:
                translated_parts.append(f"[錯誤{res.status_code}]")
        except Exception as e:
            translated_parts.append(f"[連線錯誤]")
        time.sleep(0.3) # 稍微停頓
        
    return " ".join(translated_parts)

# --- 3. UI 邏輯 ---
st.title("🧪 Azure 翻譯極限除錯 (前五項測試)")

uploaded_file = st.file_uploader("上傳您的 export.csv", type="csv")

if uploaded_file:
    # 讀取檔案
    raw_df = pd.read_csv(uploaded_file)
    # 強制只測前五筆
    test_df = raw_df.head(5).copy()
    
    st.write("🔍 待測試項目：", test_df[['成分名 (日)']])

    if st.button("🚀 開始測試"):
        # 建立一個空容器顯示實時進度
        progress_area = st.empty()
        
        for i, row in test_df.iterrows():
            with progress_area.container():
                st.write(f"正在翻譯第 {i+1} 筆：{row['成分名 (日)']}...")
            
            # 抓取原有的理由欄位（可能是「翻譯理由」或「選定理由摘要」）
            original_val = row.get('翻譯理由') or row.get('選定理由摘要')
            
            # 執行翻譯
            test_df.at[i, '已修正翻譯'] = translate_debug(original_val)
            
        st.success("✅ 測試完成")
        
        # 顯示結果
        st.dataframe(test_df[['成分名 (日)', '已修正翻譯']], use_container_width=True)
        
        # 下載
        csv = test_df.to_csv(index=False, encoding="utf-8-sig")
        st.download_button("📥 下載這五項的結果", csv, "test_fix.csv")
