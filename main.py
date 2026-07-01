import os
import requests
import feedparser
import json
import re
import urllib.parse
import smtplib
from datetime import datetime, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage
from google import genai
from PIL import Image, ImageDraw, ImageFont

# 💡 クライアント「ドコモ」とその経済圏・競合を網羅する最強の営業クエリ
CATEGORIES = {
    "ドコモ最速動向": "NTTドコモ docomo ahamo irumo eximo 新サービス 決算",
    "ドコモ経済圏・スマートライフ": "d払い dポイント dカード ポイ活 リテールメディア ドコモ",
    "通信キャリア競合動向": "KDDI au ソフトバンク SoftBank 楽天モバイル 広告 マーケティング",
    "PR TIMES（最速新着）": "https://prtimes.jp/main/html/rd/index.xml",
    "SNS・縦型動画トレンド": "TikTokプロモーション ショート動画 バズ マーケティング 縦型動画",
    "次世代マーケ・AI活用": "生成AI マーケティング活用 クリエイティブ自動化 アドテクノロジー"
}

def fetch_news(query):
    if query.startswith("http"):
        feed = feedparser.parse(query)
    else:
        encoded_query = urllib.parse.quote(query)
        url = f"https://news.google.com/rss/search?q={encoded_query}&hl=ja&gl=JP&ceid=JP:ja"
        feed = feedparser.parse(url)
    return [{"title": entry.title, "link": entry.link} for entry in feed.entries[:15]]

def create_summary_image(stories, output_path):
    """ニュースを1枚のペライチ画像(JPEG)にまとめる関数"""
    img = Image.new('RGB', (800, 1000), color='#1e1e2e')
    draw = ImageDraw.Draw(img)
    
    font_url = "https://raw.githubusercontent.com/shogo82148/fonts-noto-sans-jp/master/NotoSansJP-Regular.ttf"
    font_path = "NotoSansJP-Regular.ttf"
    font_main = None
    font_title = None
    
    if not os.path.exists(font_path):
        try:
            r = requests.get(font_url, timeout=15)
            if r.status_code == 200:
                with open(font_path, 'wb') as f: f.write(r.content)
        except: pass

    if os.path.exists(font_path):
        try:
            font_main = ImageFont.truetype(font_path, 18)
            font_title = ImageFont.truetype(font_path, 28)
        except: pass

    if not font_main:
        font_main = ImageFont.load_default()
        font_title = ImageFont.load_default()

    yesterday = (datetime.now() + timedelta(hours=9) - timedelta(days=1)).strftime("%Y-%m-%d")
    draw.text((40, 40), f"DOCOMO SALES RADAR ({yesterday})", fill='#ff79c6', font=font_title)
    draw.line([(40, 90), (760, 90)], fill='#6272a4', width=2)
    
    important_stories = [s for s in stories if s.get("importance") in ["S", "A"]][:6]
    y_offset = 120
    if not important_stories: important_stories = stories[:6]
        
    for idx, story in enumerate(important_stories, 1):
        draw.rectangle([40, y_offset, 760, y_offset + 120], outline='#44475a', width=1)
        imp = story.get("importance", "A")
        badge_color = '#ff5555' if imp == "S" else '#ffb86c'
        draw.rectangle([50, y_offset + 15, 140, y_offset + 40], fill=badge_color)
        
        badge_text = "今すぐアポ" if imp == "S" else "定例で提案"
        draw.text((58, y_offset + 18), badge_text, fill='#1e1e2e', font=font_main)
        draw.text((155, y_offset + 18), f"[{story['category']}]", fill='#8be9fd', font=font_main)
        
        title_text = story['title']
        if len(title_text) > 32: title_text = title_text[:32] + "..."
        draw.text((50, y_offset + 55), f"{idx}. {title_text}", fill='#f8f8f2', font=font_main)
        
        sum_text = story['summary'][0] if story['summary'] else ""
        if len(sum_text) > 38: sum_text = sum_text[:38] + "..."
        draw.text((50, y_offset + 85), f"{sum_text}", fill='#bd93f9', font=font_main)
        y_offset += 140
        
    img.save(output_path, 'JPEG')

def send_gmail(subject, body_text, image_path=None):
    gmail_user = os.environ.get("GMAIL_USER")
    gmail_password = os.environ.get("GMAIL_APP_PASSWORD")
    if not gmail_user or not gmail_password: return

    msg = MIMEMultipart()
    msg['From'] = gmail_user
    msg['To'] = gmail_user
    msg['Subject'] = subject
    msg.attach(MIMEText(body_text, 'html'))

    if image_path and os.path.exists(image_path):
        with open(image_path, 'rb') as f: img_data = f.read()
        image = MIMEImage(img_data, name=os.path.basename(image_path))
        msg.attach(image)

    try:
        server = smtplib.SMTP_SSL('smtp.gmail.com', 465)
        server.login(gmail_user, gmail_password)
        server.send_message(msg)
        server.close()
    except Exception as e: print("Gmail送信エラー:", e)

