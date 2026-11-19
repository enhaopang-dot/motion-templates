# -*- coding: utf-8 -*-
"""复查 72 款模板的下载开关，把新开放的包抓进 library/

用法:
  python check_downloads.py               # 只查，打印状态表
  python check_downloads.py --fetch       # 查完把能下载的全抓下来
  python check_downloads.py --id 358192   # 只查某一款

判读依据：官网模板页正文。关闭时页面写「下载开关保持关闭 / downloads remained closed in this release」，
开放时页面出现 .motion 下载链接或「下载已开放」。两边都识别不到就标 unknown，不瞎猜。
"""
import argparse, json, os, re, sys, time, urllib.request

sys.stdout = open(sys.stdout.fileno(), 'w', encoding='utf-8', closefd=False)
SKILL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(SKILL, 'data', 'catalog.json')
UA = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
      '(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36 Edg/126.0.0.0')

CLOSED = ('下载开关保持关闭', 'downloads remained closed')
# 待达标：页面写"支持数据达标后开放免费下载"——不是关了，是还没到量
PENDING = ('support goals', '支持数据达标', 'once the linked post exceeds')
OPEN = ('free template download', '下载已开放')


def fetch(url, timeout=25):
    req = urllib.request.Request(url, headers={'User-Agent': UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode('utf-8', errors='replace')


def probe(page_url):
    try:
        html = fetch(page_url)
    except Exception as e:
        return 'error', str(e)[:80]
    low = html.lower()
    if any(k in html for k in CLOSED):
        return 'closed', ''
    if any(k.lower() in low for k in PENDING):
        return 'pending', '支持量未达标，达标后开放'
    if any(k.lower() in low for k in OPEN):
        return 'open', ''
    return 'unknown', ''


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--fetch', action='store_true')
    ap.add_argument('--id', default='')
    ap.add_argument('--delay', type=float, default=0.8)
    a = ap.parse_args()

    cat = json.load(open(DATA, encoding='utf-8'))['templates']
    todo = [t for t in cat if not a.id or str(t['repositoryId']) == a.id]
    report = []
    for i, t in enumerate(todo, 1):
        state, note = probe(t['website'])
        report.append({'id': t['repositoryId'], 'name': t['title']['zh'], 'state': state, 'page': t['website'], 'note': note})
        print(f"[{i:>2}/{len(todo)}] {state:<8} {t['repositoryId']:>7} {t['title']['zh']}")
        if i < len(todo):
            time.sleep(a.delay)

    opened = [r for r in report if r['state'] == 'open']
    cnt = {k: sum(1 for r in report if r['state'] == k) for k in ('open', 'pending', 'closed', 'unknown', 'error')}
    print(f"\n开放 {cnt['open']} / 待达标 {cnt['pending']} / 关闭 {cnt['closed']} "
          f"/ 未知 {cnt['unknown']} / 出错 {cnt['error']}")
    out = os.path.join(SKILL, 'data', 'download-state.json')
    json.dump({'checked_at': time.strftime('%Y-%m-%d %H:%M'), 'report': report}, open(out, 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1)
    print('状态表:', out)

    if a.fetch and opened:
        here = os.path.dirname(os.path.abspath(__file__))
        for r in opened:
            print(f"\n=== 抓取 {r['id']} {r['name']} ===")
            os.system(f'"{sys.executable}" "{os.path.join(here, "motion_tpl.py")}" setup --template {r["id"]}')


if __name__ == '__main__':
    main()
