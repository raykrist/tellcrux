try:
    from setuptools import setup
except ImportError:
    from distutils.core import setup

config = {
    'description': 'Telldus and webcrux python cli',
    'author': 'Raymond Kristiansen',
    'url': 'https://github.com/raykrist/tellcrux',
    'download_url': 'https://github.com/raykrist/tellcrux',
    'author_email': 'raymond@nexusweb.no',
    'version': '0.1',
    'install_requires': [ 'statsd', 'tellcore-py' ],
    'packages': ['tellcrux'],
    'scripts': [],
    'name': 'tellcrux'
}

setup(**config)
