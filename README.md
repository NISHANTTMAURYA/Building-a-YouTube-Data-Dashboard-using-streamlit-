 📊 YouTube Data Dashboard — Streamlit

A clean, wide-layout **YouTube Analytics Dashboard** built using **Streamlit** and the **YouTube Data API v3**.  
Paste any YouTube Channel ID or username to instantly get insights like subscribers, total views, top videos, KPIs, interactive charts, and intelligent diagnostics.

🚀 Features

✔ **Channel Overview**  
- Subscribers, Total views, and Total video count  
- Channel logo, description, and keywords
- Wide-screen responsive layout

✔ **Deep Analytics & KPIs**  
- **Descriptive Analytics:** Natural language insights breaking down total growth, upload patterns, and engagement summaries.
- **Diagnostic Analytics:** Statistical analysis on views-to-likes correlations and anomaly/viral outlier detection.
- Fast identification of "Best by Views" and "Best by Engagement" videos.

✔ **Interactive Charts**  
- **Cumulative Growth Chart:** Monitor the compounding velocity of a channel over recent uploads.
- Custom Plotly-powered visual bar charts (Top 10s), time-series line charts, and Scatter plots determining engagement vs arguments.
- Contextual tooltips explaining exactly *"What this means"* for each chart.

✔ **Auto Competitor Discovery & Analysis**
- Instantly discover direct YouTube competitors based on video keywords.
- Compare subscribers, average views, and engagement rates side-by-side.

✔ **Export Features & Security**  
- Download full video stats as CSV  
- Secure `.env` handling with `python-dotenv`

🛠️ Tech Stack

- **Python 3**
- **Streamlit** (UI)
- **YouTube Data API v3**
- **Plotly** (Interactive charts)
- **Pandas** (Data processing)
- **Requests** & **google-api-python-client**

📂 Project Structure

├── app.py
├── .env (not committed)
├── .gitignore
├── requirements.txt
├── README.md
└── screenshot.png / demo.gif

⚙️ Setup Instructions

1️⃣ **Clone the Repository**

git clone https://github.com/NISHANTTMAURYA/Building-a-YouTube-Data-Dashboard-using-streamlit-.git
cd Building-a-YouTube-Data-Dashboard-using-streamlit-

2️⃣ **Create Virtual Environment**

python -m venv venv
# Mac/Linux:
source venv/bin/activate
# Windows:
# venv\Scripts\activate

3️⃣ **Install Dependencies**
pip install -r requirements.txt


4️⃣ **Set Up Your API Key**
Create a `.env` file in the root directory and add:
YOUTUBE_API_KEY=YOUR_API_KEY_HERE

5️⃣ **Run the Dashboard**
streamlit run app.py


🔍 How to Get a YouTube API Key

1 Go to Google Cloud Console
2 Create a new project
3 Enable YouTube Data API v3
4 Go to Credentials → Create API Key
5 Add it to .env
6 Run the app

🙌 Acknowledgements

* YouTube Data API v3
* Streamlit Community
* Python Open Source ecosystem


🧩 Future Enhancements

1 OAuth2 login for full YouTube Analytics API (watch time, impressions, CTR)
2 Daily stats tracking & database storage
3 Dark mode UI
4 Multi-channel analytics
5 Creator-level summary pages
