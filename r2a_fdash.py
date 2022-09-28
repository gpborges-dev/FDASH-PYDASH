from r2a.ir2a import IR2A;
from player.parser import *;
import time;
import numpy as np;
from statistics import mean;


class R2A_FDASH(IR2A):
    def __init__(self, id):
        IR2A.__init__(self, id);
        self.throughputs = [];
        self.throughputs_time = [];
        self.qi = [];
        self.request_time = 0;
        self.selected_qi = 0;

    def getBufferingTime(self, t):
        T = 35;
        short = 0;
        close = 0;
        long = 0;

        if t <= 2*T/3:
            short = 1;
        elif 2*T/3 < t <= T:
            short = (T - t) / (T - 2*T/3);
            close = (t - 2*T/3) / (T - 2*T/3);
        elif T < t <= 4*T:
            close = (4*T - t) / (4*T - T);
            long = (t - T) / (4*T - T);
        else:
            long = 1;

        return short, close, long;

    def getDiffBufferingTime(self, t):
        T = 35;
        falling = 0;
        steady = 0;
        rising = 0;

        if t <= -2*T/3:
            falling = 1;
        elif -2*T/3 < t <= 0: 
            falling = (-t) / (2*T/3);
            steady = (t+2*T/3) / (2*T/3);
        elif 0 < t <= 4*T:
            steady = (4*T - t) / (4*T);
            rising = (t) / (4*T);
        else:
            rising = 1;
            
        return falling, steady, rising;

    def getNextQI(self, t, dt):
        short, close, long = self.getBufferingTime(t);
        falling, steady, rising = self.getDiffBufferingTime(dt);
        r1 = min(short, falling);
        r2 = min(close, falling);
        r3 = min(long, falling);
        r4 = min(short, steady);
        r5 = min(close, steady);
        r6 = min(long, steady);
        r7 = min(short, rising);
        r8 = min(close, rising);
        r9 = min(long, rising);

        i = abs(r9);
        si = np.linalg.norm(np.array((r6, r8)));
        nc = np.linalg.norm(np.array((r3, r5, r7)));
        sr = np.linalg.norm(np.array((r2, r4)));
        r = abs(r1);

        f = (0.25 * r + 0.5 * sr + 1 * nc + 1.5 * si + 2 * i) / (sr + r + nc + si + i);

        self.checkThroughputs();
        avg = mean(self.throughputs);
        b = avg * f;
        new_selected_qi = self.qi[0];
        for i, qi in enumerate(self.qi):
            if b > qi:
                new_selected_qi = i;

        if new_selected_qi > self.selected_qi and self.whiteboard.get_playback_buffer_size()[-1][1] < 35:
            return self.selected_qi;
        elif new_selected_qi < self.selected_qi and self.whiteboard.get_playback_buffer_size()[-1][1] > 35:
            return self.selected_qi;
        else:
            self.selected_qi = new_selected_qi;
            return self.selected_qi;

    def checkThroughputs(self):
        current_time = time.perf_counter();
        d = 60;
        for t in self.throughputs_time:
            if current_time - t > d:
                self.throughputs.pop(0);
                self.throughputs_time.pop(0);
            else:
                break;
        
    def handle_xml_request(self, msg):
        self.request_time = time.perf_counter();
        self.send_down(msg);

    def handle_xml_response(self, msg):
        parsed_mpd = parse_mpd(msg.get_payload());
        self.qi = parsed_mpd.get_qi();
        rtt = time.perf_counter() - self.request_time;
        print(f'RTT => {rtt}');
        self.throughputs.append(msg.get_bit_length() / rtt);
        self.throughputs_time.append(time.perf_counter());
        print(f'THROUGHPUTS => {self.throughputs}');
        # print(f'THROUGHPUTS TIME => {self.throughputs_time}');
        self.send_up(msg);

    def handle_segment_size_request(self, msg):
        self.request_time = time.perf_counter();
        buffering_time = self.whiteboard.get_playback_segment_size_time_at_buffer()[-2:];
        print(f'BUFFERING TIME => {buffering_time}');
        if len(buffering_time) >= 2:
            t = buffering_time[-1];
            dt = buffering_time[-1] - buffering_time[-2];
            self.selected_qi = self.getNextQI(t, dt);
        print(f'SELECTED QI => {self.qi[self.selected_qi]}');
        msg.add_quality_id(self.qi[self.selected_qi]);
        self.send_down(msg);

    def handle_segment_size_response(self, msg):
        rtt = time.perf_counter() - self.request_time;
        print(f'RTT => {rtt}');
        self.throughputs.append(msg.get_bit_length() / rtt);
        self.throughputs_time.append(time.perf_counter());
        print(f'THROUGHPUTS => {self.throughputs}');
        # print(f'THROUGHPUTS TIME => {self.throughputs_time}');
        self.send_up(msg);

    def initialize(self):
        pass

    def finalization(self):
        pass