"""
پنل وب مدیریت ربات - بدون نیاز به دسترسی سرور یا ری‌دیپلوی
همراه با خود ربات، توی همون پروسه، روی یه پورت جدا اجرا می‌شه.
Railway به‌صورت خودکار این پورت رو تشخیص می‌ده و یه دامنه‌ی عمومی
براش می‌سازه (چون از env variable مخصوص PORT استفاده می‌کنیم).

احراز هویت: HTTP Basic Auth ساده (username/password از .env)
⚠️ حتماً WEB_PANEL_PASSWORD رو یه مقدار قوی و غیرپیش‌فرض بذار، وگرنه
هرکسی که آدرس ربات رو پیدا کنه می‌تونه تنظیماتت رو عوض کنه یا کاربر
مسدود/رفع‌مسدود کنه.
"""
import secrets
import httpx
from fastapi import FastAPI, Depends, HTTPException, status, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials

import database as db
from config import WEB_PANEL_USERNAME, WEB_PANEL_PASSWORD, BOT_TOKEN

app = FastAPI(title="پنل مدیریت ربات سیگنال")
security = HTTPBasic()


def verify_auth(credentials: HTTPBasicCredentials = Depends(security)) -> str:
    if not WEB_PANEL_PASSWORD:
        # اگه رمز تنظیم نشده، پنل رو کلاً غیرفعال می‌کنیم (امن‌تر از پسورد خالی)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="پنل وب فعال نیست چون WEB_PANEL_PASSWORD تنظیم نشده."
        )
    correct_user = secrets.compare_digest(credentials.username, WEB_PANEL_USERNAME)
    correct_pass = secrets.compare_digest(credentials.password, WEB_PANEL_PASSWORD)
    if not (correct_user and correct_pass):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="نام کاربری یا رمز اشتباهه",
            headers={"WWW-Authenticate": "Basic"},
        )
    return credentials.username


PAGE_STYLE = """
<style>
  * { box-sizing: border-box; }
  body { font-family: Tahoma, Segoe UI, sans-serif; direction: rtl; background:#0f1117; color:#e6e6e6; margin:0; padding:24px; }
  .container { max-width: 820px; margin: 0 auto; }
  h1 { color: #22c55e; font-size: 22px; }
  h3 { margin-top: 0; }
  .card { background:#1a1d27; border-radius:10px; padding:18px; margin-bottom:18px; border:1px solid #2a2d3a; }
  table { width:100%; border-collapse: collapse; }
  td, th { padding:10px; border-bottom:1px solid #2a2d3a; text-align:right; font-size:14px; }
  input, textarea { background:#0f1117; border:1px solid #3a3d4a; color:#e6e6e6; padding:10px; border-radius:6px; width:100%; margin-bottom:10px; font-family: inherit; }
  button { background:#22c55e; color:#0f1117; border:none; padding:10px 18px; border-radius:6px; cursor:pointer; font-weight:bold; }
  button.danger { background:#ef4444; color:white; }
  a.nav { color:#3b82f6; margin-left:18px; text-decoration:none; font-size:14px; }
  a.nav:hover { text-decoration:underline; }
  .stat { display:inline-block; background:#0f1117; padding:12px 18px; border-radius:8px; margin:4px; border:1px solid #2a2d3a; font-size:14px; }
  .hint { color:#888; font-size:13px; }
  code { background:#0f1117; padding:2px 6px; border-radius:4px; }
</style>
"""


def layout(title: str, body: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="fa"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title} — پنل ربات</title>{PAGE_STYLE}</head>
<body><div class="container">
<h1>🤖 پنل مدیریت ربات سیگنال</h1>
<div>
  <a class="nav" href="/">📊 داشبورد</a>
  <a class="nav" href="/users">👥 کاربران</a>
  <a class="nav" href="/blocked">🚫 مسدودها</a>
  <a class="nav" href="/settings">⚙️ تنظیمات</a>
  <a class="nav" href="/broadcast">📢 پیام همگانی</a>
