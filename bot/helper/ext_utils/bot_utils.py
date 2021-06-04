import logging
import re
import threading
import time

from bot import download_dict, download_dict_lock

LOGGER = logging.getLogger(__name__)

MAGNET_REGEX = r"magnet:\?xt=urn:btih:[a-zA-Z0-9]*"

URL_REGEX = r"(?:(?:https?|ftp):\/\/)?[\w/\-?=%.]+\.[\w/\-?=%.]+"


class MirrorStatus:
    STATUS_UPLOADING = "𝙐𝙥𝙡𝙤𝙖𝙙𝙞𝙣𝙜...📤"
    STATUS_DOWNLOADING = "𝘿𝙤𝙬𝙣𝙡𝙤𝙖𝙙𝙞𝙣𝙜...📥"
    STATUS_WAITING = "𝙌𝙪𝙚𝙪𝙚𝙙...⏳"
    STATUS_FAILED = "𝐅𝐚𝐢𝐥𝐞𝐝 🚫. 𝐂𝐥𝐞𝐚𝐧𝐢𝐧𝐠 𝐃𝐨𝐰𝐧𝐥𝐨𝐚𝐝"
    STATUS_CANCELLED = "𝐂𝐚𝐧𝐜𝐞𝐥𝐥𝐞𝐝 ❎"
    STATUS_ARCHIVING = "𝘼𝙧𝙘𝙝𝙞𝙫𝙞𝙣𝙜...🔐"
    STATUS_EXTRACTING = "𝙀𝙭𝙩𝙧𝙖𝙘𝙩𝙞𝙣𝙜...📂"


PROGRESS_MAX_SIZE = 100 // 8
PROGRESS_INCOMPLETE = ['●', '●', '●', '●', '●', '●', '●']

SIZE_UNITS = ['B', 'KB', 'MB', 'GB', 'TB', 'PB']


class setInterval:
    def __init__(self, interval, action):
        self.interval = interval
        self.action = action
        self.stopEvent = threading.Event()
        thread = threading.Thread(target=self.__setInterval)
        thread.start()

    def __setInterval(self):
        nextTime = time.time() + self.interval
        while not self.stopEvent.wait(nextTime - time.time()):
            nextTime += self.interval
            self.action()

    def cancel(self):
        self.stopEvent.set()


def get_readable_file_size(size_in_bytes) -> str:
    if size_in_bytes is None:
        return '0B'
    index = 0
    while size_in_bytes >= 1024:
        size_in_bytes /= 1024
        index += 1
    try:
        return f'{round(size_in_bytes, 2)}{SIZE_UNITS[index]}'
    except IndexError:
        return 'File too large'


def getDownloadByGid(gid):
    with download_dict_lock:
        for dl in download_dict.values():
            status = dl.status()
            if status != MirrorStatus.STATUS_UPLOADING and status != MirrorStatus.STATUS_ARCHIVING \
                    and status != MirrorStatus.STATUS_EXTRACTING:
                if dl.gid() == gid:
                    return dl
    return None


def get_progress_bar_string(status):
    completed = status.processed_bytes() / 8
    total = status.size_raw() / 8
    if total == 0:
        p = 0
    else:
        p = round(completed * 100 / total)
    p = min(max(p, 0), 100)
    cFull = p // 8
    cPart = p % 8 - 1
    p_str = '●' * cFull
    if cPart >= 0:
        p_str += PROGRESS_INCOMPLETE[cPart]
    p_str += '○' * (PROGRESS_MAX_SIZE - cFull)
    p_str = f"[{p_str}]"
    return p_str


def get_readable_message():
    with download_dict_lock:
        msg = "<b>➖➖➖➖➖➖➖➖➖➖➖➖➖</b>"
        for download in list(download_dict.values()):
            msg += f"\n🗂 𝗙𝗶𝗹𝗲 𝗡𝗮𝗺𝗲 : <code>{download.name()}</code>"
            msg += f"\n<b>📊 𝗦𝘁𝗮𝘁𝘂𝘀 :</b> <i>{download.status()}</i>"
            if download.status() != MirrorStatus.STATUS_ARCHIVING and download.status() != MirrorStatus.STATUS_EXTRACTING:
                msg += f"\n<code>{get_progress_bar_string(download)} {download.progress()}</code>"
                if download.status() == MirrorStatus.STATUS_DOWNLOADING:
                    msg += f"\n<b>📥 𝗗𝗼𝘄𝗻𝗹𝗼𝗮𝗱𝗲𝗱 :</b> {get_readable_file_size(download.processed_bytes())} of {download.size()}"
                else:
                    msg += f"\n<b>📤 𝗨𝗽𝗹𝗼𝗱𝗲𝗱 :</b> {get_readable_file_size(download.processed_bytes())} of {download.size()}"
                msg += f"\n<b>⚡️ 𝗦𝗽𝗲𝗲𝗱 :</b> {download.speed()}, \n<b>⏳ 𝗘𝗧𝗔 :</b> {download.eta()}"
                # if hasattr(download, 'is_torrent'):
                try:
                    msg += f"\n<b>💢 𝐈𝐧𝐟𝐨 :- 👤 𝐒𝐞𝐞𝐝𝐞𝐫𝐬 :</b> {download.aria_download().num_seeders}" \
                        f" & <b>👥 𝐏𝐞𝐞𝐫𝐬 :</b> {download.aria_download().connections}"
                except:
                    pass
            if download.status() == MirrorStatus.STATUS_DOWNLOADING:
                msg += f"\n<b>❌ 𝐓𝐨 𝐒𝐭𝐨𝐩 👉🏾</b> : <code> /cancel {download.gid()}</code>"
            msg += "\n\n"
        return msg


def get_readable_time(seconds: int) -> str:
    result = ''
    (days, remainder) = divmod(seconds, 86400)
    days = int(days)
    if days != 0:
        result += f'{days}d'
    (hours, remainder) = divmod(remainder, 3600)
    hours = int(hours)
    if hours != 0:
        result += f'{hours}h'
    (minutes, seconds) = divmod(remainder, 60)
    minutes = int(minutes)
    if minutes != 0:
        result += f'{minutes}m'
    seconds = int(seconds)
    result += f'{seconds}s'
    return result


def is_mega_link(url: str):
    return "mega.nz" in url


def is_url(url: str):
    url = re.findall(URL_REGEX, url)
    if url:
        return True
    return False


def is_magnet(url: str):
    magnet = re.findall(MAGNET_REGEX, url)
    if magnet:
        return True
    return False


def new_thread(fn):
    """To use as decorator to make a function call threaded.
    Needs import
    from threading import Thread"""

    def wrapper(*args, **kwargs):
        thread = threading.Thread(target=fn, args=args, kwargs=kwargs)
        thread.start()
        return thread

    return wrapper
