import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name='bc_orch_sdk',  
    version='0.1',
    author="Antonio Russo",
    author_email="antonio@antoniorusso.me",
    description="Utility classes to easily extend BC-Orch",
    install_requires=['docker', 'fabric', 'pika'],
    long_description=long_description,
    long_description_content_type="text/markdown",
        url="https://github.com/russanto/bc-orchestration",
        packages=setuptools.find_packages('bc-orch-sdk'),
        classifiers=[
            "Programming Language :: Python :: 3",
            "License :: OSI Approved :: MIT License",
            "Operating System :: OS Independent",
        ],
 )