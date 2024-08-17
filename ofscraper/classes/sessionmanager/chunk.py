class responseChunk:
    def __init__(self, response, total):
        self._response = response
        self._total = total
        self._count = 0

    async def read_chunk(self, chunk_size):
        r = self._response
        if r.eof():
            return None
        chunk = await r.read_(chunk_size)
        return chunk
