from setuptools import setup, find_packages

setup(
    name='mongorest',
    description='RESTful backend for MongoDB',
    version='0.0.1',
    packages=find_packages(exclude=['mongorest.tests']),
    install_requires="""
        pymongo==3.3.0
        flask==0.11.1
        flask-socketio==2.7.1
    """,
    tests_require=['nose'],
    test_suite='mongorest.tests',
    author='Pontus Enmark',
    author_email='pontus@wka.se',
    url='https://github.com/penmark/mongorest',
    entry_points={
        'console_scripts': """
            mongorest_dev = mongorest:main
        """
    }
)
