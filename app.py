# app.py
import os
import time
from dotenv import load_dotenv
import streamlit as st
import pandas as pd
import requests
from googleapiclient.discovery import build
from PIL import Image
from io import BytesIO
import plotly.express as px
import re
from collections import Counter
from st_keyup import st_keyup

# Stop words for keyword extraction
STOP_WORDS = {"the", "is", "are", "to", "for", "and", "with", "in", "on", "of", "a", "an", "my", "your", "how", "why", "this", "that", "video", "shorts", "new", "i", "you", "it", "at", "from", "by", "as", "or", "what", "be", "do", "can", "will"}

load_dotenv()
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")  # set in .env

st.set_page_config(page_title="YouTube Data Dashboard", layout="wide")

# -----------------------
# Session State Init
# -----------------------
if "selected_channel_id" not in st.session_state:
    st.session_state.selected_channel_id = None

# Injecting Custom CSS for a Premium UI
st.markdown("""
    <style>
    /* Card effect for metrics */
    div[data-testid="stMetric"] {
        background-color: rgba(128, 128, 128, 0.05);
        border: 1px solid rgba(128, 128, 128, 0.2);
        border-radius: 10px;
        padding: 15px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        transition: transform 0.2s ease-in-out;
    }
    div[data-testid="stMetric"]:hover {
        transform: translateY(-2px);
        border-color: #ff4b4b;
    }
    /* Rounded images */
    .stImage > img {
        border-radius: 12px;
        box-shadow: 0 4px 8px rgba(0,0,0,0.1);
    }
    </style>
""", unsafe_allow_html=True)

# -----------------------
# Helper: YouTube API client (Data API v3)
# -----------------------
def get_youtube_client(api_key: str):
    return build("youtube", "v3", developerKey=api_key, cache_discovery=False)

# -----------------------
# Helper: Normalize / Resolve Channel Input
# -----------------------
@st.cache_data(ttl=600)
def normalize_channel_input(_youtube, input_text):
    """
    Parses a string (ID, URL, handle, or username) and returns the actual YouTube Channel ID.
    Uses the YouTube Data API to perform lookups if necessary.
    """
    input_text = input_text.strip()
    if not input_text:
        return None

    # 1. Direct Channel ID length typically 24 starting with UC
    if input_text.startswith("UC") and len(input_text) == 24:
        return input_text

    # 2. Channel ID from URL
    if "/channel/UC" in input_text:
        idx = input_text.find("/channel/") + 9
        return input_text[idx:idx+24]

    # 3. Handle from string or URL
    if "@" in input_text:
        m = re.search(r'(@[\w.-]+)', input_text)
        if m:
            handle = m.group(1)
            # Try to resolve handle via channels().list (forHandle)
            try:
                req = _youtube.channels().list(part="id", forHandle=handle)
                res = req.execute()
                if res.get("items"):
                    return res["items"][0]["id"]
            except:
                pass
            # Fallback to search
            try:
                req = _youtube.search().list(part="snippet", q=handle, type="channel", maxResults=1)
                res = req.execute()
                if res.get("items"):
                    return res["items"][0]["snippet"]["channelId"]
            except:
                pass

    # 4. Username from URL (/c/ /user/) or simple string fallback
    username = None
    if "/user/" in input_text:
        username = input_text.split("/user/")[-1].split("/")[0]
    elif "/c/" in input_text:
        username = input_text.split("/c/")[-1].split("/")[0]
    else:
        # If it doesn't match ID or handle, fallback to treating as username or search phrase
        username = input_text

    if username:
        try:
            req = _youtube.channels().list(part="id", forUsername=username)
            res = req.execute()
            if res.get("items"):
                return res["items"][0]["id"]
        except:
            pass

        # Final fallback: search for the username / term
        try:
            req = _youtube.search().list(part="snippet", q=username, type="channel", maxResults=1)
            res = req.execute()
            if res.get("items"):
                return res["items"][0]["snippet"]["channelId"]
        except:
            pass

    return None

