import argparse
import json
import sys

from . import demo
from .auth import get_profile, login


def main():
    if len(sys.argv) > 1 and sys.argv[1] == 'login':
        parser = argparse.ArgumentParser(prog='example-cli login')
        parser.add_argument('--language', default='pt-PT', help='sign-in locale (default: pt-PT)')
        parser.add_argument('--browser', help='Playwright browser engine: chromium, firefox, or webkit (default: chromium)')
        parser.add_argument('--redirect-uri', default='lidl-com.monsieur-cuisine.companion://login/prod', help='OAuth callback URI (default: mobile app URI)')
        try:
            args = parser.parse_args(sys.argv[2:])
        except SystemExit as exc:
            return int(exc.code)
        try:
            login(args.language, args.browser, args.redirect_uri)
        except (RuntimeError, KeyboardInterrupt) as exc:
            if isinstance(exc, KeyboardInterrupt):
                print('\nLogin cancelled.', file=sys.stderr)
                return 130
            print(f'Login failed: {exc}', file=sys.stderr)
            return 1
        return 0

    if len(sys.argv) > 1 and sys.argv[1] == 'profile':
        if len(sys.argv) > 2:
            print('Usage: example-cli profile', file=sys.stderr)
            return 2
        try:
            print(json.dumps(get_profile(), indent=2, ensure_ascii=False))
        except RuntimeError as exc:
            print(f'Profile request failed: {exc}', file=sys.stderr)
            return 1
        return 0

    arg = ' '.join(sys.argv[1:])
    if not arg:
        print('Got nothing to say?')
    else:
        print(demo.echo(arg))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
