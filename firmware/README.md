# ESP32-S3 firmware (Should tier, after the freeze)

Planned layout: an ESP-IDF project that pulls in `../c` as a component, so the
board runs exactly the C core that the laptop replay uses.

- Replay: DS2 streamed over USB at 360 Hz; outputs compared with the laptop run.
- Acceptance: SQIs and SVM decision values within 1e-4 of full scale; binary outputs
  match exactly except within 1e-4 of a threshold; worst-case window time < 2.5 s.
- Live demo (only if everything else is done): AD8232 -> ADS1115, timer-triggered
  single-shot conversion every 2.78 ms.

Create the project with `idf.py create-project` here when the port starts.
