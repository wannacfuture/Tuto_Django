from django.core.management.base import BaseCommand

from axes.attempts import reset


class Command(BaseCommand):
    help = 'Reset all access attempts and lockouts'

    def handle(self, *args, **options):  # pylint: disable=unused-argument
        count = reset()

        if count:
            self.stdout.write('{0} attempts removed.'.format(count))
        else:
            self.stdout.write('No attempts found.')
