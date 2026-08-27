# -*- coding: utf-8 -*-
# Qinav (www.qinav.com) TVBox 采集爬虫
#
# 站点结构：
#   首页    /                          (.list_box 下的 ul，每个 ul 一个视频)
#   分类    /site/{parent}/{child}.html  分页 /site/{parent}/{child}-{page}.html
#   分类页  /site.html                  (h3=父站, .word 内 a=子分类)
#   详情    /video/{id}.html
#   播放页  /embed/{id}.html            (const url = '...m3u8')
#   搜索    POST /?module=tags&action=keyword  -> 302 -> /tags/{tagid}.html
#           分页 /tags/{tagid}-{page}.html
#
# 反爬：Cloudflare 仅被动检测，无 TLS 指纹/请求头完整性拦截，普通 requests 即可。
import re
import sys
import requests
from pyquery import PyQuery as pq

sys.path.append('..')
from base.spider import Spider


class Spider(Spider):

    host = "https://www.qinav.com"

    USER_AGENT = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/110.0.0.0 Safari/537.36")

    headers = {
        'User-Agent': USER_AGENT,
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
        'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
        'Referer': 'https://www.qinav.com/',
    }

    # ------------------------------------------------------------------ 生命周期
    def init(self, extend=""):
        self._session = requests.Session()
        self._session.headers.update(self.headers)
        self._tag_cache = {}

    def getName(self):
        pass

    def isVideoFormat(self, url):
        pass

    def manualVideoCheck(self):
        pass

    def destroy(self):
        pass

    # ------------------------------------------------------------------ 网络层
    def _get(self, path):
        url = path if path.startswith('http') else f"{self.host}{path}"
        r = self._session.get(url, timeout=15)
        r.encoding = 'utf-8'
        return r.text

    def getpq(self, path=''):
        return pq(self._get(path))

    # ------------------------------------------------------------------ TVBox 接口
    def homeContent(self, filter):
        # 分类列表来自 /site.html（父站 h3 + 子分类 a）
        catdata = self.getpq('/site.html')
        classes = []
        seen = set()
        parent = ''
        for child in catdata('.box').children().items():
            if child.is_('h3'):
                parent = child.text().strip()
            elif child.is_('div'):
                for a in child('a[href^="/site/"]').items():
                    href = a.attr('href')
                    name = a.text().strip()
                    if not href or not name:
                        continue
                    if not re.match(r'^/site/\d+/\d+\.html$', href):
                        continue
                    cls = f'{parent}·{name}' if parent else name
                    if href not in seen:
                        seen.add(href)
                        classes.append({'type_name': cls, 'type_id': href})

        # 首页最新列表
        home = self.getpq('/')
        return {'class': classes, 'list': self.getlist(home('ul'))}

    def homeVideoContent(self):
        pass

    def categoryContent(self, tid, pg, filter, extend):
        pg = int(pg or 1)
        data = self.getpq(self._page_path(tid, pg))
        return {
            'list': self.getlist(data('ul')),
            'page': pg,
            'pagecount': 9999,
            'limit': 90,
            'total': 999999,
        }

    def _page_path(self, tid, pg):
        """ /site/x/y.html -> /site/x/y-{pg}.html  """
        tid = (tid or '').strip()
        if not tid.endswith('.html'):
            return '/'
        base = tid[:-5]
        if pg <= 1:
            return base + '.html'
        return f'{base}-{pg}.html'

    def detailContent(self, ids):
        data = self.getpq(ids[0])
        vod_name = data('h1').text().strip()
        vod_pic = data('meta[property="og:image"]').attr('content') or ''

        # 简介格式： 简介：{分类}，，{标题}，
        des = data('div.des').text().strip()
        m = re.search(r'简介[:：]\s*([^，,]+)', des)
        type_name = m.group(1).strip() if m else ''
        content = re.sub(r'^简介[:：]\s*', '', des).strip() or vod_name

        vod = {
            'vod_name': vod_name,
            'vod_pic': vod_pic,
            'type_name': type_name,
            'vod_remarks': '',
            'vod_content': content,
            'vod_play_from': 'Qinav',
            'vod_play_url': f'正片${ids[0]}',
        }
        return {'list': [vod]}

    def searchContent(self, key, quick, pg="1"):
        pg = int(pg or 1)
        tagid, html = self._search(key)
        if not tagid:
            return {'list': []}
        if pg <= 1:
            data = pq(html)
        else:
            data = self.getpq(f'/tags/{tagid}-{pg}.html')
        return {'list': self.getlist(data('ul'))}

    def _search(self, key):
        try:
            r = self._session.post(
                self.host + '/?module=tags&action=keyword',
                data={'keyword': key},
                allow_redirects=True,
                timeout=15,
            )
            r.encoding = 'utf-8'
            m = re.search(r'/tags/(\d+)', r.url)
            tagid = m.group(1) if m else ''
            return tagid, r.text
        except Exception:
            return '', ''

    def playerContent(self, flag, id, vipFlags):
        vid = self._extract_vid(id)
        page_url = id if id.startswith('http') else f"{self.host}{id}"
        if not vid:
            return {'parse': 1, 'url': page_url, 'header': self.headers}

        embed = f'{self.host}/embed/{vid}.html'
        try:
            html = self._get(embed)
            url = self._extract_m3u8(html)
            if url:
                return {
                    'parse': 0,
                    'url': url,
                    'header': {
                        'User-Agent': self.USER_AGENT,
                        'Referer': embed,
                    },
                }
        except Exception:
            pass
        return {'parse': 1, 'url': page_url, 'header': self.headers}

    def localProxy(self, param):
        pass

    def liveContent(self, url):
        pass

    # ------------------------------------------------------------------ 解析工具
    @staticmethod
    def _extract_vid(id):
        m = re.search(r'/video/(\d+)', id or '')
        return m.group(1) if m else ''

    @staticmethod
    def _extract_m3u8(html):
        m = re.search(r"const\s+url\s*=\s*'([^']+)'", html)
        if not m:
            m = re.search(r"url\s*=\s*'([^']+\.m3u8[^']*)'", html)
        if not m:
            m = re.search(r'https?://[^"\'\s]+\.m3u8[^"\'\s]*', html)
        return m.group(1) if m else ''

    def getlist(self, data):
        videos = []
        for ul in data('ul').items():
            a = ul('a[href^="/video/"]').eq(0)
            href = a.attr('href')
            if not href:
                continue
            title = ul('li.title').text().strip() or a.attr('title') or ''
            pic = ul('img[img]').attr('img') or ul('img').attr('data-src') or ''
            remarks = ul('li.view span').text().strip()
            videos.append({
                'vod_id': href,
                'vod_name': title,
                'vod_pic': pic,
                'vod_remarks': remarks,
            })
        return videos
