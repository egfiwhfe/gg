import requests
import os
import time
from datetime import datetime

class PushPlusNotifier:
    def __init__(self):
        self.token = os.environ.get('PUSHPLUS_TOKEN')
        self.topic = os.environ.get('PUSHPLUS_TOPIC', '')
        self.max_count = int(os.environ.get('PUSH_MAX_COUNT_PER_DAY', 10))
        self.interval_minutes = int(os.environ.get('PUSH_INTERVAL_MINUTES', 30))
        self.push_count = 0
        self.last_push_date = datetime.now().date()
        self.last_push_time = None
        
    def send_push(self, title, content):
        if not self.token:
            print("PushPlus token not configured.")
            return

        # Check reset daily count
        current_now = datetime.now()
        current_date = current_now.date()
        
        if current_date != self.last_push_date:
            self.push_count = 0
            self.last_push_date = current_date
            
        if self.push_count >= self.max_count:
            print(f"Daily push limit reached ({self.max_count}).")
            return

        # Check interval
        if self.last_push_time:
            elapsed_minutes = (current_now - self.last_push_time).total_seconds() / 60
            if elapsed_minutes < self.interval_minutes:
                print(f"Skipping push: Interval {elapsed_minutes:.1f}m < {self.interval_minutes}m")
                return

        url = 'http://www.pushplus.plus/send'
        data = {
            "token": self.token,
            "title": title,
            "content": content,
            "template": "html"
        }
        if self.topic:
            data["topic"] = self.topic

        try:
            response = requests.post(url, json=data)
            result = response.json()
            if result['code'] == 200:
                print(f"Push notification sent: {title}")
                self.push_count += 1
                self.last_push_time = current_now
            else:
                print(f"Push notification failed: {result['msg']}")
        except Exception as e:
            print(f"Error sending push notification: {e}")
