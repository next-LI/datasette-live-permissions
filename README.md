# datasette-live-permissions

[![PyPI](https://img.shields.io/pypi/v/datasette-live-permissions.svg)](https://pypi.org/project/datasette-live-permissions/)
[![Changelog](https://img.shields.io/github/v/release/next-LI/datasette-live-permissions?include_prereleases&label=changelog)](https://github.com/next-LI/datasette-live-permissions/releases)
[![Tests](https://github.com/next-LI/datasette-live-permissions/workflows/Test/badge.svg)](https://github.com/next-LI/datasette-live-permissions/actions?query=workflow%3ATest)
[![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](https://github.com/next-LI/datasette-live-permissions/blob/main/LICENSE)

A Datasette plugin that allows you to dynamically set permissions for users, groups, data and plugins. __This is very much a work in progress, so expect breaking changes!__ This plugin integrates with the rest of the [datasette-live plugins][ds-live-topic].

## Installation

Install this plugin in the same environment as Datasette.

    $ datasette install datasette-live-permissions

## Usage

This plugin adds a database which will be populated with users, actions and resources that are requested from the various parts of Datasette. You can set configuration by granting access to users/groups to actions/resources via the `live_permissions` table.

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


[ds-live-topic]: https://github.com/topics/datasette-live
    "Datasette Live - GitHub Topic"