def main():
    all_news_text = ""
    for category, query in CATEGORIES.items():
        articles = fetch_news(query)
        if not articles: continue
        all_news_text += f"\n【カテゴリ: {category}】\n"
        for a in articles: all_news_text += f"- 大見出し: {a['title']}\n  URL: {a['link']}\n"

    api_key = os.environ.get("GEMINI_API_KEY")
    client = genai.Client(api_key=api_key)

    # 🧠 Geminiを「CAの天才ドコモ担当営業」にするプロンプト
    prompt = f"""
あなたはサイバーエージェント（CA）の、圧倒的な成果を出すドコモ担当の「伝説 of 広告営業（アカウントプランナー）」です。
配属初日の新人が持ってきた以下の大量のニュースデータから、ドコモの営業・提案に【直結する最重要ニュース】を厳選し、営業戦略シートとして要約・分析してください。

各ニュースの"summary"は、ただの要約ではなく、必ず以下の【3行の営業構成】で記述してください：
1行目：【事実】何が起きたか
2行目：【ドコモの狙い/課題】なぜそれが起きたか、またはドコモ（あるいは競合）の背景
3行目：【★CAからの提案の切り口】「我が社なら、この動向に対して〇〇という広告手法やクリエイティブ（TikTok/YouTube等の縦型動画、ABEMA連携、dポイントデータを活かしたリテールメディアなど）でドコモに並走・提案できる」という、CAならではの具体的な営業アイデア・切り口

また、営業の観点での重要度を [S, A, B, C] の4段階で厳密に査定し、"importance"に格納してください。
（S: ドコモの新サービス発表や予算大増額など今すぐ動くべき、A: 競合の新しい広告など次の定例で提案すべき、B: 業界トレンドなど雑談・フックネタ、C: 通常ニュース）

出力は、必ず以下の構造のJSON形式（リスト）のみにしてください。

[
  {{
    "category": "カテゴリ名",
    "title": "分かりやすく営業向けに書き直したタイトル",
    "url": "元のURL",
    "importance": "S", 
    "summary": [
      "【事実】...",
      "【ドコモの狙い/課題】...",
      "【CAからの提案の切り口】..."
    ]
  }}
]

【ニュース元データ】
{all_news_text}
"""

    response = client.models.generate_content(model='gemini-2.5-flash', contents=prompt)
    
    try:
        json_str = re.search(r'```json\s*(.*?)\s*```', response.text, re.DOTALL).group(1)
        new_stories = json.loads(json_str)
        
        jst_now = datetime.now() + timedelta(hours=9)
        today_str = jst_now.strftime("%Y-%m-%d %H:%M")
        for story in new_stories:
            story["date"] = today_str
            story["id"] = urllib.parse.quote(story["url"])[-20:] 

        history_file = "news_data.json"
        if os.path.exists(history_file):
            with open(history_file, "r", encoding="utf-8") as f: history_data = json.load(f)
        else: history_data = []
            
        existing_urls = {story["url"] for story in history_data}
        added_stories = [s for s in new_stories if s["url"] not in existing_urls]
        
        for story in added_stories: history_data.insert(0, story)
        with open(history_file, "w", encoding="utf-8") as f: json.dump(history_data[:300], f, ensure_ascii=False, indent=2)
        
        print(f"ドコモ関連の営業ナレッジを {len(added_stories)} 件蓄積しました。")

        # メール配信用設定
        current_hour = jst_now.hour
        if 5 <= current_hour <= 9:
            subject_title = "🌅【朝刊】ドコモ営業レーダー：今すぐ動くべき最重要インサイト"
            image_path = "daily_digest.jpg"
            create_summary_image(new_stories, image_path)
        elif 11 <= current_hour <= 14:
            subject_title, image_path = "☀️【昼刊】ドコモ＆競合キャリア最新動向速報", None
        else:
            subject_title, image_path = "🌙【夜刊】今日の通信業界まとめ＆明日仕掛ける提案アイデア", None

        email_body = f"<h2>{subject_title}</h2><p>分析完了時刻: {today_str}</p><hr>"
        for story in new_stories:
            if story.get("importance") in ["S", "A", "B"]:
                imp_emoji = "🚨 [S級:今すぐアポ]" if story['importance'] == "S" else "✨ [A級:定例提案]" if story['importance'] == "A" else "💡 [B級:提案の種]"
                email_body += f"<div style='margin-bottom:20px;'><b>{imp_emoji} [{story['category']}] {story['title']}</b><br>"
                email_body += "<ul style='color:#444;'>" + "".join([f"<li>{s}</li>" for s in story['summary']]) + "</ul>"
                email_body += f"<a href='{story['url']}' style='color:#00f2fe; text-decoration:none;'>👉 記事元を確認する</a></div>"
        
        email_body += "<br><hr><p>📊 過去のドコモ営業ナレッジのストックはこちらから：<br><a href='https://taichi1010723.github.io/my-news/'>ドコモ営業レーダー・ダッシュボード</a></p>"

        send_gmail(f"{subject_title} ({today_str})", email_body, image_path)
            
    except Exception as e:
        print("エラー発生:", e)

if __name__ == "__main__":
    main()
