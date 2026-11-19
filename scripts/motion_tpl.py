# -*- coding: utf-8 -*-
"""MotionGit 模板库 · 选模板 + 一条龙出片

用法:
  python motion_tpl.py pick --need "知识讲解 横屏 30秒"
  python motion_tpl.py list --group talk
  python motion_tpl.py setup  --template 385712
  python motion_tpl.py build  --template 385712 --brief my.json --out-dir D:/out/my-video [--skip-render]
  python motion_tpl.py status

设计要点:
- 有本地包的模板走完整链路 plan → prepare → preview → render(-with-audio.mp4)
- 只有文档站的模板不硬造，返回官网取包地址，不假装能出片
- 包体下载优先 jsdelivr 镜像（实测 17.6MB / 11 秒），回落 GitHub Pages 原始地址
"""
import argparse, json, os, shutil, subprocess, sys, zipfile, urllib.request, hashlib

sys.stdout = open(sys.stdout.fileno(), 'w', encoding='utf-8', closefd=False)
SKILL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(SKILL, 'data', 'catalog.json')
LIB = os.path.join(SKILL, 'library')
GROUPS = {'talk': '口播讲解', 'explainer': '讲解/解说', 'art': '艺术视觉', 'product': '产品展示', 'open': '开源测试'}


def load():
    with open(DATA, encoding='utf-8') as f:
        return json.load(f)


def ratio_score(t, want):
    if not want:
        return 0
    return 3 if want.replace(' ', '') in (t.get('ratio'), t.get('orientation')) else 0


def pick(args):
    """画幅是硬条件（不匹配直接压到底），本地可用只是加分项，不能盖过画幅。"""
    cat = load()['templates']
    need = (args.need or '').lower()
    want_ratio = (args.ratio or '').lower().replace(' ', '')
    for kw in ('横屏', '横版'):
        if kw in need:
            want_ratio = want_ratio or '16:9'
    for kw in ('竖屏', '竖版'):
        if kw in need:
            want_ratio = want_ratio or '9:16'
    target_orient = 'portrait' if want_ratio in ('9:16', '3:4') else ('landscape' if want_ratio else '')
    scored = []
    for t in cat:
        s = 0
        title = t['title'].get('zh', '').lower()
        summary = t['summary'].get('zh', '').lower()
        for kw in filter(None, need.split()):
            if kw in title:
                s += 6
            elif kw in summary:
                s += 2
        if GROUPS.get(t['group'], '') and GROUPS[t['group']] in need:
            s += 8
        if target_orient:
            s += 12 if t['orientation'] == target_orient else -25
        if want_ratio:
            s += 20 if t['ratio'] == want_ratio else -20
        if has_package(t['repositoryId']):
            s += 6  # 只做同分优先，不许压过画幅
        if float(t['fps']) >= 50:
            s += 1
        if s > 0:
            scored.append((s, t))
    scored.sort(key=lambda x: -x[0])
    out = []
    for s, t in scored[:args.top]:
        out.append({
            'score': s,
            'id': t['repositoryId'],
            'name': t['title']['zh'],
            'group': GROUPS.get(t['group'], t['group']),
            'ratio': t['ratio'], 'size': f"{t['width']}x{t['height']}", 'fps': t['fps'],
            'why': t['summary']['zh'],
            'ready': has_package(t['repositoryId']),
            'download_state': (t.get('download') or {}).get('availability'),
            'page': t.get('website'),
            'demo': t.get('demo'),
        })
    print(json.dumps({'need': need, 'candidates': out}, ensure_ascii=False, indent=1))
    if out and not out[0]['ready']:
        print('\n[提示] 命中模板目前无公开包，需在官网取包；不能直接用本地包出片。', file=sys.stderr)


def cmd_list(args):
    cat = load()['templates']
    for t in sorted(cat, key=lambda x: (x['group'], x['repositoryId'])):
        if args.group and t['group'] != args.group:
            continue
        mark = '✅' if has_package(t['repositoryId']) else '  '
        print(f"{mark} {t['repositoryId']:>7} [{GROUPS.get(t['group'], t['group'])}] {t['title']['zh']} · {t['ratio']} · {int(float(t['fps']))}fps")


def pkg_dir(tid):
    return os.path.join(LIB, str(tid))


def local_packages(tid):
    d = pkg_dir(tid)
    if not os.path.isdir(d):
        return []
    return [os.path.join(d, f) for f in os.listdir(d) if f.lower().endswith('.motion')]


def has_package(tid):
    """runner 已解压，或目录里有 .motion 包（可现解）"""
    if os.path.isdir(os.path.join(pkg_dir(tid), 'runner', 'core')):
        return True
    return bool(local_packages(tid))


def ensure_extracted(tid):
    """把 library 里现成的 .motion 解到 runner/，优先带 zh 的那个"""
    if os.path.isdir(os.path.join(pkg_dir(tid), 'runner', 'core')):
        return
    pkgs = local_packages(tid)
    if not pkgs:
        raise SystemExit(f'模板 {tid} 本地没有包')
    pkgs.sort(key=lambda p: (0 if '_zh' in os.path.basename(p) or 'zh' in os.path.basename(p).lower() else 1,
                             -os.path.getmtime(p)))
    src = pkgs[0]
    zipfile.ZipFile(src).extractall(os.path.join(pkg_dir(tid), 'runner'))
    print(f'[解压] {os.path.basename(src)} -> runner/')


