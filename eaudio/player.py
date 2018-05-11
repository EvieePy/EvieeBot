"""
LICENSE:
Copyright (c) 2018 MysterialPy, Rapptz

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE."""
from discord.opus import Encoder as OpusEncoder

import audioop
import math
import numpy
import queue
import time
import threading


class AudioPlayer(threading.Thread):

    DELAY = OpusEncoder.FRAME_LENGTH / 1000.0
    IDLE = 0
    PLAYING = 1
    MIXING = 2
    DEAD = 666

    def __init__(self, mixer, _queue, client, after):
        super().__init__()
        self.daemon = True
        self.queue = _queue
        self.mixer = mixer
        self.client = client

        self.loops = 0
        self._start = None
        self.next_loops = 0
        self.next_start = None
        self.next_vol = 0

        self._end = threading.Event()
        self._resumed = threading.Event()
        self._resumed.set()  # we are not paused
        self._current_error = None
        self._connected = client._connected
        self._lock = threading.Lock()

        self.after = after

        self.current = None
        self.previous = None
        self.next = None

    def _do_run(self):
        self.reset_tokens()
        play_audio = self.client.send_audio_packet

        while not self._end.is_set():
            if not self.current:
                self.state = self.IDLE
                print('wait')
                self.current = self.queue.get(block=True)
                self.previous = self.current
                self.state = self.PLAYING
                print('no wait')
                self.reset_tokens()
            elif not self.next:
                try:
                    self.next = self.queue.get(block=False)
                    print('got next')
                except queue.Empty:
                    pass

            if not self._resumed.is_set():
                print('Paused')
                self._resumed.wait()
                print('Resumed')
                continue

            if not self._connected.is_set():
                print('Not connected')
                self._connected.wait()
                self.reset_tokens()

            self.loops += 1
            data = self.mixer.reader()

            if not data:
                if self.next:
                    self.current = self.next
                    self.next = None
                    self.reset_tokens()
                else:
                    self.after(self._current_error, self.current)
                    self.current = None
            else:
                play_audio(data, encode=not self.current.is_opus())
                next_time = self._start + self.DELAY * self.loops
                delay = max(0, self.DELAY + (next_time - time.time()))
                time.sleep(delay)

    def reset_tokens(self):
        self.loops = 0
        self._start = time.time()

    def run(self):
        try:
            self._do_run()
        except Exception as e:
            self._current_error = e
            self._end.set()
        finally:
            pass

    def pause(self):
        self._resumed.clear()

    def resume(self):
        self.reset_tokens()
        if self.state == self.MIXING:
            self.next_loops = 0
            self.next_start = time.time()
        self._resumed.set()

    def is_playing(self):
        return self._resumed.is_set() and not self._end.is_set()

    def is_paused(self):
        return not self._end.is_set() and not self._resumed.is_set()


class AudioMixer(AudioPlayer):

    def __init__(self, *, client, after, after_all, next_call):
        self.__queue = queue.Queue()
        super().__init__(self, self.__queue, client, after)

        self.state = self.IDLE
        self.after_all = after_all
        self._next_call = next_call

    def do_start(self):
        self.start()

    def stop(self):
        self.state = self.DEAD
        self._end.set()

        self.after_all(self._current_error, (self.current, self.next, self.previous))

    def mix_streams(self):
        if not self.state == self.MIXING:
            self.state = self.MIXING

        if not self.next_start:
            self.next_start = time.time()
            self.next.volume = 0
            self.next_vol = self.current.volume

        self.next_loops += 1

        try:
            self.current.volume = self.current.volume - (math.floor(12 / 50) / 100)
            if self.next.volume < self.next_vol:
                self.next.volume = self.next.volume + (self.next_vol / math.floor(12 * 50))

            print(f'MAX: {self.next_vol}')

            print(f'NEXT   : {self.next.volume}')
            print(f'CURRENT: {self.current.volume}')
            print(self.next_loops)
            current = self.current.read(volume=self.current.volume)
            next_ = self.next.read(volume=self.next.volume)
            data = audioop.add(current, next_, 2)
        except Exception as e:
            print(type(e))
            print(e)

            self.current = self.next
            self.current.volume = math.ceil(self.current.volume * 100) / 100
            self.previous = self.current
            # The next song will be grabbed on the next loop.
            self.next = None

            data = self.current.read()

            # Current tokens need to be overridden with our mixing state tokens.
            self._start = self.next_start
            self.loops = self.next_loops
            # Reset our next tokens for our next mix
            self.next_start = None
            self.next_loops = 0
            self.next_vol = 0

            # We can assume we have finished mixing now, since the first stream has likely exhausted.
            self.state = self.PLAYING
            self.after(self._current_error, self.previous)

        return data

    def reader(self):
        data = None

        if not self.next:
            pass
        elif self.current.remaining == 16 and self.state != self.MIXING:
            self.state = self.MIXING
            self._next_call(self.next)
        elif self.current.remaining <= 12:  # !15 for testing purposes.
            data = self.mix_streams()

        # mix_streams could still return None, so an else here doesn't work
        if not data:
            data = self.current.read()
        return data
