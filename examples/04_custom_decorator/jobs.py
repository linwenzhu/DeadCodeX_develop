"""Custom decorator entry-point discovery without a framework adapter."""


def job(function):
    return function


@job
def daily_cleanup():
    return archive_records(days=30)


def archive_records(days):
    return f"archived records older than {days} days"


def old_cleanup():
    return "obsolete cleanup"
