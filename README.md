# datasette-live-permissions

[![PyPI](https://img.shields.io/pypi/v/datasette-live-permissions.svg)](https://pypi.org/project/datasette-live-permissions/)
[![Changelog](https://img.shields.io/github/v/release/next-LI/datasette-live-permissions?include_prereleases&label=changelog)](https://github.com/next-LI/datasette-live-permissions/releases)
[![Tests](https://github.com/next-LI/datasette-live-permissions/workflows/Test/badge.svg)](https://github.com/next-LI/datasette-live-permissions/actions?query=workflow%3ATest)
[![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](https://github.com/next-LI/datasette-live-permissions/blob/main/LICENSE)

A Datasette plugin that allows you to dynamically set permissions for users, groups, data and plugins

## Installation

Install this plugin in the same environment as Datasette.

    $ datasette install datasette-live-permissions

## Usage

Usage instructions go here.

## Development

To set up this plugin locally, first checkout the code. Then create a new virtual environment:

    cd datasette-live-permissions
    python3 -mvenv venv
    source venv/bin/activate

Or if you are using `pipenv`:

    pipenv shell

Now install the dependencies and tests:

    pip install -e '.[test]'

To run the tests:

    pytest
