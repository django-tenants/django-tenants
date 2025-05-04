#!/bin/bash

pip install -e .

echo "docker attach the tty in order to manage this"
while true; do
    echo "Run tests? [yn]" # can't use "read -p", no real tty
    read yn
    case $yn in
        [Yy] ) ./run_tests.sh;continue;;
        * ) exit;;
    esac
done
