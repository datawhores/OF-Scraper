# OF-Scraper

Downloads the posts, messages, stories and paid content a user can access on OnlyFans and Fansly, and records Fansly livestreams.

## Media

**Posted video**:
A video a creator posted, with a fixed length. On Fansly it may be delivered as a single file or as a stream; either way it is a posted video.
_Avoid_: stream download, live-stream download

**Livestream recording**:
A capture of a Fansly creator's broadcast while it is live, possibly in several numbered parts with a sidecar describing them. Stopping a recording ends it; what was captured is a finished recording, never a stopped download.
_Avoid_: stream video, livestream download

## Check table

**Check table**:
The interactive table that lists a creator's media so the user can pick individual files to download.

**Cart**:
The set of check-table rows the user has picked for download.
_Avoid_: queue, basket

**Batch**:
The cart rows for one creator, sent to the downloader together.

**Cart state**:
What a row's cart column says about that file: not in cart, added, downloading, downloaded, skipped, failed or stopped.

**Added**:
In the cart and waiting to be sent. A row sent but not yet started when the user stops returns to added.
_Avoid_: not started, queued

**Stopped**:
A download the user halted after it had begun. It is neither finished nor failed, and sending it again resumes it where possible.
_Avoid_: cancelled, aborted, failed

**Failed**:
A download that could not complete after its retry.

**Skipped**:
A file the downloader chose not to fetch, for example because it already exists or is outside the size limits.

## Downloading

**Stop**:
The user ending the downloads in progress without quitting the program: the first Ctrl+C, or Stop Downloads in the check table.
_Avoid_: cancel, abort, quit

**Quit**:
Ending the program. A second Ctrl+C quits.

**Part file**:
The partly downloaded copy of a file, kept under a temporary name until the download completes.

**Resume**:
Continuing a stopped or interrupted download from its part file instead of starting over.
