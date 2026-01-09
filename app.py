import streamlit as st
import pandas as pd
import requests
import re
import uuid
import time

# --- 1. 頁面基本配置 ---
st.set_page_config(page_title="藥品清單補完與翻譯系統", layout="wide")

# 【重要設定】請確保這裡的值沒有全形空格或中文字
AZURE_KEY = "您的_AZURE_SUBSCRIPTION_KEY" # 32位元金鑰
AZURE_ENDPOINT = "https://api.cognitive.microsofttranslator.com"
AZURE_LOCATION = "eastasia" # 必須為小寫英文，例如 eastasia 或 global

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
                    k_id = parts[0].replace('dr:', 'dr_ja:').strip() # 統一格式
                    full_text = parts[1]
                    if ';' in full_text:
                        en_part = full_text.split(';')[1].strip()
                        en_name = re.sub(r'[\(\（].*?[\)\）]', '', en_part).strip()
                        jp_part = full_text.split(';')[0].strip()
                        jp_name = re.sub(r'[\(\（].*?[\)\）]', '', jp_part).strip()
                        kegg_map[jp_name] = {"id": k_id, "en": en_name}
        return kegg_map
    except Exception as e:
        return {"error": str(e)}

# --- 3. 強化版翻譯函數：解決編碼錯誤與長文本超時 ---
def translate_via_azure(text):
    if not text or pd.isna(text) or str(text).strip() == "" or text == "N/A":
        return ""

    # 文本清洗
    clean_text = str(text).replace('\n', ' ').replace('\r', ' ').strip()
    clean_text = re.sub(r'\s+', ' ', clean_text)

    # 建立 Header (加上 str().strip() 確保無特殊字元)
    try:
        headers = {
            'Ocp-Apim-Subscription-Key': str(AZURE_KEY).strip(),
            'Ocp-Apim-Subscription-Region': str(AZURE_LOCATION).strip(),
            'Content-type': 'application/json',
            'X-ClientTraceId': str(uuid.uuid4())
        }
    except UnicodeEncodeError:
        return "[設定錯誤] 請檢查 Azure Key 或 Region 是否包含中文字或全形符號"

    params = {'api-version': '3.0', 'from': 'ja', 'to': 'zh-Hant'}
    
    # 針對極長文本進行分段處理 (每 1000 字一段)
    chunks = [clean_text[i:i+1000] for i in range(0, len(clean_text), 1000)]
    translated_chunks = []

    for chunk in chunks:
        body = [{'text': chunk}]
        try:
            r = requests.post(f"{AZURE_ENDPOINT}/translate", params=params, headers=headers, json=body, timeout=30)
            if r.status_code == 200:
                translated_chunks.append(r.json()[0]['translations'][0]['text'])
            else:
                translated_chunks.append(f"[錯誤 {r.status_code}]")
        except:
            translated_chunks.append("[翻譯超時]")
        time.sleep(0.1) # 避開頻率限制

    return "".join(translated_chunks)

# --- 4. Streamlit UI 流程 ---
st.title("💊 藥品清單全自動處理系統")

kegg_lookup = get_kegg_master_dict()
if "error" in kegg_lookup:
    st.error(f"KEGG 字典載入失敗，請檢查網路連線。")

uploaded_file = st.file_uploader("1. 上傳 CSV 檔案", type="csv")

if uploaded_file:
    df = pd.read_csv(uploaded_file)
    st.write("已讀取檔案，預備處理...")

    if st.button("2. 開始全自動執行"):
        # 初始化欄位
        if 'KEGG_ID' not in df.columns: df['KEGG_ID'] = ""
        if '成分名 (英)' not in df.columns: df['成分名 (英)'] = ""
        if '翻譯理由' not in df.columns: df['翻譯理由'] = ""

        progress_bar = st.progress(0)
        status_text = st.empty()
        total = len(df)

        for i, row in df.iterrows():
            # A. KEGG 對照
            jp_name_raw = str(row['成分名 (日)']).strip()
            clean_jp = re.sub(r'[（\(].*?[）\)]', '', jp_name_raw).strip()
            
            if clean_jp in kegg_lookup:
                df.at[i, 'KEGG_ID'] = kegg_lookup[clean_jp]['id']
                df.at[i, '成分名 (英)'] = kegg_lookup[clean_jp]['en']
            
            # B. 翻譯長文本摘要
            # 優先搜尋 '選定理由摘要' 或 '理由' 欄位
            reason_col = '選定理由摘要' if '選定理由摘要' in df.columns else df.columns[-1]
            df.at[i, '翻譯理由'] = translate_via_azure(row[reason_col])

            # 更新 UI
            if i % 5 == 0 or i == total - 1:
                progress_bar.progress((i + 1) / total)
                status_text.text(f"處理中 ({i+1}/{total}): {clean_jp}")

        status_text.success("✅ 任務完成！")
        
        # 顯示與下載
        st.dataframe(df, use_container_width=True)
        csv_out = df.to_csv(index=False, encoding="utf-8-sig")
        st.download_button("📥 下載最終 CSV", csv_out, "final_data.csv", "text/csv")
