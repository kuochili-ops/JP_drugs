import streamlit as st
import pandas as pd
import requests
import io

def fetch_and_fill_kegg_data(input_df):
    # --- 1. 定義您的檔案欄位名稱 ---
    # 根據您的檔案預覽，欄位分別是 '成分名 (日)', '成分名 (英)', 'KEGG_ID'
    target_col = '成分名 (日)'
    eng_col = '成分名 (英)'
    id_col = 'KEGG_ID'

    if target_col not in input_df.columns:
        st.error(f"找不到欄位 '{target_col}'，請檢查檔案格式。")
        return None

    # --- 2. 從 KEGG 下載對照表 ---
    st.info("正在連線至 KEGG 資料庫...")
    url = "https://rest.kegg.jp/list/dr_ja"
    try:
        response = requests.get(url, timeout=15)
        response.raise_for_status()
    except Exception as e:
        st.error(f"連線失敗: {e}")
        return None

    kegg_list = []
    for line in response.text.strip().split('\n'):
        parts = line.split('\t')
        if len(parts) < 2: continue
        
        k_id = parts[0].replace("dr:", "") # 取得 Dxxxxx
        full_info = parts[1] # 取得名稱部分
        
        # 拆解名稱：例如 "アスピリン (JAN); Aspirin (USP)"
        # 拿第一個分號前的內容，再去掉括號
        jap_name_in_kegg = full_info.split(';')[0].split(' (')[0].strip()
        
        # 提取括號內的英文名
        eng_name_in_kegg = ""
        if "(" in full_info and ")" in full_info:
            eng_name_in_kegg = full_info[full_info.rfind("(")+1 : full_info.rfind(")")]
        
        kegg_list.append({
            target_col: jap_name_in_kegg, 
            'REF_ID': k_id, 
            'REF_ENG': eng_name_in_kegg
        })

    ref_df = pd.DataFrame(kegg_list).drop_duplicates(target_col)

    # --- 3. 合併與填補 ---
    # 使用左合併，將抓到的參考資料根據「成分名 (日)」對齊
    merged = pd.merge(input_df, ref_df, on=target_col, how='left')

    # 如果原本的 ID 或 英文名是空的，就填入從 KEGG 查到的資料
    merged[id_col] = merged[id_col].fillna(merged['REF_ID'])
    merged[eng_col] = merged[eng_col].fillna(merged['REF_ENG'])

    # 移除暫存欄位
    result = merged.drop(columns=['REF_ID', 'REF_ENG'])
    return result

# --- Streamlit 介面 ---
st.title("💊 KEGG 藥品資料補齊工具")
st.write("針對《日本醫學會推薦必要藥品清單》自動填補空缺的 KEGG_ID 與 英文名")

uploaded_file = st.file_uploader("請上傳您的 CSV 檔案", type=['csv'])

if uploaded_file:
    # 讀取 CSV
    df = pd.read_csv(uploaded_file)
    
    st.subheader("原始資料預覽 (前5筆)")
    st.dataframe(df.head())

    if st.button("開始執行自動補齊"):
        with st.spinner('比對中，請稍候...'):
            final_df = fetch_and_fill_kegg_data(df)
            
            if final_df is not None:
                st.success("處理完成！")
                
                # 顯示統計：補齊了多少筆
                filled_count = final_df['KEGG_ID'].count() - df['KEGG_ID'].count()
                st.write(f"💡 本次成功為 {filled_count} 個項目補齊了資訊。")
                
                st.subheader("補齊後的完整結果")
                st.dataframe(final_df)

                # 提供下載
                output = io.BytesIO()
                final_df.to_csv(output, index=False, encoding='utf-8-sig')
                st.download_button(
                    label="📥 下載更新後的 CSV 檔案",
                    data=output.getvalue(),
                    file_name="KEGG_Updated_List.csv",
                    mime="text/csv"
                )
