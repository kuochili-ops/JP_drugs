import streamlit as st
import pandas as pd
import requests
import io
import re

# 1. 基礎工具函數：處理全形轉半形，並統一標點符號
def normalize_text(text):
    if not isinstance(text, str): return str(text)
    # 轉換全形數字、英文字母與括號
    text = text.translate(str.maketrans(
        '０１２３４５６７８９ＡＢＣＤＥＦＧＨＩＪＫＬＭＮＯＰＱＲＳＴＵＶＷＸＹＺ（）',
        '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ()'
    ))
    # 統一將常見的分隔符號轉為標準中間點 '・'
    text = text.replace(' ', '').replace('　', '').replace('/', '・').replace(',', '・')
    return text.strip()

# 2. 核心比對邏輯
def smart_match(search_name, kegg_ref):
    """
    search_name: 使用者上傳的成分名
    kegg_ref: KEGG 資料庫的參考清單
    """
    normalized_search = normalize_text(search_name)
    
    # 策略 A: 完全或包含比對 (例如 "A" 包含在 "A (JAN)")
    for ref in kegg_ref:
        if normalized_search in ref['clean_full']:
            return ref['id'], ref['eng']

    # 策略 B: 複方拆解比對 (處理 "A・B" 這種情況)
    if '・' in normalized_search:
        parts = [p for p in normalized_search.split('・') if p] # 拆分成分
        for ref in kegg_ref:
            # 必須所有拆分的成分都出現在 KEGG 的名稱中 (不限順序)
            if all(part in ref['clean_full'] for part in parts):
                return ref['id'], ref['eng']
    
    return None, None

def fetch_and_fill_kegg_data_advanced(input_df):
    target_col = '成分名 (日)'
    eng_col = '成分名 (英)'
    id_col = 'KEGG_ID'

    # 下載 KEGG 對照表
    url = "https://rest.kegg.jp/list/dr_ja"
    try:
        response = requests.get(url, timeout=20)
        response.raise_for_status()
    except:
        st.error("無法連線至 KEGG 資料庫，請稍後再試。")
        return None

    # 預處理 KEGG 資料以加快速度
    kegg_ref = []
    for line in response.text.strip().split('\n'):
        parts = line.split('\t')
        if len(parts) < 2: continue
        d_id = parts[0].replace("dr:", "")
        full_info = parts[1]
        
        # 提取括號內的英文名 (JAN/USP)
        eng_match = re.search(r'\(([^)]+)\)$', full_info)
        eng_name = eng_match.group(1) if eng_match else ""
        
        kegg_ref.append({
            'id': "dr_ja:" + d_id,
            'clean_full': normalize_text(full_info),
            'eng': eng_name
        })

    # 執行補齊
    progress_bar = st.progress(0)
    total_rows = len(input_df)
    
    for i, row in input_df.iterrows():
        # 只有當 KEGG_ID 為空時才填補
        current_id = str(row.get(id_col, ""))
        if pd.isna(row.get(id_col)) or current_id.strip() == "" or current_id == "nan":
            found_id, found_eng = smart_match(row[target_col], kegg_ref)
            if found_id:
                input_df.at[i, id_col] = found_id
                # 只有當英文名也為空時才補
                if pd.isna(row.get(eng_col)) or str(row.get(eng_col)).strip() == "":
                    input_df.at[i, eng_col] = found_eng
        
        progress_bar.progress((i + 1) / total_rows)
    
    return input_df

# --- 3. Streamlit UI ---
st.set_page_config(page_title="藥品資料智慧補齊器", layout="wide")
st.title("💊 智慧型藥品資料補齊工具 (複方加強版)")
st.markdown("""
本工具會自動補齊 `KEGG_ID` 與 `成分名 (英)`：
- **模糊比對**：自動處理全形數字 (４) 與半形 (4) 的差異。
- **複方支援**：自動拆解 `・` 隔開的成分並進行交叉檢索。
""")

uploaded_file = st.file_uploader("上傳 CSV 檔案 (需包含 '成分名 (日)' 欄位)", type=['csv'])

if uploaded_file:
    # 讀取資料
    df = pd.read_csv(uploaded_file)
    
    st.write("### 原始資料預覽")
    st.dataframe(df.head(5))

    if st.button("啟動智慧補齊"):
        # 紀錄原始狀態
        initial_missing = df['KEGG_ID'].isna().sum()
        
        with st.spinner("正在檢索 KEGG 並分析複方成分..."):
            result_df = fetch_and_fill_kegg_data_advanced(df.copy())
            
            if result_df is not None:
                # 計算結果
                final_missing = result_df['KEGG_ID'].isna().sum()
                filled_count = initial_missing - final_missing
                
                st.success("補齊程序執行完畢！")
                
                # --- 統計面板 ---
                col1, col2, col3 = st.columns(3)
                col1.metric("成功補齊數量", f"{filled_count} 項")
                col2.metric("尚未配對數量", f"{final_missing} 項", delta=f"-{filled_count}", delta_color="normal")
                col3.metric("資料總筆數", f"{len(result_df)} 筆")
                
                # --- 顯示未配對清單 ---
                if final_missing > 0:
                    with st.expander("🔍 查看無法配對的項目 (建議手動檢查)"):
                        unmatched = result_df[result_df['KEGG_ID'].isna()][['成分名 (日)', '成分名 (英)']]
                        st.table(unmatched)
                
                st.subheader("補齊後的資料結果")
                st.dataframe(result_df)
                
                # 下載按鈕
                csv_buffer = io.BytesIO()
                result_df.to_csv(csv_buffer, index=False, encoding='utf-8-sig')
                st.download_button(
                    label="📥 下載更新後的 CSV",
                    data=csv_buffer.getvalue(),
                    file_name="KEGG_Updated_List.csv",
                    mime="text/csv"
                )