</div>
<hr style="border-color:#2a2d3a; margin:16px 0;">
{body}
</div></body></html>"""


@app.get("/", response_class=HTMLResponse)
async def dashboard(user: str = Depends(verify_auth)):
    stats = await db.get_bot_stats()
    access_mode = await db.get_setting("access_mode", "open")
    mode_badge = "🔒 لیست سفید" if access_mode == "whitelist" else "🌐 باز برای همه"
    body = f"""
    <div class="card">
      <h3>آمار کلی</h3>
      <div class="stat">👥 کل کاربران: <b>{stats['total_users']}</b></div>
      <div class="stat">🔄 اسکن خودکار فعال: <b>{stats['active_autoscan']}</b></div>
      <div class="stat">⭐ آیتم واچ‌لیست: <b>{stats['total_watchlist']}</b></div>
      <div class="stat">🚫 کاربر مسدود: <b>{stats['total_blocked']}</b></div>
      <div class="stat">📈 سیگنال امروز: <b>{stats['signals_today']}</b></div>
      <div class="stat">حالت دسترسی: <b>{mode_badge}</b></div>
    </div>
    <div class="card hint">
      این پنل مستقیماً به همون دیتابیس ربات وصله. هر تغییری این‌جا بدی
      بلافاصله (بدون نیاز به ری‌استارت یا ری‌دیپلوی) روی ربات اعمال می‌شه.
    </div>
    """
    return layout("داشبورد", body)


PAGE_SIZE = 20


@app.get("/users", response_class=HTMLResponse)
async def users_page(user: str = Depends(verify_auth), page: int = 1):
    page = max(1, page)
    total = await db.get_user_total_count()
    offset = (page - 1) * PAGE_SIZE
    users = await db.get_users_page(limit=PAGE_SIZE, offset=offset)

    rows = ""
    for u in users:
        badges = ""
        if u["is_blocked"]:
            badges += "<span style='color:#ef4444'>🚫 مسدود</span> "
        if u["is_whitelisted"]:
            badges += "<span style='color:#22c55e'>✅ لیست‌سفید</span>"
        uname = u["username"] or "بدون‌نام"

        if u["is_whitelisted"]:
            wl_form = f"""<form method='post' action='/users/unwhitelist' style='margin:0'>
                <input type='hidden' name='user_id' value='{u["user_id"]}'>
                <button class='danger' type='submit'>حذف از لیست سفید</button></form>"""
        else:
            wl_form = f"""<form method='post' action='/users/whitelist' style='margin:0'>
                <input type='hidden' name='user_id' value='{u["user_id"]}'>
                <button type='submit'>افزودن به لیست سفید</button></form>"""

        rows += (
            f"<tr><td>{u['user_id']}</td><td>{uname}</td><td>{u['joined_at'][:10]}</td>"
            f"<td>{badges or '-'}</td><td>{wl_form}</td></tr>"
        )

    if not rows:
        rows = "<tr><td colspan='5' class='hint'>کاربری پیدا نشد.</td></tr>"

    total_pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)
    nav = ""
    if page > 1:
        nav += f"<a class='nav' href='/users?page={page-1}'>« قبلی</a>"
    if page < total_pages:
        nav += f"<a class='nav' href='/users?page={page+1}'>بعدی »</a>"

    body = f"""
    <div class="card">
      <h3>کاربرانی که ربات رو استارت کردن ({total})</h3>
      <p class="hint">صفحه {page} از {total_pages}</p>
      <table><tr><th>شناسه</th><th>یوزرنیم/نام</th><th>تاریخ عضویت</th><th>وضعیت</th><th></th></tr>{rows}</table>
      <div style="margin-top:12px">{nav}</div>
    </div>
    """
    return layout("کاربران", body)


@app.post("/users/whitelist")
async def whitelist_user_web(user_id: str = Form(...), user: str = Depends(verify_auth)):
    cleaned = user_id.strip()
    if cleaned.lstrip("-").isdigit():
        await db.add_to_whitelist(int(cleaned), "از پنل وب")
    return RedirectResponse("/users", status_code=303)


@app.post("/users/unwhitelist")
async def unwhitelist_user_web(user_id: str = Form(...), user: str = Depends(verify_auth)):
    cleaned = user_id.strip()
    if cleaned.lstrip("-").isdigit():
        await db.remove_from_whitelist(int(cleaned))
    return RedirectResponse("/users", status_code=303)


@app.get("/blocked", response_class=HTMLResponse)
async def blocked_page(user: str = Depends(verify_auth)):
    blocked = await db.get_blocked_users()
    rows = "".join(
        f"<tr><td>{b['user_id']}</td><td>{b['reason']}</td><td>{b['blocked_at'][:10]}</td>"
        f"<td><form method='post' action='/blocked/unblock' style='margin:0'>"
        f"<input type='hidden' name='user_id' value='{b['user_id']}'>"
        f"<button class='danger' type='submit'>رفع مسدودی</button></form></td></tr>"
        for b in blocked
    )
    if not rows:
        rows = "<tr><td colspan='4' class='hint'>هیچ کاربری مسدود نیست.</td></tr>"

    body = f"""
    <div class="card">
      <h3>مسدودکردن کاربر جدید</h3>
      <form method="post" action="/blocked/block">
        <input name="user_id" placeholder="شناسه‌ی عددی کاربر (نه یوزرنیم)" required>
        <input name="reason" placeholder="دلیل (اختیاری)">
        <button type="submit">مسدود کن</button>
      </form>
      <p class="hint">شناسه‌ی عددی رو با فوروارد پیام کاربر به @userinfobot پیدا کن.</p>
    </div>
    <div class="card">
      <h3>کاربران مسدودشده ({len(blocked)})</h3>
      <table><tr><th>شناسه</th><th>دلیل</th><th>تاریخ</th><th></th></tr>{rows}</table>
    </div>
    """
    return layout("کاربران مسدود", body)


@app.post("/blocked/block")
async def block_user_web(user_id: str = Form(...), reason: str = Form(""), user: str = Depends(verify_auth)):
    cleaned = user_id.strip()
    if cleaned.lstrip("-").isdigit():
        await db.block_user(int(cleaned), reason.strip() or "بدون دلیل ثبت‌شده (از پنل وب)")
    return RedirectResponse("/blocked", status_code=303)


@app.post("/blocked/unblock")
async def unblock_user_web(user_id: str = Form(...), user: str = Depends(verify_auth)):
    cleaned = user_id.strip()
    if cleaned.lstrip("-").isdigit():
        await db.unblock_user(int(cleaned))
    return RedirectResponse("/blocked", status_code=303)


# هر آیتم: (کلید در bot_settings, برچسب فارسی, مقدار پیش‌فرض, توضیح کوتاه)
SETTINGS_SCHEMA = [
    ("max_watchlist_per_user", "حداکثر واچ‌لیست هر کاربر", "15", "عدد صحیح"),
    ("confidence_threshold_fraction", "آستانه‌ی صدور سیگنال قطعی", "0.25",
     "بین ۰ تا ۱ - هرچی بزرگ‌تر، سیگنال‌های کمتر ولی مطمئن‌تر"),
    ("atr_sl_mult", "ضریب ATR برای حد ضرر", "1.5", "عدد اعشاری"),
    ("rr_targets", "نسبت‌های ریسک‌به‌ریوارد TP1,TP2,TP3", "1.0,2.0,3.0", "سه عدد با کاما جدا"),
]


@app.get("/settings", response_class=HTMLResponse)
async def settings_page(user: str = Depends(verify_auth)):
    current = await db.get_all_settings()
    forms = ""
    for key, label, default, hint in SETTINGS_SCHEMA:
        value = current.get(key, default)
        forms += f"""
        <div style="margin-bottom:16px; padding-bottom:16px; border-bottom:1px solid #2a2d3a;">
          <label><b>{label}</b> <code>{key}</code></label>
          <p class="hint">{hint}</p>
          <form method="post" action="/settings/update" style="display:flex; gap:8px; align-items:center;">
            <input name="key" value="{key}" type="hidden">
            <input name="value" value="{value}" style="margin-bottom:0;">
            <button type="submit">ذخیره</button>
          </form>
        </div>
        """

    access_mode = current.get("access_mode", "open")
    open_checked = "checked" if access_mode == "open" else ""
    wl_checked = "checked" if access_mode == "whitelist" else ""

    welcome_msg = current.get("custom_welcome_message", "")

    body = f"""
    <div class="card">
      <h3>🔒 کنترل دسترسی</h3>
      <p class="hint">
        در حالت «باز»، هر کسی می‌تونه از ربات استفاده کنه (مگر مسدودشده‌ها).
        در حالت «لیست سفید»، فقط کاربرانی که تاییدشون کردی دسترسی دارن؛
        بقیه فقط پیام «منتظر تایید» می‌گیرن. مدیریت لیست سفید از صفحه‌ی
        <a class="nav" href="/users">کاربران</a> انجام می‌شه.
      </p>
      <form method="post" action="/settings/access-mode">
        <label><input type="radio" name="mode" value="open" {open_checked}> باز برای همه</label><br>
        <label><input type="radio" name="mode" value="whitelist" {wl_checked}> فقط لیست سفید</label><br><br>
        <button type="submit">ذخیره حالت دسترسی</button>
      </form>
    </div>

    <div class="card">
      <h3>👋 پیام خوش‌آمدگویی سفارشی</h3>
      <p class="hint">این پیام، قبل از راهنمای استاندارد، به هر کسی که /start بزنه نشون داده می‌شه.</p>
      <form method="post" action="/settings/welcome">
        <textarea name="message" rows="3" placeholder="مثلاً: به کانال ما هم سر بزن...">{welcome_msg}</textarea>
        <button type="submit">ذخیره پیام</button>
      </form>
      <form method="post" action="/settings/welcome/delete" style="margin-top:8px">
        <button class="danger" type="submit">حذف پیام سفارشی (برگشت به پیش‌فرض)</button>
      </form>
    </div>

    <div class="card">
      <h3>تنظیمات موتور سیگنال</h3>
      <p class="hint">این‌ها بدون نیاز به ری‌دیپلوی، بلافاصله روی تحلیل‌های بعدی اثر می‌ذارن.</p>
      {forms}
    </div>
    """
    return layout("تنظیمات", body)


@app.post("/settings/update")
async def update_setting_web(key: str = Form(...), value: str = Form(...), user: str = Depends(verify_auth)):
    valid_keys = {k for k, _, _, _ in SETTINGS_SCHEMA}
    if key in valid_keys:
        await db.set_setting(key, value.strip())
    return RedirectResponse("/settings", status_code=303)


@app.post("/settings/access-mode")
async def update_access_mode_web(mode: str = Form(...), user: str = Depends(verify_auth)):
    if mode in ("open", "whitelist"):
        await db.set_setting("access_mode", mode)
    return RedirectResponse("/settings", status_code=303)


@app.post("/settings/welcome")
async def update_welcome_web(message: str = Form(...), user: str = Depends(verify_auth)):
    await db.set_setting("custom_welcome_message", message.strip())
    return RedirectResponse("/settings", status_code=303)


@app.post("/settings/welcome/delete")
async def delete_welcome_web(user: str = Depends(verify_auth)):
    await db.set_setting("custom_welcome_message", "")
    return RedirectResponse("/settings", status_code=303)


@app.get("/broadcast", response_class=HTMLResponse)
async def broadcast_page(user: str = Depends(verify_auth)):
    user_count = len(await db.get_all_user_ids())
    body = f"""
    <div class="card">
      <h3>ارسال پیام همگانی</h3>
      <p class="hint">این پیام برای هر {user_count} کاربر ثبت‌شده‌ی ربات ارسال می‌شه.</p>
      <form method="post" action="/broadcast/send">
        <textarea name="message" rows="4" placeholder="متن پیام..." required></textarea>
        <button type="submit">ارسال به همه</button>
      </form>
    </div>
    """
    return layout("پیام همگانی", body)


@app.post("/broadcast/send", response_class=HTMLResponse)
async def send_broadcast_web(message: str = Form(...), user: str = Depends(verify_auth)):
    user_ids = await db.get_all_user_ids()
    sent, failed = 0, 0
    async with httpx.AsyncClient(timeout=10) as client:
        for uid in user_ids:
            try:
                resp = await client.post(
                    f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
                    json={"chat_id": uid, "text": f"📢 {message}"}
                )
                if resp.status_code == 200:
                    sent += 1
                else:
                    failed += 1
            except Exception:
                failed += 1

    body = f"""
    <div class="card">
      ✅ ارسال شد به <b>{sent}</b> کاربر (ناموفق: {failed})
      <br><br><a class="nav" href="/broadcast">بازگشت</a>
    </div>
    """
    return layout("پیام همگانی", body)
