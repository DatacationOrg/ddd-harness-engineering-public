"""Streamlit styling hooks backed by dedicated HTML templates."""

from random import choice

import streamlit as st

from ddd_harness_engineering.ui_templates import load_template, render_template

_GENERATION_STATUSES = (
    "Thinking out loud, quietly...",
    "Calibrating the brain cells...",
    "Firing up the engines...",
    "Reinventing a small wheel...",
    "Connecting a few dots...",
    "Gathering the useful bits...",
    "Putting the kettle on...",
    "Checking the mental whiteboard...",
    "Taking the scenic route to an answer...",
    "Untangling the interesting part...",
    "Sharpening the pencils...",
    "Doing the math twice...",
    "Consulting the imaginary notebook...",
    "Making the gears mesh...",
    "Finding a sensible angle...",
    "Giving the idea a once-over...",
    "Mapping the rabbit holes...",
    "Asking the pixels nicely...",
    "Warming up the good neurons...",
    "Lining up the dominoes...",
    "Sorting signal from noise...",
    "Poking at the edge cases...",
    "Reading between the lines...",
    "Checking which way is up...",
    "Turning the crank...",
    "Building the answer from spare parts...",
    "Polishing a rough thought...",
    "Taking a thoughtful pause...",
    "Running a quick sanity lap...",
    "Finding the shortest path through this...",
    "Trying not to overthink it...",
    "Assembling the useful pieces...",
    "Letting the thoughts simmer...",
    "Tuning the mental antenna...",
    "Opening a fresh tab in the mind...",
    "Putting the clues in order...",
    "Kicking the tires on the answer...",
    "Following the thread...",
    "Stacking the building blocks...",
    "Taking the problem apart gently...",
    "Giving the gears a nudge...",
    "Looking for the clean version...",
    "Sketching the route...",
    "Running the numbers past the bouncer...",
    "Finding the least surprising answer...",
    "Checking the map before setting off...",
    "Gathering a few good thoughts...",
    "Making a tiny plan...",
    "Refilling the idea tank...",
    "Working the puzzle...",
)


def add_footer() -> None:
    st.write(load_template("components/footer.html"), unsafe_allow_html=True)


def add_user_chat_alignment() -> None:
    st.html(load_template("styles/user_chat.html"))


def add_reasoning_styling() -> None:
    st.html(load_template("styles/reasoning.html"))


def add_follow_up_styling() -> None:
    st.html(load_template("styles/follow_up.html"))


def add_trace_styling() -> None:
    for template_name in (
        "styles/app_chrome.html",
        "styles/trace.html",
        "styles/workspace.html",
    ):
        st.html(load_template(template_name))


def set_workspace_layout(*, chat_open: bool) -> None:
    right_pad = "min(445px, 36vw)" if chat_open else "0px"
    st.html(render_template("styles/workspace_layout.html", right_pad=right_pad))


def get_generation_status() -> str:
    return choice(_GENERATION_STATUSES)
