# -*- coding: utf-8 -*-
# 91吃瓜 (www.91cg1.com) TVBox 采集爬虫（Typecho + DPlayer，HLS m3u8）
#
# 结构与 mrds66.com 完全一致（同一套模板）：
#   首页     /
#   分类     /category/{slug}/        分页 /category/{slug}/{N}/
#   详情     /archives/{id}/
#   搜索     /search/{kw}/            分页 /search/{kw}/{N}/
#
# 播放地址：详情页 data-config 里的 m3u8 是带签名、有时效的，需实时抓取。
# 封面图：AES 加密，通过图片代理解密后显示。
# 全部用字符串解析，不依赖 lxml/pyquery，避免 TVBox 内置环境编码误判报错。
import json
import sys
import requests
from html import unescape
from urllib.parse import quote

sys.path.append('..')
from base.spider import Spider


class Spider(Spider):

    host = 'https://www.91cg1.com'

    img_proxy = ''

    USER_AGENT = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                  '(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')

    headers = {
        'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
        'accept-language': 'zh-CN,zh;q=0.9,en;q=0.8',
        'user-agent': USER_AGENT,
        'referer': 'https://www.91cg1.com/',
    }

    CATEGORIES = [
        ('zxcghl', '今日吃瓜'),
        ('sports-live', '体育直播'),
        ('sstp', '偷拍·热门'),
        ('sstp/live', '偷拍·监控'),
        ('sstp/replay', '偷拍·回放'),
        ('rsdg', '最高点击'),
        ('zdtop', '91周榜'),
        ('ydtop', '91月榜'),
        ('bcdg', '必吃大瓜'),
        ('whhl', '网红黑料'),
        ('mxhl', '明星黑料'),
        ('qwys', '社会奇闻'),
        ('mrds', '每日大赛'),
        ('dydj', 'AI短剧'),
        ('lpsd', '深夜撸片'),
        ('hjll', '海角乱伦'),
        ('91th', '91探花'),
        ('crdm', '成人动漫'),
        ('xsjlb', '师生专栏'),
        ('fclv', '反差靓女'),
        ('tgqg', '投稿求瓜'),
        ('gcwh', '网黄合集'),
        ('aikj', '明星AI'),
        ('zptp', '自拍偷拍'),
        ('lqzk', '猎奇重口'),
    ]

    def init(self, extend=''):
        self._session = requests.Session()
        self._session.headers.update(self.headers)
        self.img_proxy = 'http://192.168.0.3/cg91_img.php'
        if extend:
            try:
                cfg = json.loads(extend) if isinstance(extend, str) else extend
                if cfg.get('img_proxy'):
                    self.img_proxy = cfg['img_proxy'].rstrip('/')
            except Exception:
                pass

    def getName(self):
        pass

    def isVideoFormat(self, url):
        pass

    def manualVideoCheck(self):
        pass

    def destroy(self):
        pass

    # ------------------------------------------------------------------ 网络层
    def _get(self, path, referer=None):
        url = path if path.startswith('http') else f'{self.host}{path}'
        h = {'referer': referer} if referer else {}
        r = self._session.get(url, headers=h, timeout=15)
        r.encoding = 'utf-8'
        return r.text

    # ------------------------------------------------------------------ TVBox 接口
    def homeContent(self, filter):
        raw = self._get('/')
        classes = [{'type_name': name, 'type_id': '/category/' + slug + '/'} for slug, name in self.CATEGORIES]
        return {'class': classes, 'list': self.getlist(raw)}

    def homeVideoContent(self):
        pass

    def categoryContent(self, tid, pg, filter, extend):
        pg = int(pg or 1)
        raw = self._get(self._page_path(tid, pg))
        return {
            'list': self.getlist(raw),
            'page': pg,
            'pagecount': 9999,
            'limit': 90,
            'total': 999999,
        }

    def _page_path(self, tid, pg):
        tid = (tid or '').strip()
        if not tid:
            tid = '/'
        if pg <= 1:
            return tid
        if tid == '/':
            return f'/page/{pg}/'
        if not tid.endswith('/'):
            tid = tid + '/'
        return f'{tid}{pg}/'

    def detailContent(self, ids):
        vid = ids[0] if ids else ''
        raw = self._get(vid)

        vod_name = self._meta_content(raw, 'property="og:title"') or self._meta_content(raw, 'itemprop="headline"') or ''
        if not vod_name:
            i = raw.find('<title>')
            if i >= 0:
                j = raw.find('</title>', i)
                if j >= 0:
                    vod_name = unescape(raw[i + 7:j]).strip()

        desc = self._meta_content(raw, 'property="og:description"') or vod_name
        rel = self._meta_content(raw, 'itemprop="dateModified"') or ''
        if rel:
            rel = rel[:10]

        pic = ''
        i = raw.find('data-xkrkllgl="')
        if i >= 0:
            i += len('data-xkrkllgl="')
            j = raw.find('"', i)
            if j >= 0:
                pic = raw[i:j]
        pic = self._pic(pic)

        urls = self._extract_m3u8(raw)
        lines = []
        seen = set()
        counts = {}
        multi = self._extract_multi_episodes(raw) if raw.count("data-config='") > 1 else []
        if multi:
            for label, u in multi:
                if u in seen:
                    continue
                seen.add(u)
                lines.append(label + chr(36) + u)
        else:
            series = self._collect_series(raw)
            if len(series) > 1:
                for label, u in series:
                    if u in seen:
                        continue
                    seen.add(u)
                    lines.append(label + chr(36) + u)
            elif urls:
                for u in urls:
                    if u in seen:
                        continue
                    seen.add(u)
                    base = 'H265' if '/m3m/' in u else '高清'
                    n = counts.get(base, 0) + 1
                    counts[base] = n
                    label = base if n == 1 else base + str(n)
                    lines.append(label + chr(36) + u)
            else:
                for title, href in self._extract_ranking(raw)[:20]:
                    try:
                        sub = self._get(href)
                    except Exception:
                        continue
                    sub_urls = self._extract_m3u8(sub)
                    if not sub_urls:
                        continue
                    u = sub_urls[0]
                    if u in seen:
                        continue
                    seen.add(u)
                    label = title or '视频'
                    n = counts.get(label, 0) + 1
                    counts[label] = n
                    if n > 1:
                        label = label + str(n)
                    lines.append(label + chr(36) + u)

        play_from = ''
        play_url = ''
        if lines:
            play_from = '在线'
            play_url = '#'.join(lines)

        vod = {
            'vod_id': vid,
            'vod_name': vod_name,
            'vod_pic': pic,
            'vod_content': desc or vod_name,
            'vod_remarks': rel,
            'vod_play_from': play_from,
            'vod_play_url': play_url,
        }
        return {'list': [vod]}

    def searchContent(self, key, quick, pg='1'):
        pg = int(pg or 1)
        kw = quote((key or '').strip(), safe='')
        path = f'/search/{kw}/' if pg <= 1 else f'/search/{kw}/{pg}/'
        try:
            raw = self._get(path)
            return {'list': self.getlist(raw)}
        except Exception:
            return {'list': []}

    def playerContent(self, flag, id, vipFlags):
        url = id
        if url.startswith('http'):
            return {'parse': 0, 'jx': 0, 'url': url, 'header': {'user-agent': self.USER_AGENT, 'referer': self.host + '/'}}
        return {'parse': 1, 'jx': 0, 'url': url, 'header': {'user-agent': self.USER_AGENT}}

    def localProxy(self, param):
        pass

    def liveContent(self, url):
        pass

    # ------------------------------------------------------------------ 解析工具
    def _pic(self, url):
        if not url:
            return ''
        if url.startswith('//'):
            url = 'https:' + url
        if self.img_proxy and url.startswith('https://pic.hdhwqx.cn/'):
            return self.img_proxy + '?url=' + quote(url, safe='')
        return url

    def _getlist_realtime(self, html):
        videos = []
        seen = set()
        pos = 0
        while True:
            i = html.find('realtime-card', pos)
            if i < 0:
                break
            start = html.rfind('<a ', 0, i)
            if start < 0:
                start = i - 200
            end = html.find('</a>', i)
            if end < 0:
                end = i + 500
            block = html[start:end]
            pos = end + 1

            href = ''
            j = block.find('href="')
            if j >= 0:
                j += 6
                k = block.find('"', j)
                if k >= 0:
                    href = block[j:k]
            if not href or href in seen:
                continue
            seen.add(href)

            title = ''
            j = block.find('aria-label="')
            if j >= 0:
                j += len('aria-label="')
                k = block.find('"', j)
                if k >= 0:
                    title = unescape(block[j:k]).strip()
            if not title:
                j = block.find('alt="')
                if j >= 0:
                    j += 5
                    k = block.find('"', j)
                    if k >= 0:
                        title = unescape(block[j:k]).strip()
            if not title:
                continue

            pic = ''
            j = block.find('data-xkrkllgl="')
            if j >= 0:
                j += len('data-xkrkllgl="')
                k = block.find('"', j)
                if k >= 0:
                    pic = block[j:k]
            pic = self._pic(pic)

            remarks = ''
            j = block.find('realtime-card__status')
            if j >= 0:
                j = block.find('>', j)
                if j >= 0:
                    k = block.find('<', j + 1)
                    if k >= 0:
                        remarks = block[j + 1:k].strip()

            videos.append({
                'vod_id': href,
                'vod_name': title,
                'vod_pic': pic,
                'vod_remarks': remarks,
            })
        return videos

    def _meta_content(self, raw, key):
        i = raw.find(key)
        if i < 0:
            return ''
        i = raw.find('content="', i)
        if i < 0:
            return ''
        i += len('content="')
        j = raw.find('"', i)
        if j < 0:
            return ''
        return unescape(raw[i:j]).strip()

    def _label_from_title_attr(self, tt):
        s = tt.strip()
        if len(s) >= 3 and s[-3:].isdigit():
            return '第' + str(int(s[-3:])) + '集'
        return ''

    def _extract_multi_episodes(self, raw):
        episodes = []
        pos = 0
        n = 0
        while True:
            i = raw.find("data-config='", pos)
            if i < 0:
                break
            j = raw.find("'", i + len("data-config='"))
            if j < 0:
                break
            cfg = raw[i + len("data-config='"):j]
            pos = j + 1
            u = ''
            mi = cfg.find('.m3u8')
            if mi >= 0:
                s2 = cfg.rfind('https', 0, mi)
                e2 = cfg.find('"', mi)
                if s2 >= 0 and e2 >= 0:
                    u = cfg[s2:e2].replace(chr(92) + '/', '/').strip()
            if not u:
                continue
            n += 1
            label = ''
            ti = raw.rfind('data-video_title="', 0, i)
            if ti >= 0:
                tj = raw.find('"', ti + len('data-video_title="'))
                if tj >= 0:
                    tt = raw[ti + len('data-video_title="'):tj]
                    label = self._label_from_title_attr(tt)
            if not label:
                label = '第' + str(n) + '集'
            episodes.append((label, u))
        return episodes

    def _series_key(self, title):
        i = title.find('第')
        if i >= 0 and title.find('集', i) > i:
            return title[:i].strip()
        return ''

    def _episode_label(self, title):
        i = title.find('第')
        if i >= 0:
            j = title.find('集', i)
            if j >= 0:
                return title[i:j + 1]
        return title

    def _collect_series(self, raw):
        cur_title = self._meta_content(raw, 'property="og:title"') or ''
        cur_key = self._series_key(cur_title)
        if not cur_key:
            urls = self._extract_m3u8(raw)
            return [(self._episode_label(cur_title) or cur_title, urls[0])] if urls else []

        episodes = []
        seen = set()
        cur = raw
        for _ in range(30):
            urls = self._extract_m3u8(cur)
            t = self._meta_content(cur, 'property="og:title"') or ''
            label = self._episode_label(t) or t
            if urls:
                episodes.append((label, urls[0]))
            nxt = ''
            for lt, h in self._extract_ranking(cur):
                if h and '/archives/' in h and h not in seen and self._series_key(lt) == cur_key:
                    seen.add(h)
                    nxt = h
                    break
            if not nxt:
                break
            try:
                cur = self._get(nxt)
            except Exception:
                break
        episodes.reverse()
        return episodes

    def _extract_ranking(self, raw):
        entries = []
        seen = set()
        pos = 0
        while True:
            i = raw.find('btn btn-primary', pos)
            if i < 0:
                break
            start = raw.rfind('<a ', 0, i)
            if start < 0:
                pos = i + 10
                continue
            end = raw.find('</a>', i)
            if end < 0:
                pos = i + 10
                continue
            block = raw[start:end]
            pos = end + 4

            href = ''
            j = block.find('href="')
            if j >= 0:
                j += 6
                k = block.find('"', j)
                if k >= 0:
                    href = block[j:k]
            if not href or '/archives/' not in href or href in seen:
                continue
            seen.add(href)

            title = ''
            j = block.find('>')
            if j >= 0:
                title = unescape(block[j + 1:]).strip()
            title = title.split('|')[0].replace('点击查看详情', '').strip()
            if not title:
                title = '视频'
            entries.append((title, href))
        return entries

    def _extract_m3u8(self, raw):
        urls = []
        seen = set()
        pos = 0
        bs = chr(92)
        while True:
            i = raw.find('.m3u8', pos)
            if i < 0:
                break
            start = raw.rfind('https', 0, i)
            if start < 0:
                start = i - 200
                if start < 0:
                    start = 0
            end = raw.find('"', i + 5)
            if end < 0:
                end = i + 220
            u = raw[start:end]
            u = u.replace(bs + '/', '/').strip()
            if 'm3u8' in u and u.startswith('http') and u not in seen:
                seen.add(u)
                urls.append(u)
            pos = i + 5
        return urls

    def getlist(self, html):
        if 'realtime-card' in html:
            return self._getlist_realtime(html)
        videos = []
        seen = set()
        parts = html.split('<article ')
        for part in parts[1:]:
            block = part.split('</article>', 1)[0]
            if 'BlogPosting' not in block:
                continue
            href = ''
            i = block.find('/archives/')
            if i >= 0:
                j = block.find('"', i)
                if j >= 0:
                    href = block[i:j]
            if not href or href in seen:
                continue
            seen.add(href)

            title = ''
            i = block.find('itemprop="headline">')
            if i >= 0:
                i += len('itemprop="headline">')
                j = block.find('<div', i)
                if j < 0:
                    j = block.find('</h2>', i)
                if j >= 0:
                    title = unescape(block[i:j]).strip()
            if not title:
                continue

            date = ''
            i = block.find('itemprop="datePublished"')
            if i >= 0:
                i = block.find('>', i)
                if i >= 0:
                    j = block.find('<', i + 1)
                    if j >= 0:
                        date = block[i + 1:j].strip()
            if date:
                date = date.replace('•', '').replace('·', '').strip()

            pic = ''
            i = block.find("loadBannerDirect('")
            if i >= 0:
                i += len("loadBannerDirect('")
                j = block.find("'", i)
                if j >= 0:
                    pic = block[i:j]
            pic = self._pic(pic)

            videos.append({
                'vod_id': href,
                'vod_name': title,
                'vod_pic': pic,
                'vod_remarks': date,
            })
        return videos
