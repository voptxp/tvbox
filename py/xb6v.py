# -*- coding: utf-8 -*-
# 6V电影网 (www.xb6v.com) TVBox 采集爬虫（磁力下载站，EmpireCMS，UTF-8）
#
# 结构：
#   首页   /                            (.widget 里的 <li><a> 文字列表，无封面)
#   分类   /xijupian/ /dongzuopian/ ...  分页 /xijupian/index_2.html
#   详情   /juqingpian/29466.html        (h1/封面/简介 + 磁力 magnet:?...)
#   搜索   POST /e/search/11index.php    (keyboard=关键词)
import re
import json
import sys
import requests
from pyquery import PyQuery as pq

sys.path.append('..')
from base.spider import Spider


class Spider(Spider):

    host = "https://www.xb6v.com"

    USER_AGENT = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/110.0.0.0 Safari/537.36")

    headers = {
        'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
        'accept-language': 'zh-CN,zh;q=0.9,en;q=0.8',
        'user-agent': USER_AGENT,
        'referer': 'https://www.xb6v.com/',
    }

    CATEGORIES = [
        ('/xijupian/', '喜剧片'),
        ('/dongzuopian/', '动作片'),
        ('/aiqingpian/', '爱情片'),
        ('/kehuanpian/', '科幻片'),
        ('/kongbupian/', '恐怖片'),
        ('/juqingpian/', '剧情片'),
        ('/zhanzhengpian/', '战争片'),
        ('/jilupian/', '纪录片'),
        ('/donghuapian/', '动画片'),
        ('/dianshiju/', '电视剧'),
        ('/dianshiju/guoju/', '国剧'),
        ('/dianshiju/duanju/', '短剧'),
        ('/dianshiju/rihanju/', '日韩剧'),
        ('/dianshiju/oumeiju/', '欧美剧'),
        ('/ZongYi/', '综艺'),
    ]

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
        try:
            r = self.fetch(url, headers=self.headers)
            if hasattr(r, 'text'):
                return r.text
        except Exception:
            pass
        r = requests.get(url, headers=self.headers, timeout=15)
        r.encoding = r.apparent_encoding or 'utf-8'
        return r.text

    def getpq(self, path=''):
        data = self._get(path)
        try:
            return pq(data)
        except Exception:
            return pq(data.encode('utf-8'))

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
        if pg <= 1:
            return tid or '/'
        if tid.endswith('/'):
            return f'{tid}index_{pg}.html'
        return f'{tid}/index_{pg}.html'

    def detailContent(self, ids):
        data = self.getpq(ids[0])
        vod_name = data('h1').eq(-1).text().strip()
        if not vod_name:
            t = data('title').text().strip()
            vod_name = t.split('-')[0].strip()

        pic = ''
        for img in data('img').items():
            src = img.attr('src') or ''
            if 'tu.66tutup.com' in src or ('/d/file/' in src):
                pic = src
                break
        if pic.startswith('//'):
            pic = 'https:' + pic

        desc = data('meta[name="description"]').attr('content') or ''

        # 磁力链接（多个，带画质标签）
        froms = []
        urls = []
        for a in data('a[href^="magnet:"]').items():
            u = a.attr('href') or ''
            if not u:
                continue
            label = a.text().strip() or '磁力'
            # 画质：取标签第一个点之前的部分，如 2160p / 1080p
            quality = label.split('.')[0].strip() if '.' in label else label
            froms.append(quality)
            urls.append(f'{quality}${u}')

        if not froms:
            # 兜底：没有磁力就不设播放源
            froms = []
            urls = []

        vod = {
            'vod_name': vod_name,
            'vod_pic': pic,
            'vod_content': desc or vod_name,
            'vod_play_from': '$$$'.join(froms),
            'vod_play_url': '$$$'.join(urls),
        }
        return {'list': [vod]}

    def searchContent(self, key, quick, pg="1"):
        pg = int(pg or 1)
        try:
            r = requests.post(
                self.host + '/e/search/11index.php',
                data={
                    'keyboard': key,
                    'show': 'title',
                    'tempid': '1',
                    'tbname': 'article',
                    'mid': '1',
                    'dopost': 'search',
                },
                headers=self.headers,
                timeout=15,
            )
            r.encoding = r.apparent_encoding or 'utf-8'
            return {'list': self.getlist(pq(r.text))}
        except Exception:
            return {'list': []}

    def playerContent(self, flag, id, vipFlags):
        url = id
        if url.startswith('magnet:') or url.startswith('ed2k:') or url.startswith('thunder:'):
            return {'parse': 0, 'jx': 0, 'url': url, 'header': {}}
        return {'parse': 1, 'jx': 0, 'url': url, 'header': {'user-agent': self.USER_AGENT}}

    def localProxy(self, param):
        pass

    def liveContent(self, url):
        pass

    # ------------------------------------------------------------------ 解析工具
    def getlist(self, data):
        videos = []
        seen = set()
        # 只取正文容器 #post_container 里的 li.post，避开每个页面都相同的“最新电影”侧边栏
        for it in data('#post_container li.post').items():
            a = it('h2 a').eq(0)
            href = a.attr('href') or ''
            title = a.attr('title') or a.text().strip() or ''
            if not title:
                title = it('a[rel="bookmark"]').attr('title') or ''
            title = re.sub(r'<[^>]+>', '', title).strip()
            pic = it('.thumbnail img').attr('src') or ''
            if pic.startswith('//'):
                pic = 'https:' + pic
            date = it('.info_date').text().strip() or ''
            if not href or not title:
                continue
            if href in seen:
                continue
            seen.add(href)
            videos.append({
                'vod_id': href,
                'vod_name': title,
                'vod_pic': pic,
                'vod_remarks': date,
            })
        return videos


