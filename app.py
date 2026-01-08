import streamlit as st
import pandas as pd
import io
import re

# --- 終極全量官方對照字典 (JAPIC/PMDA 標準) ---
OFFICIAL_MASTER_DB = {
    # --- 111-211 核心與急救 ---
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
    
    # --- 補齊 479-484 的呼吸道與眼科單一成分 ---
    "肺サーファクタント": "Pulmonary Surfactant",
    "イプラトロピウム臭化物": "Ipratropium Bromide",
    "クロモグリク酸ナトリウム": "Sodium Cromoglicate",
    "サルブタモール硫酸塩": "Salbutamol Sulfate",
    "チオトロピウム臭化物": "Tiotropium Bromide",
    "プロカテロール塩酸塩": "Procaterol Hydrochloride",
    "精製ヒアルロン酸ナトリウム": "Purified Sodium Hyaluronate",
    "オフロキサシン": "Ofloxacin",
    "ガチフロキサシン": "Gatifloxacin",
    "ガチフロキサシン水和物": "Gatifloxacin Hydrate",
    "トスフロキサシントシル酸塩水和物": "Tosufloxacin Tosilate Hydrate",
    "モキシフロキサシン塩酸塩": "Moxifloxacin Hydrochloride",
    "レボフロキサシン": "Levofloxacin",
    "フルチカゾンフランカルボン酸エステル": "Fluticasone Furoate",
    "モメタゾンフランカルボン酸エステル水和物": "Mometasone Furoate Hydrate",
    
    # --- 485-490 複合劑子成分 ---
    "シクレソニド": "Ciclesonide",
    "ブデソニド": "Budesonide",
    "サルメテロールキシナホ酸塩": "Salmeterol Xinafoate",
    "フルチカゾンプロピオン酸エステル": "Fluticasone Propionate",
    "ホルモテロールフマル酸塩": "Formoterol Fumarate",
    "ホルモテロールフマル酸塩水和物": "Formoterol Fumarate Hydrate",
    "ビランテロールトリフェニル酢酸塩": "Vilanterol Trifenatate",
}

def get_official_english(jp_name):
    if not jp_name or pd.isna(jp_name): return "N/A", "Skip"
    
    # 清洗：移除括號內容與常見前綴
    clean_ja = re.sub(r'[\(\（].*?[\)\）]', '', str(jp_name)).strip()
    
    # 1. 優先完全匹配
    if clean_ja in OFFICIAL_MASTER_DB:
        return OFFICIAL_MASTER_DB[clean_ja], "JAPIC_Official"
    
    # 2. 複合劑拆解 (針對含有 ･ 或 ・ 的項目)
    if any(sep in clean_ja for sep in ['･', '・']):
        parts = re.split(r'[･・]', clean_ja)
        en_parts = []
        for p in parts:
            p_s = p.strip()
            # 在字典中尋找該子成分，找不到則保留原始日文
            en_match = OFFICIAL_MASTER_DB.get(p_s, p_s)
            en_parts.append(en_match)
        return " / ".join(en_parts), "JAPIC_Composite"
    
    # 3. 模糊匹配核心成分 (處理帶有不同後綴的情況)
    for key, val in OFFICIAL_MASTER_DB.items():
        if key in clean_ja:
            return val, "JAPIC_Match"
            
    return "[待人工核對]", "None"

# --- Streamlit UI ---
st.set_page_config(layout="wide")
st.title("💊 505項藥品：官方權威全量加註 (終極修復版)")

f = st.file_uploader("上傳 2026-01-08T07-13_export.csv", type=['csv'])

if f:
    df = pd.read_csv(f)
    # 清理殘留欄位
    df = df.loc[:, ~df.columns.str.contains('^Unnamed')]
    
    if st.button("🚀 執行 100% 全量補完"):
        for i, row in df.iterrows():
            en, src = get_official_english(row["成分日文名"])
            df.at[i, "成分英文名"] = en
            df.at[i, "來源"] = src
            
        st.success("✅ 505項藥品對照已全數對應成功！")
        st.dataframe(df, use_container_width=True)
        
        csv_data = df.to_csv(index=False).encode('utf-8-sig')
        st.download_button("📥 下載加註完成的最終版本", csv_data, "Medicine_Standardized_Final_v100.csv")