def find_entry(tid):
    cat = {str(t['repositoryId']): t for t in load()['templates']}
    return cat.get(str(tid))


def download(tid, entry):
    os.makedirs(pkg_dir(tid), exist_ok=True)
    urls = (entry.get('download') or {}).get('urls') or {}
    target = urls.get('zh') or urls.get('en')
    if not target:
        raise SystemExit(f'模板 {tid} 无公开下载地址，请到官网取包：{entry.get("website")}')
    repo = entry['repositoryId']
    name = os.path.basename(target)
    mirrors = [f'https://cdn.jsdelivr.net/gh/motiontemplates/{repo}@main/downloads/{name}', target]
    dst = os.path.join(pkg_dir(tid), name)
    for m in mirrors:
        try:
            print(f'[下载] {m}')
            with urllib.request.urlopen(m, timeout=300) as r, open(dst, 'wb') as f:
                shutil.copyfileobj(r, f)
            if os.path.getsize(dst) > 100000:
                break
        except Exception as e:
            print(f'  失败: {e}')
    else:
        raise SystemExit('所有镜像都失败，改手动下载后放到 ' + pkg_dir(tid))
    h = hashlib.sha256(open(dst, 'rb').read()).hexdigest()
    z = zipfile.ZipFile(dst)
    assert z.testzip() is None, 'ZIP 损坏'
    z.extractall(os.path.join(pkg_dir(tid), 'runner'))
    print(f'[解压] {dst}  sha256={h[:16]}…')
    return dst


def npm_ci(tid):
    runner = os.path.join(pkg_dir(tid), 'runner')
    if os.path.isdir(os.path.join(runner, 'node_modules')):
        return
    subprocess.run('npm ci --no-audit --no-fund', cwd=runner, shell=True, check=True,
                   stdout=subprocess.DEVNULL)


def adapter(tid, *argv):
    runner = os.path.join(pkg_dir(tid), 'runner')
    cmd = ['uv', 'run', 'adapter.py', *argv]
    print('[run]', ' '.join(cmd))
    subprocess.run(cmd, cwd=runner, check=True)


def cmd_setup(args):
    e = find_entry(args.template)
    if not e:
        raise SystemExit('catalog 里没有这个编号')
    if not has_package(args.template):
        download(args.template, e)
    ensure_extracted(args.template)
    npm_ci(args.template)
    print(f'[就绪] {args.template} {e["title"]["zh"]} -> {pkg_dir(args.template)}')


def cmd_build(args):
    tid = str(args.template)
    e = find_entry(tid)
    if not e:
        raise SystemExit('catalog 里没有这个编号')
    if not has_package(tid):
        print('[包缺失] 尝试自动下载…')
        download(tid, e)
    ensure_extracted(tid)
    npm_ci(tid)
    out = os.path.abspath(args.out_dir)
    os.makedirs(out, exist_ok=True)
    brief = os.path.abspath(args.brief)
    adapter(tid, 'plan', '--input', brief, '--out', os.path.join(out, 'plan.json'))
    inst = os.path.join(out, 'instance')
    adapter(tid, 'prepare', '--input', brief, '--out', inst)
    prev = os.path.join(out, 'preview.png')
    adapter(tid, 'preview', '--instance', inst, '--out', prev, '--time', str(args.preview_time))
    print('[预览]', prev)
    if args.skip_render:
        print('[跳过渲染] 用户确认预览后再跑：python motion_tpl.py render --template', tid, '--out-dir', out)
        return
    silent = os.path.join(out, 'silent.mp4')
    adapter(tid, 'render', '--instance', inst, '--out', silent)
    final = os.path.join(out, 'silent-with-audio.mp4')
    print('[成片]', final if os.path.exists(final) else silent)


def cmd_render(args):
    tid = str(args.template)
    out = os.path.abspath(args.out_dir)
    silent = os.path.join(out, 'silent.mp4')
    adapter(tid, 'render', '--instance', os.path.join(out, 'instance'), '--out', silent)
    final = os.path.join(out, 'silent-with-audio.mp4')
    print('[成片]', final if os.path.exists(final) else silent)


def cmd_status(args):
    cat = load()['templates']
    ready = [t for t in cat if has_package(t['repositoryId'])]
    print(f'模板总数 {len(cat)}，本地可用 {len(ready)}')
    for t in ready:
        print(f"  ✅ {t['repositoryId']} {t['title']['zh']} {t['ratio']}")


def main():
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest='cmd', required=True)
    q = sub.add_parser('pick'); q.add_argument('--need', default=''); q.add_argument('--ratio', default=''); q.add_argument('--top', type=int, default=5); q.set_defaults(f=pick)
    q = sub.add_parser('list'); q.add_argument('--group', default=''); q.set_defaults(f=cmd_list)
    q = sub.add_parser('setup'); q.add_argument('--template', required=True); q.set_defaults(f=cmd_setup)
    q = sub.add_parser('build'); q.add_argument('--template', required=True); q.add_argument('--brief', required=True)
    q.add_argument('--out-dir', required=True); q.add_argument('--skip-render', action='store_true')
    q.add_argument('--preview-time', default='2'); q.set_defaults(f=cmd_build)
    q = sub.add_parser('render'); q.add_argument('--template', required=True); q.add_argument('--out-dir', required=True); q.set_defaults(f=cmd_render)
    sub.add_parser('status').set_defaults(f=cmd_status)
    a = p.parse_args()
    a.f(a)


if __name__ == '__main__':
    main()
