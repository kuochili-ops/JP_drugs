import streamlit as st
import pdfplumber
import pandas as pd
import requests
import re
import time
import io
from urllib.parse import quote
from bs4 import BeautifulSoup

# --- 1. 設定區域 ---
AZURE_KEY = "9JDF24qrsW8rXiYmChS17yEPyNRI96nNXXqEKn5CyI6ql6iYcTOFJQQJ99BLAC3pKaRXJ3w3AAAbACOGVYVU"
AZURE_ENDPOINT = "https://api.cognitive.microsofttranslator.com"
AZURE_REGION = "eastasia"

# --- 2. 功能函式庫 ---

def translate_via_azure(text):
    """ 第一階段：嘗試使用 Azure 翻譯成分名 """
    if not text: return ""
    clean_text = str(text).split('(')[0].split('（')[0].strip() # 移除劑型括號以利翻譯
    url = f"{AZURE_ENDPOINT.strip('/')}/translate?api-version=3.0&from=ja&to=en"
    headers = {
        'Ocp-Apim-Subscription-Key': AZURE_KEY,
        'Ocp-Apim-Subscription-Region': AZURE_REGION,
        'Content-type': 'application/json; charset=utf-8'
    }
    try:
        response = requests.post(url, headers=headers, json=[{'text': clean_text}], timeout=10)
        if response.status_code == 200:
            res_data = response.json()
            return res_data[0]['translations'][0]['text']
    except: pass
    return None

def fetch_from_kegg(jp_name):
    """ 第二階段：Azure 失敗或需要精確術語時，查詢 KEGG """
    headers = {"User-Agent": "Mozilla/5.0"}
    raw_clean = re.split(r'[\(\n\s（]', str(jp_name))[0].strip()
    try:
        search_url = f"https://www.kegg.jp/medicus-bin/search_drug?search_keyword={quote(raw_clean)}"
        r_s = requests.get(search_url, headers=headers, timeout=10)
        codes = re.findall(r'japic_code=(\d+)', r_s.text + r_s.url)
        if codes:
            jid = codes[0].zfill(8)
            ri = requests.get(f"https://www.kegg.jp/medicus-bin/japic_med?japic_code={jid}", headers=headers)
            ri.encoding = ri.apparent_encoding
            i_soup = BeautifulSoup(ri.text, 'html.parser')
            th = i_soup.find('th', string=re.compile(r'欧文一般名'))
            if th and th.find_next_sibling('td'):
                return th.find_next_sibling('td').get_text(strip=True)
    except: pass
    return "[對照失敗]"

def parse_medicine_pdf(file):
    """ 解析 PDF 並提取基本欄位 """
    data = []
    current_cat = "未知"
    with pdfplumber.open(file) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            if "(1)" in text: current_cat = "カテゴリ A"
            elif "(2)" in text: current_cat = "カテゴリ B"
            elif "(3)" in text: current_cat = "カテゴリ C"
            
            tables = page.extract_tables()
            for table in tables:
                for row in table:
                    if len(row) >= 3 and str(row[0]).strip() in ['内', '注', '外', '注 注']:
                        data.append({
                            "類別": current_cat,
                            "給藥方式": str(row[0]).replace('\n', ' ').strip(),
                            "用途類別": str(row[1]).strip(),
                            "成分日文名": str(row[2]).strip().replace('\n', '')
                        })
    return pd.DataFrame(data)

# --- 3. Streamlit 介面 ---
st.title("💊 安定確保醫藥品全量對照系統")
st.write("邏輯：Azure 翻譯優先 ➔ KEGG 資料庫補底")

f = st.file_uploader("上傳 PDF 檔案", type=['pdf'])

if f:
    if 'raw_df' not in st.session_state:
        st.session_state.raw_df = parse_medicine_pdf(f)
    
    df = st.session_state.raw_df
    st.write(f"已讀取 {len(df)} 項成分。")
    
    if st.button("開始 506 項全解析"):
        results = []
        bar = st.progress(0)
        msg = st.empty()
        
        for i, row in df.iterrows():
            jp_name = row["成分日文名"]
            msg.text(f"正在處理 ({i+1}/{len(df)}): {jp_name}")
            
            # 策略實施：先看 Azure
            en_name = translate_via_azure(jp_name)
            source = "Azure Translator"
            
            # 如果 Azure 沒結果，去 KEGG 找
            if not en_name or "[API 錯誤" in en_name:
                en_name = fetch_from_kegg(jp_name)
                source = "KEGG/Japic"
            
            results.append({
                "類別": row["類別"],
                "給藥方式": row["給藥方式"],
                "用途類別": row["用途類別"],
                "成分日文名": jp_name,
                "成分英文名": en_name,
                "資料來源": source
            })
            bar.progress((i + 1) / len(df))
            if i % 10 == 0: time.sleep(0.1) # 緩衝
            
        final_df = pd.DataFrame(results)
        st.success("解析完成！")
        st.dataframe(final_df)
        
        # 下載 Excel
        out = io.BytesIO()
        with pd.ExcelWriter(out, engine='xlsxwriter') as writer:
            final_df.to_excel(writer, index=False)
        st.download_button("📥 下載全解析報告", out.getvalue(), "Medicine_Report.xlsx")
