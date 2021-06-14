from setuptools import setup
import os


VERSION = "0.4.14"


def get_long_description():
    with open(
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "README.md"),
        encoding="utf8",
    ) as fp:
        return fp.read()


setup(
    name="datasette-live-permissions",
    description="A Datasette plugin that allows you to dynamically set permissions for users, groups, data and plugins",
    long_description=get_long_description(),
    long_description_content_type="text/markdown",
    author="Brandon Roberts",
    url="https://github.com/next-LI/datasette-live-permissions",
    project_urls={
        "Issues": "https://github.com/next-LI/datasette-live-permissions/issues",
        "CI": "https://github.com/next-LI/datasette-live-permissions/actions",
        "Changelog": "https://github.com/next-LI/datasette-live-permissions/releases",
    },
    license="Apache License, Version 2.0",
    version=VERSION,
    packages=["datasette_live_permissions"],
    entry_points={"datasette": ["live_permissions = datasette_live_permissions"]},
    # install_requires=["datasette"],
    extras_require={"test": ["pytest", "pytest-asyncio"]},
    tests_require=["datasette-live-permissions[test]"],
    package_data={
        "datasette_live_permissions": ["templates/*", "static/*"]
    },
    python_requires=">=3.6",
)
