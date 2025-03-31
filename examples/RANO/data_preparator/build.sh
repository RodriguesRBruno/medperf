#! /bin/bash
mkdir tmp
cd tmp
git clone -b fets_2.0 https://github.com/FeTS-AI/Front-End.git
cd Front-End
git submodule update --init
docker build --target=fets_base -t local/fets_tool .
cd ../../
docker build -t local/rano-data-prep-mlcube:1.0.11 .  # TODO change back do mlcommons/ once finished
rm -rf tmp