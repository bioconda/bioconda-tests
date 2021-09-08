#! /usr/bin/env bash

set -xeuo pipefail

conda_install_prefix="${HOME}/conda"

cat >> "${HOME}/solve_only_condarc" <<EOF
# Use this only for --dry-run solves!
# (Because bioconda-repodata-archive only has the repodata but not the actual packages.)

pkgs_dirs:
  - ${HOME}/solve_only_pkgs

channels:
  - conda-forge
  - bioconda
  - defaults
channel_alias: https://github.com/bioconda/bioconda-repodata-archive/raw/${REPODATA}/repodata/https=3A=2F/conda.anaconda.org
custom_channels:
  pkgs/main:   https://github.com/bioconda/bioconda-repodata-archive/raw/${REPODATA}/repodata/https=3A=2F/repo.anaconda.com
  pkgs/r:      https://github.com/bioconda/bioconda-repodata-archive/raw/${REPODATA}/repodata/https=3A=2F/repo.anaconda.com
  pkgs/pro:    https://github.com/bioconda/bioconda-repodata-archive/raw/${REPODATA}/repodata/https=3A=2F/repo.anaconda.com
default_channels:
  -            https://github.com/bioconda/bioconda-repodata-archive/raw/${REPODATA}/repodata/https=3A=2F/repo.anaconda.com/pkgs/main
  -            https://github.com/bioconda/bioconda-repodata-archive/raw/${REPODATA}/repodata/https=3A=2F/repo.anaconda.com/pkgs/r
EOF

curl \
  --silent \
  --location \
  --output micromamba \
  "https://github.com/mamba-org/boa-forge/releases/download/micromamba-${MICROMAMBA_VERSION}/micromamba-${SUBDIR}"
chmod +x micromamba

# Create new Conda installation with packages:
#   - conda ( to run `conda create`)
#   - mamba ( to run `mamba create`)
#   - conda-build (to run `conda-build --test`)
#   - boa (to run `conda-mambabuild --test`)
#   - coreutils (for `timeout` command)
./micromamba \
  install \
  --yes \
  --quiet \
  --root-prefix="${conda_install_prefix}" \
  --name=base \
  --channel=conda-forge \
  conda \
  mamba \
  conda-build \
  boa \
  coreutils

. "${conda_install_prefix}/etc/profile.d/conda.sh"
conda activate base
conda config --sys --append channels conda-forge
conda config --sys --append channels bioconda
conda config --sys --append channels defaults

mkdir "${conda_install_prefix}/conda-bld"
conda-index "${conda_install_prefix}/conda-bld"
