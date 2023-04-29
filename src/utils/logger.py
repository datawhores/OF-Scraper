import logging
import src.utils.args as args_
import src.utils.paths as paths

log=logging.getLogger("ofscraper")
log.setLevel(args_.getargs().log or 100)
fh=logging.FileHandler(paths.getlogpath(),mode="a")
fh.setLevel(args_.getargs().log or 100)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s',"%Y-%m-%d %H:%M:%S")
fh.setFormatter(formatter)
log.addHandler(fh)
