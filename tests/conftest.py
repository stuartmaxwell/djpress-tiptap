"""Pytest configuration for the djpress-tiptap project."""
def pytest_collection_modifyitems(items):
    """Run the fast Python tests before the e2e browser tests.

    sort() is stable, so order within each group is untouched.
    """
    items.sort(key=lambda item: item.get_closest_marker("e2e") is not None)
