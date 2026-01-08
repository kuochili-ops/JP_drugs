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

# --- 2. 翻譯與對照核心邏輯 (嚴格執行 Azure 優先) ---

def get_english_name_logic(jp_name):
    """
    邏輯：1. Azure 翻譯 -> 2. 失敗則 KEGG 爬蟲
    """
    if not jp_name or str(jp_name).lower() == 'none':
        return "N/A", "Skip"

    # --- Step 1: Azure 翻譯 ---
    try:
        clean_ja = re.split(r'[\(\n\s（]', str(jp_name))[0].strip()
        url = f"{AZURE_ENDPOINT.strip('/')}/translate?api-version=3.0&from=ja&to=en"
        headers = {
            'Ocp-Apim-Subscription-Key': AZURE_KEY,
            'Ocp-Apim-Subscription-Region': AZURE_REGION,
            'Content-type': 'application/json; charset=utf-8'
        }
        res = requests.post(url, headers=headers, json=[{'text': clean_ja}], timeout=8)
        if res.status_code == 200:
            en_res = res.json()[0]['translations'][0]['text']
            if en_res and len(en_res) > 2:
                return en_res, "Azure"
    except:
        pass

    # --- Step 2: KEGG 爬蟲 (Azure 沒拿到結果時) ---
    try:
        search_kw = re.split(r'[\(\n\s（]', str(jp_name))[0].strip()
        search_url = f"https://www.kegg.jp/medicus-bin/search_drug?search_keyword={quote(search_kw)}"
        r_s = requests.get(search_url, timeout=10)
        codes = re.findall(r'japic_code=(\d+)', r_s.text + r_s.url)
        if codes:
            jid = codes[0].zfill(8)
            ri = requests.get(f"https://www.kegg.jp/medicus-bin/japic_med?id={jid}")
            ri.encoding = ri.apparent_encoding
            soup = BeautifulSoup(ri.text, 'html.parser')
            th = soup.find('th', string=re.compile(r'欧文一般名'))
            if th and th.find_next_sibling('td'):
                return th.find_next_sibling('td').get_text(strip=True), "KEGG"
    except:
        pass

    return "[翻譯失敗]", "None"

# --- 3. 解析函式 (修正漏抓 506 項的問題) ---

def parse_full_medicine_pdf(file):
    all_data = []
    cat = "未知類別"
    
    with pdfplumber.open(file) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            # 1. 動態判定類別 (根據頁面標題)
            if "(1)" in text or "カテゴリA" in text: cat = "Cat A (最優先)"
            elif "(2)" in text or "カテゴリB" in text: cat = "Cat B (優先)"
            elif "(3)" in text or "カテゴリC" in text: cat = "Cat C (穩定確保)"

            # --- 核心邏輯：模糊模式掃描 ---
            # 匹配規律：行首或字串中出現 (内|注|外)，後跟 3 位數字，後跟一段日文字元
            # 這個正則表達式會捕獲所有「長得像藥品列」的文字，不管它是不是在表格裡
            pattern = re.compile(r'(内|注|外)\s*(\d{3})\s*([^\s\d\t]+)')
            
            # 我們將整頁文字按行處理，並進行深度清洗
            lines = text.split('\n')
            for l in lines:
                l = l.strip()
                # 排除標題列
                if "成分名" in l or "薬效分類" in l: continue
                
                # 執行匹配
                matches = pattern.findall(l)
                for m in matches:
                    route, code, name = m
                    name = name.strip()
                    
                    # 過濾掉太短或無意義的字元
                    if len(name) < 2: continue
                    
                    # 檢查重複 (非常重要，因為這會抓到表格內的文字)
                    if not any(d['成分日文名'] == name for d in all_data):
                        all_data.append({
                            "類別": cat,
                            "給藥方式": route,
                            "用途類別": code,
                            "成分日文名": name
                        })

    # 最終校對：如果抓到的數量還是不對，可能是因為有些成分名中間帶有空格
    # 我們可以增加一組更寬鬆的匹配邏輯
    return pd.DataFrame(all_data)
# --- 4. Streamlit UI 介面 ---
st.set_page_config(layout="wide", page_title="安定確保醫藥品 506項解析")
st.title("💊 安定確保醫藥品全量解析工具")
st.write("解析邏輯：PDF 表格+文字掃描 (506項) -> Azure 優先翻譯 -> KEGG 備援")

f = st.file_uploader("請上傳 PDF (000785498.pdf)", type=['pdf'])

if f:
    if 'raw_df' not in st.session_state:
        with st.spinner("正在提取 506 項成分清單..."):
            # 呼叫修正後的函式名
            st.session_state.raw_df = parse_full_medicine_pdf(f)
    
    df = st.session_state.raw_df
    st.success(f"✅ 成功提取 {len(df)} 項成分！")
    st.dataframe(df, use_container_width=True)

    if st.button("🚀 開始全量對照 (Azure + KEGG)"):
        final_list = []
        bar = st.progress(0)
        status = st.empty()
        
        for i, row in df.iterrows():
            jp_name = row["成分日文名"]
            status.text(f"處理進度 ({i+1}/{len(df)}): {jp_name}")
            
            # 執行翻譯邏輯
            en_name, source = get_english_name_logic(jp_name)
            
            final_list.append({
                "類別": row["類別"],
                "給藥方式": row["給藥方式"],
                "用途類別": row["用途類別"],
                "成分日文名": jp_name,
                "成分英文名": en_name,
                "翻譯來源": source
            })
            bar.progress((i + 1) / len(df))
            
            # 緩衝
            if i % 15 == 0: time.sleep(0.1)
            
        res_df = pd.DataFrame(final_list)
        st.success("🎉 全量對照完成！")
        st.dataframe(res_df, use_container_width=True)
        
        # 下載 Excel
        out = io.BytesIO()
        with pd.ExcelWriter(out, engine='xlsxwriter') as writer:
            res_df.to_excel(writer, index=False)
        st.download_button("📥 下載全解析 Excel 報告", out.getvalue(), "Medicine_Full_Report.xlsx")
