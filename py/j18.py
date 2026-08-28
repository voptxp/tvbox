# -*- coding: utf-8 -*-
# 18J.TV (18j.tv) TVBox 采集爬虫（MacCMS 类站点）
#
# 结构（UTF-8）：
#   首页   /vod/                         (.box 列表)
#   分类   /t/{id}/                       分页 /t/{id}/page/{page}/
#   标签   /label/sort/                   (分类导航)
#   详情   /v/{id}/                       (h1/封面 + const source = '...m3u8')
#   搜索   /index.php/vod/search.html?wd=关键词
#
# 播放地址：详情页内嵌 JS： const source = 'https://.../index.m3u8';
import re
import json
import sys
from pyquery import PyQuery as pq

sys.path.append('..')
from base.spider import Spider


class Spider(Spider):

    host = "https://18j.tv"

    USER_AGENT = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/110.0.0.0 Safari/537.36")

    headers = {
        'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
        'accept-language': 'zh-CN,zh;q=0.9,en;q=0.8',
        'user-agent': USER_AGENT,
        'referer': 'https://18j.tv/',
    }

    def init(self, extend=""):
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
    def _get(self, path):
        url = path if path.startswith('http') else f"{self.host}{path}"
        return self.fetch(url, headers=self.headers).text

    def getpq(self, path=''):
        data = self._get(path)
        try:
            return pq(data)
        except Exception:
            return pq(data.encode('utf-8'))

    # ------------------------------------------------------------------ TVBox 接口
    def homeContent(self, filter):
        data = self.getpq('/vod/')
        # 分类列表（去分类页拿 /t/{id}/）
        cat = self.getpq('/label/sort/')
        classes = []
        seen = set()
        for a in cat('a[href^="/t/"]').items():
            href = a.attr('href')
            name = a.text().strip()
            if not href or not name:
                continue
            if href in seen:
                continue
            seen.add(href)
            classes.append({'type_name': name, 'type_id': href})
        return {'class': classes, 'list': self.getlist(data)}

    def homeVideoContent(self):
        pass

    def categoryContent(self, tid, pg, filter, extend):
        pg = int(pg or 1)
        data = self.getpq(self._page_path(tid, pg))
        return {
            'list': self.getlist(data),
            'page': pg,
            'pagecount': 9999,
            'limit': 90,
            'total': 999999,
        }

    def _page_path(self, tid, pg):
        tid = (tid or '').strip().rstrip('/')
        if pg <= 1:
            return tid + '/' if tid else '/'
        return f'{tid}/page/{pg}/'

    def detailContent(self, ids):
        data = self.getpq(ids[0])
        vod_name = data('h1').text().strip()
        if not vod_name:
            vod_name = data('meta[property="og:title"]').attr('content') or ''
        if not vod_name:
            vod_name = data('title').text().strip()
        poster = data('meta[property="og:image"]').attr('content') or ''
        if not poster:
            for img in data('img').items():
                src = img.attr('data-original') or img.attr('src') or ''
                if src and ('poster' in src or 'cdn' in src):
                    poster = src
                    break
        if poster.startswith('//'):
            poster = 'https:' + poster
        desc = data('meta[name="description"]').attr('content') or ''

        # 播放地址：const source = '...m3u8';
        m = re.search(r"const\s+source\s*=\s*'([^']+)'", data.html())
        play_url = m.group(1) if m else ''

        vod = {
            'vod_name': vod_name,
            'vod_pic': poster,
            'vod_content': desc or vod_name,
            'vod_play_from': '正片' if play_url else '',
            'vod_play_url': ('正片$' + play_url) if play_url else '',
        }
        return {'list': [vod]}

    def searchContent(self, key, quick, pg="1"):
        pg = int(pg or 1)
        try:
            data = self.getpq(f'/index.php/vod/search.html?wd={self._q(key)}&page={pg}')
            return {'list': self.getlist(data)}
        except Exception:
            return {'list': []}

    def playerContent(self, flag, id, vipFlags):
        url = id if id.startswith('http') else id
        return {
            'parse': 0,
            'jx': 0,
            'url': url,
            'header': {
                'user-agent': self.USER_AGENT,
                'referer': self.host + '/',
            },
        }

    def localProxy(self, param):
        pass

    def liveContent(self, url):
        pass

    # ------------------------------------------------------------------ 解析工具
    @staticmethod
    def _q(s):
        try:
            from urllib.parse import quote
            return quote(s, safe='')
        except Exception:
            return s

    def getlist(self, data):
        videos = []
        seen = set()
        for it in data('div.box').items():
            a = it('a[href^="/v/"]').eq(0)
            href = a.attr('href')
            if not href:
                continue
            title = it('.info .title').text().strip() or a.attr('title') or ''
            pic = it('img').attr('data-original') or it('img').attr('src') or ''
            if pic.startswith('//'):
                pic = 'https:' + pic
            remarks = it('.vodlist_img span').text().strip() or ''
            if href in seen:
                continue
            seen.add(href)
            videos.append({
                'vod_id': href,
                'vod_name': title,
                'vod_pic': pic,
                'vod_remarks': remarks,
            })
        return videos
