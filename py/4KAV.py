# -*- coding: utf-8 -*-
# by @嗷呜
import re
import sys
from pyquery import PyQuery as pq
sys.path.append('..')
from base.spider import Spider


class Spider(Spider):

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

    # 站点在 Cloudflare 后加了拦截: 首次访问(无 Cookie)返回 403 并下发
    # Set-Cookie(langID / ASP.NET_SessionId), 带上 Cookie 刷新后才会放行,
    # 等价于浏览器“第一次打开 403, 刷新后正常”。
    # 因此这里统一保存并回传 Cookie, 首次请求若被 403 拦截会自动带 Cookie 重试一次。
    # 请求头改为与 UA 匹配的现代桌面 Chrome, 避免 UA / sec-ch-ua 不一致被识别为机器人。
    headers = {
        'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
        'accept-language': 'zh-CN,zh;q=0.9,en;q=0.8',
        'accept-encoding': 'gzip, deflate',
        'sec-ch-ua': '"Chromium";v="152", "Not?A_Brand";v="24", "Google Chrome";v="152"',
        'sec-ch-ua-mobile': '?0',
        'sec-ch-ua-platform': '"Windows"',
        'sec-fetch-dest': 'document',
        'sec-fetch-mode': 'navigate',
        'sec-fetch-site': 'none',
        'sec-fetch-user': '?1',
        'upgrade-insecure-requests': '1',
        'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36'
    }

    host = "https://4k-av.com"

    # /movie/ 页面提供的细分标签(站点标签页同时含电影与剧集, 排序与分类页相同)
    movie_tags = [
        ('动作', '/tag/%E5%8A%A8%E4%BD%9C/'),
        ('剧情', '/tag/%E5%89%A7%E6%83%85/'),
        ('冒险', '/tag/%E5%86%92%E9%99%A9/'),
        ('喜剧', '/tag/%E5%96%9C%E5%89%A7/'),
        ('国产剧', '/tag/%E5%9B%BD%E4%BA%A7%E5%89%A7/'),
        ('恐怖', '/tag/%E6%81%90%E6%80%96/'),
        ('战争', '/tag/%E6%88%98%E4%BA%89/'),
        ('科幻', '/tag/%E7%A7%91%E5%B9%BB/'),
        ('动画', '/tag/%E5%8A%A8%E7%94%BB/'),
        ('韩剧', '/tag/%E9%9F%A9%E5%89%A7/'),
        ('犯罪', '/tag/%E7%8A%AF%E7%BD%AA/'),
        ('纪录片', '/tag/%E7%BA%AA%E5%BD%95%E7%89%87/'),
    ]

    # ---------- Cookie 管理 ----------
    def _cookie_jar(self):
        if not hasattr(self, '_ck'):
            self._ck = {}
        return self._ck

    def _save_cookies(self, resp):
        try:
            jar = getattr(resp, 'cookies', None)
            if jar is not None:
                for c in jar:
                    self._cookie_jar()[c.name] = c.value
        except Exception:
            pass

    def _cookie_str(self):
        ck = self._cookie_jar()
        if not ck:
            return ''
        return '; '.join('{}={}'.format(k, v) for k, v in ck.items())

    def _fetch_text(self, path=''):
        url = path if path.startswith('http') else '{}{}'.format(self.host, path or '')
        resp = None
        for _ in range(2):  # 第一次无 Cookie -> 403 + Set-Cookie; 第二次带 Cookie -> 放行(等同手动刷新)
            try:
                ck = self._cookie_jar()
                if ck:
                    resp = self.fetch(url, headers=self.headers, cookies=dict(ck))
                else:
                    resp = self.fetch(url, headers=self.headers)
            except TypeError:
                # 部分运行环境/本地调试桩的 fetch() 不支持 cookies 参数
                try:
                    resp = self.fetch(url, headers=self.headers)
                except Exception:
                    resp = None
            except Exception:
                resp = None
            if resp is None:
                break
            self._save_cookies(resp)
            try:
                if resp.status_code == 200:
                    break
            except Exception:
                break
        try:
            return (resp.text if resp is not None else '') or ''
        except Exception:
            return ''

    # ---------- 分页排序处理 ----------
    # 站点分页是“倒序”的: page-1.html 是最旧, 页码越大越新,
    # 分类根页(如 /tv/、/movie/、/tag/xx/)就是最后一页=最新。
    # TVBox 习惯第一页看最新, 因此把 TVBox 第 pg 页映射到站点第 (total-pg+1) 页,
    # 第 1 页直接取分类根页。
    def _cat_state(self):
        if not hasattr(self, '_cat'):
            self._cat = {}
        return self._cat

    def _parse_page_total(self, text):
        try:
            m = re.search(r'页次\s*(\d+)\s*/\s*(\d+)', text or '')
            if m:
                return int(m.group(2))
        except Exception:
            pass
        return 0

    def _ensure_category(self, tid):
        tid = tid if tid.endswith('/') else '{}/'.format(tid)
        st = self._cat_state()
        if tid not in st:
            root_text = self._fetch_text(tid)   # 根页=最新, 同时可解析出总页数
            total = self._parse_page_total(root_text)
            st[tid] = {'total': total if total > 0 else 1, 'root': root_text}
        return st[tid]

    def homeContent(self, filter):
        data = self.getpq()
        result = {}
        classes = []
        for k in list(data('#category ul li').items())[:-1]:
            classes.append({
                'type_name': k.text(),
                'type_id': k('a').attr('href')
            })
        # 追加 /movie/ 页上的细分标签分类
        for name, href in self.movie_tags:
            classes.append({'type_name': name, 'type_id': href})
        result['class'] = classes
        result['list'] = self.getlist(data('#MainContent_scrollul ul li'), '.poster span')
        return result

    def homeVideoContent(self):
        pass

    def categoryContent(self, tid, pg, filter, extend):
        tid = tid if tid.endswith('/') else '{}/'.format(tid)
        try:
            pg = int(pg)
        except Exception:
            pg = 1
        if pg < 1:
            pg = 1
        st = self._ensure_category(tid)
        total = st['total']
        if pg == 1:
            text = st['root'] or self._fetch_text(tid)
        else:
            n = total - pg + 1
            if n < 1:
                n = 1
            text = self._fetch_text('{}page-{}.html'.format(tid, n))
        data = pq(text or '')
        result = {}
        result['list'] = self.getlist(data('#MainContent_newestlist .virow .NTMitem'))
        result['page'] = pg
        result['pagecount'] = total if total > 0 else 1
        result['limit'] = 90
        result['total'] = total * 90
        return result

    def detailContent(self, ids):
        data = self.getpq(ids[0])
        v = data('#videoinfo')
        vod = {
            'vod_name': data('#tophead h1').text().split(' ')[0],
            'type_name': v('#MainContent_tags.tags a').text(),
            'vod_year': v('#MainContent_videodetail.videodetail a').text(),
            'vod_remarks': v('#MainContent_titleh12 h2').text(),
            'vod_content': v('p.cnline').text(),
            'vod_play_from': '4KAV',
            'vod_play_url': ''
        }
        vlist = data('#rtlist li')
        jn = '{}_'.format(vod['vod_name']) if 'EP0' in vlist.eq(0)('span').text() else ''
        if vlist:
            c = ['{}{}${}'.format(jn, i('span').text(), i('a').attr('href')) for i in list(vlist.items())[1:]]
            c.insert(0, '{}{}${}'.format(jn, vlist.eq(0)('span').text(), ids[0]))
            vod['vod_play_url'] = '#'.join(c)
        else:
            vod['vod_play_url'] = '{}$'.format(vod['vod_name']) + ids[0]
        return {'list': [vod]}

    def searchContent(self, key, quick, pg="1"):
        # 站点搜索表单字段名为 y(旧版为 x/k)
        data = self.getpq('/s?y={}'.format(key))
        return {'list': self.getlist(data('#MainContent_newestlist .virow.search .NTMitem.Main'))}

    def playerContent(self, flag, id, vipFlags):
        try:
            data = self.getpq(id)
            p, url = 0, data('#MainContent_videowindow source').attr('src')
            if not url:
                raise Exception("未找到播放地址")
        except Exception as e:
            p, url = 1, '{}{}'.format(self.host, id)
        headers = {
            'origin': self.host,
            'referer': '{}/'.format(self.host),
            'sec-ch-ua': self.headers['sec-ch-ua'],
            'sec-ch-ua-platform': self.headers['sec-ch-ua-platform'],
            'user-agent': self.headers['user-agent'],
        }
        ck = self._cookie_str()
        if ck:
            headers['cookie'] = ck
        return {'parse': p, 'url': url, 'header': headers}

    def localProxy(self, param):
        pass

    def liveContent(self, url):
        pass

    def getlist(self, data, y='.resyear label[title="分辨率"]'):
        videos = []
        for i in data.items():
            ns = i('.title h2').text().split(' ')
            videos.append({
                'vod_id': i('.title a').attr('href'),
                'vod_name': ns[0],
                'vod_pic': i('.poster img').attr('src'),
                'vod_remarks': ns[-1] if len(ns) > 1 else '',
                'vod_year': i(y).text()
            })
        return videos

    def getpq(self, path=''):
        data = self._fetch_text(path)
        try:
            return pq(data)
        except Exception as e:
            print(str(e))
            return pq(data.encode('utf-8'))