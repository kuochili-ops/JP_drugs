import streamlit as st
import pandas as pd
import requests
import re
import time
import io
from urllib.parse import quote
from bs4 import BeautifulSoup

# --- 1. 配置區域 ---
AZURE_KEY = "9JDF24qrsW8rXiYmChS17yEPyNRI96nNXXqEKn5CyI6ql6iYcTOFJQQJ99BLAC3pKaRXJ3w3AAAbACOGVYVU"
AZURE_ENDPOINT = "https://api.cognitive.microsofttranslator.com"
AZURE_REGION = "eastasia"

# --- 2. 翻譯與對照邏輯 ---

def translate_via_azure(jp_name):
    """ 強制使用 Azure 翻譯 """
    if not jp_name or pd.isna(jp_name): return None
    # 移除括號內的劑型（如：水和物），增加 API 命中率
    clean_ja = re.split(r'[\(\n\s（]', str(jp_name))[0].strip()
    try:
        url = f"{AZURE_ENDPOINT.strip('/')}/translate?api-version=3.0&from=ja&to=en"
        headers = {
            'Ocp-Apim-Subscription-Key': AZURE_KEY,
            'Ocp-Apim-Subscription-Region': AZURE_REGION,
            'Content-type': 'application/json'
        }
        res = requests.post(url, headers=headers, json=[{'text': clean_ja}], timeout=10)
        if res.status_code == 200:
            return res.json()[0]['translations'][0]['text']
    except:
        pass
    return None

def fetch_from_kegg(jp_name):
    """ Azure 失敗時的備援：爬取 KEGG 官方英文名 """
    clean_ja = re.split(r'[\(\n\s（]', str(jp_name))[0].strip()
    try:
        search_url = f"https://www.kegg.jp/medicus-bin/search_drug?search_keyword={quote(clean_ja)}"
        r = requests.get(search_url, timeout=10)
        codes = re.findall(r'japic_code=(\d+)', r.text + r.url)
        if codes:
            ri = requests.get(f"https://www.kegg.jp/medicus-bin/japic_med?id={codes[0].zfill(8)}")
            ri.encoding = ri.apparent_encoding
            soup = BeautifulSoup(ri.text, 'html.parser')
            th = soup.find('th', string=re.compile(r'欧文一般名'))
            if th and th.find_next_sibling('td'):
                return th.find_next_sibling('td').get_text(strip=True)
    except:
        pass
    return None

# --- 3. Streamlit UI ---
st.set_page_config(layout="wide", page_title="505項藥品修補工具")
st.title("💊 醫藥品清單英文補全工具")
st.write("目前策略：上傳您的 XLSX/CSV，針對「成分英文名」為空白或對照失敗的項目進行補完。")

# 支援上傳您剛生成的檔案
uploaded_file = st.file_uploader("請上傳 Medicine_Full_Report.xlsx (或 CSV)", type=['xlsx', 'csv'])

if uploaded_file:
    # 讀取檔案
    if uploaded_file.name.endswith('.xlsx'):
        df = pd.read_excel(uploaded_file)
    else:
        df = pd.read_csv(uploaded_file)
    
    st.write(f"✅ 成功載入資料，共 {len(df)} 筆。")
    st.dataframe(df.head(10), use_container_width=True)

    if st.button("🚀 開始補全英文成分名 (Azure 優先)"):
        results = []
        bar = st.progress(0)
        status = st.empty()
        
        for i, row in df.iterrows():
            jp_name = row["成分日文名"]
            status.text(f"正在修補 ({i+1}/{len(df)}): {jp_name}")
            
            # 1. 先試 Azure
            en_name = translate_via_azure(jp_name)
            source = "Azure"
            
            # 2. Azure 不行再試 KEGG
            if not en_name:
                en_name = fetch_from_kegg(jp_name)
                source = "KEGG"
            
            # 3. 如果都失敗
            if not en_name:
                en_name = "[仍未找到]"
                source = "None"
            
            # 更新資料
            row["成分英文名"] = en_name
            row["來源"] = source if "來源" in df.columns or "來源" in row else source
            results.append(row)
            
            bar.progress((i + 1) / len(df))
            if i % 10 == 0: time.sleep(0.1) # 避免 API 頻率限制
            
        final_df = pd.DataFrame(results)
        st.success("🎉 全量修補完成！")
        st.dataframe(final_df, use_container_width=True)
        
        # 下載 Excel
        out = io.BytesIO()
        with pd.ExcelWriter(out, engine='xlsxwriter') as writer:
            final_df.to_excel(writer, index=False)
        st.download_button("📥 下載修正後的完整 Excel", out.getvalue(), "Medicine_Fixed_Report.xlsx")
