# -*- coding: utf-8 -*-
# by @Codex
import re
import json
import time
from urllib.parse import quote
from html import unescape
from pyquery import PyQuery as pq
import requests
import sys
sys.path.append('..')
from base.spider import Spider

try:
    from curl_cffi import requests as _cffi_requests
    HAS_CFFI = True
except Exception:
    _cffi_requests = None
    HAS_CFFI = False


class Spider(Spider):

    host = "https://xchina.co"
    proxy = ""  # 例如 "http://192.168.0.2:12315/xchina_proxy.php"

    def init(self, extend=""):
        self.host = "https://xchina.co"
        self.proxy = ""
        if extend:
            try:
                cfg = json.loads(extend)
                self.proxy = (cfg.get("proxy") or "").rstrip("/")
            except Exception:
                pass
        self._session()
        self._warm()

    def getName(self):
        pass

    def isVideoFormat(self, url):
        pass

    def manualVideoCheck(self):
        pass

    def destroy(self):
        pass

    headers = {
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
        'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
        'Referer': 'https://xchina.co/',
        'Sec-Ch-Ua': '"Not/A)Brand";v="8", "Chromium";v="134", "Google Chrome";v="134"',
        'Sec-Ch-Ua-Mobile': '?0',
        'Sec-Ch-Ua-Platform': '"Windows"',
        'Sec-Fetch-Dest': 'document',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-Site': 'same-origin',
        'Sec-Fetch-User': '?1',
        'Upgrade-Insecure-Requests': '1',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36',
    }

    def _session(self):
        if not hasattr(self, 'session'):
            self.session = requests.Session()
        self.session.headers.update(self.headers)
        return self.session

    def _warm(self):
        """先访问一次首页，建立会话 Cookie，降低被 Cloudflare 挑战的概率。"""
        try:
            self._session().get(self.host + '/', timeout=15)
        except Exception:
            pass

    def _referer(self, path):
        if '/video/' in path or '/videos/series-' in path:
            return f"{self.host}/videos.html"
        return f"{self.host}/"

    def _get_html(self, path):
        """获取页面 HTML，按 代理 -> curl_cffi -> requests 的顺序选择可用通道。"""
        url = path if path.startswith('http') else f"{self.host}{path}"
        referer = self._referer(path)

        if self.proxy:
            # 服务端代理：由代理服务器用 curl 抓取，绕过 Cloudflare 的 TLS 指纹拦截
            fetch_url = f"{self.proxy}?url={quote(url, safe='')}"
            return self._fetch_retry(fetch_url, referer=url)

        if HAS_CFFI:
            return self._fetch_retry_cffi(url, referer)

        return self._fetch_retry_requests(url, referer)

    def _fetch_retry(self, fetch_url, referer, retries=3):
        """通过基类 self.fetch 请求代理/普通地址。"""
        for attempt in range(retries):
            try:
                r = self.fetch(fetch_url, headers=self.headers, timeout=25)
                text = r.text if hasattr(r, 'text') else ''
                code = r.status_code if hasattr(r, 'status_code') else 200
                if self._is_challenge(code, text):
                    time.sleep(0.8 * (attempt + 1))
                    continue
                return text
            except Exception:
                if attempt == retries - 1:
                    raise
                time.sleep(0.5 * (attempt + 1))
        raise Exception('request failed: %s' % fetch_url)

    def _fetch_retry_requests(self, url, referer, retries=3):
        for attempt in range(retries):
            try:
                r = self._session().get(url, headers={'Referer': referer}, timeout=20)
                text = r.text or ''
                if self._is_challenge(r.status_code, text):
                    time.sleep(0.8 * (attempt + 1))
                    self._warm()
                    continue
                return text
            except requests.RequestException:
                if attempt == retries - 1:
                    raise
                time.sleep(0.5 * (attempt + 1))
        raise Exception('request failed: %s' % url)

    def _fetch_retry_cffi(self, url, referer, retries=3):
        for attempt in range(retries):
            try:
                r = _cffi_requests.get(url, impersonate='chrome',
                                       headers={'Referer': referer, 'Accept-Language': 'zh-CN,zh;q=0.9'},
                                       timeout=20)
                text = r.text or ''
                if self._is_challenge(r.status_code, text):
                    time.sleep(0.8 * (attempt + 1))
                    continue
                return text
            except Exception:
                if attempt == retries - 1:
                    raise
                time.sleep(0.5 * (attempt + 1))
        raise Exception('request failed: %s' % url)

    def _is_challenge(self, code, text):
        if code in (403, 503):
            return True
        low = (text or '')[:3000].lower()
        return any(k in low for k in ('just a moment', 'attention required', 'cf-chl', 'enable javascript'))

    def getpq(self, path=''):
        data = self._get_html(path)
        try:
            return pq(data)
        except Exception:
            return pq(data.encode('utf-8'))

    def homeContent(self, filter):
        data = self.getpq('')
        catdata = self.getpq('/categories.html')
        classes = []
        for a in catdata('.category-container .parent a').items():
            href = a.attr('href')
            name = a.text().strip()
            if not href or not name:
                continue
            name = re.sub(r'\s*\(\d+\)\s*$', '', name)
            classes.append({'type_name': name, 'type_id': href})
        result = {}
        result['class'] = classes
        result['list'] = self.getlist(data('.item.video'))
        return result

    def homeVideoContent(self):
        pass

    def categoryContent(self, tid, pg, filter, extend):
        if '/videos/series-' not in tid:
            path = f"/videos.html?page={pg}"
        else:
            base = tid[:-5] if tid.endswith('.html') else tid
            path = f"{base}/{pg}.html"
        data = self.getpq(path)
        result = {}
        result['list'] = self.getlist(data('.item.video'))
        result['page'] = pg
        result['pagecount'] = 9999
        result['limit'] = 90
        result['total'] = 999999
        return result

    def detailContent(self, ids):
        data = self.getpq(ids[0])
        info = self.jsonld(data)
        vod_name = data('h1').text().strip() or info.get('name', '')
        vod_pic = info.get('thumbnailUrl') or data('meta[property="og:image"]').attr('content') or ''
        breadcrumbs = info.get('breadcrumbs', [])
        if len(breadcrumbs) > 2:
            type_name = unescape(' / '.join(breadcrumbs[1:-1]))
        else:
            type_name = unescape(breadcrumbs[1]) if len(breadcrumbs) > 1 else ''
        vod_year = info.get('uploadDate', '')[:4]
        actors = [p.get('name', '') for p in info.get('actor', []) if p.get('name')]
        vod = {
            'vod_name': vod_name,
            'vod_pic': vod_pic,
            'type_name': type_name,
            'vod_year': vod_year,
            'vod_actor': ' / '.join(actors),
            'vod_remarks': info.get('duration', ''),
            'vod_content': info.get('description', '') or vod_name,
            'vod_play_from': 'xChina',
            'vod_play_url': f"正片${ids[0]}"
        }
        return {'list': [vod]}

    def searchContent(self, key, quick, pg="1"):
        path = f"/search.html?keyword={quote(key)}"
        data = self.getpq(path)
        return {'list': self.getlist(data('.item.video'))}

    def playerContent(self, flag, id, vipFlags):
        page_url = id if id.startswith('http') else f"{self.host}{id}"
        try:
            html = self._get_html(page_url)
            m = re.search(r"src:\s*'([^']+\.m3u8[^']*)'", html)
            if not m:
                m = re.search(r'src:\s*"([^"]+\.m3u8[^"]*)"', html)
            if not m:
                m = re.search(r'https?://[^"\'\s]+\.m3u8[^"\'\s]*', html)
            if not m:
                raise Exception('未找到播放地址')
            url = m.group(1)
            headers = {
                'Referer': f'{self.host}/',
                'origin': self.host,
                'User-Agent': self.headers.get('User-Agent', '')
            }
            return {'parse': 0, 'url': url, 'header': headers}
        except Exception:
            headers = {
                'Referer': f'{self.host}/',
                'origin': self.host,
                'User-Agent': self.headers.get('User-Agent', '')
            }
            return {'parse': 1, 'url': page_url, 'header': headers}

    def localProxy(self, param):
        pass

    def liveContent(self, url):
        pass

    def jsonld(self, data):
        result = {'breadcrumbs': []}
        raw = data.html()
        m = re.search(r'<script type="application/ld\+json">(.*?)</script>', raw, re.S)
        if not m:
            return result
        try:
            items = json.loads(m.group(1))
        except Exception:
            return result
        for it in items:
            if it.get('@type') == 'VideoObject':
                result['name'] = it.get('name', '')
                result['description'] = it.get('description', '')
                result['thumbnailUrl'] = it.get('thumbnailUrl', '')
                result['uploadDate'] = it.get('uploadDate', '')
                result['duration'] = self.iso_duration(it.get('duration', ''))
                result['actor'] = it.get('actor', [])
            if it.get('@type') == 'BreadcrumbList':
                result['breadcrumbs'] = [x.get('name', '') for x in it.get('itemListElement', [])][1:]
        return result

    def iso_duration(self, value):
        if not value:
            return ''
        m = re.match(r'PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?', value)
        if not m:
            return value
        h = int(m.group(1) or 0)
        mi = int(m.group(2) or 0)
        s = int(m.group(3) or 0)
        if h:
            return f"{h:02d}:{mi:02d}:{s:02d}"
        return f"{mi:02d}:{s:02d}"

    def getlist(self, data):
        videos = []
        for i in data.items():
            a = i('a[href^="/video/"]').eq(0)
            href = a.attr('href')
            if not href:
                continue
            title = i('.title a').text().strip() or a.attr('title') or ''
            pic = self.parse_style_url(i('.img').attr('style'))
            duration = ''
            for tag in i('.tags div').items():
                if tag('i.fa-clock').length:
                    duration = tag.text().strip()
                    break
            videos.append({
                'vod_id': href,
                'vod_name': title,
                'vod_pic': pic,
                'vod_remarks': duration
            })
        return videos

    def parse_style_url(self, style):
        if not style:
            return ''
        m = re.search(r"url\(['\"]?([^'\")]+)", style)
        return m.group(1) if m else ''