from setuptools import setup

def readme():
    try:
        return open('README.rst').read()
    except:
        return ""

setup(
    name='django-html5-multifileinput',
    version='1.0.0-dev',
    packages=['multifileinput',],
    include_package_data=True,
    description='',
    long_description=readme(),
    author='Nakahara Kunihiko',
    author_email='nakahara.kunihiko@gmail.com',
    url='https://github.com/nkunihiko/django-html5-multifileinput',
    license='BSD License',
    classifiers=[
        'Intended Audience :: Developers',
        'License :: OSI Approved :: Apache Software License',
        'Programming Language :: Python',
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 3',
        'Operating System :: OS Independent',
        'Topic :: Software Development :: Libraries',
        'Topic :: Utilities',
        'Environment :: Web Environment',
        'Framework :: Django',
    ],
)
