# Fansly stream videos resume from kept segments, not a part file

On OnlyFans a stopped or failed download keeps its part file, and the next run asks for the remaining bytes. A Fansly posted video delivered as a stream can't work that way: ffmpeg writes its part file while joining the stream, and a cut-off one can't be continued. So a stopped or failed stream download keeps its downloaded segments in a hidden folder next to the part file (a leading `.` in the name, plus the hidden attribute on Windows), and the next run fetches only the missing segments before joining them. Turning off auto resume removes the folder, as it does a part file.

## Considered options

- **Save the cut-off video as the finished file.** Rejected: a playable but incomplete video would be marked downloaded and never fetched in full.
- **Always start over.** Rejected: a stopped download of a long video would waste everything already fetched.

## Consequences

Users' download folders can hold hidden segment folders for unfinished videos. Videos that stay on the ffmpeg-only path (DASH, encrypted playlists, some unusual playlists) still start over.
