# Update git:// URLs to https:// in layer metadata
#
# Replaces git://git.openembedded.org/ and git://git.yoctoproject.org/ with
# their https:// equivalents on LayerItem records. Also rewrites legacy
# http:// cgit web-interface URLs for those hosts to https:// so the
# generated browse/tree/file/commit links work.
#
# References:
#   https://bugzilla.yoctoproject.org/show_bug.cgi?id=16240
#   https://bugzilla.yoctoproject.org/show_bug.cgi?id=16272
#
# Usage:
#   python manage.py update_git_urls --dry-run
#   python manage.py update_git_urls
#
# Copyright (C) 2026 Konsulko Group
# SPDX-License-Identifier: MIT

from django.core.management.base import BaseCommand
from django.db import transaction

from layerindex.models import LayerItem


# Fields on LayerItem that may carry a URL we want to rewrite.
LAYER_URL_FIELDS = (
    'vcs_url',
    'vcs_web_url',
    'vcs_web_tree_base_url',
    'vcs_web_file_base_url',
    'vcs_web_commit_url',
)

# (old_prefix, new_prefix) replacements. Order matters: longer / more-specific
# prefixes must come first so we never partially-match a shorter one.
REPLACEMENTS = (
    # Fetch URLs: git:// -> https://
    ('git://git.openembedded.org/', 'https://git.openembedded.org/'),
    ('git://git.yoctoproject.org/', 'https://git.yoctoproject.org/'),
    ('git://github.com/', 'https://github.com/'),
    ('git://gitlab.com/', 'https://gitlab.com/'),
    ('git://bitbucket.org/', 'https://bitbucket.org/'),
    # Old /cgit/cgit.cgi/ paths redirect to https://git...
    ('http://cgit.openembedded.org/cgit/cgit.cgi/', 'https://git.openembedded.org/'),
    ('https://cgit.openembedded.org/cgit/cgit.cgi/', 'https://git.openembedded.org/'),
    ('http://cgit.openembedded.org/cgit.cgi/', 'https://git.openembedded.org/'),
    ('https://cgit.openembedded.org/cgit.cgi/', 'https://git.openembedded.org/'),
    ('http://git.openembedded.org/cgit/cgit.cgi/', 'https://git.openembedded.org/'),
    ('https://git.openembedded.org/cgit/cgit.cgi/', 'https://git.openembedded.org/'),
    ('http://git.yoctoproject.org/cgit/cgit.cgi/', 'https://git.yoctoproject.org/'),
    ('https://git.yoctoproject.org/cgit/cgit.cgi/', 'https://git.yoctoproject.org/'),
    # Web-interface URLs: http:// -> https:// for the same hosts. Both
    # cgit.openembedded.org and git.yoctoproject.org redirect http to
    # https, but storing https directly avoids the extra round-trip and
    # mixed-content warnings inside the layer index UI.
    ('http://cgit.openembedded.org/', 'https://git.openembedded.org/'),
    ('http://git.yoctoproject.org/', 'https://git.yoctoproject.org/'),
    ('http://github.com/', 'https://github.com/'),
    ('http://gitlab.com/', 'https://gitlab.com/'),
    ('http://bitbucket.org/', 'https://bitbucket.org/'),
)


def rewrite(value):
    """Return (new_value, changed) after applying REPLACEMENTS."""
    if not value:
        return value, False
    new_value = value
    for old, new in REPLACEMENTS:
        if new_value.startswith(old):
            new_value = new + new_value[len(old):]
            # A given URL only matches one prefix, so we can stop here.
            return new_value, True
    return value, False


class Command(BaseCommand):
    help = (
        'Rewrite legacy git:// (and matching http:// cgit) URLs on layer '
        'metadata to their https:// equivalents.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '-n', '--dry-run',
            action='store_true',
            help='Show what would change without writing to the database.',
        )
        parser.add_argument(
            '-q', '--quiet',
            action='store_true',
            help='Only print a summary line.',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        quiet = options['quiet']

        changed_layers = 0
        changed_fields = 0

        # Wrap the whole pass in a transaction so a --dry-run can be rolled
        # back cleanly and a real run is atomic. We bail out at the end if
        # this is a dry run.
        with transaction.atomic():
            for layer in LayerItem.objects.all().order_by('name'):
                layer_changes = []
                for field in LAYER_URL_FIELDS:
                    old_value = getattr(layer, field)
                    new_value, changed = rewrite(old_value)
                    if changed:
                        setattr(layer, field, new_value)
                        layer_changes.append((field, old_value, new_value))

                if layer_changes:
                    changed_layers += 1
                    changed_fields += len(layer_changes)
                    if not quiet:
                        self.stdout.write(
                            self.style.MIGRATE_HEADING(
                                'Layer "%s" (id=%d):' % (layer.name, layer.pk)
                            )
                        )
                        for field, old_value, new_value in layer_changes:
                            self.stdout.write(
                                '  %s:\n    - %s\n    + %s'
                                % (field, old_value, new_value)
                            )
                    if not dry_run:
                        layer.save(update_fields=[c[0] for c in layer_changes])

            if dry_run:
                # Roll back any pending writes (there shouldn't be any since
                # we skipped save(), but stay defensive).
                transaction.set_rollback(True)

        verb = 'Would update' if dry_run else 'Updated'
        self.stdout.write(self.style.SUCCESS(
            '%s %d field(s) across %d layer(s).'
            % (verb, changed_fields, changed_layers)
        ))
