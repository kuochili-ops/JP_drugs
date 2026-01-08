import streamlit as st
import pdfplumber
import pandas as pd
import requests
import re
import time
import io
from urllib.parse import quote
from bs4 import BeautifulSoup

# --- 1. 設定區域 (請確保 Key 正確) ---
AZURE_KEY = "9JDF24qrsW8rXiYmChS17yEPyNRI96nNXXqEKn5CyI6ql6iYcTOFJQQJ99BLAC3pKaRXJ3w3AAAbACOGVYVU"
AZURE_ENDPOINT = "https://api.cognitive.microsofttranslator.com"
AZURE_REGION = "eastasia"

# --- 2. 核心功能函式 ---

def translate_via_azure(text):
    """ 第一階段：使用 Azure 翻譯成分名 """
    if not text or len(str(text)) < 2: return None
    # 清理名稱：移除括號備註以利翻譯
    clean_text = re.split(r'[\(\n\s（]', str(text))[0].strip()
    url = f"{AZURE_ENDPOINT.strip('/')}/translate?api-version=3.0&from=ja&to=en"
    headers = {
        'Ocp-Apim-Subscription-Key': AZURE_KEY,
        'Ocp-Apim-Subscription-Region': AZURE_REGION,
        'Content-type': 'application/json; charset=utf-8'
    }
    try:
        response = requests.post(url, headers=headers, json=[{'text': clean_text}], timeout=10)
        if response.status_code == 200:
            return response.json()[0]['translations'][0]['text']
    except: pass
    return None

def fetch_from_kegg(jp_name):
    """ 第二階段：Azure 失敗時，查詢 KEGG 資料庫 """
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

def parse_full_pdf(file):
    """ 解析 506 項 PDF：兼容表格與純文字模式 """
    all_data = []
    current_cat = "未知"
    
    with pdfplumber.open(file) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            # 動態判定類別
            if "(1)" in text: current_cat = "カテゴリ A (最優先)"
            elif "(2)" in text: current_cat = "カテゴリ B (優先)"
            elif "(3)" in text: current_cat = "カテゴリ C (安定確保)"

            # A. 處理表格模式 (主要針對前10頁)
            tables = page.extract_tables()
            for table in tables:
                for row in table:
                    if not row or len(row) < 3: continue
                    route = str(row[0]).strip()
                    # 處理 "注 注" 或換行重疊情況
                    if any(r in route for r in ['内', '注', '外']):
                        clean_route = "".join(sorted(list(set(re.findall(r'内|注|外', route)))))
                        all_data.append({
                            "類別": current_cat,
                            "給藥方式": clean_route,
                            "用途類別": str(row[1]).strip().split('\n')[0],
                            "成分日文名": str(row[2]).strip().replace('\n', '')
                        })

            # B. 處理純文字模式 (補足第11頁後的內容)
            lines = text.split('\n')
            for line in lines:
                # 匹配格式如: "注 311 マキサカルシトール"
                match = re.search(r'^(内|注|外)\s+(\d{3})\s+(.+)$', line.strip())
                if match:
                    route, cat_no, name = match.groups()
                    # 檢查是否已存在 (避免與表格重複抓取)
                    if not any(d['成分日文名'] == name for d in all_data):
                        all_data.append({
                            "類別": current_cat,
                            "給藥方式": route,
                            "用途類別": cat_no,
                            "成分日文名": name
                        })
    return pd.DataFrame(all_data)

# --- 3. Streamlit UI ---
st.set_page_config(layout="wide", page_title="安定確保醫藥品 506 項全解析")
st.title("💊 安定確保醫藥品全量對照系統 (506項)")
st.info("解析策略：Azure 翻譯優先 ➔ KEGG 資料庫補底 ➔ 支援文字與表格混合 PDF")

f = st.file_uploader("請上傳 000785498.pdf", type=['pdf'])

if f:
    if 'data_list' not in st.session_state:
        with st.spinner("第一階段：正在從 PDF 提取 506 項清單..."):
            st.session_state.data_list = parse_full_pdf(f)
    
    df = st.session_state.data_list
    st.write(f"✅ 成功讀取清單，共計 {len(df)} 項成分。")
    st.dataframe(df, use_container_width=True)

    if st.button("🚀 開始全量對照英文成分名"):
        results = []
        bar = st.progress(0)
        status = st.empty()
        
        for i, row in df.iterrows():
            jp_name = row["成分日文名"]
            status.text(f"正在處理 ({i+1}/{len(df)}): {jp_name}")
            
            # 優先 Azure
            en_name = translate_via_azure(jp_name)
            source = "Azure Translator"
            
            # 失敗則轉向 KEGG
            if not en_name:
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
            if i % 15 == 0: time.sleep(0.2) # 防止過快
            
        final_df = pd.DataFrame(results)
        st.session_state.final_df = final_df
        st.success("🎉 506 項全解析對照完成！")
        st.dataframe(final_df, use_container_width=True)
        
        # 下載 Excel
        out = io.BytesIO()
        with pd.ExcelWriter(out, engine='xlsxwriter') as writer:
            final_df.to_excel(writer, index=False)
        st.download_button("📥 下載全解析報告 (Excel)", out.getvalue(), "Medicine_Full_Report.xlsx")
