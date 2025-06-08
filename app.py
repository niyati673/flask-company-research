from flask import Flask, render_template, request, send_file, session
import wikipedia
import requests
from googlesearch import search
from bs4 import BeautifulSoup
from fpdf import FPDF
import pandas as pd
import openai
import os

from dotenv import load_dotenv
import os

load_dotenv()  # This loads environment variables from .env into os.environ

news_api_key = os.getenv("NEWSAPI_KEY")
openai_key = os.getenv("OPENAI_KEY")


app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "fallback-secret-key-for-dev")
openai.api_key = openai_key

def get_company_summary(company_name):
    print(f"[DEBUG] Searching Wikipedia summary for: {company_name}")
    try:
        summary = wikipedia.summary(company_name, sentences=5)
        page = wikipedia.page(company_name)
        print(f"[DEBUG] Wikipedia summary found. URL: {page.url}")
        print(f"[DEBUG] Summary preview: {summary[:200]}...")
        return {'summary': summary, 'url': page.url}
    except Exception as e:
        print(f"[ERROR] Wikipedia error: {e}")
        return {'summary': 'No summary found.', 'url': None}

def get_recent_news(company_name):
    url = f"https://newsapi.org/v2/everything?q={company_name}&apiKey={news_api_key}&pageSize=5"
    res = requests.get(url)
    if res.status_code == 200:
        return res.json().get("articles", [])
    return []

def find_linkedin_profile(company_name):
    query = f"{company_name} site:linkedin.com/company"
    for result in search(query, num_results=5):
        if "linkedin.com/company" in result:
            return result
    return "Not found"

def get_future_plans(company_name):
    query = f"{company_name} future plans"
    print(f"[DEBUG] Google searching for: {query}")
    try:
        for url in search(query, num_results=3):
            print(f"[DEBUG] Trying URL: {url}")
            try:
                page = requests.get(url, timeout=5)
                soup = BeautifulSoup(page.content, "html.parser")
                paragraphs = soup.find_all("p")
                text = " ".join([p.get_text() for p in paragraphs[:10]])
                print(f"[DEBUG] Extracted {len(text)} characters of text from page")
                if text.strip():
                    summary = summarize_text(text)
                    return summary
            except Exception as e:
                print(f"[ERROR] Failed to scrape {url}: {e}")
        print("[WARN] No suitable page found with content for future plans.")
        return "No future plans information found."
    except Exception as e:
        print(f"[ERROR] Google search failed: {e}")
        return "Could not perform future plans search."

def summarize_text(text):
    try:
        print(f"[DEBUG] Sending text to OpenAI for summarization. Text length: {len(text)} chars")
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "user", "content": f"Summarize this company's future plans:\n\n{text}"}
            ],
            max_tokens=200,
        )
        summary = response.choices[0].message.content.strip()
        print(f"[DEBUG] OpenAI summary response received: {summary[:200]}...")
        return summary
    except Exception as e:
        print(f"[ERROR] OpenAI API error: {e}")
        return "Could not retrieve summary from OpenAI."

def export_to_pdf(info, filename="report.pdf"):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)
    for key, val in info.items():
        pdf.multi_cell(0, 10, f"{key}: {val}")
    pdf.output(filename)
    return filename

def export_to_csv(info, filename="report.csv"):
    df = pd.DataFrame([info])
    df.to_csv(filename, index=False)
    return filename

@app.route("/", methods=["GET", "POST"])
def index():
    info = {}
    news = []
    linkedin = ""
    future = ""

    if request.method == "POST":
        company = request.form["company"]
        info = get_company_summary(company)
        news = get_recent_news(company)
        linkedin = find_linkedin_profile(company)
        future = get_future_plans(company)

        info.update({
            "linkedin": linkedin,
            "future_plans": future
        })

        # Store in session
        session['session_info'] = info
        session['session_news'] = news
    
    else:
        # Load from session for GET requests if you want
        info = session.get('session_info', {})
        news = session.get('session_news', [])

    return render_template("index.html", info=info, news=news)

@app.route("/download/pdf")
def download_pdf():
    info = session.get('session_info', {})
    if not info:
        return "No data available to download.", 400
    filename = export_to_pdf(info)
    return send_file(filename, as_attachment=True)

@app.route("/download/csv")
def download_csv():
    info = session.get('session_info', {})
    if not info:
        return "No data available to download.", 400
    filename = export_to_csv(info)
    return send_file(filename, as_attachment=True)

if __name__ == "__main__":
    app.run(debug=True)