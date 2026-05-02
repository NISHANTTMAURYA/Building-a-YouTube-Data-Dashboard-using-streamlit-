import urllib.request
with open('app.py', 'r') as f:
    text = f.read()

# ADD THE HELPER FUNCTIONS AFTER search_channels
helper_fns = """
# -----------------------
# Auto Competitor Discovery Helpers
# -----------------------
def extract_keywords(titles, top_n=5):
    words = []
    for t in titles:
        clean_t = re.sub(r'[^\\w\\s]', '', t.lower())
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
"""
if "def extract_keywords(" not in text:
    text = text.replace("# UI: Sidebar controls", helper_fns + "\n# UI: Sidebar controls", 1)

# WRITE IT BACK
with open('app.py', 'w') as f:
    f.write(text)
