from django.core.management.base import BaseCommand

from axes.attempts import reset


class Command(BaseCommand):
    help = 'Reset all access attempts and lockouts for given IP addresses'

    def add_arguments(self, parser):
        parser.add_argument('ip', nargs='+', type=str)

    def handle(self, *args, **options):
        count = 0

        for ip in options['ip']:
            count += reset(ip=ip)

        if count:
            self.stdout.write('{0} attempts removed.'.format(count))
        else:
            self.stdout.write('No attempts found.')
