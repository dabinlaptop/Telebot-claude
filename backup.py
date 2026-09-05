"""
بکاپ خودکار دیتابیس

چرا از sqlite3.Connection.backup() استفاده می‌کنیم، نه کپی خام فایل؟
چون دیتابیس ممکنه دقیقاً همون لحظه در حال نوشته‌شدن باشه؛ کپی خام فایل
می‌تونه یه فایل نیمه‌نوشته و خراب کپی کنه. متد backup() داخلی خود
SQLite، یه کپی atomic و سازگار (consistent) می‌سازه حتی اگه هم‌زمان
چیزی داره نوشته می‌شه.

چون backup() یه عملیات بلاک‌کننده‌ست (نه async)، توی یه ترد جدا
(asyncio.to_thread) اجراش می‌کنیم تا event loop اصلی ربات قفل نشه.
"""
import os
import sqlite3
import asyncio
import logging
from datetime import datetime

from config import DB_PATH, BACKUP_DIR, BACKUP_MAX_COUNT

logger = logging.getLogger(__name__)

BACKUP_PREFIX = "backup_"
BACKUP_SUFFIX = ".db"


def _do_backup_sync(source_path: str, dest_path: str):
    source = sqlite3.connect(source_path)
    try:
        dest = sqlite3.connect(dest_path)
        try:
            source.backup(dest)
        finally:
            dest.close()
    finally:
        source.close()


def _rotate_backups():
    """قدیمی‌ترین بکاپ‌ها رو حذف می‌کنه تا تعدادشون از BACKUP_MAX_COUNT بیشتر نشه"""
    files = sorted(
        f for f in os.listdir(BACKUP_DIR)
        if f.startswith(BACKUP_PREFIX) and f.endswith(BACKUP_SUFFIX)
    )
    while len(files) > BACKUP_MAX_COUNT:
        oldest = files.pop(0)
        try:
            os.remove(os.path.join(BACKUP_DIR, oldest))
            logger.info(f"بکاپ قدیمی حذف شد (رول‌شدن): {oldest}")
        except OSError as e:
            logger.warning(f"حذف بکاپ قدیمی {oldest} ناموفق بود: {e}")


async def create_backup() -> str:
    """یه بکاپ جدید می‌سازه، رول‌آپ قدیمی‌ها رو انجام می‌ده، مسیر فایل جدید رو برمی‌گردونه"""
    os.makedirs(BACKUP_DIR, exist_ok=True)
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    dest_path = os.path.join(BACKUP_DIR, f"{BACKUP_PREFIX}{timestamp}{BACKUP_SUFFIX}")

    if not os.path.isfile(DB_PATH):
        raise FileNotFoundError(f"فایل دیتابیس اصلی پیدا نشد: {DB_PATH}")

    await asyncio.to_thread(_do_backup_sync, DB_PATH, dest_path)
    await asyncio.to_thread(_rotate_backups)

    size_kb = os.path.getsize(dest_path) / 1024
    logger.info(f"بکاپ جدید ساخته شد: {dest_path} ({size_kb:.1f} KB)")
    return dest_path


def list_backups() -> list[dict]:
    """لیست بکاپ‌های موجود، جدیدترین اول - برای نمایش توی پنل وب/تلگرام"""
    if not os.path.isdir(BACKUP_DIR):
        return []
    result = []
    for f in sorted(os.listdir(BACKUP_DIR), reverse=True):
        if not (f.startswith(BACKUP_PREFIX) and f.endswith(BACKUP_SUFFIX)):
            continue
        full_path = os.path.join(BACKUP_DIR, f)
        try:
            size_kb = os.path.getsize(full_path) / 1024
            mtime = datetime.fromtimestamp(os.path.getmtime(full_path))
        except OSError:
            continue
        result.append({"filename": f, "size_kb": size_kb, "created_at": mtime})
    return result


def get_backup_path(filename: str) -> str | None:
    """
    مسیر امن یه فایل بکاپ رو برمی‌گردونه - فقط اگه اسم فایل دقیقاً
    مطابق الگوی مورد انتظار باشه (جلوگیری از path traversal، چون این
    تابع قراره از ورودی کاربر/پنل وب هم صدا زده بشه)
    """
    if "/" in filename or "\\" in filename or ".." in filename:
        return None
    if not (filename.startswith(BACKUP_PREFIX) and filename.endswith(BACKUP_SUFFIX)):
        return None
    full_path = os.path.join(BACKUP_DIR, filename)
    return full_path if os.path.isfile(full_path) else None
