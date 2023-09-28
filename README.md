## scan-unused
[![Tests](https://github.com/WalshKieran/scan-unused/actions/workflows/run_tests.yml/badge.svg)](https://github.com/WalshKieran/scan-unused/actions/workflows/run_tests.yml)

Find, delete and notify users of unused files on a shared filesystem.
Similar to e.g. `find /tmp -type f -atime +3 -delete` but:
1. Non-empty folders have a last used time of the maximum contained "atime"
2. Empty folders have a last used time of "mtime"

Due to notifications (grouping by file owner) and multiple range requests, more than one pass is needed so they are stored in memory.

## Install
```bash
pip install git+https://github.com/WalshKieran/scan-unused
```

## Check
```bash
scan-unused --days 3 --dryrun /directory/to/scan
```

## Scan & Delete
```bash
scan-unused --days 3 --email-domain unsw.edu.au --email-limit 50 --force /directory/to/scan
```

## Usage
```
usage: scan-unused [-h] [--days N] [--force]
                   [--email-domain EMAIL_DOMAIN]
                   [--email-days EMAIL_DAYS]
                   [--email-limit EMAIL_LIMIT]
                   [--email-template EMAIL_TEMPLATE]
                   [--email-whitelist EMAIL_WHITELIST [EMAIL_WHITELIST ...]]
                   [--dryrun]
                   directory

Recursively delete files/folders older than a
specified number of days

positional arguments:
  directory

options:
  -h, --help            show this help message
                        and exit
  --days N              number of days after
                        which a file is
                        considered old (default
                        3)
  --force               Force yes for
                        confirmation (dangerous)
  --email-domain EMAIL_DOMAIN
                        Send an email to each
                        owner@domain about future
                        deletions (modify
                        template for more
                        control)
  --email-days EMAIL_DAYS
                        if provided, only mention
                        files that will be
                        deleted in this exact
                        number of days
  --email-limit EMAIL_LIMIT
                        limit number of paths in
                        emails
  --email-template EMAIL_TEMPLATE
                        path to override jinja2
                        template
  --email-whitelist EMAIL_WHITELIST [EMAIL_WHITELIST ...]
                        limit users that can
                        receive emails
  --dryrun              Print files/emails that
                        would have been
                        deleted/sent
```