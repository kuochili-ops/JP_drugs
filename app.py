import streamlit as st
import pandas as pd
import requests
import re
import uuid
import time

# --- 1. 基本配置 ---
st.set_page_config(page_title="藥品翻譯測試版 (前五項)", layout="wide")

# 【請檢查金鑰】
AZURE_KEY = "您的_32位元金鑰"
AZURE_ENDPOINT = "https://api.cognitive.microsofttranslator.com"
AZURE_LOCATION = "eastasia" # 必須是英文小寫

# --- 2. 核心翻譯函數 (強化分段與清洗) ---
def translate_via_azure_test(text):
    if not text or pd.isna(text) or str(text).strip() == "":
        return ""

    # 強力清洗換行符，避免 API 解析錯誤
    clean_text = str(text).replace('\n', ' ').replace('\r', ' ').strip()
    
    # 按「學會括號」切分段落，這能把長文拆成多個小請求，徹底解決超時
    segments = re.split(r'(?=（|\()', clean_text)
    segments = [s for s in segments if s.strip()]

    headers = {
        'Ocp-Apim-Subscription-Key': str(AZURE_KEY).strip(),
        'Ocp-Apim-Subscription-Region': str(AZURE_LOCATION).strip(),
        'Content-type': 'application/json',
        'X-ClientTraceId': str(uuid.uuid4())
    }
    params = {'api-version': '3.0', 'from': 'ja', 'to': 'zh-Hant'}
    
    translated_result = []
    
    for seg in segments:
        body = [{'text': seg}]
        try:
            # 針對每一小段給予 30 秒等候
            r = requests.post(f"{AZURE_ENDPOINT}/translate", params=params, headers=headers, json=body, timeout=30)
            if r.status_code == 200:
                translated_result.append(r.json()[0]['translations'][0]['text'])
            else:
                translated_result.append(f"[錯誤{r.status_code}]")
        except Exception:
            translated_result.append("[超時]")
        time.sleep(0.2) # 保護頻率

    return " ".join(translated_result)

# --- 3. UI 流程 ---
st.title("🧪 藥品清單翻譯測試 (僅執行前五項)")

uploaded_file = st.file_uploader("上傳您的 CSV 檔案", type="csv")

if uploaded_file:
    # 讀取完整檔案
    full_df = pd.read_csv(uploaded_file)
    
    # 【測試核心】僅取前五項
    df = full_df.head(5).copy()
    
    st.write("📋 偵測到檔案，將對以下前五項進行深度翻譯測試：")
    st.table(df[['成分名 (日)', 'KEGG_ID']])

    if st.button("🚀 開始測試前五項翻譯"):
        df['翻譯理由'] = ""
        progress_bar = st.progress(0)
        
        for i, row in df.iterrows():
            reason_jp = row.get('選定理由摘要') or row.get('翻譯理由') # 相容不同欄位名
            # 執行翻譯
            df.at[i, '翻譯理由'] = translate_via_azure_test(reason_jp)
            
            progress_bar.progress((i + 1) / 5)
            st.write(f"✅ 已完成: {row['成分名 (日)']}")

        st.success("🎯 前五項測試完成！")
        
        # 顯示結果：特別拉寬顯示「翻譯理由」
        st.dataframe(df[['成分名 (日)', 'KEGG_ID', '翻譯理由']], use_container_width=True)

        # 下載測試結果
        csv_test = df.to_csv(index=False, encoding="utf-8-sig")
        st.download_button("📥 下載測試結果 CSV", csv_test, "test_top5.csv", "text/csv")
