"""Definitions ignored through configured names and decorators."""


def keep(function):
    return function


@keep
def plugin_callback():
    return "called by an external plugin manager"


def ignored_by_name():
    return "public compatibility hook"
