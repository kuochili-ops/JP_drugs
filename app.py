import streamlit as st
import pandas as pd
import requests
import re

@st.cache_data
def download_kegg_master_list_v2():
    """修正版：下載並精確解析 KEGG 全量清單"""
    url = "https://rest.kegg.jp/list/drug_ja"
    master_dict = {}
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            for line in response.text.split('\n'):
                if '\t' in line:
                    # 格式: dr:DXXXXX \t 日文 (標籤); 英文 (標籤); 英文 (標籤)
                    parts = line.split('\t')
                    content = parts[1]
                    
                    # 1. 拆分日文與英文部分 (用分號拆)
                    sub_parts = content.split(';')
                    
                    # 提取日文 Key (第一部分括號前)
                    ja_match = re.search(r'^(.*?)(\s*\(|$)', sub_parts[0])
                    if ja_key := ja_match.group(1).strip() if ja_match else None:
                        
                        # 2. 尋找真正的英文名 (遍歷分號後的項目)
                        en_name = ""
                        for p in sub_parts:
                            # 尋找純英文字符為主的項目，並移除 (JP18), (JAN), (USP) 等
                            clean_en = re.sub(r'\(.*?\)', '', p).strip()
                            if re.search(r'[a-zA-Z]{3,}', clean_en): # 至少包含3個英文字母
                                en_name = clean_en
                                break
                        
                        if en_name:
                            master_dict[ja_key] = en_name
            return master_dict
    except:
        st.error("連線失敗")
    return {}

def smart_match_v2(ja_name, master_dict):
    if not ja_name or pd.isna(ja_name): return "N/A"
    
    # 清洗：移除括號與備註
    clean_ja = re.sub(r'[\(\（].*?[\)\）]', '', str(ja_name)).strip()
    
    # 複合藥拆分處理
    if '･' in clean_ja or '・' in clean_ja:
        parts = re.split(r'[･・]', clean_ja)
        return " / ".join([smart_match_v2(p, master_dict) for p in parts])
    
    # 1. 精確匹配
    if clean_ja in master_dict:
        return master_dict[clean_ja]
    
    # 2. 模糊匹配 (針對鹽類變體)
    for key, val in master_dict.items():
        if key in clean_ja and len(key) > 2:
            return val
            
    return f"Manual Check: {clean_ja}"

# --- UI ---
st.title("🛡️ KEGG 精準對照站 (修正解析邏輯版)")

if st.button("🔄 重新同步 KEGG 數據"):
    st.session_state['master_dict_v2'] = download_kegg_master_list_v2()
    st.success(f"同步完成！已載入 {len(st.session_state['master_dict_v2'])} 筆資料。")

f = st.file_uploader("上傳 505 項 CSV", type=['csv'])

if f and 'master_dict_v2' in st.session_state:
    df = pd.read_csv(f)
    # 移除舊的錯誤結果欄位
    df = df.loc[:, ~df.columns.str.contains('^Unnamed|來源|成分英文名')]
    
    if st.button("🚀 執行精準對照"):
        df['成分英文名'] = df['成分日文名'].apply(lambda x: smart_match_v2(x, st.session_state['master_dict_v2']))
        df['來源'] = "KEGG_Official_Corrected"
        st.dataframe(df)
        st.download_button("📥 下載修正版 CSV", df.to_csv(index=False).encode('utf-8-sig'), "Corrected_Medicine_List.csv")
