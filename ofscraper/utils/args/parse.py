import re
import sys

import ofscraper.utils.args.groups.main_args as main
import ofscraper.utils.args.groups.manual_args as manual
import ofscraper.utils.args.groups.message_args as message
import ofscraper.utils.args.groups.paid_args as paid
import ofscraper.utils.args.groups.post_args as post
import ofscraper.utils.args.groups.story_args as story
import ofscraper.utils.args.write as write_args


class AutoDotDict(dict):
    """
    Class that automatically converts a dictionary to an object-like structure
    with dot notation access for top-level keys.
    """

    def __getattr__(self, attr):
        """
        Overrides getattr to access dictionary keys using dot notation.
        Raises AttributeError if the key is not found.
        """
        try:
            return self.get(attr)
        except KeyError:
            raise AttributeError(f"Attribute '{attr}' not found")

    def __setattr__(self, attr, value):
        """
        Overrides setattr to set values using dot notation.
        """
        self[attr] = value


def parse_args():
    try:
        main.program.add_command(manual.manual, "manual")
        main.program.add_command(message.message_check, "msg_check")
        main.program.add_command(story.story_check, "story_check")
        main.program.add_command(paid.paid_check, "paid_check")
        main.program.add_command(post.post_check, "post_check")

        filter_str = r"\b(multiprocessing|pipe_handle|fork|parent_pid)\b"
        result = main.program(
            standalone_mode=False,
            prog_name="OF-Scraper",
            args=[text for text in sys.argv if not re.search(filter_str, text)][1:],
        )
        if result == 0:
            sys.exit()
        args, command = result
        args["command"] = command
        d = AutoDotDict(args)
        write_args.setArgs(d)
        return d
    except SystemExit as e:
        if e.code != 0:
            raise
