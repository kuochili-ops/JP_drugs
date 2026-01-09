import streamlit as st
import pandas as pd
import requests
import re
import uuid

# --- 1. 初始化與環境設定 ---
st.set_page_config(page_title="藥品清單補完工具", layout="wide")

# Azure Translator 配置 (請填入您的資訊)
AZURE_KEY = "您的_AZURE_KEY"
AZURE_LOCATION = "您的_區域" # 例如 eastasia
AZURE_ENDPOINT = "https://api.cognitive.microsofttranslator.com"

# --- 2. KEGG 字典模組：精確抓取分號後英文 ---
@st.cache_data(ttl=3600)
def get_kegg_master_dict():
    url = "https://rest.kegg.jp/list/drug_ja/"
    kegg_map = {}
    try:
        res = requests.get(url, timeout=15)
        if res.status_code == 200:
            for line in res.text.strip().split('\n'):
                parts = line.split('\t')
                if len(parts) >= 2:
                    k_id = parts[0].replace('dr:', '').strip()
                    full_text = parts[1]
                    
                    # 格式：日文 (備註); 英文 (備註)
                    if ';' in full_text:
                        # 抓分號後的英文並移除 (JP18) 等標記
                        en_raw = full_text.split(';')[1].strip()
                        en_name = re.sub(r'[\(\（].*?[\)\）]', '', en_raw).strip()
                        
                        # 抓分號前的日文作為 Key
                        jp_raw = full_text.split(';')[0].strip()
                        jp_name = re.sub(r'[\(\（].*?[\)\）]', '', jp_raw).strip()
                        
                        kegg_map[jp_name] = {"id": k_id, "en": en_name}
        return kegg_map
    except Exception as e:
        st.error(f"KEGG 字典加載失敗: {e}")
        return {}

# --- 3. Azure 翻譯模組：處理長文本理由 ---
def translate_via_azure(text):
    if not text or pd.isna(text) or str(text).strip() == "":
        return ""
    
    # 重要：清洗換行符號，讓語意連貫
    clean_text = str(text).replace('\n', ' ').strip()
    
    path = '/translate'
    url = AZURE_ENDPOINT + path
    headers = {
        'Ocp-Apim-Subscription-Key': AZURE_KEY,
        'Ocp-Apim-Subscription-Region': AZURE_LOCATION,
        'Content-type': 'application/json',
        'X-ClientTraceId': str(uuid.uuid4())
    }
    params = {'api-version': '3.0', 'from': 'ja', 'to': 'zh-Hant'}
    body = [{'text': clean_text}]

    try:
        r = requests.post(url, params=params, headers=headers, json=body, timeout=10)
        r.raise_for_status()
        return r.json()[0]['translations'][0]['text']
    except:
        return f"[翻譯失敗] {clean_text}"

# --- 4. Streamlit UI 流程 ---
st.title("💊 醫藥清單全自動處理 (KEGG + Azure)")

# 預載字典
kegg_dict = get_kegg_master_dict()

uploaded_file = st.file_uploader("第一步：上傳您從 PDF 導出的 CSV", type="csv")

if uploaded_file:
    df = pd.read_csv(uploaded_file)
    
    # 預備欄位
    if 'KEGG_ID' not in df.columns: df['KEGG_ID'] = ""
    if '成分名 (英)' not in df.columns: df['成分名 (英)'] = ""
    if '翻譯理由' not in df.columns: df['翻譯理由'] = ""

    if st.button("第二步：開始全自動處理"):
        progress_bar = st.progress(0)
        status = st.empty()
        
        for i, row in df.iterrows():
            # A. 比對 KEGG
            original_jp = str(row['成分名 (日)']).replace('\n', '').strip()
            clean_jp = re.sub(r'[（\(].*?[）\)]', '', original_jp).strip()
            
            if clean_jp in kegg_dict:
                df.at[i, 'KEGG_ID'] = kegg_dict[clean_jp]['id']
                df.at[i, '成分名 (英)'] = kegg_dict[clean_jp]['en']
            else:
                df.at[i, 'KEGG_ID'] = "Not Found"
            
            # B. 翻譯長文本 (選定理由摘要)
            reason_jp = row.get('選定理由摘要', '')
            df.at[i, '翻譯理由'] = translate_via_azure(reason_jp)
            
            # C. 處理其他固定詞彙 (如藥效分類)
            # (可依據之前提到的 TERM_MAP 進行替換)

            progress_bar.progress((i + 1) / len(df))
            status.text(f"正在處理: {clean_jp}")

        status.success("✅ 任務完成！")
        
        # 顯示結果
        st.dataframe(df[['區分', '成分名 (日)', '成分名 (英)', 'KEGG_ID', '翻譯理由']], use_container_width=True)

        # 下載
        csv = df.to_csv(index=False, encoding="utf-8-sig")
        st.download_button("📥 下載最終完成檔案", csv, "final_med_data.csv", "text/csv")
