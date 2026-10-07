# Paired noisy-vs-clean differences by cause and place

Post-hoc analysis after the freeze-v1 DS2 run (`scripts/analyze_differences.py`);
it does not affect the verdict. Frozen Robust model at its default threshold, no
gate. Values are events per hour of scored windows at that place; causes are
defined in the script docstring.

## DS1-cal, all noise types

| place | hours | false V: spurious detection | false V: beat reclassified | false V: same as clean | V lost: missed detection | V lost: reclassified |
|---|---|---|---|---|---|---|
| 18 dB | 2.7 | 0.4 | 47.0 | 384.1 | 0.0 | 4.4 |
| 12 dB | 2.9 | 65.8 | 221.6 | 301.4 | 0.3 | 5.1 |
| 6 dB | 3.2 | 354.4 | 766.1 | 337.7 | 0.9 | 17.0 |
| 0 dB | 2.6 | 941.0 | 1487.5 | 281.8 | 4.6 | 14.1 |
| clean segment | 14.9 | 0.0 | 0.6 | 278.5 | 0.0 | 0.0 |
| all | 26.4 | 144.6 | 272.0 | 299.4 | 0.6 | 4.5 |

## DS1-cal, em

| place | hours | false V: spurious detection | false V: beat reclassified | false V: same as clean | V lost: missed detection | V lost: reclassified |
|---|---|---|---|---|---|---|
| 18 dB | 0.9 | 0.0 | 57.8 | 418.9 | 0.0 | 2.2 |
| 12 dB | 1.0 | 3.1 | 218.9 | 340.6 | 0.0 | 1.0 |
| 6 dB | 1.1 | 528.9 | 1163.5 | 385.1 | 0.9 | 13.0 |
| 0 dB | 0.9 | 2040.4 | 2310.4 | 342.9 | 3.4 | 8.0 |
| clean segment | 5.0 | 0.0 | 0.2 | 277.9 | 0.0 | 0.0 |
| all | 8.8 | 268.6 | 403.3 | 318.9 | 0.5 | 2.7 |

## DS1-cal, ma

| place | hours | false V: spurious detection | false V: beat reclassified | false V: same as clean | V lost: missed detection | V lost: reclassified |
|---|---|---|---|---|---|---|
| 18 dB | 0.9 | 1.1 | 25.6 | 328.9 | 0.0 | 7.8 |
| 12 dB | 1.0 | 194.3 | 337.5 | 243.4 | 1.0 | 11.3 |
| 6 dB | 1.1 | 495.5 | 640.2 | 262.6 | 1.9 | 26.0 |
| 0 dB | 0.9 | 633.4 | 966.1 | 198.2 | 9.1 | 23.9 |
| clean segment | 5.0 | 0.0 | 0.8 | 277.4 | 0.0 | 0.0 |
| all | 8.8 | 145.6 | 215.3 | 269.2 | 1.3 | 7.6 |

## DS1-cal, bw

| place | hours | false V: spurious detection | false V: beat reclassified | false V: same as clean | V lost: missed detection | V lost: reclassified |
|---|---|---|---|---|---|---|
| 18 dB | 0.9 | 0.0 | 57.8 | 404.4 | 0.0 | 3.3 |
| 12 dB | 1.0 | 0.0 | 108.4 | 320.1 | 0.0 | 3.1 |
| 6 dB | 1.1 | 39.0 | 494.5 | 365.6 | 0.0 | 12.1 |
| 0 dB | 0.9 | 149.2 | 1185.9 | 304.2 | 1.1 | 10.3 |
| clean segment | 5.0 | 0.0 | 0.8 | 280.3 | 0.0 | 0.0 |
| all | 8.8 | 19.7 | 197.3 | 310.2 | 0.1 | 3.2 |

## DS2, all noise types

| place | hours | false V: spurious detection | false V: beat reclassified | false V: same as clean | V lost: missed detection | V lost: reclassified |
|---|---|---|---|---|---|---|
| 18 dB | 9.4 | 13.1 | 32.1 | 94.7 | 0.3 | 2.3 |
| 12 dB | 10.5 | 76.9 | 140.4 | 78.2 | 1.0 | 6.0 |
| 6 dB | 11.5 | 497.8 | 691.9 | 67.4 | 1.6 | 14.3 |
| 0 dB | 9.4 | 1010.9 | 1439.8 | 48.8 | 7.6 | 32.4 |
| clean segment | 53.0 | 0.0 | 0.5 | 105.9 | 0.0 | 0.0 |
| all | 94.0 | 172.7 | 249.0 | 91.2 | 1.1 | 5.9 |

## DS2, em

| place | hours | false V: spurious detection | false V: beat reclassified | false V: same as clean | V lost: missed detection | V lost: reclassified |
|---|---|---|---|---|---|---|
| 18 dB | 3.1 | 17.8 | 32.4 | 91.4 | 0.3 | 3.2 |
| 12 dB | 3.5 | 72.9 | 160.3 | 80.6 | 1.1 | 3.4 |
| 6 dB | 3.8 | 871.2 | 945.5 | 64.4 | 2.9 | 13.5 |
| 0 dB | 3.1 | 2016.2 | 2060.0 | 50.5 | 11.4 | 32.4 |
| clean segment | 17.7 | 0.0 | 0.2 | 105.7 | 0.0 | 0.1 |
| all | 31.3 | 319.7 | 344.6 | 90.9 | 1.7 | 5.7 |

## DS2, ma

| place | hours | false V: spurious detection | false V: beat reclassified | false V: same as clean | V lost: missed detection | V lost: reclassified |
|---|---|---|---|---|---|---|
| 18 dB | 3.1 | 15.2 | 30.5 | 90.8 | 0.3 | 3.5 |
| 12 dB | 3.5 | 144.9 | 203.4 | 66.6 | 1.7 | 11.7 |
| 6 dB | 3.8 | 580.0 | 779.2 | 59.2 | 1.6 | 24.9 |
| 0 dB | 3.1 | 888.3 | 1026.7 | 34.0 | 9.5 | 57.5 |
| clean segment | 17.7 | 0.0 | 0.0 | 105.6 | 0.1 | 0.1 |
| all | 31.3 | 178.3 | 224.8 | 86.9 | 1.4 | 10.5 |

## DS2, bw

| place | hours | false V: spurious detection | false V: beat reclassified | false V: same as clean | V lost: missed detection | V lost: reclassified |
|---|---|---|---|---|---|---|
| 18 dB | 3.1 | 6.3 | 33.3 | 101.9 | 0.3 | 0.3 |
| 12 dB | 3.5 | 12.9 | 57.4 | 87.4 | 0.3 | 2.9 |
| 6 dB | 3.8 | 42.3 | 350.9 | 78.7 | 0.3 | 4.4 |
| 0 dB | 3.1 | 128.3 | 1232.7 | 61.9 | 1.9 | 7.3 |
| clean segment | 17.7 | 0.0 | 1.2 | 106.3 | 0.0 | 0.0 |
| all | 31.3 | 20.2 | 177.5 | 95.9 | 0.3 | 1.6 |
