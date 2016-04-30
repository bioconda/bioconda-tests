#!/bin/bash
set -euo pipefail

if [[ $TRAVIS_OS_NAME = "linux" ]]
then
    # run CentOS5 based docker container
    docker run -e SUBDAG -e SUBDAGS -e TRAVIS_BRANCH -e TRAVIS_PULL_REQUEST -e ANACONDA_TOKEN -v `pwd`/bioconda-recipes:/bioconda-recipes bioconda/bioconda-builder --testonly --env-matrix /bioconda-recipes/scripts/env_matrix.yml
else
    export PATH=/anaconda/bin:$PATH
    # build packages
    scripts/build-packages.py --testonly --repository bioconda-recipes --env-matrix bioconda-recipes/scripts/env_matrix.yml
fi
