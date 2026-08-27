# -*- coding: utf-8 -*-
# 电影港 (www.dygangs.net) TVBox 采集爬虫（下载站）
#
# 结构：
#   首页    /                              (最新列表)
#   分类    /ys/ /bd/ /gy/ /gp/ /dsj/ ...  (分页 /ys/index_2.htm)
#   详情    /ys/20260826/60412.htm         (.title 标题 + 封面 + 简介 + 磁力/网盘)
#   搜索    POST /e/search/index.php       (keyboard=关键词)
#
# 播放/下载地址：详情页内嵌
#   磁力   magnet:?xt=urn:btih:...
#   网盘   迅雷/夸克/百度网盘链接
import re
import sys
import requests
from urllib.parse import quote
from pyquery import PyQuery as pq

sys.path.append('..')
from base.spider import Spider


class Spider(Spider):

    host = "https://www.dygangs.net"

    USER_AGENT = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/110.0.0.0 Safari/537.36")

    headers = {
        'User-Agent': USER_AGENT,
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
        'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
        'Referer': 'https://www.dygangs.net/',
    }

    # 分类：路径 -> 名称
    CATEGORIES = [
        ('/ys/', '最新电影'),
        ('/bd/', '经典高清'),
        ('/gy/', '国配电影'),
        ('/gp/', '经典港片'),
        ('/dsj/', '国剧'),
        ('/dsj1/', '日韩剧'),
        ('/yx/', '美剧'),
        ('/zy/', '综艺'),
        ('/dmq/', '动漫'),
        ('/jilupian/', '纪录片'),
        ('/1080p/', '高清原盘'),
        ('/3d/', '3D电影'),
    ]

    def init(self, extend=""):
        self._session = requests.Session()
        self._session.headers.update(self.headers)

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
        # 站点为 GB2312/GBK 编码
        r.encoding = r.apparent_encoding or 'gbk'
        return r.text

    def getpq(self, path=''):
        return pq(self._get(path))

    # ------------------------------------------------------------------ TVBox 接口
    def homeContent(self, filter):
        data = self.getpq('/')
        classes = [{'type_name': name, 'type_id': path} for path, name in self.CATEGORIES]
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
        tid = (tid or '').strip()
        if not tid.endswith('/'):
            tid = tid + '/'
        if pg <= 1:
            return tid
        return f'{tid}index_{pg}.htm'

    def detailContent(self, ids):
        data = self.getpq(ids[0])
        vod_name = data('.title a').text().strip()
        if not vod_name:
            t = data('title').text().strip()
            vod_name = t.split('_')[0].strip()
        pic = ''
        for img in data('img').items():
            src = img.attr('src') or ''
            if 'tu.66tutup.com' in src:
                pic = src
                break
        desc = data('p').text().strip()

        # 只取磁力（下载站，磁力边下边播）
        magnet = data('a[href^="magnet:"]').attr('href') or ''

        vod = {
            'vod_name': vod_name,
            'vod_pic': pic,
            'vod_content': desc or vod_name,
            'vod_play_from': '磁力' if magnet else '',
            'vod_play_url': ('磁力$' + magnet) if magnet else '',
        }
        return {'list': [vod]}

    def searchContent(self, key, quick, pg="1"):
        pg = int(pg or 1)
        try:
            # 站点为 GBK 编码，关键词需按 GBK 百分号编码（quote 直接处理 bytes）
            kw = quote(key.encode('gbk', 'ignore'), safe='')
            r = self._session.post(
                self.host + '/e/search/index.php',
                data=f'keyboard={kw}&tempid=1&tbname=article&show=title,smalltext&page={pg}',
                headers={'Content-Type': 'application/x-www-form-urlencoded'},
                timeout=15,
            )
            r.encoding = r.apparent_encoding or 'gbk'
            data = pq(r.text)
            return {'list': self.getlist(data)}
        except Exception:
            return {'list': []}

    def playerContent(self, flag, id, vipFlags):
        url = id
        if url.startswith('magnet:') or url.startswith('ed2k:') or url.startswith('thunder:'):
            return {'parse': 0, 'jx': 0, 'url': url, 'header': {}}
        # 兜底：网页链接 → webview
        return {'parse': 1, 'jx': 0, 'url': url, 'header': {'User-Agent': self.USER_AGENT}}

    def localProxy(self, param):
        pass

    def liveContent(self, url):
        pass

    # ------------------------------------------------------------------ 解析工具
    def getlist(self, data):
        videos = []
        seen = set()
        # 详情链接形如 /ys/20260826/60412.htm（分类/日期/ID.htm），只取站内相对链接
        for a in data('a[href]').items():
            href = a.attr('href') or ''
            if not re.search(r'^/\w+/\d{8}/\d+\.htm$', href):
                continue
            if '/dyzt/' in href:
                continue  # 电影专题是合集，结构不同，跳过
            text = a.text().strip()
            img = a('img').attr('src') or ''
            if not text or img:
                continue  # 只要标题链接（有文本无内嵌图）
            if text.startswith('['):
                continue  # 跳过 [本站教程] 之类置顶帖
            if href in seen:
                continue
            seen.add(href)
            pic = data(f'a[href="{href}"] img').attr('src') or ''
            videos.append({
                'vod_id': href,
                'vod_name': text,
                'vod_pic': pic,
                'vod_remarks': '',
            })
        return videos








