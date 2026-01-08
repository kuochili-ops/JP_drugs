import streamlit as st
import pandas as pd
import requests
import re
from urllib.parse import quote

def get_official_inn_via_kegg(ja_name):
    """
    透過 KEGG API 直接將日文片假名轉換為官方英文名 (INN)
    """
    if not ja_name or pd.isna(ja_name):
        return "N/A"

    # 清除括號內的品牌名，避免干擾匹配
    clean_ja = re.sub(r'[\(\（].*?[\)\）]', '', str(ja_name)).strip()
    
    # 處理複合劑：拆分後分別查詢再合併
    if '･' in clean_ja or '・' in clean_ja:
        parts = re.split(r'[･・]', clean_ja)
        return " / ".join([get_official_inn_via_kegg(p) for p in parts])

    try:
        # 第一步：直接搜尋日文名稱對應的 KEGG ID
        # 這是日本官方提供的 find 接口
        search_url = f"https://rest.kegg.jp/find/drug/{quote(clean_ja)}"
        response = requests.get(search_url, timeout=5)
        
        if response.status_code == 200 and response.text.strip():
            # 獲取搜尋結果的第一筆 ID (例如 dr:D00544)
            kegg_id = response.text.split('\t')[0]
            
            # 第二步：獲取該 ID 的詳細資料
            info_url = f"https://rest.kegg.jp/get/{kegg_id}"
            info_resp = requests.get(info_url, timeout=5)
            
            if info_resp.status_code == 200:
                lines = info_resp.text.split('\n')
                for line in lines:
                    # 搜尋「NAME」欄位中的英文括號部分
                    if line.startswith('NAME'):
                        # 格式通常為：NAME  ミダゾラム (Midazolam)
                        match = re.search(r'\((.*?)\)', line)
                        if match:
                            # 提取第一個分號前的名稱 (即主成分名)
                            return match.group(1).split(';')[0].strip()
        
        return f"[未查獲] {clean_ja}"

    except Exception as e:
        return f"[連線錯誤] {clean_ja}"

# --- UI 介面 ---
st.set_page_config(layout="wide")
st.title("🛡️ 505項官方對照：KEGG API 權威版")
st.info("本引擎放棄搜尋引擎爬蟲，改由日本 KEGG 官方 API 直接進行名稱解析。")

f = st.file_uploader("上傳您目前的 CSV", type=['csv'])

if f:
    df = pd.read_csv(f)
    # 移除之前失敗的測試欄位
    df = df.loc[:, ~df.columns.str.contains('^Unnamed|來源|成分英文名')]
    
    if st.button("🚀 啟動官方 API 全量解析"):
        with st.spinner('正在與日本官方伺服器連線...'):
            df['成分英文名'] = df['成分日文名'].apply(get_official_inn_via_kegg)
            df['來源'] = "Official_KEGG_API"
            
        st.success("✅ 解析完畢！")
        st.dataframe(df, use_container_width=True)
        
        csv_data = df.to_csv(index=False).encode('utf-8-sig')
        st.download_button("📥 下載最終對照版 CSV", csv_data, "Medicine_Final_Official.csv")
