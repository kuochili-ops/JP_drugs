import streamlit as st
import pandas as pd
import requests
import re
import uuid

# --- 1. 頁面基本配置 ---
st.set_page_config(page_title="藥品清單補完與翻譯系統", layout="wide")

# 【設定區】請填入您的 Azure 翻譯金鑰資訊
AZURE_KEY = "您的_AZURE_SUBSCRIPTION_KEY"
AZURE_ENDPOINT = "https://api.cognitive.microsofttranslator.com"
AZURE_LOCATION = "您的_區域" # 例如: eastasia

# --- 2. KEGG 字典模組：精確抓取分號後的英文名 ---
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
                    k_id = parts[0].replace('dr:', '').strip()
                    full_text = parts[1]
                    
                    # 處理格式: 日文名 (JP18); English name (JP18)
                    if ';' in full_text:
                        # A. 抓取分號後的英文部分並移除括號標記
                        en_part = full_text.split(';')[1].strip()
                        en_name = re.sub(r'[\(\（].*?[\)\）]', '', en_part).strip()
                        
                        # B. 抓取分號前的日文部分作為比對 Key
                        jp_part = full_text.split(';')[0].strip()
                        jp_name = re.sub(r'[\(\（].*?[\)\）]', '', jp_part).strip()
                        
                        kegg_map[jp_name] = {"id": k_id, "en": en_name}
        return kegg_map
    except Exception as e:
        st.error(f"KEGG 字典下載失敗: {e}")
        return {}

# --- 3. Azure 翻譯模組：強力清洗文本解決 [連線失敗] ---
def translate_via_azure(text):
    if not text or pd.isna(text) or str(text).strip() == "" or text == "N/A":
        return ""

    # 【核心修正】移除所有換行符與多餘空格，讓長文本連貫
    clean_text = str(text).replace('\n', ' ').replace('\r', ' ').strip()
    clean_text = re.sub(r'\s+', ' ', clean_text)

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
        # 增加 timeout 到 20 秒，確保長文本翻譯有足夠時間
        r = requests.post(url, params=params, headers=headers, json=body, timeout=20)
        if r.status_code == 200:
            return r.json()[0]['translations'][0]['text']
        else:
            return f"[API錯誤 {r.status_code}]"
    except Exception as e:
        return f"[翻譯超時/連線失敗]"

# --- 4. Streamlit UI 流程 ---
st.title("🧪 藥品清單全自動處理 (KEGG 對照 + 理由翻譯)")

# 預載字典
kegg_lookup = get_kegg_master_dict()

uploaded_file = st.file_uploader("1. 上傳 CSV 檔案", type="csv")

if uploaded_file:
    # 讀取檔案
    df = pd.read_csv(uploaded_file)
    st.write("檔案預覽：")
    st.dataframe(df.head(3))

    if st.button("2. 開始全自動執行 (ID 比對 + 理由翻譯)"):
        # 初始化或清空舊欄位
        df['KEGG_ID'] = "Searching..."
        df['成分名 (英)'] = "N/A"
        df['翻譯理由'] = ""

        progress_bar = st.progress(0)
        status_text = st.empty()
        
        total_rows = len(df)
        
        for i, row in df.iterrows():
            # A. 處理成分名並比對 KEGG
            raw_jp = str(row['成分名 (日)']).strip()
            # 移除括號內容進行精準比對 (如: 水和物)
            clean_jp = re.sub(r'[（\(].*?[）\)]', '', raw_jp).strip()
            
            if clean_jp in kegg_lookup:
                df.at[i, 'KEGG_ID'] = kegg_lookup[clean_jp]['id']
                df.at[i, '成分名 (英)'] = kegg_lookup[clean_jp]['en']
            else:
                df.at[i, 'KEGG_ID'] = "Not Found"
            
            # B. 翻譯長文本 (選定理由摘要)
            # 這裡假設 CSV 欄位名稱為 '選定理由摘要'
            reason_jp = row.get('選定理由摘要', '')
            df.at[i, '翻譯理由'] = translate_via_azure(reason_jp)
            
            # 更新進度條
            if i % 5 == 0 or i == total_rows - 1:
                progress_bar.progress((i + 1) / total_rows)
                status_text.text(f"正在處理第 {i+1}/{total_rows} 筆: {clean_jp}")

        status_text.success("✅ 處理完成！")
        
        # 顯示結果 (調整欄位順序)
        display_cols = ['區分', '成分名 (日)', '成分名 (英)', 'KEGG_ID', '翻譯理由']
        existing_cols = [c for c in display_cols if c in df.columns]
        st.dataframe(df[existing_cols], use_container_width=True)

        # 匯出 CSV (使用 sig 確保 Excel 開啟不亂碼)
        csv_data = df.to_csv(index=False, encoding="utf-8-sig")
        st.download_button(
            label="📥 下載最終完整 CSV",
            data=csv_data,
            file_name="final_translated_med_list.csv",
            mime="text/csv"
        )