# -----------------------
# Fetch channel summary (by username or channelId)
# -----------------------
@st.cache_data(ttl=600)
def fetch_channel(_youtube, for_username=None, channel_id=None):
    if channel_id:
        req = _youtube.channels().list(part="snippet,statistics,brandingSettings", id=channel_id)
    else:
        req = _youtube.channels().list(part="snippet,statistics,brandingSettings", forUsername=for_username)
    res = req.execute()
    items = res.get("items", [])
    if not items:
        return None
    c = items[0]
    snippet = c.get("snippet", {})
    stats = c.get("statistics", {})
    branding = c.get("brandingSettings", {}).get("channel", {})
    return {
        "id": c.get("id"),
        "title": snippet.get("title"),
        "description": snippet.get("description"),
        "logo": snippet.get("thumbnails", {}).get("default", {}).get("url"),
        "subs": int(stats.get("subscriberCount", 0)),
        "views": int(stats.get("viewCount", 0)),
        "videos": int(stats.get("videoCount", 0)),
        "country": snippet.get("country"),
        "keywords": branding.get("keywords"),
        "customUrl": snippet.get("customUrl")
    }

# -----------------------
# Fetch videos for channel (most recent, paginated)
# -----------------------
@st.cache_data(ttl=600)
def fetch_videos_for_channel(_youtube, channel_id, max_results=50):
    videos = []
    try:
        req = _youtube.search().list(part="snippet", channelId=channel_id, maxResults=50, order="date", type="video")
        res = req.execute()
        for item in res.get("items", []):
            vid = {
                "videoId": item["id"]["videoId"],
                "title": item["snippet"]["title"],
                "publishedAt": item["snippet"]["publishedAt"],
                "thumbnail": item["snippet"]["thumbnails"]["high"]["url"]
            }
            videos.append(vid)
    except Exception as e:
        if "quotaExceeded" in str(e):
            st.error("🚨 YouTube API Quota Exceeded! You have used up your free daily Data API requests (10,000 units). Please wait until midnight PT for a reset, or create a new API key in Google Cloud Console.")
            st.stop()
        else:
            st.error(f"Error fetching videos: {e}")
    # optionally page through nextPageToken if you want more than 50 (left as exercise)
    return videos

# -----------------------
# Fetch stats for a list of video ids (batch)
# -----------------------
@st.cache_data(ttl=600)
def fetch_videos_stats(_youtube, video_ids):
    df_rows = []
    if not video_ids:
        return pd.DataFrame()
    # chunk into groups of 50
    for i in range(0, len(video_ids), 50):
        chunk = video_ids[i:i+50]
        req = _youtube.videos().list(part="snippet,statistics,contentDetails", id=",".join(chunk))
        res = req.execute()
        for it in res.get("items", []):
            stats = it.get("statistics", {})
            snippet = it.get("snippet", {})
            df_rows.append({
                "videoId": it["id"],
                "title": snippet.get("title"),
                "publishedAt": snippet.get("publishedAt"),
                "views": int(stats.get("viewCount", 0)),
                "likes": int(stats.get("likeCount", 0)) if stats.get("likeCount") else 0,
                "comments": int(stats.get("commentCount", 0)) if stats.get("commentCount") else 0,
                "duration": it.get("contentDetails", {}).get("duration")
            })
    return pd.DataFrame(df_rows)

# -----------------------
# Search for channels
# -----------------------
@st.cache_data(ttl=600)
def search_channels(_youtube, query):
    """
    Searches for YouTube channels using the Data API.
    Returns a list of dictionaries with channel title and id, plus stats.
    """
    if not query:
        return []
    try:
        req = _youtube.search().list(part="snippet", q=query, type="channel", maxResults=5)
        res = req.execute()
        
        channel_ids = [item["snippet"]["channelId"] for item in res.get("items", [])]
        if not channel_ids:
            return []
        
        # Batch fetch for details like subscribers and handle/customUrl
        req_details = _youtube.channels().list(part="snippet,statistics", id=",".join(channel_ids))
        res_details = req_details.execute()
        
        results = []
        for c in res_details.get("items", []):
            snippet = c.get("snippet", {})
            stats = c.get("statistics", {})
            results.append({
                "title": snippet.get("title"),
                "channelId": c.get("id"),
                "thumbnail": snippet.get("thumbnails", {}).get("default", {}).get("url"),
                "customUrl": snippet.get("customUrl"),
                "subs": int(stats.get("subscriberCount", 0))
            })
            
        # Re-order to match original search result rank
        results_dict = {r["channelId"]: r for r in results}
        return [results_dict[cid] for cid in channel_ids if cid in results_dict]
    except Exception as e:
        return []

