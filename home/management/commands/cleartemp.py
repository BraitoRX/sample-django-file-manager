
from django.core.management.base import BaseCommand
import os
import time
from django.conf import settings

class Command(BaseCommand):
    help = 'Clears the temporary media folder.'

    def handle(self, *args, **kwargs):
        temp_dir_path = os.path.join(settings.MEDIA_ROOT, 'Temp')
        now = time.time()
        cutoff = now - (24 * 60 * 60)  # 24 horas

        for filename in os.listdir(temp_dir_path):
            file_path = os.path.join(temp_dir_path, filename)
            if os.path.isfile(file_path):
                file_age = os.stat(file_path).st_mtime
                if file_age < cutoff:
                    try:
                        os.remove(file_path)
                        self.stdout.write(self.style.SUCCESS(f'Deleted {file_path}'))
                    except Exception as e:
                        self.stdout.write(self.style.ERROR(f'Failed to delete {file_path}. Reason: {e}'))

        self.stdout.write(self.style.SUCCESS('Temporary media folder cleared.'))
