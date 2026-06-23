import feedparser
from datetime import datetime
import time
from groq import Groq
import json
import os

# --- 1. API Configuration ---
# Insert your Groq API Key here
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "YOUR_GROQ_API_KEY_HERE")
client = Groq(api_key=GROQ_API_KEY)

# --- 2. Targeted Search Queries ---
# Broadened search to include ALL publications, plus specific targets for community & Māori media
SEARCH_QUERIES = [
    # 基础全局搜索：涵盖所有主流媒体、Chris Lynch 等独立媒体
    '"Christchurch City Council"',
    '"Te Kaha" OR "Apollo Projects stadium" Christchurch',
    '"local government" "Christchurch City"',
    '"Phil Mauger" Christchurch',
    
    # VIP 定向抓取通道：强制搜索毛利媒体和本地社区报纸，防止被大新闻掩盖
    '"Christchurch" ("Te Ao Maori News" OR "Star News" OR "Nor\'West News" OR "Pegasus Post" OR "Bay Harbour News")'
]

def analyze_single_article(title, snippet, date_str):
    """[Role 1: Analyst Agent] Scores a single article from 1 to 10."""
    prompt = f"""
    Analyse this article regarding the Christchurch City Council.
    Headline: {title}
    Snippet: {snippet}
    Date: {date_str}

    Use this strict 1-10 scoring scale:
    - 1-3: Negative (critical, highlights failures, quotes angry residents)
    - 4-7: Neutral (factual, balanced, informational)
    - 8-10: Positive (supportive, highlights success, quotes satisfied residents)

    Respond ONLY in valid JSON format exactly like this:
    {{
        "score": 5,
        "key_drivers": "Brief reason based on text",
        "comms_action": "Recommended Comms Action"
    }}
    """
    try:
        response = client.chat.completions.create(
            messages=[{"role": "system", "content": "You output strictly valid JSON only."},
                      {"role": "user", "content": prompt}],
            model="llama-3.1-8b-instant",
            temperature=0.1,
        )
        text = response.choices[0].message.content.replace("```json", "").replace("```", "").strip()
        return json.loads(text)
    except Exception as e:
        return {"score": 5, "key_drivers": "Failed to analyze", "comms_action": "None"}

def generate_executive_summary(all_articles_data):
    """[Role 2: Executive Agent] Writes the overarching summary."""
    context = json.dumps(all_articles_data, indent=2, ensure_ascii=False)
    
    prompt = f"""
    You are the Chief PR Officer for the Christchurch City Council.
    Below is the raw sentiment data for articles published today:
    {context}
    
    Based ONLY on this data, write an "Executive Summary" (about 3-4 sentences).
    Summarize the overarching narrative, highlight the biggest risks (if any scores are 1-3), and note any positive wins (scores 8-10).
    Do not output JSON, just write the professional summary paragraphs.
    """
    try:
        response = client.chat.completions.create(
            messages=[{"role": "system", "content": "You are an expert PR executive."},
                      {"role": "user", "content": prompt}],
            model="llama-3.1-8b-instant",
            temperature=0.4,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        return "Failed to generate executive summary."

def run_daily_agent():
    # Set the target date to TODAY (e.g., 23 June 2026)
    target_date = datetime.now().date()
    date_formatted = target_date.strftime("%d %B %Y")
    
    print(f"🤖 Agent starting: Compiling report for TODAY ({date_formatted})...")
    
    all_scored_articles = []
    
    for query in SEARCH_QUERIES:
        url = f"https://news.google.com/rss/search?q={query.replace(' ', '+')}&hl=en-NZ&gl=NZ&ceid=NZ:en"
        feed = feedparser.parse(url)
        
        for entry in feed.entries:
            # Parse publication date
            pub_date = datetime(*entry.published_parsed[:6]).date()
            
            # Verify the publication date: EXCLUDE anything that is not from TODAY
            if pub_date != target_date:
                continue
                
            date_str = pub_date.strftime("%Y-%m-%d")
            print(f"  -> Found relevant article: {entry.title[:40]}...")
            
            # AI Analyst evaluates the article
            analysis = analyze_single_article(entry.title, entry.description, date_str)
            
            all_scored_articles.append({
                "Headline": entry.title,
                "Date": date_str,
                "Score": analysis["score"],
                "Key Sentiment Drivers": analysis["key_drivers"],
                "Recommended Comms Action": analysis["comms_action"],
                "URL": entry.link
            })
            
    if not all_scored_articles:
        print(f"\nNo relevant articles found for {date_formatted}.")
        return

    print(f"\n🧠 Analyst complete. Processed {len(all_scored_articles)} articles.")
    print("👔 Executive Agent is writing the summary...")
    
    summary = generate_executive_summary(all_scored_articles)
    
    # --- 3. Generate the Markdown Report ---
    report_filename = f"CCC_Daily_Report_{target_date.strftime('%Y%m%d')}.md"
    
    with open(report_filename, "w", encoding="utf-8") as f:
        f.write("# 📊 Christchurch City Council - Daily PR Sentiment Report\n\n")
        f.write(f"**Date:** {date_formatted}\n\n")
        
        f.write("## 1. Executive Summary\n")
        f.write(summary + "\n\n")
        
        f.write("## 2. Detailed Articles Matrix\n")
        f.write("| Headline | Date | Score (1-10) | Key Sentiment Drivers | Recommended Comms Action |\n")
        f.write("|---|---|---|---|---|\n")
        
        # Sort by score (lowest/most critical first)
        all_scored_articles.sort(key=lambda x: x["Score"])
        
        for art in all_scored_articles:
            score_display = f"🔴 {art['Score']}" if art['Score'] <= 3 else (f"🟡 {art['Score']}" if art['Score'] <= 7 else f"🟢 {art['Score']}")
            f.write(f"| [{art['Headline']}]({art['URL']}) | {art['Date']} | **{score_display}** | {art['Key Sentiment Drivers']} | {art['Recommended Comms Action']} |\n")

    print(f"\n✅ Success! Report generated: {report_filename}")

if __name__ == "__main__":
    run_daily_agent()
