#!/usr/bin/env python

import os
import websocket
import json
import re
from itertools import ifilter
from threading import Timer
from threading import Thread
from threading import Lock

class PushBulletSmsCodeReader:
  def __init__(self, pbAccessKey, messagePattern, timeout=60.0):
    self._url = 'wss://stream.pushbullet.com/websocket/' + pbAccessKey
    self._messagePattern = messagePattern
    self._lock = Lock()
    self._timeout = timeout

  def start_watching(self):
    self._final_sms_code = None
    self._ws = websocket.WebSocketApp(self._url, on_message = self._on_message)
    self._timer = Timer(self._timeout, self._close, [self._ws, True])
    self._timer.start()
    self._thread = Thread(target=self._ws.run_forever)
    self._thread.start()

  def wait_for_sms_code(self):
    try:
      self._thread.join(2**31)
    except:
      self._close(self._ws)
    return self._final_sms_code

  def _on_message(self, ws, message):
    #message = '{"push": {"notifications": [{"body":"Your Personal Capital device authentication code is 1234."}]}}'
    #print(message)
    data = json.loads(message)
    if 'push' in data:
      push = data['push']
      if 'notifications' in push:
        notifications = push['notifications']
        if notifications:
          match = next(
                    ifilter(None, (
                      re.match(self._messagePattern, n['body']) for n in notifications if 'body' in n
                      )
                    ), None
                  )
          if match:
            self._final_sms_code = match.group(1)
            #print ("_final_sms_code", self._final_sms_code)
            self._close(ws)

  def _close(self, ws, fromTimer=False):
    self._lock.acquire()
    try:
      ws.close()
      if not fromTimer and self._timer:
        self._timer.cancel()
    finally:
      self._lock.release()

if __name__ == "__main__":
  if 'PB_ACCESS_KEY' not in os.environ:
      raise Exception('PB_ACCESS_KEY is not defined')
  PB_ACCESS_KEY = os.environ.get('PB_ACCESS_KEY')

  MESSAGE_PATTERN = r'^Your Personal Capital device authentication code is (\d+)\.$'

  pb = PushBulletSmsCodeReader(PB_ACCESS_KEY, MESSAGE_PATTERN)
  pb.start_watching()
  print(pb.wait_for_sms_code())

