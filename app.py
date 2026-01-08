import streamlit as st
import pdfplumber
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

# 日本藥效分類番號對照表 (常用部分)
PURPOSE_MAP = {
    "111": "全身麻醉劑", "112": "催眠鎮靜劑", "113": "抗癲癇劑", "114": "解熱鎮痛劑",
    "116": "抗巴金森氏症劑", "117": "精神神經用劑", "121": "局部麻醉劑", "122": "骨骼肌鬆弛劑",
    "123": "自律神經劑", "124": "解痙劑", "131": "眼科用劑", "132": "耳鼻喉科用劑",
    "211": "強心劑", "212": "不整律用劑", "213": "利尿劑", "214": "血壓降下劑",
    "217": "血管擴張劑", "218": "高脂血症劑", "219": "其他循環器官用劑",
    "221": "呼吸促進劑", "222": "鎮咳劑", "223": "祛痰劑", "225": "支氣管擴張劑",
    "232": "消化性潰瘍劑", "233": "健胃消化劑", "234": "制酸劑", "235": "止瀉劑",
    "239": "其他消化器官用劑", "241": "腦下垂體激素", "243": "甲狀腺激素", "245": "腎上腺激素",
    "247": "卵巢激素", "249": "其他激素劑", "252": "泌尿器官用劑", "255": "痔瘡用劑",
    "261": "外用殺菌消毒劑", "264": "鎮痛消炎劑 (外用)", "311": "維生素 D 劑",
    "331": "血液代用劑", "332": "止血劑", "333": "血液凝固阻止劑", "339": "其他血液/體液用藥",
    "391": "肝臟疾患劑", "392": "解毒劑", "395": "酵素製劑", "396": "糖尿病用劑",
    "399": "免疫抑制劑/代謝藥", "421": "烷化劑", "422": "代謝拮抗劑", "423": "抗癌性抗生素",
    "424": "植物性抗癌劑", "429": "其他抗惡性腫瘤劑 (標靶藥)", "441": "抗組織胺劑",
    "611": "抗生素 (革蘭氏陽性)", "612": "抗生素 (革蘭氏陰性)", "613": "廣效抗生素",
    "614": "抗生素 (大環內酯)", "615": "抗生素 (四環素)", "619": "其他抗生素",
    "624": "合成抗菌劑 (喹諾酮)", "625": "抗病毒劑", "629": "其他化學療法劑",
    "634": "血液製劑", "639": "疫苗/生物製品", "711": "診斷用藥", "721": "X光造影劑"
}

# --- 2. 核心對照功能 ---

def get_english_name(jp_name):
    """ 先 Azure 翻譯 -> 失敗則 KEGG 爬蟲 """
    if not jp_name: return "N/A", "Skip"
    clean_ja = re.split(r'[\(\n\s（]', str(jp_name))[0].strip()
    
    # Step 1: Azure
    try:
        url = f"{AZURE_ENDPOINT.strip('/')}/translate?api-version=3.0&from=ja&to=en"
        headers = {'Ocp-Apim-Subscription-Key': AZURE_KEY, 'Ocp-Apim-Subscription-Region': AZURE_REGION, 'Content-type': 'application/json'}
        res = requests.post(url, headers=headers, json=[{'text': clean_ja}], timeout=5)
        if res.status_code == 200:
            en = res.json()[0]['translations'][0]['text']
            if en and len(en) > 2: return en, "Azure"
    except: pass

    # Step 2: KEGG Fallback
    try:
        search_url = f"https://www.kegg.jp/medicus-bin/search_drug?search_keyword={quote(clean_ja)}"
        r_s = requests.get(search_url, timeout=5)
        codes = re.findall(r'japic_code=(\d+)', r_s.text + r_s.url)
        if codes:
            ri = requests.get(f"https://www.kegg.jp/medicus-bin/japic_med?id={codes[0].zfill(8)}")
            ri.encoding = ri.apparent_encoding
            soup = BeautifulSoup(ri.text, 'html.parser')
            th = soup.find('th', string=re.compile(r'欧文一般名'))
            if th and th.find_next_sibling('td'):
                return th.find_next_sibling('td').get_text(strip=True), "KEGG"
    except: pass
    return "[對照失敗]", "None"

# --- 3. 解析功能 (錨點+合併) ---

def parse_full_medicine_pdf(file):
    all_data = []
    current_cat = "未知"
    
    with pdfplumber.open(file) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            # 類別判定
            if "(1)" in text: current_cat = "Cat A (最優先)"
            elif "(2)" in text: current_cat = "Cat B (優先)"
            elif "(3)" in text: current_cat = "Cat C (穩定確保)"

            lines = text.split('\n')
            for line in lines:
                line = line.strip()
                if not line or "成分名" in line: continue
                
                # 錨點匹配: (給藥方式) (3碼) (成分名)
                match = re.search(r'^(内|注|外)\s*(\d{3})\s*(.+)$', line)
                if match:
                    route, code, name = match.groups()
                    all_data.append({
                        "類別": current_cat,
                        "給藥方式": route,
                        "用途編號": code,
                        "用途說明": PURPOSE_MAP.get(code, "其他藥效類別"),
                        "成分日文名": name.strip()
                    })
                else:
                    # 跨行合併
                    if all_data and not re.match(r'^\d+$', line) and "厚生労働省" not in line:
                        all_data[-1]["成分日文名"] += line.strip()

    # 清洗日文名稱 (移除空格與尾端頁碼)
    for d in all_data:
        d["成分日文名"] = re.sub(r'\s+', '', d["成分日文名"])
        d["成分日文名"] = re.sub(r'\d+$', '', d["成分日文名"])
    
    return pd.DataFrame(all_data)

# --- 4. Streamlit UI ---
st.set_page_config(layout="wide", page_title="505項醫藥品對照")
st.title("💊 安定確保醫藥品全量對照 (Azure + KEGG)")
st.write("解析規則：以「內/注/外」定標，自動對照三碼用途說明。")

f = st.file_uploader("上傳 PDF (000785498.pdf)", type=['pdf'])

if f:
    if 'raw_df' not in st.session_state:
        with st.spinner("正在執行定標解析..."):
            st.session_state.raw_df = parse_full_medicine_pdf(f)
    
    df = st.session_state.raw_df
    st.success(f"✅ 成功提取 {len(df)} 項成分！")
    st.dataframe(df, use_container_width=True)

    if st.button("🚀 開始全量執行翻譯與官方名稱對照"):
        results = []
        bar = st.progress(0)
        status = st.empty()
        
        for i, row in df.iterrows():
            jp_name = row["成分日文名"]
            status.text(f"處理中 ({i+1}/{len(df)}): {jp_name}")
            
            en_name, source = get_english_name(jp_name)
            
            results.append({
                "類別": row["類別"], "給藥方式": row["給藥方式"],
                "用途編號": row["用途編號"], "用途說明": row["用途說明"],
                "成分日文名": jp_name, "成分英文名": en_name, "來源": source
            })
            bar.progress((i + 1) / len(df))
            
        final_df = pd.DataFrame(results)
        st.success("🎉 全量對照完成！")
        st.dataframe(final_df, use_container_width=True)
        
        # 下載成果
        out = io.BytesIO()
        with pd.ExcelWriter(out, engine='xlsxwriter') as writer:
            final_df.to_excel(writer, index=False)
        st.download_button("📥 下載完整 Excel 報告", out.getvalue(), "Medicine_Full_Report.xlsx")
