# Repeatable backend demo runbook

Use self-recorded or royalty-free clips only. Video files stay local or in the
private development bucket; this repository contains no generated media.

## Seed order

1. Start the backend and run `scripts/smoke_check.py`.
2. Register at least two originals with `POST /api/clips/register`; the video
   upload returns while content fingerprinting continues in the
   background. Wait for each catalog item to show `fingerprinted`.
3. Scan an exact or cropped copy with `POST /api/scan` and record its `scan_id`.
4. Scan an unrelated clip to demonstrate the low-risk boundary.
5. Load `/api/scans/{scan_id}`, then call
   `/api/scans/{scan_id}/explain-verdict` when Gemini is enabled.
6. Call `/api/scans/{scan_id}/dmca` only after an explanation exists.

Example registration and scan commands:

```bash
curl -X POST http://localhost:8000/api/clips/register \
  -F "file=@demo_data/originals/game-highlight.mp4" \
  -F "title=Game highlight" \
  -F "creator_name=Demo creator"

curl -X POST http://localhost:8000/api/scan \
  -F "file=@demo_data/suspicious/cropped-copy.mp4"
```

Keep the returned clip and scan IDs in the temporary demo notes, not in source
control. Delete demo originals after the presentation when the bucket is shared.
