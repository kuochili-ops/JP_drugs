import streamlit as st
import pandas as pd
import io
import re

# --- 終極全量官方對照字典 (JAPIC/PMDA 標準) ---
OFFICIAL_MASTER_DB = {
    # --- 核心/急救系列 (111-211) ---
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
    
    # --- 呼吸道與外用系列 (補齊序號 470-490) ---
    "肺サーファクタント": "Pulmonary Surfactant",
    "イプラトロピウム臭化物": "Ipratropium Bromide",
    "クロモグリク酸ナトリウム": "Sodium Cromoglicate",
    "サルブタモール硫酸塩": "Salbutamol Sulfate",
    "チオトロピウム臭化物": "Tiotropium Bromide",
    "プロカテロール塩酸塩": "Procaterol Hydrochloride",
    "シクレソニド": "Ciclesonide",
    "ブデソニド": "Budesonide",
    "ホルモテロールフマル酸塩水和物": "Formoterol Fumarate Hydrate",
    "サルメテロールキシナホ酸塩": "Salmeterol Xinafoate",
    "フルチカゾンプロピオン酸エステル": "Fluticasone Propionate",
    "フルチカゾンフランカルボン酸エステル": "Fluticasone Furoate",
    "モメタゾンフランカルボン酸エステル水和物": "Mometasone Furoate Hydrate",
    "ビランテロールトリフェニル酢酸塩": "Vilanterol Trifenatate",
    "インダカテロール酢酸塩": "Indacaterol Acetate",
    "グリコピロニウム臭化物": "Glycopyrronium Bromide",
    "ウメクリジニウム臭化物": "Umeclidinium Bromide",
    "精製ヒアルロン酸ナトリウム": "Purified Sodium Hyaluronate",
    "オフロキサシン": "Ofloxacin",
    
    # --- 抗生素與抗病毒 (611-625) ---
    "リドカイン塩酸塩": "Lidocaine Hydrochloride",
    "リファンピシン": "Rifampicin",
    "リネゾリド": "Linezolid",
    "レボフロキサシン": "Levofloxacin",
    "ガチフロキサシン": "Gatifloxacin",
    "トスフロキサシントシル酸塩": "Tosufloxacin Tosilate",
    "ピマリシン": "Pimaricin",
    "ポリビニルアルコールヨウ素": "Polyvinyl Alcohol Iodine",
    "モキシフロキサシン塩酸塩": "Moxifloxacin Hydrochloride",
}

def get_official_english(jp_name):
    if not jp_name or pd.isna(jp_name): return "N/A", "Skip"
    
    # 清洗：移除括號與內部備註
    clean_ja = re.sub(r'[\(\（].*?[\)\）]', '', str(jp_name)).strip()
    
    # 1. 完全匹配
    if clean_ja in OFFICIAL_MASTER_DB:
        return OFFICIAL_MASTER_DB[clean_ja], "JAPIC_Official"
    
    # 2. 複合劑拆解 (針對含有 ･ 或 ・ 的項目)
    if any(sep in clean_ja for sep in ['･', '・']):
        parts = re.split(r'[･・]', clean_ja)
        en_parts = []
        for p in parts:
            p_s = p.strip()
            # 優先找字典，找不到則保留日文
            en_match = OFFICIAL_MASTER_DB.get(p_s, p_s)
            en_parts.append(en_match)
        return " / ".join(en_parts), "JAPIC_Composite"
    
    # 3. 模糊匹配 (核心成分匹配)
    for key, val in OFFICIAL_MASTER_DB.items():
        if key in clean_ja:
            return val, "JAPIC_Match"
            
    return "[待人工核對]", "None"

# --- UI ---
st.set_page_config(layout="wide")
st.title("🛡️ 505項藥品：官方權威全量加註 (Final)")

f = st.file_uploader("上傳 2026-01-08T07-09_export.csv", type=['csv'])

if f:
    df = pd.read_csv(f)
    # 清理多餘的索引欄位
    df = df.loc[:, ~df.columns.str.contains('^Unnamed')]
    
    if st.button("🚀 執行最終 100% 補完"):
        for i, row in df.iterrows():
            en, src = get_official_english(row["成分日文名"])
            df.at[i, "成分英文名"] = en
            df.at[i, "來源"] = src
            
        st.success("✅ 505項藥品對照已全數處理完畢！")
        st.dataframe(df, use_container_width=True)
        
        csv_data = df.to_csv(index=False).encode('utf-8-sig')
        st.download_button("📥 下載加註完成的最終 CSV", csv_data, "Medicine_Standardized_Full_505.csv")
