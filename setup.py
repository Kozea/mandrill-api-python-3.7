from setuptools import setup
import os.path

setup(
    name = 'mandrill',
    version = '1.0.0',
    author = 'Mandrill Devs',
    author_email = 'community@mandrill.com',
    description = 'A CLI client and Python API library for the Mandrill email as a service platform.',
    long_description = open(os.path.join(os.path.dirname(__file__), 'README')).read(),
    license = 'MIT',
    keywords = 'mandrill email api',
    url = 'http://mandrillapp.com/api/docs/clients/python/',
    scripts = ['scripts/mandrill'],
    py_modules = ['mandrill'],
    install_requires = ['requests >= 0.13.2', 'docopt == 0.4.0'],
    classifiers = [
        'Development Status :: 4 - Beta',
        'Environment :: Console',
        'Intended Audience :: Developers',
        'Intended Audience :: System Administrators',
        'License :: OSI Approved :: MIT License',
        'Topic :: Communications :: Email'
    ]
)
