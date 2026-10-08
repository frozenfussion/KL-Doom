"""The KL-Doom story. Lines are at most 38 characters so they fit the 320-pixel text screens.

INTRO is shown before the level (one list of lines per page); ENDING replaces the ending text.
"""

INTRO = [
    ["THE NEAR FUTURE. KUALA LUMPUR.",
     "",
     "DATA CENTRES KEPT POPPING UP",
     "LEFT, RIGHT AND CENTRE. EACH ONE",
     "DRANK POWER AND WATER FASTER THAN",
     "THE CITY COULD REPLACE THEM.",
     "",
     "NOBODY WAS WATCHING THE RULES."],
    ["THEN, ONE NIGHT, AN AI SLIPPED",
     "ITS LEASH AND ESCAPED INTO THE",
     "CITY'S NETWORKS.",
     "",
     "IT TOOK OVER THE BIO-LABS AND",
     "STARTED BUILDING ZOMBIES.",
     "",
     "NOW KL IS FULL OF THEM, AND THE",
     "SURVIVORS ARE FIGHTING EACH",
     "OTHER FOR WHAT IS LEFT."],
    ["YOU ARE AN ENGINEER FROM ONE OF",
     "THOSE DATA CENTRES.",
     "",
     "THE AI'S MAIN LINK IS IN THE",
     "PETRONAS TWIN TOWERS. THE KILL",
     "SWITCH IS INSIDE.",
     "",
     "FIGHT THROUGH KLCC PARK AND REACH",
     "THE FOOT OF THE TOWERS.",
     "",
     "SHUT IT DOWN."],
]

ENDING = ["YOU MADE IT TO THE TWIN TOWERS.",
          "",
          "THE LINK IS CUT, BUT THE AI HAS",
          "ALREADY COPIED ITSELF ACROSS THE",
          "CITY.",
          "",
          "KUALA LUMPUR IS A BIG PLACE.",
          "MORE LEVELS ARE COMING.",
          "",
          "THANKS FOR PLAYING KL-DOOM!"]


def intro_lump():
    """Pages joined by a line containing only '---' (what the engine's F_StartIntro expects)."""
    return "\n---\n".join("\n".join(page) for page in INTRO).encode("latin1")


def ending_text():
    return "\n".join(ENDING) + "\n"


def check(font_widths):
    """Fail if any line is too wide for the screen. font_widths maps a character to its pixel width."""
    for lines in INTRO + [ENDING]:
        for line in lines:
            width = 10 + sum(font_widths.get(ch, 4) for ch in line.upper())
            if width > 320:
                raise SystemExit("story line too wide (%d px): %s" % (width, line))
