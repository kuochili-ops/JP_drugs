import streamlit as st
import pandas as pd
import re
from urllib.parse import quote

def generate_official_links(ja_name):
    if not ja_name or pd.isna(ja_name):
        return "N/A", "N/A"
    
    # 清洗：移除括號備註 (如ブランド名)
    clean_ja = re.sub(r'[\(\（].*?[\)\）]', '', str(ja_name)).strip()
    
    # 1. 生成 Google 搜尋連結 (依據您的發現：成分名 + japic)
    google_search_url = f"https://www.google.com/search?q={quote(clean_ja + ' japic')}"
    
    # 2. 生成 KEGG Medicus 直接搜尋連結 (日本藥典官方介面)
    kegg_medicus_url = f"https://www.kegg.jp/medicus-bin/search_medicus?search_string={quote(clean_ja)}&type=drug"
    
    return google_search_url, kegg_medicus_url

# --- UI 介面 ---
st.set_page_config(layout="wide")
st.title("🔎 505項藥品：官方資料庫快速核對工具")
st.markdown(f"根據您的發現：直接連結至 [JAPIC/KEGG](https://www.kegg.jp/) 獲取 100% 準確的 JAN/INN 英文名。")

f = st.file_uploader("上傳您目前的 CSV", type=['csv'])

if f:
    df = pd.read_csv(f)
    # 清理舊的無用欄位
    df = df.loc[:, ~df.columns.str.contains('^Unnamed|來源|成分英文名')]
    
    if st.button("🚀 生成官方對照連結"):
        links = df['成分日文名'].apply(generate_official_links)
        df['Google官方搜尋'] = [x[0] for x in links]
        df['KEGG直接核對'] = [x[1] for x in links]
        
        st.success("✅ 連結已生成！請點擊連結獲取最正確的英文名。")
        
        # 使用 Streamlit 的 link 顯示方式讓使用者好點擊
        st.dataframe(
            df,
            column_config={
                "Google官方搜尋": st.column_config.LinkColumn("Google Search"),
                "KEGG直接核對": st.column_config.LinkColumn("KEGG Official")
            },
            use_container_width=True
        )
        
        csv = df.to_csv(index=False).encode('utf-8-sig')
        st.download_button("📥 下載帶有官方連結的工作表", csv, "Medicine_Check_Links.csv")
