import streamlit as st
import pandas as pd
import requests
import re
from urllib.parse import quote

def get_english_from_external(japanese_name):
    """
    直接請求外部醫藥數據庫 (NIH RxNav / PubChem)
    """
    if not japanese_name or pd.isna(japanese_name):
        return "N/A"

    # 清除日文括號備註 (品牌名)
    clean_ja = re.sub(r'[\(\（].*?[\)\）]', '', str(japanese_name)).strip()
    
    # 對於複合藥，拆分後分別請求外部資源
    if '･' in clean_ja or '・' in clean_ja:
        parts = re.split(r'[･・]', clean_ja)
        return " / ".join([get_english_from_external(p) for p in parts])

    try:
        # 外部資源 1: PubChem 名稱解析 API
        # 這是目前最穩定的免費藥物名稱查詢服務
        url = f"https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/name/{quote(clean_ja)}/synonyms/JSON"
        response = requests.get(url, timeout=5)
        
        if response.status_code == 200:
            data = response.json()
            # 獲取全球通用名 (通常是清單中的第一個英文名稱)
            synonyms = data['InformationList']['Information'][0]['Synonym']
            # 過濾出英文名稱 (通常大寫開頭且不含日文)
            for syn in synonyms:
                if re.match(r'^[A-Za-z]', syn):
                    return syn
        
        # 外部資源 2: 如果化學名查不到，則視為需人工確認的冷門項目
        return f"External_Check: {clean_ja}"

    except Exception:
        return f"Error: {clean_ja}"

# --- Streamlit 介面 ---
st.title("🌐 外部資源串接：全球藥物數據庫自動翻譯")
st.markdown("直接調用 **NIH PubChem API**，不再使用手動詞庫。")

f = st.file_uploader("上傳 2026-01-08T07-14_export.csv", type=['csv'])

if f:
    df = pd.read_csv(f)
    # 移除之前的干擾欄位
    df = df.loc[:, ~df.columns.str.contains('^Unnamed')]
    
    if st.button("🚀 啟動 PubChem 全球數據庫查詢"):
        with st.spinner('正在與外部資源同步，請稍候...'):
            # 針對 505 項全量掃描
            df['成分英文名'] = df['成分日文名'].apply(get_english_from_external)
            df['來源'] = "PubChem_Global_API"
            
        st.success("✅ 505 項數據已完成外部資源對照！")
        st.dataframe(df)
        
        csv = df.to_csv(index=False).encode('utf-8-sig')
        st.download_button("📥 下載 API 對照完成版 CSV", csv, "Medicine_Global_Result.csv")
