CHECKLISTINSTRUCTIONS = """
&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&

Instructions
============================================================
Enter one of the  'SELECT KEYS' to confirm

MINUMUM CHOICE: 1
MAX CHOICE:1
============================================================

KEYS
============================================================

   SELECT KEYS
   ======================================================================
   END  |  HOME   | PAGEUP | PAGEDOWN | SPACE | ENTER | shift+right
   ========================================================================

   SPECIAL SELECT
   Will select and move cursor
   ================
   TAB | SHIFT+TAB
   =================


==============================================================
PRESS ENTER TO RETURN

&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&
"""

_FUZZY_BODY = """
&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&

Instructions
=========================================================================
Enter Confirm KEY to confirm selection

Parantheses indicates number of selected user


MINUMUM CHOICE: 1
MAX CHOICE:ALL

=========================================================================

KEYS
=========================================================================
  CONFIRM KEY
  ============
  ENTER
  ================


   SELECT KEYS
   ================================================
   END  |  HOME | PAGEUP | PAGEDOWN | shift+right
   ================================================

   SPECIAL SELECT
   Will select and move cursor
   ================
   TAB | SHIFT+TAB
   =================


  TOGGLE ALL FALSE
   ========
   CTRL+D
   ========

  TOGGLE ALL TRUE
   ========
   CTRL+S
   ========

   TOGGLE ALL
   Selects all, or clears all when all are selected
   ========
   CTRL+A
   ========
"""

_FUZZY_FOOTER = """===================================================================
PRESS ENTER TO RETURN

&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&"""

FUZZY_INSTRUCTION = f"{_FUZZY_BODY}   \n\n{_FUZZY_FOOTER}"

MODEL_FUZZY = (
    f"{_FUZZY_BODY}\n\n"
    "   CHANGE FILTER/SORT\n"
    "   ========\n"
    "   ALT+X|CTRL+B\n"
    "   ========\n"
    f"{_FUZZY_FOOTER}"
)

SCRAPE_PAID = """
This is meant really for scraping content for deleted models
This can greatly increase the time needed for a single scrape

It should not be needed to turn this on everytime, especially with  frequent scrapes

SHOW KEYBINDINGS AND INSTRUCTIONS: [ALT+V] or [CTRL+V] (in Windows Terminal, Ctrl+V pastes instead)
"""

SINGLE_LINE = """
&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&


Instructions for submitting text
=========================================================================
HIT one of the 'SUBMIT KEYs' to submit text
===========================================================================

KEYS
==========================================================================

   SUBMIT KEYs
   ======================================================================
   END  |  HOME   | PAGEUP | PAGEDOWN | SPACE | ENTER | shift+right
   ========================================================================

==============================================================================
PRESS ENTER TO RETURN

&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&"""

KEY_BOARD = """
SHOW KEYBINDINGS AND INSTRUCTIONS: [ALT+V] or [CTRL+V] (in Windows Terminal, Ctrl+V pastes instead)
"""

NUMBER = """
SHOW INSTRUCTIONS: [ALT+V] or [CTRL+V] (in Windows Terminal, Ctrl+V pastes instead)
"""

MODEL_SELECT = """
CHANGE SORT/FILTER: [ALT+X] or [CTRL+B]
MODEL DETAILS: [ALT+D] ||| RANGE SELECT: [ALT+B]
"""
PRICE_DETAILS = """
SHOW CURRENT PRICE STATUS/INFO: [ALT+D]
"""
FILTER_DETAILS = """
SHOW CURRENT FILTERS/SORTING: [ALT+D]
"""
LIST_PROMPT_INFO = """
List are case-insensitive and should be seperate via comma and/or via 'Enter Key'
Default List are used if input is empty
"""

SORT_DETAILS = """
SHOW CURRENT SORTING: [ALT+D]
"""

MULTI_LINE = """
&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&

Instructions for editing
===========================================================================
HIT one of the 'SUBMIT' combinations when your auth syntax is corrected
============================================================================

KEYS
===========================================================================
   SUBMIT
   ==============================================================================
   END+ENTER  |  HOME+ENTER   | PAGEUP+ENTER | PAGEDOWN+ENTER | SPACE+ENTER
   ================================================================================

==============================================================================
PRESS ENTER TO RETURN

&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&
"""

AUTH_MULTI = """
&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&


Instructions for editing auth
=========================================================================
HIT one of the 'SUBMIT' combinations to confirm text
=========================================================================

KEYS
=========================================================================

   SUBMIT KEYs
   =============================================================================
   END+ENTER  |  HOME+ENTER   | PAGEUP+ENTER | PAGEDOWN+ENTER | SPACE+ENTER
   =============================================================================

==============================================================================
PRESS ENTER TO RETURN

&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&
"""

CONFIG_MULTI = """
&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&

Instructions for editing config
=========================================================================
HIT one of the 'SUBMIT' combinations when your auth syntax is corrected
=========================================================================

KEYS
=========================================================================
   SUBMIT KEYs
   ================================================================================
   END+ENTER  |  HOME+ENTER   | PAGEUP+ENTER | PAGEDOWN+ENTER | SPACE+ENTER
   ===============================================================================

==============================================================================
PRESS ENTER TO RETURN

&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&
"""

CONFIG_MENU = "CONFIG SECTIONS DETAILS: [ALT+X]"
