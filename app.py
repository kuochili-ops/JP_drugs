import streamlit as st
import pandas as pd
import requests
import io
import re

# 1. 基礎工具函數：處理全形轉半形
def zen_to_han(text):
    if not isinstance(text, str): return str(text)
    return text.translate(str.maketrans(
        '０１２３４５６７８９ＡＢＣＤＥＦＧＨＩＪＫＬＭＮＯＰＱＲＳＴＵＶＷＸＹＺ（）',
        '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ()'
    )).strip()

# 2. 核心補齊函數
def fetch_and_fill_kegg_data_smart(input_df):
    target_col = '成分名 (日)'
    eng_col = '成分名 (英)'
    id_col = 'KEGG_ID'

    # 從 KEGG 抓取最新對照表
    url = "https://rest.kegg.jp/list/dr_ja"
    try:
        response = requests.get(url, timeout=15)
        response.raise_for_status()
    except:
        st.error("無法連線至 KEGG 資料庫，請檢查網路。")
        return None

    # 預處理 KEGG 資料
    kegg_ref = []
    for line in response.text.strip().split('\n'):
        parts = line.split('\t')
        if len(parts) < 2: continue
        d_id = parts[0].replace("dr:", "")
        full_info = parts[1]
        
        # 提取括號內的英文名 (JAN/USP等)
        eng_match = re.search(r'\(([^)]+)\)$', full_info)
        eng_name = eng_match.group(1) if eng_match else ""
        
        kegg_ref.append({
            'id': "dr_ja:" + d_id,
            'clean_full': zen_to_han(full_info),
            'eng': eng_name
        })

    # 執行補齊邏輯
    progress_bar = st.progress(0)
    total_rows = len(input_df)
    
    for i, row in input_df.iterrows():
        # 若已存在 ID 則跳過
        if pd.notna(row.get(id_col)) and str(row.get(id_col)).strip() != "":
            progress_bar.progress((i + 1) / total_rows)
            continue
            
        search_name = zen_to_han(str(row[target_col]))
        
        # 模糊比對：搜尋 KEGG 名稱是否包含藥品名
        for ref in kegg_ref:
            if search_name in ref['clean_full']:
                input_df.at[i, id_col] = ref['id']
                if pd.isna(row.get(eng_col)) or str(row.get(eng_col)).strip() == "":
                    input_df.at[i, eng_col] = ref['eng']
                break
        
        progress_bar.progress((i + 1) / total_rows)
    
    return input_df

# --- 3. Streamlit 使用者介面 ---
st.set_page_config(page_title="KEGG 藥品資料補齊器", layout="wide")
st.title("💊 智慧型藥品資料補齊工具")
st.markdown("針對 `成分名 (日)` 欄位進行模糊比對，自動補全 `KEGG_ID` 與 `英文成分名`。")

uploaded_file = st.file_uploader("請上傳您的 CSV 檔案", type=['csv'])

if uploaded_file:
    df = pd.read_csv(uploaded_file)
    
    st.write("### 原始資料預覽")
    st.dataframe(df.head(5))

    if st.button("啟動智慧補齊"):
        # 統計處理前的狀態
        initial_missing = df['KEGG_ID'].isna().sum()
        
        with st.spinner("正在檢索 KEGG 資料庫並進行模糊比對..."):
            result_df = fetch_and_fill_kegg_data_smart(df.copy())
            
            if result_df is not None:
                final_missing = result_df['KEGG_ID'].isna().sum()
                filled_count = initial_missing - final_missing
                
                st.success("處理完成！")
                
                # --- 統計儀表板 ---
                
                m1, m2, m3 = st.columns(3)
                m1.metric("成功補齊項數", f"{filled_count} 項")
                m2.metric("尚未配對項數", f"{final_missing} 項", delta=f"-{filled_count}", delta_color="normal")
                m3.metric("資料總筆數", f"{len(result_df)} 筆")
                
                # 顯示未配對清單
                if final_missing > 0:
                    with st.expander("查看無法配對的項目清單"):
                        unmatched = result_df[result_df['KEGG_ID'].isna()][['成分名 (日)', '成分名 (英)']]
                        st.table(unmatched)
                
                st.subheader("補齊後的資料結果")
                st.dataframe(result_df)
                
                # 下載按鈕
                csv_buffer = io.BytesIO()
                result_df.to_csv(csv_buffer, index=False, encoding='utf-8-sig')
                st.download_button(
                    label="📥 下載修正後的 CSV",
                    data=csv_buffer.getvalue(),
                    file_name="KEGG_Updated_List.csv",
                    mime="text/csv"
                )
