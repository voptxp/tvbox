# -*- coding: utf-8 -*-
# 飘花电影网 (www.piaohua.com) TVBox 采集爬虫（m3u8 在线流，UTF-8，DedeCMS）
#
# 结构：
#   首页   /                                    (li 列表：封面 + 标题 + 日期)
#   分类   /html/{cat}/index.html               分页 /html/{cat}/list_{N}.html
#   详情   /html/{cat}/{year}/{MMDD}/{id}.html   (h1 + 封面 + 简介 + jianpian:// 链接)
#   搜索   POST /plus/search.php                (kwtype=0&keyword=关键词&searchtype=title)
#
# 播放地址：详情页内嵌 jianpian://pathtype=url&path=https://.../index.m3u8?title=xxx
#           需从 path= 里解析出真实 m3u8 地址。
import re
import sys
import requests
from pyquery import PyQuery as pq

sys.path.append('..')
from base.spider import Spider


class Spider(Spider):

    host = "https://www.piaohua.com"

    USER_AGENT = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/110.0.0.0 Safari/537.36")

    headers = {
        'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
        'accept-language': 'zh-CN,zh;q=0.9,en;q=0.8',
        'user-agent': USER_AGENT,
        'referer': 'https://www.piaohua.com/',
    }

    CATEGORIES = [
        ('/html/dongzuo/index.html', '动作片'),
        ('/html/xiju/index.html', '喜剧片'),
        ('/html/aiqing/index.html', '爱情片'),
        ('/html/kehuan/index.html', '科幻片'),
        ('/html/juqing/index.html', '剧情片'),
        ('/html/xuannian/index.html', '悬疑片'),
        ('/html/zhanzheng/index.html', '战争片'),
        ('/html/kongbu/index.html', '恐怖片'),
        ('/html/zainan/index.html', '灾难片'),
        ('/html/lianxuju/index.html', '连续剧'),
        ('/html/dongman/index.html', '动漫'),
        ('/html/zongyijiemu/index.html', '综艺片'),
        ('/html/lianzaidongman/index.html', '连载动漫'),
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
        base = tid[:-len('index.html')] if tid.endswith('index.html') else tid.rstrip('/') + '/'
        return f'{base}list_{pg}.html'

    def detailContent(self, ids):
        data = self.getpq(ids[0])
        vod_name = data('h1').text().strip()
        if not vod_name:
            vod_name = data('title').text().strip().split('_')[0].strip()

        pic = ''
        for img in data('img').items():
            src = img.attr('src') or ''
            if 'ph.dnscf.vip' in src or 'pic' in src or 'allimg' in src:
                pic = src
                break
        if pic.startswith('//'):
            pic = 'https:' + pic
        elif pic.startswith('/http'):
            pic = pic[1:]  # 修复站点封面 /https:// 前缀 bug

        desc = data('meta[name="description"]').attr('content') or ''

        # 播放链接：jianpian://pathtype=url&path={真实地址}?title=xxx
        # path 可能是 http(s)://...m3u8，也可能是 ftp://...MP4 等，协议无关解析。
        # 每条链接同时输出：荐片(原 jianpian://，P2P) + 直连(抠出的真实地址)。
        froms = []
        urls = []
        seen = set()
        for a in data('a[href^="jianpian://"]').items():
            link = a.attr('href') or ''
            label = a.text().strip() or '正片'
            real_url = self._extract_path(link)
            if link in seen:
                continue
            seen.add(link)
            froms.append(f'荐片·{label}')
            urls.append(f'荐片·{label}${link}')
            # 只有 http(s) 才额外给出直连线路；ftp 等协议交给荐片 P2P 内核
            if real_url and real_url.lower().startswith(('http://', 'https://')):
                froms.append(f'直连·{label}')
                urls.append(f'直连·{label}${real_url}')

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
                self.host + '/plus/search.php',
                data={'kwtype': '0', 'keyword': key, 'searchtype': 'title', 'page': pg},
                headers=self.headers,
                timeout=15,
            )
            r.encoding = r.apparent_encoding or 'utf-8'
            return {'list': self.getlist(pq(r.text))}
        except Exception:
            return {'list': []}

    def playerContent(self, flag, id, vipFlags):
        url = id
        if url.startswith('jianpian://'):
            # 荐片 P2P 协议，交给壳内置 P2P 内核
            return {'parse': 0, 'jx': 0, 'url': url, 'header': {}}
        if url.startswith('http://') or url.startswith('https://'):
            return {
                'parse': 0,
                'jx': 0,
                'url': url,
                'header': {
                    'user-agent': self.USER_AGENT,
                    'referer': self.host + '/',
                },
            }
        # ftp:// 等其它协议：交给播放器尝试
        return {'parse': 0, 'jx': 0, 'url': url, 'header': {}}

    def localProxy(self, param):
        pass

    def liveContent(self, url):
        pass

    # ------------------------------------------------------------------ 解析工具
    @staticmethod
    def _extract_path(link):
        # jianpian://pathtype=url&path={真实地址}[?title=xxx|&title=xxx]
        # 真实地址可能是 http(s)://...m3u8、ftp://...MP4 等，协议无关解析
        m = re.search(r'path=(.+)', link)
        if not m:
            return ''
        url = m.group(1).strip()
        # 去掉站点附加的 ?title= / &title= 标签，保留真实地址里其它 query 参数
        url = re.sub(r'[?&]title=.*$', '', url).strip()
        return url

    def getlist(self, data):
        videos = []
        seen = set()
        # 详情链接形如 /html/juqing/2026/0818/75994.html
        for a in data('a[href]').items():
            href = a.attr('href') or ''
            if not re.search(r'/html/[a-z]+/\d{4}/\d{4}/\d+\.html$', href):
                continue
            li = a.closest('li')
            # 标题：首页是 .txt h3，分类页是 h4 font（分类页无封面）
            title = li('.txt h3').text().strip() or li('h4 font').text().strip() or li('h4').text().strip() or a.text().strip()
            title = re.sub(r'<[^>]+>', '', title)
            title = re.sub(r'\s+', ' ', title).strip()
            pic = li('.pic img').attr('src') or ''
            if pic.startswith('//'):
                pic = 'https:' + pic
            date = li('.txt span').text().strip() or ''
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



