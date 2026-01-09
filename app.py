import streamlit as st
import pandas as pd
import requests
import uuid
import re

# --- Azure Translator 設定 ---
# 請在此填入您的 Azure 金鑰資訊
AZURE_KEY = "您的_AZURE_SUBSCRIPTION_KEY"
AZURE_ENDPOINT = "https://api.cognitive.microsofttranslator.com"
AZURE_LOCATION = "您的_區域_例如_eastasia"

def translate_long_text_azure(text):
    """
    專門處理長文本翻譯的函數
    """
    if not text or pd.isna(text) or str(text).strip() == "":
        return ""

    # 1. 文本清洗：移除 PDF 產生的換行符號，這對長文本翻譯至關重要
    clean_text = str(text).replace('\n', ' ').replace('\r', '').strip()
    # 壓縮多餘空白
    clean_text = re.sub(r'\s+', ' ', clean_text)

    # 2. Azure API 呼叫設定
    path = '/translate'
    constructed_url = AZURE_ENDPOINT + path
    params = {
        'api-version': '3.0',
        'from': 'ja',
        'to': 'zh-Hant' # 翻譯為繁體中文
    }
    headers = {
        'Ocp-Apim-Subscription-Key': AZURE_KEY,
        'Ocp-Apim-Subscription-Region': AZURE_LOCATION,
        'Content-type': 'application/json',
        'X-ClientTraceId': str(uuid.uuid4())
    }
    body = [{'text': clean_text}]

    try:
        response = requests.post(constructed_url, params=params, headers=headers, json=body, timeout=10)
        response.raise_for_status()
        result = response.json()
        return result[0]['translations'][0]['text']
    except Exception as e:
        # 如果翻譯失敗，返回原樣並註記 (或進行簡易替換)
        return f"[翻譯失敗] {clean_text}"

# --- 在 Streamlit 的按鈕執行邏輯內 ---
if st.button("執行選定理由完整翻譯"):
    with st.spinner('正在翻譯長文本理由，請稍候...'):
        # 建立進度條
        total = len(df)
        progress_bar = st.progress(0)
        
        for i, row in df.iterrows():
            # 針對「選定理由摘要」欄位進行處理
            original_reason = row.get('選定理由摘要', '')
            
            # 呼叫 Azure 翻譯
            translated_reason = translate_long_text_azure(original_reason)
            
            # 更新到 DataFrame
            df.at[i, '選定理由摘要'] = translated_reason
            
            # 更新進度
            progress_bar.progress((i + 1) / total)
            
        st.success("✅ 選定理由翻譯完成！")
        st.dataframe(df)

        # 提供下載
        csv_data = df.to_csv(index=False, encoding="utf-8-sig")
        st.download_button("📥 下載翻譯完成的 CSV", csv_data, "translated_med_list.csv", "text/csv")
