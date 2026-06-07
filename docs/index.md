---
layout: default
title: Home
---

<div id="lang-zh" class="lang-section" markdown="1">

歡迎來到 **autonomous.tw** — 一個以本地 LLM 優先的 AI 驅動資訊聚合系統，每日產出繁體中文新聞簡報。

## 📰 每日速遞 <a class="rss-icon" href="{{ '/feed-zh.xml' | relative_url }}" aria-label="訂閱中文 RSS"><svg viewBox="0 0 448 512" xmlns="http://www.w3.org/2000/svg"><path fill="currentColor" d="M128.081 415.959c0 35.369-28.672 64.041-64.041 64.041S0 451.328 0 415.959s28.672-64.041 64.041-64.041 64.04 28.673 64.04 64.041zm175.66 47.25c-8.354-154.6-132.185-278.587-286.95-286.95C7.656 175.765 0 183.105 0 192.253v48.069c0 8.415 6.49 15.472 14.887 16.018 111.832 7.284 201.473 96.702 208.772 208.772.547 8.397 7.604 14.887 16.018 14.887h48.069c9.149.001 16.489-7.655 15.995-16.79zm144.249.288C439.596 229.677 251.465 40.445 16.503 32.01 7.473 31.686 0 38.981 0 48.016v48.068c0 8.625 6.835 15.645 15.453 15.999 191.179 7.839 344.627 161.316 352.465 352.465.353 8.618 7.373 15.453 15.999 15.453h48.068c9.034-.001 16.329-7.474 16.005-16.504z"/></svg></a>

<ul>
  {% assign zh_posts = site.posts | where: "lang", "zh" %}
  {% for post in zh_posts limit:20 %}
    <li>
      <a href="{{ post.url | relative_url }}">{{ post.date | date: "%Y-%m-%d" }}</a>
    </li>
  {% else %}
    <li><em>暫無內容 — 執行 <code>uv run autonomous-tw</code> 來產生第一份簡報</em></li>
  {% endfor %}
</ul>

## 📖 文件

- [設定指南](configuration) — AI 服務提供者、資訊來源、篩選規則與環境變數替換
- [資訊來源採集器](scrapers) — 支援 GitHub、Hacker News、RSS、Reddit、Telegram、Twitter、Threads、OpenBB 等平台
- [評分系統](scoring) — AI 五大領域評分（AI 科技、台灣時事、國際政治、體育、知識管理）

</div>

<div id="lang-en" class="lang-section" markdown="1">

Welcome to **autonomous.tw** — a local-LLM-first, AI-driven information aggregation system producing daily Traditional Chinese news briefings.

## 📰 Daily Digest <a class="rss-icon" href="{{ '/feed-en.xml' | relative_url }}" aria-label="Subscribe English RSS"><svg viewBox="0 0 448 512" xmlns="http://www.w3.org/2000/svg"><path fill="currentColor" d="M128.081 415.959c0 35.369-28.672 64.041-64.041 64.041S0 451.328 0 415.959s28.672-64.041 64.041-64.041 64.04 28.673 64.04 64.041zm175.66 47.25c-8.354-154.6-132.185-278.587-286.95-286.95C7.656 175.765 0 183.105 0 192.253v48.069c0 8.415 6.49 15.472 14.887 16.018 111.832 7.284 201.473 96.702 208.772 208.772.547 8.397 7.604 14.887 16.018 14.887h48.069c9.149.001 16.489-7.655 15.995-16.79zm144.249.288C439.596 229.677 251.465 40.445 16.503 32.01 7.473 31.686 0 38.981 0 48.016v48.068c0 8.625 6.835 15.645 15.453 15.999 191.179 7.839 344.627 161.316 352.465 352.465.353 8.618 7.373 15.453 15.999 15.453h48.068c9.034-.001 16.329-7.474 16.005-16.504z"/></svg></a>

<ul>
  {% assign en_posts = site.posts | where: "lang", "en" %}
  {% for post in en_posts limit:20 %}
    <li>
      <a href="{{ post.url | relative_url }}">{{ post.date | date: "%Y-%m-%d" }}</a>
    </li>
  {% else %}
    <li><em>No posts yet — run <code>uv run autonomous-tw</code> to generate your first briefing</em></li>
  {% endfor %}
</ul>

## 📖 Documentation

- [Configuration Guide](configuration) — AI providers, information sources, filtering, and environment variable substitution
- [Source Scrapers](scrapers) — Supports GitHub, Hacker News, RSS, Reddit, Telegram, Twitter, Threads, OpenBB, and more
- [Scoring System](scoring) — AI five-domain scoring (AI Tech, Taiwan Affairs, Intl Politics, Sports, KM)

</div>