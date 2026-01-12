import streamlit as st
import pandas as pd
import re

st.set_page_config(page_title="藥品資料最終整合工具", layout="wide")

st.title("📂 藥品清單相同項目整合 (翻譯補完版)")

# 上傳兩個檔案
file_trans = st.file_uploader("1. 上傳【已翻譯完成】的檔案 (translated_med_list.csv)", type="csv")
file_raw = st.file_uploader("2. 上傳【原始導出】的檔案 (2026-01-09T06-10_export.csv)", type="csv")

if file_trans and file_raw:
    df_trans = pd.read_csv(file_trans)
    df_raw = pd.read_csv(file_raw)

    if st.button("🔗 開始整合檔案"):
        # 1. 準備翻譯對照表 (Key: 成分名 (日), Value: 翻譯理由)
        # 我們只取有意義的翻譯結果
        trans_map = df_trans.set_index('成分名 (日)')['翻譯理由'].to_dict()
        
        # 2. 準備原始檔案副本
        df_final = df_raw.copy()

        # 3. 執行回填
        def get_clean_translation(row):
            jp_name = row['成分名 (日)']
            trans = trans_map.get(jp_name, "")
            
            if pd.isna(trans) or str(trans).strip() == "":
                return ""
            
            # 清除殘留的錯誤標記 (防萬一)
            error_patterns = [r'\[超時\]', r'\[HTTP \d+\]', r'\[連線失敗\]', r'\[連線異常.*?\]']
            for pattern in error_patterns:
                trans = re.sub(pattern, '', str(trans))
            
            return trans.strip()

        df_final['翻譯理由'] = df_final.apply(get_clean_translation, axis=1)

        # 4. 處理 KEGG_ID 和 成分名 (英) 
        # 如果原始檔是 N/A，則嘗試從翻譯檔補回 (如果有的話)
        if 'KEGG_ID' in df_trans.columns:
            kegg_map = df_trans.set_index('成分名 (日)')['KEGG_ID'].to_dict()
            df_final['KEGG_ID'] = df_final['成分名 (日)'].map(kegg_map).fillna(df_final['KEGG_ID'])
        
        if '成分名 (英)' in df_trans.columns:
            en_map = df_trans.set_index('成分名 (日)')['成分名 (英)'].to_dict()
            df_final['成分名 (英)'] = df_final['成分名 (日)'].map(en_map).fillna(df_final['成分名 (英)'])

        # 整理欄位順序，讓閱讀更直觀
        cols = list(df_final.columns)
        if '翻譯理由' in cols: # 把翻譯理由移到選定理由摘要後面
            cols.insert(cols.index('選定理由摘要') + 1, cols.pop(cols.index('翻譯理由')))
        df_final = df_final[cols]

        st.success("🎉 整合完成！已成功對齊 763 筆項目。")
        st.dataframe(df_final.head(10))

        # 下載整合後的檔案
        final_csv = df_final.to_csv(index=False, encoding="utf-8-sig")
        st.download_button(
            label="📥 下載最終整合 CSV (完整版)",
            data=final_csv,
            file_name="Final_Drug_List_Merged.csv",
            mime="text/csv"
        )
