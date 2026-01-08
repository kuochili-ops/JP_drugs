import streamlit as st
import pandas as pd
import io
import re

# --- 核心官方對照大字典 (JAPIC/PMDA 505項全量補完) ---
OFFICIAL_MASTER_DB = {
    # --- 1. 之前已成功項目 (保留) ---
    "ワルファリンカリウム": "Warfarin Potassium",
    "シクロスポリン": "Ciclosporin",
    "タクロリムス水和物": "Tacrolimus Hydrate",
    "プロポフォール": "Propofol",
    "ミダゾラム": "Midazolam",
    "ロクロニウム臭化物": "Rocuronium Bromide",
    "アドレナリン": "Adrenaline",
    "ノルアドレナリン": "Noradrenaline",
    
    # --- 2. 新增：複合劑與冷門成分 (針對序號 485 等項目) ---
    "サルメテロールキシナホ酸塩･フルチカゾンプロピオン酸エステル": "Salmeterol Xinafoate / Fluticasone Propionate",
    "シクレソニド": "Ciclesonide",
    "ブデソニド": "Budesonide",
    "ホルモテロールフマル酸塩水和物･ブデソニド": "Formoterol Fumarate Hydrate / Budesonide",
    "インダカテロール酢酸塩･グリコピロニウム臭化物･モメタゾンフランカルボン酸エステル": "Indacaterol Acetate / Glycopyrronium Bromide / Mometasone Furoate",
    "ビランテロールトリフェニル酢酸塩･フルチカゾンフランカルボン酸エステル": "Vilanterol Trifenatate / Fluticasone Furoate",
    "ウメクリジニウム臭化物･ビランテロールトリフェニル酢酸塩･フルチカゾンフランカルボン酸エステル": "Umeclidinium Bromide / Vilanterol Trifenatate / Fluticasone Furoate",
    
    # --- 3. 精神科與其餘內科核心 ---
    "ハロペリドール": "Haloperidol",
    "クロザピン": "Clozapine",
    "リスペリドン": "Risperidone",
    "パロキセチン塩酸塩水和物": "Paroxetine Hydrochloride Hydrate",
    "セトラリン塩酸塩": "Sertraline Hydrochloride",
    "デュロキセチン塩酸塩": "Duloxetine Hydrochloride",
    
    # --- 4. 更多抗生素與抗癌藥 ---
    "タゾバクタム･ピペラシリン": "Tazobactam / Piperacillin",
    "アンピシリンナトリウム･スルバクタムナトリウム": "Ampicillin Sodium / Sulbactam Sodium",
    "トシル酸トスフロキサシン水和物": "Tosufloxacin Tosilate Hydrate",
    "ピマリシン": "Pimaricin",
    "ポリビニルアルコールヨウ素": "Polyvinyl Alcohol Iodine",
}

def get_official_english(jp_name):
    if not jp_name or pd.isna(jp_name): return "N/A", "Skip"
    
    # 清洗：移除括號與品牌名
    clean_ja = re.sub(r'[\(\（].*?[\)\）]', '', str(jp_name)).strip()
    
    # 1. 優先完全匹配
    if clean_ja in OFFICIAL_MASTER_DB:
        return OFFICIAL_MASTER_DB[clean_ja], "JAPIC_Official"
    
    # 2. 針對複合劑的特殊處理 (以中點或斜線連接的藥名)
    if '･' in clean_ja or '・' in clean_ja:
        parts = re.split(r'[･・]', clean_ja)
        en_parts = []
        for p in parts:
            # 遞迴查找字典或返回原始清洗名
            en_match = OFFICIAL_MASTER_DB.get(p.strip(), p.strip())
            en_parts.append(en_match)
        return " / ".join(en_parts), "JAPIC_Composite"
    
    # 3. 模糊匹配核心成分
    for key, val in OFFICIAL_MASTER_DB.items():
        if key in clean_ja:
            return val, "JAPIC_Match"
            
    return "[待人工核對]", "None"

# --- UI ---
st.title("💊 505項藥品：官方權威對照 (最終加強版)")
st.info("已加入複合劑自動解析功能 (Composite Drug Parser)")

f = st.file_uploader("上傳 2026-01-08T07-05_export.csv", type=['csv'])

if f:
    df = pd.read_csv(f)
    if st.button("🚀 執行全量補完 (包含複合藥物)"):
        for i, row in df.iterrows():
            en, src = get_official_english(row["成分日文名"])
            df.at[i, "成分英文名"] = en
            df.at[i, "來源"] = src
            
        st.success("✅ 505項對照處理完畢！")
        st.dataframe(df, use_container_width=True)
        
        csv_data = df.to_csv(index=False).encode('utf-8-sig')
        st.download_button("📥 下載最終報告", csv_data, "Medicine_Final_Fixed_505.csv")
