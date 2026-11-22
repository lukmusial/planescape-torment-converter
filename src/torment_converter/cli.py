"""Command line interface: `torment-convert convert ...` and `torment-convert validate ...`."""
import argparse
import os
import sys

from .resources import GameResources, find_game_root

EE_DIR_NAME = 'Planescape Torment - Enhanced Edition'

# Where installs usually live. Steam names the PST:EE folder "Project P".
EE_INSTALL_CANDIDATES = [
    '/Applications/' + EE_DIR_NAME,
    '~/Applications/' + EE_DIR_NAME,
    '~/Library/Application Support/Steam/steamapps/common/Project P',
    '~/.steam/steam/steamapps/common/Project P',
    '~/.local/share/Steam/steamapps/common/Project P',
    '~/GOG Games/Planescape Torment Enhanced Edition',
    r'C:\Program Files (x86)\Steam\steamapps\common\Project P',
    r'C:\GOG Games\Planescape Torment Enhanced Edition',
    r'C:\Program Files (x86)\GOG Galaxy\Games\Planescape Torment Enhanced Edition',
    r'C:\Program Files\Beamdog\Games\00806',
]


def default_ee_save_dir():
    """Where PST:EE keeps its saves for the current user."""
    if sys.platform.startswith('linux'):
        base = os.environ.get('XDG_DATA_HOME', os.path.expanduser('~/.local/share'))
        return os.path.join(base, EE_DIR_NAME, 'save')
    return os.path.join(os.path.expanduser('~'), 'Documents', EE_DIR_NAME, 'save')


def locate_ee(path):
    candidates = [path] if path else EE_INSTALL_CANDIDATES
    for c in candidates:
        c = os.path.expanduser(c)
        if os.path.isdir(c):
            root = find_game_root(c)
            if root:
                return root
    return None


def save_folders(path):
    """A save folder itself, or every save folder inside a `save` directory."""
    path = os.path.abspath(os.path.expanduser(path))
    has = lambda d: any(f.upper() == 'TORMENT.GAM' for f in os.listdir(d))
    if has(path):
        return [path]
    return sorted(os.path.join(path, d) for d in os.listdir(path)
                  if os.path.isdir(os.path.join(path, d)) and has(os.path.join(path, d)))


def cmd_convert(args):
    from .convert import SaveConverter

    ee_root = locate_ee(args.ee)
    if not ee_root:
        sys.exit('Could not find the Enhanced Edition install (chitin.key). Pass it with --ee.')
    ee = GameResources(ee_root)
    if ee.get('BALDUR', 0x3F5) is None or ee.get('CHARBASE', 0x3F1) is None:
        sys.exit('%s does not look like Planescape: Torment - Enhanced Edition.' % ee_root)
    out_dir = os.path.abspath(os.path.expanduser(args.out or default_ee_save_dir()))

    folders = []
    for src in args.saves:
        found = save_folders(src)
        if not found:
            sys.exit('%s: no original Planescape: Torment saves (TORMENT.GAM) found.' % src)
        folders += found

    print('Enhanced Edition data: %s' % ee_root)
    print('Writing to:            %s' % out_dir)
    failures = 0
    for src in folders:
        dst = os.path.join(out_dir, os.path.basename(src.rstrip(os.sep)) + args.suffix)
        if os.path.exists(dst) and not args.force:
            print('skip  %s (already exists; use --force to overwrite)' % os.path.basename(dst))
            continue
        try:
            report = SaveConverter(ee).convert_folder(src, dst)
        except Exception as ex:          # one broken save should not stop the batch
            failures += 1
            print('FAIL  %s: %s' % (os.path.basename(src), ex))
            continue
        print('ok    %s' % os.path.basename(dst))
        if args.verbose:
            for line in report:
                print('        ' + line)
    return 1 if failures else 0


def cmd_validate(args):
    from .validate import validate_creatures

    ee_root, orig_root = locate_ee(args.ee), find_game_root(args.original)
    if not ee_root or not orig_root:
        sys.exit('Need both --ee and --original game folders (each containing chitin.key).')
    result = validate_creatures(GameResources(orig_root), GameResources(ee_root))
    print('creatures compared:        %d' % result['total'])
    print('identical after convert:   %d' % result['identical'])
    print('header bytes that differ (offset: creatures):')
    for off, n in result['header'][:40]:
        print('  %s: %d' % (off, n))
    print('sections that differ: %s' % (result['sections'] or 'none'))
    return 0


def main(argv=None):
    p = argparse.ArgumentParser(
        prog='torment-convert',
        description='Convert original Planescape: Torment saves for Planescape: Torment - Enhanced Edition.')
    sub = p.add_subparsers(dest='command', required=True)

    c = sub.add_parser('convert', help='convert save folders')
    c.add_argument('saves', nargs='+',
                   help='an original save folder (holding TORMENT.GAM) or the original "save" directory')
    c.add_argument('--ee', help='Enhanced Edition install folder (auto-detected if omitted)')
    c.add_argument('--out', help='EE save directory to write to (default: %s)' % default_ee_save_dir())
    c.add_argument('--suffix', default='', help='text appended to each converted folder name')
    c.add_argument('--force', action='store_true', help='overwrite existing save folders')
    c.add_argument('-v', '--verbose', action='store_true', help='print what was carried over')
    c.set_defaults(func=cmd_convert)

    v = sub.add_parser('validate',
                       help='convert every creature of the original game and compare with the EE copies')
    v.add_argument('--original', required=True, help='original game install folder')
    v.add_argument('--ee', help='Enhanced Edition install folder (auto-detected if omitted)')
    v.set_defaults(func=cmd_validate)

    args = p.parse_args(argv)
    return args.func(args)


if __name__ == '__main__':
    sys.exit(main())
