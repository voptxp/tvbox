# -*- coding: utf-8 -*-
# xChina (xchina.co) TVBox 采集爬虫
#
# 关键结论（已实测验证）：
#   * 反爬不是 JS 挑战、也不是 TLS 指纹，而是“请求头完整性校验”：
#     只带 User-Agent 会 403，补全 Sec-Ch-Ua / Sec-Fetch-* / Accept-Language
#     等浏览器头即可拿到 200 + 真实 HTML。
#   * 播放地址 m3u8 内嵌在详情页 inline JS：
#       new VideoPlayer('video-player', { src: '.../720.m3u8?expires=...&md5=...' })
#     因此必须实时抓详情页提取这个带签名、有时效性的 URL。
#   * 页面结构：
#       分类    /categories.html                     (.category-container .parent a / .subs a)
#       首页    /                                    (.item.video)
#       系列    /videos/series-{id}.html             (分页 /videos/series-{id}/{pg}.html)
#       搜索    /videos/keyword-{kw}.html            (分页 /videos/keyword-{kw}/{pg}.html)
#       详情    /video/id-{hexid}.html
#
# 部署方式（与 box.json 中 py_xchina 条目对应）：
#   ext.proxy 指向宝塔上的 PHP 代理：
#       http://192.168.0.2:12315/xchina_proxy.php
#   当配置了 proxy 时，所有 HTML 抓取都走该代理（服务端 curl 携带完整浏览器头），
#   这是最稳的通道；未配置 proxy 时依次尝试 curl_cffi / requests。
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
    proxy = ""        # 例如 "http://192.168.0.2:12315/xchina_proxy.php"
    sleep = 0.3       # 两次成功抓取之间的间隔（秒），降低触发风控的概率

    USER_AGENT = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36"
    )
    SEC_CH_UA = '"Not/A)Brand";v="8", "Chromium";v="134", "Google Chrome";v="134"'

    headers = {
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,'
                  'image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
        'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
        'Cache-Control': 'max-age=0',
        'Sec-Ch-Ua': SEC_CH_UA,
        'Sec-Ch-Ua-Mobile': '?0',
        'Sec-Ch-Ua-Platform': '"Windows"',
        'Sec-Fetch-Dest': 'document',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-Site': 'none',
        'Sec-Fetch-User': '?1',
        'Upgrade-Insecure-Requests': '1',
        'User-Agent': USER_AGENT,
    }

    # ------------------------------------------------------------------ 生命周期
    def init(self, extend=""):
        self.host = "https://xchina.co"
        self.proxy = ""
        self.sleep = 0.3
        if extend:
            try:
                cfg = json.loads(extend) if isinstance(extend, str) else extend
                self.proxy = (cfg.get("proxy") or "").rstrip("/")
                if cfg.get("host"):
                    self.host = cfg["host"].rstrip("/")
                if cfg.get("sleep") is not None:
                    self.sleep = float(cfg["sleep"])
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

    # ------------------------------------------------------------------ 网络层
    def _session(self):
        if not hasattr(self, 'session'):
            self.session = requests.Session()
        self.session.headers.update(self.headers)
        return self.session

    def _warm(self):
        """先访问一次首页预热（走与 _get_html 相同的通道），失败不阻塞。"""
        try:
            self._get_html('/')
        except Exception:
            pass

    def _referer(self, path):
        if '/video/' in path or '/videos/' in path:
            return f"{self.host}/videos.html"
        return f"{self.host}/"

    def _get_html(self, path):
        """获取页面 HTML，按 代理 -> curl_cffi -> requests 顺序选择通道。"""
        url = path if path.startswith('http') else f"{self.host}{path}"

        if self.proxy:
            # 代理用 path 模式：只传相对路径，避免在 query 里出现完整 URL 被宝塔/nginx 拦截
            rel = url
            if url.startswith(self.host):
                rel = url[len(self.host):]
            if not rel:
                rel = '/'
            if rel.startswith('/'):
                fetch_url = f"{self.proxy}?path={quote(rel, safe='')}"
            else:
                fetch_url = f"{self.proxy}?url={quote(url, safe='')}"
            text = self._fetch_retry_proxy(fetch_url)
        elif HAS_CFFI:
            text = self._fetch_retry_cffi(url, self._referer(path))
        else:
            text = self._fetch_retry_requests(url, self._referer(path))

        if self.sleep > 0:
            time.sleep(self.sleep)
        return text

    def _fetch_retry_proxy(self, fetch_url, retries=3):
        """代理通道：PHP 代理成功时返回纯 HTML；失败返回 502 + JSON {"error":...}。"""
        for attempt in range(retries):
            try:
                r = self.fetch(fetch_url, headers=self.headers, timeout=25)
                text = r.text if hasattr(r, 'text') else ''
                code = r.status_code if hasattr(r, 'status_code') else 200
                stripped = text.lstrip()
                ok = code == 200 and stripped and not stripped.startswith('{"error"')
                if ok and not self._is_challenge(code, text):
                    return text
            except Exception:
                pass
            if attempt < retries - 1:
                time.sleep(0.8 * (attempt + 1))
        raise Exception('proxy request failed: %s' % fetch_url)

    def _fetch_retry_requests(self, url, referer, retries=3):
        for attempt in range(retries):
            try:
                r = self._session().get(url, headers={'Referer': referer}, timeout=20)
                text = r.text or ''
                if not self._is_challenge(r.status_code, text):
                    return text
                self._warm()
            except requests.RequestException:
                pass
            if attempt < retries - 1:
                time.sleep(0.8 * (attempt + 1))
        raise Exception('request failed: %s' % url)

    def _fetch_retry_cffi(self, url, referer, retries=3):
        for attempt in range(retries):
            try:
                r = _cffi_requests.get(
                    url, impersonate='chrome',
                    headers={'Referer': referer, 'Accept-Language': 'zh-CN,zh;q=0.9'},
                    timeout=20)
                text = r.text or ''
                if not self._is_challenge(r.status_code, text):
                    return text
            except Exception:
                pass
            if attempt < retries - 1:
                time.sleep(0.8 * (attempt + 1))
        raise Exception('request failed: %s' % url)

    def _is_challenge(self, code, text):
        if code in (403, 503):
            return True
        low = (text or '')[:4000].lower()
        return any(k in low for k in (
            'just a moment', 'attention required', 'cf-chl', 'enable javascript',
            'checking your browser', 'cf_chl'))

    def getpq(self, path=''):
        data = self._get_html(path)
        try:
            return pq(data)
        except Exception:
            return pq(data.encode('utf-8'))

    # ------------------------------------------------------------------ TVBox 接口
    def homeContent(self, filter):
        data = self.getpq('')
        catdata = self.getpq('/categories.html')

        classes = []
        seen = set()

        # 父级系列：中文AV / 日本AV / 模特私拍 / ...
        for a in catdata('.category-container .parent a').items():
            href = a.attr('href')
            name = re.sub(r'\s*\(\d+\)\s*$', '', a.text().strip())
            if href and name and href.startswith('/videos/series-') and href not in seen:
                seen.add(href)
                classes.append({'type_name': name, 'type_id': href})

        # 子级系列：麻豆传媒 / 糖心Vlog / ...，便于按片商浏览
        for a in catdata('.category-container .subs a').items():
            href = a.attr('href')
            name = a('.title').text().strip() or a.text().strip()
            if href and name and href.startswith('/videos/series-') and href not in seen:
                seen.add(href)
                classes.append({'type_name': name, 'type_id': href})

        return {'class': classes, 'list': self.getlist(data('.item.video'))}

    def homeVideoContent(self):
        pass

    def categoryContent(self, tid, pg, filter, extend):
        pg = int(pg or 1)
        data = self.getpq(self._category_path(tid, pg))
        return {
            'list': self.getlist(data('.item.video')),
            'page': pg,
            'pagecount': 9999,
            'limit': 90,
            'total': 999999,
        }

    def _category_path(self, tid, pg):
        """把分类 id（系列/搜索 URL）转换成带页码的真实地址。"""
        tid = (tid or '').strip()
        if not tid or tid == '/videos.html':
            return '/videos.html'

        # 去掉可能残留的页码后缀 /N.html
        tid = re.sub(r'/\d+\.html$', '.html', tid)

        if tid.endswith('.html'):
            base = tid[:-5]
            if base.startswith('/videos/series-') or base.startswith('/videos/keyword-'):
                if pg <= 1:
                    return base + '.html'
                return f"{base}/{pg}.html"

        # 其它无法识别的分类回退到聚合页
        return '/videos.html'

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
            'vod_play_url': f"正片${ids[0]}",
        }
        return {'list': [vod]}

    def searchContent(self, key, quick, pg="1"):
        pg = int(pg or 1)
        kw = quote((key or '').strip(), safe='')
        base = f'/videos/keyword-{kw}'
        path = base + '.html' if pg <= 1 else f'{base}/{pg}.html'
        data = self.getpq(path)
        return {'list': self.getlist(data('.item.video'))}

    def playerContent(self, flag, id, vipFlags):
        page_url = id if id.startswith('http') else f"{self.host}{id}"
        headers = {
            'Referer': page_url,
            'Origin': self.host,
            'User-Agent': self.USER_AGENT,
        }
        try:
            html = self._get_html(page_url)
            url = self._extract_m3u8(html)
            if url:
                return {'parse': 0, 'url': url, 'header': headers}
        except Exception:
            pass
        # 兜底：交给播放器 WebView 解析详情页
        return {'parse': 1, 'url': page_url, 'header': headers}

    def localProxy(self, param):
        pass

    def liveContent(self, url):
        pass

    # ------------------------------------------------------------------ 解析工具
    @staticmethod
    def _extract_m3u8(html):
        m = re.search(r"src:\s*'([^']+\.m3u8[^']*)'", html)
        if not m:
            m = re.search(r'src:\s*"([^"]+\.m3u8[^"]*)"', html)
        if not m:
            m = re.search(r'https?://[^"\'\s]+\.m3u8[^"\'\s]*', html)
        return m.group(1) if m else ''

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
                result['breadcrumbs'] = [
                    x.get('name', '') for x in it.get('itemListElement', [])
                ][1:]
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
                'vod_remarks': duration,
            })
        return videos

    def parse_style_url(self, style):
        if not style:
            return ''
        m = re.search(r"url\(['\"]?([^'\")]+)", style)
        return m.group(1) if m else ''



