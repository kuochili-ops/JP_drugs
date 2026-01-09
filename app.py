def get_kegg_master_dict():
    url = "https://rest.kegg.jp/list/drug_ja/"
    try:
        response = requests.get(url, timeout=10)
        kegg_map = {}
        if response.status_code == 200:
            for line in response.text.strip().split('\n'):
                parts = line.split('\t')
                if len(parts) >= 2:
                    k_id = parts[0].replace('dr:', '')
                    full_names = parts[1]
                    
                    # 修正後的解析邏輯：
                    # KEGG 格式通常是：日文名 (英文名); 別名1, 別名2
                    # 先用分號切開，只拿第一組最主要的名稱
                    primary_name = full_names.split(';')[0]
                    
                    # 使用正則提取括號內的英文
                    # 匹配格式：日文名 (英文名)
                    match = re.search(r'(.+?)\s*[\(\（](.+?)[\)\）]', primary_name)
                    
                    if match:
                        jp_name = match.group(1).strip()
                        en_name = match.group(2).strip()
                        # 以日文名當 Key，存入 ID 與正確的英文名
                        kegg_map[jp_name] = {"id": k_id, "en": en_name}
        return kegg_map
    except Exception as e:
        st.error(f"無法讀取 KEGG 字典: {e}")
        return {}
