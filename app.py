import streamlit as st
import pandas as pd
import requests
import re

@st.cache_data
def download_kegg_master_list():
    """下載並處理 KEGG 全量對照表"""
    url = "https://rest.kegg.jp/list/drug_ja"
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            # 建立對照字典: {日文名: 英文名}
            master_dict = {}
            for line in response.text.split('\n'):
                if '\t' in line:
                    parts = line.split('\t')
                    # parts[1] 通常格式為: ミダゾラム (Midazolam)
                    full_name = parts[1]
                    match = re.search(r'(.*?) \((.*?)\)', full_name)
                    if match:
                        ja_key = match.group(1).strip()
                        en_val = match.group(2).split(';')[0].strip()
                        master_dict[ja_key] = en_val
            return master_dict
    except:
        st.error("無法下載 KEGG 官方清單，請檢查網路連線。")
    return {}

def smart_match(ja_name, master_dict):
    """智慧匹配邏輯"""
    if not ja_name or pd.isna(ja_name): return "N/A"
    
    # 清洗：移除括號與品牌
    clean_ja = re.sub(r'[\(\（].*?[\)\）]', '', str(ja_name)).strip()
    
    # 複合藥拆分
    if '･' in clean_ja or '・' in clean_ja:
        parts = re.split(r'[･・]', clean_ja)
        return " / ".join([smart_match(p, master_dict) for p in parts])
    
    # 1. 直接精確匹配
    if clean_ja in master_dict:
        return master_dict[clean_ja]
    
    # 2. 處理鹽類變體 (如: ワルファリンカリウム -> ワルファリン)
    # 嘗試從 master_dict 找包含關係
    for key in master_dict:
        if key in clean_ja and len(key) > 2:
            return master_dict[key]
            
    return f"[未查獲: {clean_ja}]"

# --- UI ---
st.title("🛡️ KEGG 全量列表同步對照站")
st.markdown("利用 `list/drug_ja` 官方全量清單，進行本地高效比對。")

if st.button("🔄 同步 KEGG 官方數據庫"):
    with st.spinner('正在下載最新官方清單...'):
        master_dict = download_kegg_master_list()
        st.session_state['master_dict'] = master_dict
        st.success(f"成功加載 {len(master_dict)} 筆官方數據！")

f = st.file_uploader("上傳您的 505 項 CSV", type=['csv'])

if f and 'master_dict' in st.session_state:
    df = pd.read_csv(f)
    df = df.loc[:, ~df.columns.str.contains('^Unnamed|來源|成分英文名')]
    
    if st.button("🚀 開始全量比對"):
        df['成分英文名'] = df['成分日文名'].apply(lambda x: smart_match(x, st.session_state['master_dict']))
        df['來源'] = "KEGG_Master_List"
        
        st.success("✅ 對照完成！")
        st.dataframe(df)
        
        csv_data = df.to_csv(index=False).encode('utf-8-sig')
        st.download_button("📥 下載對照完成版 CSV", csv_data, "Medicine_KEGG_Sync.csv")
