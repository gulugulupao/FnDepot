#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""应用源索引自动同步（零依赖，Python 3.8+）。

从各应用仓库的 GitHub Release 读取最新元数据（tag / asset.digest / asset.size /
published_at），自动更新本仓库的 moo.json 与 fnpack.json：
  - 每个应用保留最近 KEEP 个版本（默认 2）
  - 顶层字段（moo）跟最新版
  - 同版本换包（sha 变化）默认拒绝——防止用户缓存校验和失配
  - 无变化不写文件（幂等）

数据源是 GitHub Release API 自带的 asset.digest（sha256）与 size，
无需下载 FPK 本体，快且校验值权威。

用法：
  python3 tools/sync_index.py            # 同步
  python3 tools/sync_index.py --dry-run  # 只打印将要做的改动
  python3 tools/sync_index.py --check    # 仅校验索引是否已最新（最新退出0，需更新退出1）
"""
import argparse
import datetime
import json
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MOO = os.path.join(ROOT, 'moo.json')
FNDEPOT = os.path.join(ROOT, 'fnpack.json')
KEEP = 2

# appname -> (仓库, fpk 文件名模板)
# 模板里 {v} 替换为裸版本号；固定文件名（如 FnSmartdisk.fpk）不带 {v} 即可。
APPS = {
    'fncleankernel': ('gulugulupao/fncleankernel', 'fncleankernel-V{v}.fpk'),
    'onekey-overclock': ('gulugulupao/onekey-overclock', 'OneKey-OC-v{v}-node.fpk'),
    'com.gulugulupao.smartdisk': ('gulugulupao/fnsmartdisk', 'FnSmartdisk.fpk'),
    'chipbeat': ('gulugulupao/chipbeat', 'chipbeat.fpk'),
    'clamsentinel': ('gulugulupao/clamsentinel', 'clamsentinel-v{v}.fpk'),
}


def gh_api(path):
    """调 gh api 拿 JSON；本地与 Actions 均预装 gh CLI。"""
    p = subprocess.run(['gh', 'api', path], stdout=subprocess.PIPE,
                       stderr=subprocess.PIPE)
    if p.returncode != 0:
        raise RuntimeError('gh api %s 失败: %s' %
                           (path, p.stderr.decode('utf-8', 'replace')[:300]))
    return json.loads(p.stdout.decode('utf-8'))


def bare_version(tag):
    v = (tag or '').strip()
    for prefix in ('v', 'release-v', 'release-'):
        if v.lower().startswith(prefix) and len(v) > len(prefix):
            return v[len(prefix):]
    return v


def clean_changelog(body, limit=200):
    """Release body 压成一行短说明。"""
    text = (body or '').strip()
    if not text:
        return ''
    # 取第一段非空文本
    line = ''
    for ln in text.splitlines():
        ln = ln.strip().lstrip('#*-').strip()
        if ln:
            line = ln
            break
    for ch in ('\r', '\n', '|'):
        line = line.replace(ch, ' ')
    if len(line) > limit:
        line = line[:limit].rstrip() + '…'
    return line


def fetch_releases(appname, repo, pattern, want):
    """返回 [(version, release_node_dict)]，按版本从新到旧，最多 want 条。"""
    data = gh_api('repos/%s/releases?per_page=20' % repo)
    out = []
    for rel in data:
        if rel.get('prerelease') or rel.get('draft'):
            continue
        tag = rel.get('tag_name') or ''
        ver = bare_version(tag)
        if not ver:
            continue
        fname = pattern.replace('{v}', ver)
        asset = None
        for a in rel.get('assets', []):
            if a.get('name') == fname:
                asset = a
                break
        if not asset:
            continue  # 该 release 没有本应用对应的 fpk，跳过
        digest = (asset.get('digest') or '').lower()
        if not digest.startswith('sha256:'):
            # 老 release 可能没有 digest 字段，跳过（无法提供权威校验和）
            continue
        sha = digest.split(':', 1)[1]
        size = int(asset.get('size') or 0)
        if not sha or not size:
            continue
        node = dict(
            changelog=clean_changelog(rel.get('body')),
            updated_at=rel.get('published_at') or rel.get('created_at') or '',
            packages={'arm': dict(
                download_url=asset.get('browser_download_url') or '',
                sha256=sha, size=size)})
        if not node['packages']['arm']['download_url']:
            continue
        out.append((ver, node))
        if len(out) >= want:
            break
    if not out:
        raise RuntimeError('%s: 未在 %s 找到任何有效 release（检查文件名模板 %s 与 digest 字段）' %
                           (appname, repo, pattern))
    return out


def same_node(a, b):
    return a == b


def sync():
    with open(MOO, encoding='utf-8') as f:
        moo = json.load(f)
    with open(FNDEPOT, encoding='utf-8') as f:
        fndepot = json.load(f)

    changes = []
    for appname, (repo, pattern) in APPS.items():
        if appname not in moo['apps'] or appname not in fndepot['apps']:
            raise RuntimeError('索引里缺少应用 %s（请先手工添加）' % appname)
        fetched = fetch_releases(appname, repo, pattern, KEEP)
        new_releases = {v: n for v, n in fetched}

        # 同版本换包检测
        old_moo_rel = moo['apps'][appname].get('releases', {})
        for ver, node in new_releases.items():
            if ver in old_moo_rel:
                old_sha = old_moo_rel[ver].get('packages', {}).get('arm', {}).get('sha256', '')
                new_sha = node['packages']['arm']['sha256']
                if old_sha and old_sha != new_sha:
                    raise RuntimeError(
                        '%s %s 的 sha256 发生变化（旧 %s… 新 %s…）——'
                        '已发布版本不允许静默换包，请升版本号后重新发布。' %
                        (appname, ver, old_sha[:12], new_sha[:12]))

        # 更新两个索引的 releases
        moo['apps'][appname]['releases'] = new_releases
        fndepot['apps'][appname]['releases'] = new_releases

        # moo 顶层跟最新版
        latest_ver, latest_node = fetched[0]
        top = moo['apps'][appname]
        pkg = latest_node['packages']['arm']
        updated_fields = dict(
            version=latest_ver, download_url=pkg['download_url'],
            sha256=pkg['sha256'], size=round(pkg['size'] / 1048576.0, 2),
            size_bytes=pkg['size'], updated_at=latest_node['updated_at'],
            changelog=latest_node['changelog'])
        for k, v in updated_fields.items():
            if top.get(k) != v:
                changes.append('%s.%s: %r -> %r' % (appname, k, top.get(k), v))
                top[k] = v

        if old_moo_rel != new_releases:
            changes.append('%s.releases: %s -> %s' %
                           (appname, list(old_moo_rel.keys()), list(new_releases.keys())))

    return moo, fndepot, changes


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--check', action='store_true')
    args = ap.parse_args()

    moo, fndepot, changes = sync()

    if not changes:
        print('索引已是最新，无需改动。')
        if args.check:
            sys.exit(0)
        return

    print('检测到 %d 项变更：' % len(changes))
    for c in changes:
        print('  -', c)

    if args.check:
        sys.exit(1)  # 需要更新
    if args.dry_run:
        print('--dry-run：不写文件。')
        return

    for path, obj in [(MOO, moo), (FNDEPOT, fndepot)]:
        tmp = path + '.tmp'
        with open(tmp, 'w', encoding='utf-8') as f:
            json.dump(obj, f, ensure_ascii=False, indent=2)
            f.write('\n')
        os.replace(tmp, path)
        print('已写入', os.path.basename(path))


if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        print('同步失败：%s' % e, file=sys.stderr)
        sys.exit(2)