# -----------------------

# -----------------------
# Auto Competitor Discovery Helpers
# -----------------------
def extract_keywords(titles, top_n=5):
    words = []
    for t in titles:
        clean_t = re.sub(r'[^\w\s]', '', t.lower())
        words.extend(clean_t.split())
    words = [w for w in words if w not in STOP_WORDS and len(w) > 2]
    most_common = Counter(words).most_common(top_n)
    return " ".join([w[0] for w in most_common])

@st.cache_data(ttl=600)
def discover_competitors(_youtube, keywords, original_channel_id, max_results=5):
    if not keywords: return []
    try:
        req = _youtube.search().list(part="snippet", q=keywords, type="channel", maxResults=max_results+2)
        res = req.execute()
        comp_ids = []
        for item in res.get("items", []):
            cid = item["snippet"]["channelId"]
            if cid != original_channel_id and len(comp_ids) < max_results:
                comp_ids.append(cid)
        return comp_ids
    except:
        return []

# UI: Sidebar controls
# -----------------------
st.sidebar.title("YouTube Dashboard")
analysis_mode = st.sidebar.radio("Mode", ["Single Channel Analytics", "Competitor Analysis"])

with st.sidebar:
    search_query = st_keyup("Search YouTube channel or enter link/ID", value="", key="search", debounce=500)
    
max_videos = st.sidebar.slider("Max videos to fetch (approx)", 10, 50, 25)
refresh = st.sidebar.button("Refresh data")

# -----------------------
# Main
# -----------------------
st.title("YouTube Data Dashboard — Streamlit")
if not YOUTUBE_API_KEY:
    st.error("No YOUTUBE_API_KEY found. Add it to `.env` as YOUTUBE_API_KEY and restart.")
    st.stop()

youtube = get_youtube_client(YOUTUBE_API_KEY)

if not search_query and not st.session_state.selected_channel_id:
    st.info("Enter a channel name to search, or paste a link/ID on the left sidebar to get started.")
    st.stop()

if search_query:
    with st.sidebar:
        st.markdown("### Search Results")
        with st.spinner("Searching..."):
            # Try normalizing first (direct ID, URL, handle)
            resolved_channel_id = normalize_channel_input(youtube, search_query)
            results_to_show = []

            if resolved_channel_id:
                exact_info = fetch_channel(youtube, channel_id=resolved_channel_id)
                if exact_info:
                    results_to_show.append({
                        "title": exact_info["title"],
                        "channelId": exact_info["id"],
                        "thumbnail": exact_info.get("logo"),
                        "customUrl": exact_info.get("customUrl"),
                        "subs": exact_info.get("subs")
                    })
            
            search_results = search_channels(youtube, search_query)
            seen_ids = set([r["channelId"] for r in results_to_show])
            
            for r in search_results:
                if r["channelId"] not in seen_ids:
                    results_to_show.append(r)
                    seen_ids.add(r["channelId"])
            
            if not results_to_show:
                st.warning("No channels found.")
            else:
                for r in results_to_show:
                    with st.container():
                        col1, col2 = st.columns([1, 2.5])
                        with col1:
                            if r.get("thumbnail"):
                                try:
                                    img_data = requests.get(r["thumbnail"], timeout=3).content
                                    st.image(Image.open(BytesIO(img_data)), use_container_width=True)
                                except:
                                    st.write("🖼️")
                            else:
                                st.write("🖼️")
                        with col2:
                            st.markdown(f"**{r['title']}**")
                            
                            sub_text = ""
                            if r.get('customUrl'):
                                sub_text += f"{r['customUrl']} • "
                            if r.get('subs') is not None:
                                sub_text += f"{r['subs']:,} subs"
                                
                            if sub_text:
                                st.caption(sub_text.strip(" • "))
                                
                            # When clicked, update session state and re-trigger execution
                            if st.button("Select", key=f"btn_{r['channelId']}", use_container_width=True):
                                st.session_state.selected_channel_id = r['channelId']
                                st.rerun()
                        st.markdown("<hr style='margin: 0.5rem 0; opacity: 0.2'>", unsafe_allow_html=True)

