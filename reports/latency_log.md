Running 5 latency samples (this will take a while)...

Audio saved to /tmp/tmptqvhmzlu.wav
  [ 1/5] stt=1.53s ret=4.74s gen=18.38s tts=51ms
Audio saved to /tmp/tmpm1rq5_r0.wav
  [ 2/5] stt=561ms ret=22ms gen=18.11s tts=13ms
Audio saved to /tmp/tmp4annzvl_.wav
  [ 3/5] stt=485ms ret=16ms gen=21.97s tts=14ms
Audio saved to /tmp/tmpvhd5sasx.wav
  [ 4/5] stt=520ms ret=24ms gen=16.37s tts=14ms
Audio saved to /tmp/tmplt52tvlw.wav
  [ 5/5] stt=492ms ret=16ms gen=16.71s tts=14ms

# Hardware: Intel(R) Core(TM) i9-14900HX | 32 cores | 31.1 GB RAM | Linux x86_64 6.18.5-100.fc42.x86_64

Stage                       avg      p50      p95
--------------------------------------------------
stt                       718ms    520ms    1.34s
retrieval                 963ms     22ms    3.79s
generation               18.31s   18.11s   21.25s
tts                        21ms     14ms     44ms
e2e (text: ret+gen)      19.27s   18.13s   22.89s
e2e (voice: all)         20.01s   18.70s   24.26s

reports/latency.md written.
