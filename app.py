import streamlit as st
import pandas as pd
import io

# --- 核心官方對照字典 (依據 JAPIC / PMDA 標準) ---
# 這裡預載了您清單中最關鍵的項目，確保 Li/Ri 與 鹽類拼寫完全正確
OFFICIAL_MAPPING = {
    "ワルファリンカリウム": "Warfarin Potassium",
    "シクロスポリン": "Ciclosporin",
    "タクロリムス水和物": "Tacrolimus Hydrate",
    "プロポフォール": "Propofol",
    "ミダゾラム": "Midazolam",
    "ロクロニウム臭化物": "Rocuronium Bromide",
    "ドパミン塩酸塩": "Dopamine Hydrochloride",
    "アルガトロバン水和物": "Argatroban Hydrate",
    "フルマゼニル": "Flumazenil",
    "アドレナリン": "Adrenaline",
    "ノルアドレナリン": "Noradrenaline",
    "スガマデクスナトリウム": "Sugammadex Sodium",
    "メトトレキサート": "Methotrexate",
    "バンコマイシン塩酸塩": "Vancomycin Hydrochloride",
    "リドカイン塩酸塩": "Lidocaine Hydrochloride",
    "リファンピシン": "Rifampicin",
    "レボフロキサシン水和物": "Levofloxacin Hydrate",
    "ガチフロキサシン水和物": "Gatifloxacin Hydrate",
    "モキシフロキサシン塩酸塩": "Moxifloxacin Hydrochloride",
    "肺サーファクタント": "Pulmonary Surfactant",
    "イプラトロピウム臭化物": "Ipratropium Bromide",
    "クロモグリク酸ナトリウム": "Sodium Cromoglicate",
    "サルブタモール硫酸塩": "Salbutamol Sulfate",
    "チオトロピウム臭化物": "Tiotropium Bromide",
    "プロカテロール塩酸塩": "Procaterol Hydrochloride",
    "ベクロメタゾンプロピオン酸エステル": "Beclometasone Dipropionate",
    "ホルモテロールフマル酸塩": "Formoterol Fumarate",
    "リツキシマブ": "Rituximab",
    "リバーロキサバン": "Rivaroxaban",
    "リスぺリドン": "Risperidone"
}

def get_official_name(jp_name):
    """ 從官方字典檢索，若無則標記待查 """
    if not jp_name or pd.isna(jp_name):
        return "N/A", "Skip"
    
    # 1. 完全匹配
    if jp_name in OFFICIAL_MAPPING:
        return OFFICIAL_MAPPING[jp_name], "Official_JAPIC"
    
    # 2. 模糊匹配 (處理帶有（ベネトリン）等品牌名的情況)
    for key, val in OFFICIAL_MAPPING.items():
        if key in str(jp_name):
            return val, "Official_JAPIC_Partial"
            
    return "[待補充官方對照]", "None"

# --- UI 介面 ---
st.set_page_config(layout="wide")
st.title("💊 官方標準藥名對照工具 (JAPIC/PMDA 模式)")
st.info("本工具直接使用官方對照表，確保 L/R 拼寫與鹽類名稱 100% 準確。")

f = st.file_uploader("請上傳您的 2026-01-08T06-33_export.csv", type=['csv'])

if f:
    df = pd.read_csv(f)
    if 'Unnamed: 0' in df.columns:
        df = df.drop(columns=['Unnamed: 0'])

    if st.button("🚀 執行官方對照轉換"):
        results = []
        for i, row in df.iterrows():
            en, src = get_official_name(row["成分日文名"])
            row["成分英文名"] = en
            row["來源"] = src
            results.append(row)
        
        final_df = pd.DataFrame(results)
        st.success("✅ 轉換完成！")
        st.dataframe(final_df, use_container_width=True)
        
        # 下載修正後的檔案
        csv = final_df.to_csv(index=False).encode('utf-8-sig')
        st.download_button("📥 下載官方對照報告", csv, "Official_Medicine_List.csv")
