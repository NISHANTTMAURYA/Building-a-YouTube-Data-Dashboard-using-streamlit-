
if not final_channel_id:
    st.stop()

if final_channel_id:
    with st.spinner("Fetching channel..."):
        channel_info = fetch_channel(youtube, channel_id=final_channel_id)

    if not channel_info:
        st.warning("Channel not found. Check ID/username or try OAuth for private channel metrics.")
        st.stop()

    # Premium header presentation
    st.markdown("---")
    header_cols = st.columns([1.5, 6.5, 2])
    with header_cols[0]:
        if channel_info.get("logo"):
            r = requests.get(channel_info["logo"])
            img = Image.open(BytesIO(r.content))
            st.image(img, use_container_width=True)
    with header_cols[1]:
        st.markdown(f"<h1 style='margin-bottom: 0;'>{channel_info['title']}</h1>", unsafe_allow_html=True)
        st.caption(f"🌍 **{channel_info.get('country', 'Not specified')}** &nbsp; | &nbsp; 🏷️ **{str(channel_info.get('keywords', 'No tags'))[:80]}...**")
        desc = channel_info.get("description", "")
        if desc:
            st.write(desc[:250] + "..." if len(desc) > 250 else desc)
    with header_cols[2]:
        st.markdown("<br>", unsafe_allow_html=True)
        st.metric("Subscribers", f"{channel_info['subs']:,}")
        st.metric("Total Views", f"{channel_info['views']:,}")
        st.metric("Total Videos", f"{channel_info['videos']:,}")
    
    st.markdown("---")

    # Fetch main channel videos
    with st.spinner("Fetching videos..."):
        actual_channel_id = channel_info["id"]
        videos = fetch_videos_for_channel(youtube, channel_id=actual_channel_id, max_results=max_videos)
        vid_ids = [v["videoId"] for v in videos][:max_videos]
        stats_df = fetch_videos_stats(youtube, vid_ids)

    # Calculate Engagement Rate -> ((likes + comments) / views) * 100
    if not stats_df.empty:
        thumb_map = {v['videoId']: v['thumbnail'] for v in videos}
        stats_df['thumbnail'] = stats_df['videoId'].map(thumb_map)
        stats_df['publishedAt'] = pd.to_datetime(stats_df['publishedAt'])
        
        def calc_eng(row):
            v, l, c = row['views'], row['likes'], row['comments']
            if v == 0: return 0
            return ((l + c) / v) * 100
            
        stats_df['engagement_rate'] = stats_df.apply(calc_eng, axis=1)
        stats_df = stats_df.sort_values('views', ascending=False)
        
    if analysis_mode == "Single Channel Analytics":
        if stats_df.empty:
            st.info("No videos found or the videos are private.")
        else:
            st.subheader("Advanced Single Channel Analytics")
            
            # Additional KPI Averages
            avg_v = int(stats_df['views'].mean())
            avg_l = int(stats_df['likes'].mean())
            avg_c = int(stats_df['comments'].mean())
            avg_e = stats_df['engagement_rate'].mean()
            
            k1, k2, k3, k4 = st.columns(4)
            k1.metric("Average Views", f"{avg_v:,}")
            k2.metric("Average Likes", f"{avg_l:,}")
            k3.metric("Average Comments", f"{avg_c:,}")
            k4.metric("Avg Engagement Rate", f"{avg_e:.2f}%")
            
            st.markdown("<br>", unsafe_allow_html=True)
            
            best_by_views = stats_df.iloc[0]
            best_by_eng = stats_df.sort_values('engagement_rate', ascending=False).iloc[0]
            
            b1, b2 = st.columns(2)
            with b1:
                st.info(f"**Best by Views**: {best_by_views['title'][:40]}... ({best_by_views['views']:,} views)")
            with b2:
                st.success(f"**Best by Engagement**: {best_by_eng['title'][:40]}... ({best_by_eng['engagement_rate']:.2f}% ER)")

            tab1, tab2 = st.tabs(["🔥 Top Videos Table", "📈 Detailed Charts"])
            
            with tab1:
                # Format table
                display_df = stats_df[['title', 'publishedAt', 'views', 'likes', 'comments', 'engagement_rate', 'videoId']].copy()
                display_df['publishedAt'] = display_df['publishedAt'].dt.date
                display_df['engagement_rate'] = display_df['engagement_rate'].apply(lambda x: f"{x:.2f}%")
                display_df['URL'] = display_df['videoId'].apply(lambda x: f"https://youtube.com/watch?v={x}")
                st.dataframe(display_df.drop(columns=['videoId']), use_container_width=True)

            with tab2:
                c1, c2 = st.columns(2)
                with c1:
                    fig_v = px.bar(stats_df.head(10).sort_values('views', ascending=True), 
                                   x='views', y='title', orientation='h', title='Top 10 By Views')
                    fig_v.update_yaxes(showticklabels=False)
                    st.plotly_chart(fig_v, use_container_width=True)
                with c2:
                    fig_e = px.bar(stats_df.sort_values('engagement_rate', ascending=False).head(10).sort_values('engagement_rate', ascending=True), 
                                   x='engagement_rate', y='title', orientation='h', title='Top 10 By Engagement Rate')
                    fig_e.update_yaxes(showticklabels=False)
                    st.plotly_chart(fig_e, use_container_width=True)
                    
                c3, c4 = st.columns(2)
                with c3:
                    agg = stats_df.copy()
                    agg['date'] = agg['publishedAt'].dt.date
                    daily = agg.groupby('date')['views'].sum().reset_index()
                    fig_time = px.line(daily, x='date', y='views', title='Views Over Publish Date')
                    st.plotly_chart(fig_time, use_container_width=True)
                with c4:
                    fig_scatter = px.scatter(stats_df, x='likes', y='comments', size='views', hover_name='title', title='Likes vs Comments')
                    st.plotly_chart(fig_scatter, use_container_width=True)

            # Download CSV
            csv = stats_df.to_csv(index=False)
            st.download_button("Download CSV (videos stats)", csv, file_name=f"{channel_info['title']}_videos.csv", mime="text/csv")

    elif analysis_mode == "Competitor Analysis":
        st.subheader("Auto Competitor Discovery & Analysis")
        if stats_df.empty:
            st.warning("Needs recent videos to discover competitors based on titles!")
            st.stop()
            
        with st.spinner("Finding competitors via title keywords..."):
            titles = videos = stats_df['title'].tolist()
            keywords = extract_keywords(titles, top_n=5)
            st.caption(f"**Discovered Keywords:** {keywords}")
            
            comp_ids = discover_competitors(youtube, keywords, actual_channel_id, max_results=5)
            
        if not comp_ids:
            st.warning("No competitors found using these keywords.")
        else:
            with st.spinner("Fetching competitor stats..."):
                all_channels = [actual_channel_id] + comp_ids
                comp_data = []
                
                # Fetch each
                for cid in all_channels:
                    c_info = fetch_channel(youtube, channel_id=cid)
                    if not c_info: continue
                    
                    # Fetch videos stats for averages
                    c_vids = fetch_videos_for_channel(youtube, channel_id=cid, max_results=max_videos)
                    c_vid_ids = [v["videoId"] for v in c_vids][:max_videos]
                    c_df = fetch_videos_stats(youtube, c_vid_ids)
                    
                    avg_v = 0; avg_l = 0; avg_c = 0; avg_e = 0; best_vid = "N/A"
                    if not c_df.empty:
                        def calc_c_eng(row):
                            if row['views'] == 0: return 0
                            return ((row['likes'] + row['comments']) / row['views']) * 100
                        c_df['eng'] = c_df.apply(calc_c_eng, axis=1)
                        avg_v = c_df['views'].mean()
                        avg_l = c_df['likes'].mean()
                        avg_c = c_df['comments'].mean()
                        avg_e = c_df['eng'].mean()
                        best_vid = c_df.sort_values('views', ascending=False).iloc[0]['title']
                        
                    comp_data.append({
                        "Channel": c_info["title"],
                        "Subscribers": c_info["subs"],
                        "Total Views": c_info["views"],
                        "Total Videos": c_info["videos"],
                        "Avg Views": avg_v,
                        "Avg Likes": avg_l,
                        "Avg Comments": avg_c,
                        "Avg Engagement Rate": avg_e,
                        "Best Video": best_vid
                    })
                    
            comp_df = pd.DataFrame(comp_data)
            
            # --- Auto Analytics Summary (Rule-based) ---
            st.markdown("### Analytics Summary")
            highest_subs = comp_df.loc[comp_df['Subscribers'].idxmax()]
            highest_avg_views = comp_df.loc[comp_df['Avg Views'].idxmax()]
            highest_eng = comp_df.loc[comp_df['Avg Engagement Rate'].idxmax()]
            
            st.info(f"🏆 **{highest_subs['Channel']}** leads the pack with the highest subscriber base ({highest_subs['Subscribers']:,}).")
            st.info(f"👁️ **{highest_avg_views['Channel']}** has the highest average views per recent video ({int(highest_avg_views['Avg Views']):,}).")
            st.info(f"💬 **{highest_eng['Channel']}** boasts the best audience connection with an average engagement rate of {highest_eng['Avg Engagement Rate']:.2f}%.")
            
            st.markdown("### Competitor Comparison Table")
            disp_comp = comp_df.copy()
            for col in ['Avg Views', 'Avg Likes', 'Avg Comments']: disp_comp[col] = disp_comp[col].apply(lambda x: f"{int(x):,}")
            disp_comp['Avg Engagement Rate'] = disp_comp['Avg Engagement Rate'].apply(lambda x: f"{x:.2f}%")
            st.dataframe(disp_comp, use_container_width=True)
            
            # --- Competitor Charts ---
            cc1, cc2 = st.columns(2)
            with cc1:
                st.plotly_chart(px.bar(comp_df, x='Channel', y='Subscribers', title='Subscribers Comparison', color='Channel'), use_container_width=True)
                st.plotly_chart(px.bar(comp_df, x='Channel', y='Avg Views', title='Average Views Comparison (Recent)', color='Channel'), use_container_width=True)
            with cc2:
                st.plotly_chart(px.bar(comp_df, x='Channel', y='Total Views', title='Total Channel Views', color='Channel'), use_container_width=True)
                st.plotly_chart(px.bar(comp_df, x='Channel', y='Avg Engagement Rate', title='Avg Engagement Rate Comparison (Recent)', color='Channel'), use_container_width=True)

# Footer quick note
st.markdown("---")
st.caption("Built with Streamlit • Auto Competitor Discovery & Analytics.")
