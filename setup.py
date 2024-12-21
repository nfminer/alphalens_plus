from setuptools import setup, find_packages
import sys
from alphalens_plus import __version__


python_version = f"cp{sys.version_info.major}{sys.version_info.minor}"

setup(
    name='alphalens_plus',
    version=__version__,
    description='Alpha analysis tools box',
    long_description=open('README.md').read(),
    long_description_content_type='text/markdown',
    author='msliu98',
    author_email='mingshuoliu98@163.com',
    python_requires='>=3.9.12',
    packages=find_packages(),
    install_requires=[
        'loguru',
        'scipy',
        'pandas==1.3.5',
        'numpy==1.21.6',
    ],
    classifiers=[
        'Development Status :: 4 - Beta',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
    ],
    options={'bdist_wheel': {'python_tag': python_version, 'plat_name': 'win_amd64'}}
)