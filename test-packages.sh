#!/bin/bash

# Test script to check package availability in Ubuntu Noble

echo "Testing package availability in Ubuntu Noble..."

docker run --rm ubuntu:noble bash -c "
apt-get update > /dev/null 2>&1
echo 'Checking OpenGL packages:'
apt-cache search libgl | grep -E '^libgl[0-9]*(-mesa)?[[:space:]]' | head -5
echo ''
echo 'Checking sound packages:'
apt-cache search libasound | grep -E '^libasound' | head -5
echo ''
echo 'Checking image libraries:'
apt-cache search libwebp | grep -E '^libwebp[0-9]*[[:space:]]' | head -5
apt-cache search libjpeg | grep -E '^libjpeg[0-9]' | head -5
apt-cache search libpng | grep -E '^libpng[0-9]' | head -5
"