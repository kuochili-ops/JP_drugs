import streamlit as st
import pandas as pd
import requests
import re
from bs4 import BeautifulSoup

def fetch_kegg_by_japic(japic_code):
    """
    透過 japic_code 直接從 KEGG/JAPIC 抓取標準英文名稱
    """
    if not japic_code or pd.isna(japic_code):
        return None
    
    # 格式化 code 為 8 位數 (補零)
    code = str(int(float(japic_code))).zfill(8)
    url = f"https://www.kegg.jp/medicus-bin/japic_med?japic_code={code}"
    
    try:
        response = requests.get(url, timeout=5)
        response.encoding = 'utf-8' # 確保日文不亂碼
        
        if response.status_code == 200:
            # 尋找「一般名」欄位中的英文部分
            # 通常在括號內，例如: ミダゾラム (Midazolam)
            soup = BeautifulSoup(response.text, 'html.parser')
            content = soup.get_text()
            
            # 使用正規表達式抓取一般名欄位後的英文
            match = re.search(r'一般名.*?\((\w+)\)', content)
            if match:
                return match.group(1)
            
            # 備案：抓取頁面中所有英文字母組成的可能藥名
            match_alt = re.search(r'\[JAN:(.*?)\]', content)
            if match_alt:
                return match_alt.group(1).strip()
                
        return "Not Found"
    except:
        return "Connection Error"

# --- UI ---
st.set_page_config(layout="wide")
st.title("💊 JAPIC Code 精準對照工具")
st.info("根據您的發現：輸入 8 位 JAPIC Code，自動獲取 KEGG 官方英文藥名。")

f = st.file_uploader("上傳您目前的 CSV", type=['csv'])

if f:
    df = pd.read_csv(f)
    # 確保有 'japic_code' 這一欄，如果沒有就建立
    if 'japic_code' not in df.columns:
        df['japic_code'] = ""

    st.write("### 編輯區：請在下方表格填入您搜尋到的 JAPIC Code")
    edited_df = st.data_editor(df, use_container_width=True, num_rows="dynamic")

    if st.button("🚀 根據 JAPIC Code 抓取英文名"):
        with st.spinner('正在從 KEGG 官方資料庫提取數據...'):
            for i, row in edited_df.iterrows():
                code = row.get('japic_code')
                if code and str(code).strip():
                    en_name = fetch_kegg_by_japic(code)
                    edited_df.at[i, '成分英文名'] = en_name
                    edited_df.at[i, '來源'] = "KEGG_JAPIC_Official"
        
        st.success("✅ 官方對照完成！")
        st.dataframe(edited_df)
        
        csv_data = edited_df.to_csv(index=False).encode('utf-8-sig')
        st.download_button("📥 下載最終校正版 CSV", csv_data, "Medicine_JAPIC_Fixed.csv")
