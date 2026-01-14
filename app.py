if st.button("啟動智慧補齊"):
    with st.spinner("智慧搜尋中..."):
        # 紀錄處理前的空值數量
        before_empty_id = df['KEGG_ID'].isna().sum()
        before_empty_eng = df['成分名 (英)'].isna().sum()
        
        result_df = fetch_and_fill_kegg_data_smart(df)
        
        if result_df is not None:
            # 紀錄處理後的空值數量
            after_empty_id = result_df['KEGG_ID'].isna().sum()
            after_empty_eng = result_df['成分名 (英)'].isna().sum()
            
            # 計算補齊數量
            filled_id = before_empty_id - after_empty_id
            
            st.success("處理完成！")
            
            # --- 顯示統計數據 ---
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("本次補齊項目", f"{filled_id} 項")
            with col2:
                st.metric("剩餘空缺 (ID)", f"{after_empty_id} 項", delta_color="inverse")
            with col3:
                st.metric("總處理筆數", f"{len(result_df)} 筆")
            
            # 針對無法配對的項目提供提示
            if after_empty_id > 0:
                st.warning(f"注意：尚有 {after_empty_id} 項藥品無法在 KEGG 找到精確匹配。")
                with st.expander("查看未配對項目清單"):
                    unmatched = result_df[result_df['KEGG_ID'].isna()][['成分名 (日)']]
                    st.write(unmatched)
            
            st.subheader("補齊後的完整結果")
            st.dataframe(result_df)
            
            # 下載按鈕...
