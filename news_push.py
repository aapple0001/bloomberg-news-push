import feedparser
import smtplib
from email.mime.text import MIMEText
import requests
import re
import os
import datetime

# ---------------------- Gmail配置（从GitHub Secret读取，不用改） ----------------------
GMAIL_EMAIL = os.getenv("GMAIL_EMAIL")
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD")
RECEIVER_EMAILS = os.getenv("RECEIVER_EMAILS")
SMTP_SERVER = "smtp.gmail.com"
CUSTOM_NICKNAME = "♥️彭博速递"

# ---------------------- 基础配置（不用改） ----------------------
RSS_URL = "https://bloombergnew.buzzing.cc/feed.xml"  # 彭博资讯数据源
LAST_LINK_FILE = "last_link.txt"  # 记最新资讯，防重复推送
REQUEST_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "*/*",
    "Connection": "keep-alive"
}

# 提取时间（有分时显示分时，没有显示月日，不用改）
def get_show_time(news):
    content = news.get("content", [{}])[0].get("value", "") if news.get("content") else ""
    try:
        pattern = r'(\d{2}:\d{2})<\/time>'
        hour_min = re.search(pattern, content).group(1)
        return hour_min
    except:
        updated_str = news.get("updated", news.get("published", ""))
        date_part = updated_str.split('T')[0]
        month_day = '-'.join(date_part.split('-')[1:])
        return month_day

# 抓取资讯（不用改）
def fetch_news():
    try:
        response = requests.get(RSS_URL, headers=REQUEST_HEADERS, timeout=15)
        response.raise_for_status()
        news_list = feedparser.parse(response.content).entries
        if not news_list:
            print("📭 未抓取到任何彭博资讯")
            return None, None
        latest_link = news_list[0]["link"].strip()
        print(f"📭 成功抓取到{len(news_list)}条彭博资讯")
        return news_list, latest_link
    except Exception as e:
        print(f"❌ 资讯抓取失败：{str(e)}")
        return None, None

# 判重：是否需要推送（不用改）
def check_push():
    is_first = not os.path.exists(LAST_LINK_FILE)
    last_link = ""

    if not is_first:
        try:
            with open(LAST_LINK_FILE, 'r', encoding='utf-8') as f:
                last_link = f.read().strip()
        except Exception as e:
            print(f"⚠️  读取历史链接失败，按首次运行处理：{str(e)}")
            is_first = True

    all_news, current_link = fetch_news()
    if not all_news or not current_link:
        return False, None

    if is_first or current_link != last_link:
        with open(LAST_LINK_FILE, 'w', encoding='utf-8') as f:
            f.write(current_link)
        if is_first:
            print("🚨 首次运行，强制推送最新资讯")
        else:
            print("🔄 检测到新资讯，立即推送")
        return True, all_news
    else:
        print("ℹ️  暂无新资讯，本次不推送")
        return False, None

# 生成邮件内容（样式固定，不用改）
def make_content(all_news):
    if not all_news:
        return "暂无可用的彭博资讯"
    news_list = all_news[:300]

    title_color = "#2E4057"
    time_color = "#FFB400"
    time_bg_color = "transparent"
    serial_color = "#1E88E5"
    news_title_color = "#333333"
    link_text_color = "#143060"

    title = f"<p><strong><span style='color:{title_color};'>「彭博速递」</span></strong></p>"

    content = []
    for i, news in enumerate(news_list, 1):
        link = news["link"]
        news_title = news["title"]
        show_t = get_show_time(news)
        content.append(f"""
        <p style='margin: 8px 0; padding: 0;'>
            <span style='color:{serial_color}; font-size: 16px;'>{i}</span>. 
            【<span style='color:{time_color}!important; text-decoration: none!important; background:{time_bg_color}; font-weight: bold; font-size: 16px;'>{show_t}</span>】
            <span style='color:{news_title_color}; font-size: 16px;'>{news_title}</span>
        </p>
        <p style='margin: 0 0 12px 0; padding: 0;'>👉 <a href='{link}' target='_blank' style='color:{link_text_color}; text-decoration: underline; font-size: 14px;'>原文链接</a></p>
        """)

    return title + "".join(content)

# 发送邮件（Gmail核心功能，不用改）
def send_email(content):
    if not all([GMAIL_EMAIL, GMAIL_APP_PASSWORD, RECEIVER_EMAILS]):
        print("❌ 请配置完整的GitHub Secrets！")
        return

    html_content = f"""
    <!DOCTYPE html>
    <html lang="zh-CN">
    <head>
        <meta charset="utf-8">
        <style>
            body {{ font-family: 微软雅黑, Arial, sans-serif; line-height: 2.2; font-size: 15px; }}
            p {{ margin: 0; padding: 0; }}
        </style>
    </head>
    <body>{content}</body>
    </html>
    """

    receiver_list = [email.strip() for email in RECEIVER_EMAILS.split(",") if email.strip()]
    if not receiver_list:
        print("❌ 收件人邮箱格式错误！")
        return

    try:
        smtp = smtplib.SMTP_SSL(SMTP_SERVER, 465, timeout=20)
        smtp.login(GMAIL_EMAIL, GMAIL_APP_PASSWORD)
        print(f"✅ 连接Gmail成功，向{len(receiver_list)}个收件人发送")

        for receiver in receiver_list:
            msg = MIMEText(html_content, "html", "utf-8")
            msg["From"] = f"{CUSTOM_NICKNAME} <{GMAIL_EMAIL}>"
            msg["To"] = receiver
            msg["Subject"] = "「彭博速递」"
            smtp.sendmail(GMAIL_EMAIL, [receiver], msg.as_string())
            print(f"✅ 已发送给：{receiver}")

        smtp.quit()
        print("✅ 所有邮件发送完成！")
    except smtplib.SMTPAuthenticationError:
        print("❌ Gmail登录失败！检查Secret是否正确、两步验证是否开启！")
    except Exception as e:
        print(f"❌ 邮件发送失败：{str(e)}")
        raise

# 程序入口（不用改）
if __name__ == "__main__":
    utc_now = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    cst_now = (datetime.datetime.utcnow() + datetime.timedelta(hours=8)).strftime("%Y-%m-%d %H:%M:%S")
    print(f"==================================================")
    print(f"📅 执行时间 | UTC：{utc_now} | 东八区：{cst_now}")
    print(f"==================================================")

    try:
        need_push, news = check_push()
        if need_push and news:
            email_content = make_content(news)
            send_email(email_content)
        print(f"🎉 本次资讯检测+推送流程结束")
    except Exception as e:
        print(f"💥 流程执行失败：{str(e)}")
        raise
