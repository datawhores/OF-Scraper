async def handle(self, record):
    """
    Conditionally emit the specified logging record.

    Emission depends on filters which may have been added to the handler.
    Wrap the actual emission of the record with acquisition/release of
    the I/O thread lock. Returns whether the filter passed the record for
    emission.
    """
    rv = self.filter(record)
    if rv:
        self.acquire()
        try:
            await self.emit(record)
        finally:
            self.release()
    return rv
