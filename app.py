import streamlit as st
import pdfplumber
import pandas as pd
import requests
import re
import time
import io
from urllib.parse import quote
from bs4 import BeautifulSoup

# --- 1. Azure 設定 ---
AZURE_KEY = "9JDF24qrsW8rXiYmChS17yEPyNRI96nNXXqEKn5CyI6ql6iYcTOFJQQJ99BLAC3pKaRXJ3w3AAAbACOGVYVU"
AZURE_ENDPOINT = "https://api.cognitive.microsofttranslator.com"
AZURE_REGION = "eastasia"

# --- 2. 翻譯與對照邏輯 (嚴格執行先後順序) ---

def get_english_name(jp_name):
    """
    核心邏輯：
    1. 先嘗試 Azure 翻譯
    2. 如果 Azure 失敗 (None 或錯誤)，再爬 KEGG
    """
    if not jp_name or str(jp_name).lower() == 'none':
        return "N/A", "Skip"

    # --- Step 1: Azure 翻譯 ---
    en_name = None
    try:
        # 清理日文，移除括號
        clean_ja = re.split(r'[\(\n\s（]', str(jp_name))[0].strip()
        url = f"{AZURE_ENDPOINT.strip('/')}/translate?api-version=3.0&from=ja&to=en"
        headers = {
            'Ocp-Apim-Subscription-Key': AZURE_KEY,
            'Ocp-Apim-Subscription-Region': AZURE_REGION,
            'Content-type': 'application/json; charset=utf-8'
        }
        res = requests.post(url, headers=headers, json=[{'text': clean_ja}], timeout=8)
        if res.status_code == 200:
            en_name = res.json()[0]['translations'][0]['text']
            # 如果翻譯結果看起來有效，直接回傳
            if en_name and len(en_name) > 2:
                return en_name, "Azure"
    except:
        pass

    # --- Step 2: KEGG 爬蟲 (當 Azure 失敗時) ---
    try:
        search_keyword = re.split(r'[\(\n\s（]', str(jp_name))[0].strip()
        search_url = f"https://www.kegg.jp/medicus-bin/search_drug?search_keyword={quote(search_keyword)}"
        r_s = requests.get(search_url, timeout=10)
        codes = re.findall(r'japic_code=(\d+)', r_s.text + r_s.url)
        if codes:
            jid = codes[0].zfill(8)
            ri = requests.get(f"https://www.kegg.jp/medicus-bin/japic_med?id={jid}")
            ri.encoding = ri.apparent_encoding
            soup = BeautifulSoup(ri.text, 'html.parser')
            th = soup.find('th', string=re.compile(r'欧文一般名'))
            if th and th.find_next_sibling('td'):
                kegg_en = th.find_next_sibling('td').get_text(strip=True)
                return kegg_en, "KEGG"
    except:
        pass

    return "[翻譯失敗]", "None"

def parse_full_506(file):
    all_data = []
    current_cat = "未知"
    
    with pdfplumber.open(file) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            # 更新類別判定
            if "(1)" in text: current_cat = "Cat A"
            elif "(2)" in text: current_cat = "Cat B"
            elif "(3)" in text: current_cat = "Cat C"

            # 策略 A: 抓取標準表格 (前10頁)
            tables = page.extract_tables()
            for table in tables:
                for row in table:
                    if len(row) >= 3:
                        route_raw = str(row[0])
                        # 只要包含關鍵字就抓取
                        if any(r in route_raw for r in ['内', '注', '外']):
                            clean_route = "".join(set(re.findall(r'内|注|外', route_raw)))
                            all_data.append({
                                "類別": current_cat,
                                "給藥方式": clean_route,
                                "用途類別": str(row[1]).strip().split('\n')[0],
                                "成分日文名": str(row[2]).strip().replace('\n', '')
                            })

            # 策略 B: 針對第11頁後的「純文字行」進行 Regex 補抓
            lines = text.split('\n')
            for line in lines:
                # 匹配格式：給藥方式(内/注/外) + 3位數字 + 成分名
                match = re.search(r'^(内|注|外)\s+(\d{3})\s+(.+)$', line.strip())
                if match:
                    route, code, name = match.groups()
                    # 檢查重複，避免與策略 A 抓到的重疊
                    if not any(d['成分日文名'] == name for d in all_data):
                        all_data.append({
                            "類別": current_cat,
                            "給藥方式": route,
                            "用途類別": code,
                            "成分日文名": name
                        })
    return pd.DataFrame(all_data)
# --- 3. Streamlit UI ---
st.title("💊 506項藥品全解析 (Azure 優先模式)")

f = st.file_uploader("上傳 PDF", type=['pdf'])

if f:
    if 'raw_df' not in st.session_state:
        st.session_state.raw_df = parse_medicine_pdf(f)
    
    df = st.session_state.raw_df
    st.write(f"已從 PDF 提取 {len(df)} 項成分清單。")
    st.dataframe(df.head(10)) # 先預覽前10項確保日文名沒抓錯

    if st.button("🚀 開始全量翻譯 (先 Azure 後 KEGG)"):
        final_results = []
        bar = st.progress(0)
        status = st.empty()
        
        for i, row in df.iterrows():
            jp_name = row["成分日文名"]
            status.text(f"處理中 ({i+1}/{len(df)}): {jp_name}")
            
            # 執行雙重對照邏輯
            en_name, source = get_english_name(jp_name)
            
            final_results.append({
                "類別": row["類別"],
                "給藥方式": row["給藥方式"],
                "用途類別": row["用途類別"],
                "成分日文名": jp_name,
                "成分英文名": en_name,
                "對照來源": source
            })
            bar.progress((i + 1) / len(df))
            
        res_df = pd.DataFrame(final_results)
        st.success("全部解析完成！")
        st.dataframe(res_df)
        
        # 匯出 CSV (UTF-8-SIG 確保 Excel 不亂碼)
        csv_data = res_df.to_csv(index=False).encode('utf-8-sig')
        st.download_button("📥 下載完整 CSV 報告", csv_data, "Japan_Medicine_Full_Report.csv")
