#!/bin/bash

while IFS= read -r package
do
  tlmgr install "$package"
done < "tex_packages.txt"
