def get_kegg_master_dict():
    url = "https://rest.kegg.jp/list/drug_ja/"
    kegg_map = {}
    try:
        response = requests.get(url, timeout=15)
        if response.status_code == 200:
            for line in response.text.strip().split('\n'):
                parts = line.split('\t')
                if len(parts) >= 2:
                    k_id = parts[0].replace('dr:', '')
                    full_text = parts[1]
                    
                    # --- 核心修正處：抓取分號後面的英文 ---
                    if ';' in full_text:
                        # 以分號分割，取後半部
                        en_part = full_text.split(';')[1].strip()
                        # 移除英文名稱後的 (JP18) 或 (USP) 等括號標記
                        en_name = re.sub(r'[\(\（].*?[\)\）]', '', en_part).strip()
                        
                        # 前半部為日文名稱，同樣移除括號標記作為 Key
                        jp_part = full_text.split(';')[0].strip()
                        jp_name = re.sub(r'[\(\（].*?[\)\）]', '', jp_part).strip()
                        
                        kegg_map[jp_name] = {"id": k_id, "en": en_name}
        return kegg_map
    except Exception as e:
        return {"error": str(e)}