# Default to the session state selection whenever set
final_channel_id = st.session_state.selected_channel_id


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
        # Show more tags by extending the slice limit
        tags_str = str(channel_info.get('keywords', 'No tags'))
        st.caption(f"🌍 **{channel_info.get('country', 'Not specified')}** &nbsp; | &nbsp; 🏷️ **{tags_str[:300] + '...' if len(tags_str) > 300 else tags_str}**")
        desc = channel_info.get("description", "")
        if desc:
            # Let the description take more space before truncating
            st.write(desc[:1000] + "..." if len(desc) > 1000 else desc)
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
                st.info(f"**Best by Views**: {best_by_views['title'][:80]}... ({best_by_views['views']:,} views)")
            with b2:
                st.success(f"**Best by Engagement**: {best_by_eng['title'][:80]}... ({best_by_eng['engagement_rate']:.2f}% ER)")

            tab1, tab2, tab3 = st.tabs(["🔥 Top Videos Table", "📈 Detailed Charts", "🧠 Descriptive & Diagnostic Insights"])
            
            with tab1:
                # Cumulative Growth Chart
                growth_df = stats_df.sort_values('publishedAt', ascending=True).copy()
                growth_df['Cumulative Views'] = growth_df['views'].cumsum()
                fig_growth = px.area(growth_df, x='publishedAt', y='Cumulative Views', title='Cumulative Views Growth (Sample Videos)')
                st.plotly_chart(fig_growth, use_container_width=True)
                
                # Descriptive Analytics Interpretation
                total_growth = int(growth_df['views'].sum())
                top_v_date = growth_df.loc[growth_df['views'].idxmax()]['publishedAt'].strftime('%b %d, %Y')
                st.info(f"📈 **Descriptive Analytics:** The channel generated a total of **{total_growth:,}** views across these {len(growth_df)} videos. A major inflection point in growth occurred around **{top_v_date}**.")
                
                st.markdown("---")

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
                    
                    # Descriptive Analytics for Views
                    top_view_vid = stats_df.iloc[0]
                    sec_view_vid = stats_df.iloc[1] if len(stats_df) > 1 else None
                    if sec_view_vid is not None:
                        diff = int(top_view_vid['views'] - sec_view_vid['views'])
                        st.info(f"📈 **Descriptive Analytics:** The primary traffic driver is **\"{top_view_vid['title'][:30]}...\"**, maintaining a lead of **{diff:,}** views over the 2nd place video.")
                    else:
                        st.info(f"📈 **Descriptive Analytics:** The primary traffic driver is **\"{top_view_vid['title'][:30]}...\"** with **{int(top_view_vid['views']):,}** views.")
                        
                with c2:
                    fig_e = px.bar(stats_df.sort_values('engagement_rate', ascending=False).head(10).sort_values('engagement_rate', ascending=True), 
                                   x='engagement_rate', y='title', orientation='h', title='Top 10 By Engagement Rate')
                    fig_e.update_yaxes(showticklabels=False)
                    st.plotly_chart(fig_e, use_container_width=True)
                    
                    # Descriptive Analytics for Engagement
                    top_eng_vid = stats_df.sort_values('engagement_rate', ascending=False).iloc[0]
                    st.info(f"📈 **Descriptive Analytics:** **\"{top_eng_vid['title'][:30]}...\"** resonated strongest with the core audience, driving an exceptional **{top_eng_vid['engagement_rate']:.2f}%** interaction rate.")
                    
                st.markdown("<br>", unsafe_allow_html=True)
                
                c3, c4 = st.columns(2)
                with c3:
                    agg = stats_df.copy()
                    agg['date'] = agg['publishedAt'].dt.date
                    daily = agg.groupby('date')['views'].sum().reset_index()
                    fig_time = px.line(daily, x='date', y='views', title='Views Over Publish Date')
                    st.plotly_chart(fig_time, use_container_width=True)
                    
                    # Descriptive Analytics for Time Series
                    peak_date_row = daily.loc[daily['views'].idxmax()]
                    st.info(f"📈 **Descriptive Analytics:** The highest traffic occurred for videos published on **{peak_date_row['date']}**, accumulating a massive peak sum of **{int(peak_date_row['views']):,}** views.")
                    
                with c4:
                    fig_scatter = px.scatter(stats_df, x='likes', y='comments', size='views', hover_name='title', title='Likes vs Comments')
                    st.plotly_chart(fig_scatter, use_container_width=True)
                    
                    # Descriptive Analytics for Scatter Plot
                    most_comments = stats_df.loc[stats_df['comments'].idxmax()]
                    st.info(f"📈 **Descriptive Analytics:** **\"{most_comments['title'][:30]}...\"** sparked the highest volume of community debate with **{int(most_comments['comments']):,}** active comments.")

            with tab3:
                st.markdown("### Descriptive Analytics (What Happened?)")
                # Descriptive metrics
                total_views_sample = int(stats_df['views'].sum())
                total_likes_sample = int(stats_df['likes'].sum())
                
                stats_df['publish_day'] = stats_df['publishedAt'].dt.day_name()
                most_freq_day = stats_df['publish_day'].mode()[0]
                best_day = stats_df.groupby('publish_day')['views'].mean().idxmax()
                
                col_d1, col_d2 = st.columns(2)
                with col_d1:
                    st.info(f"**Sample Dataset Totals:**\n\n👁️ **Views**: {total_views_sample:,}\n\n👍 **Likes**: {total_likes_sample:,}")
                with col_d2:
                    st.info(f"**Publishing Patterns:**\n\n📅 **Most uploaded on**: {most_freq_day}\n\n🏆 **Highest Average Views on**: {best_day}")
                
                st.markdown("---")
                
                st.markdown("### Diagnostic Analytics (Why it Happened?)")
                # Correlation
                corr_likes = stats_df['views'].corr(stats_df['likes'])
                corr_comments = stats_df['views'].corr(stats_df['comments'])
                
                # Outliers definition (Videos performing significantly above average)
                view_std = stats_df['views'].std()
                view_mean = stats_df['views'].mean()
                # Ensure we have variability to determine outliers
                if pd.isna(view_std): view_std = 0
                
                outliers = stats_df[stats_df['views'] > (view_mean + 1.5 * view_std)]
                
                d_c1, d_c2 = st.columns(2)
                with d_c1:
                    st.warning(f"**Engagement Correlations:**\n\nLikes to Views: **{corr_likes:.2f}**\n\nComments to Views: **{corr_comments:.2f}**\n\n*(Values closer to 1.0 indicate that a higher engagement strongly predicts higher video views.)*")
                with d_c2:
                    if not outliers.empty:
                        outlier_titles = outliers['title'].tolist()
                        outliers_str = "\n- ".join([f"{t[:40]}..." for t in outlier_titles[:3]])
                        st.success(f"**Viral Breakouts Detected (Outliers):**\n\nThese videos beat the channel average by >1.5x StdDev:\n- {outliers_str}\n\n*Diagnostics point to these specific topics driving disproportionate traffic.*")
                    else:
                        st.success("**Consistent Performance (No Outliers):**\n\nVideo views are relatively uniform across the recent sample, indicating steady audience retention without major viral spikes.")

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
