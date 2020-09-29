from datetime import datetime


class TimeManager:
    def __init__(self):
        self.start = 0
        self.end = 0
        self.skipped = 0

    def parseDuration(self, duration):
        duration = int(duration)
        m, s = divmod(duration, 60)
        h, m = divmod(m, 60)
        return f"{h:02d}:{m:02d}:{s:02d}"

    def timeParse(self, time):
        seconds = 0
        try:
            seconds = int(time)
        except:
            parts = time.split(":")
            for i in range(len(parts)):
                seconds += int(parts[-i - 1]) * (60 ** i)
        return seconds